"""Tests for bicep_whatif_advisor.cli module."""

import json

import pytest
from click.testing import CliRunner

from bicep_whatif_advisor.cli import (
    _load_bicep_files,
    extract_json,
    filter_by_confidence,
    main,
)


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestExtractJson:

    def test_pure_json(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the response:\n{"key": "value"}\nEnd.'
        result = extract_json(text)
        assert result == {"key": "value"}

    def test_deeply_nested_json(self):
        obj = {"a": {"b": {"c": [1, 2, {"d": True}]}}}
        text = f"Some prefix {json.dumps(obj)} suffix"
        result = extract_json(text)
        assert result == obj

    def test_json_with_escaped_quotes(self):
        text = '{"msg": "He said \\"hello\\""}'
        result = extract_json(text)
        assert result["msg"] == 'He said "hello"'

    def test_no_json_raises_value_error(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_json("no json here at all")

    def test_no_brace_raises_value_error(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_json("just plain text")

    def test_invalid_json_raises_value_error(self):
        with pytest.raises(ValueError, match="Could not extract"):
            extract_json("{invalid json content]")

    def test_markdown_fenced_json(self):
        text = "```json\n{\"resources\": []}\n```"
        result = extract_json(text)
        assert result == {"resources": []}


# ---------------------------------------------------------------------------
# filter_by_confidence
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestFilterByConfidence:

    def test_splits_by_confidence(self):
        data = {
            "resources": [
                {"resource_name": "r1", "confidence_level": "high"},
                {"resource_name": "r2", "confidence_level": "low"},
                {"resource_name": "r3", "confidence_level": "medium"},
            ],
            "overall_summary": "test",
        }
        high, low = filter_by_confidence(data)
        assert len(high["resources"]) == 2
        assert len(low["resources"]) == 1
        assert low["resources"][0]["resource_name"] == "r2"

    def test_noise_level_goes_to_low(self):
        data = {
            "resources": [
                {"resource_name": "r1", "confidence_level": "noise"},
            ],
            "overall_summary": "",
        }
        high, low = filter_by_confidence(data)
        assert len(high["resources"]) == 0
        assert len(low["resources"]) == 1

    def test_preserves_ci_fields_in_high(self):
        data = {
            "resources": [],
            "overall_summary": "",
            "risk_assessment": {"drift": {}},
            "verdict": {"safe": True},
        }
        high, low = filter_by_confidence(data)
        assert "risk_assessment" in high
        assert "verdict" in high
        assert "risk_assessment" not in low

    def test_defaults_missing_confidence_to_medium(self):
        data = {
            "resources": [{"resource_name": "r1"}],
            "overall_summary": "",
        }
        high, low = filter_by_confidence(data)
        assert len(high["resources"]) == 1  # medium -> included


# ---------------------------------------------------------------------------
# _load_bicep_files
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestLoadBicepFiles:

    def test_loads_bicep_files(self, tmp_path):
        bicep = tmp_path / "main.bicep"
        bicep.write_text("param location string")
        result = _load_bicep_files(str(tmp_path))
        assert "param location string" in result

    def test_returns_none_for_nonexistent_dir(self):
        result = _load_bicep_files("/nonexistent/dir")
        assert result is None

    def test_returns_none_for_empty_dir(self, tmp_path):
        result = _load_bicep_files(str(tmp_path))
        assert result is None

    def test_limits_to_five_files(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file{i}.bicep").write_text(f"resource r{i}")
        result = _load_bicep_files(str(tmp_path))
        # Should contain at most 5 files
        assert result.count("// File:") <= 5

    def test_recursive_discovery(self, tmp_path):
        subdir = tmp_path / "modules"
        subdir.mkdir()
        (subdir / "child.bicep").write_text("module content")
        result = _load_bicep_files(str(tmp_path))
        assert "module content" in result


# ---------------------------------------------------------------------------
# CLI invocations via CliRunner
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCLIMain:

    def _make_runner(self):
        return CliRunner(mix_stderr=False)

    def test_version_flag(self):
        runner = self._make_runner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower() or "." in result.output

    def test_no_stdin_shows_error(self, clean_env, monkeypatch):
        """Running without piped stdin should error."""
        runner = self._make_runner()
        # CliRunner provides non-TTY stdin by default, but we mock isatty
        # to simulate no-piped-input
        monkeypatch.setattr("bicep_whatif_advisor.input.sys.stdin.isatty", lambda: True)
        result = runner.invoke(main, [], input=None)
        assert result.exit_code == 2

    def test_standard_mode_table_output(self, clean_env, monkeypatch, mocker, sample_standard_response):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1 to create.\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--format", "json"], input=whatif_input)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "high_confidence" in parsed

    def test_standard_mode_markdown_output(self, clean_env, monkeypatch, mocker, sample_standard_response):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--format", "markdown"], input=whatif_input)
        assert result.exit_code == 0
        assert "| #" in result.output

    def test_ci_mode_safe_exit_0(self, clean_env, monkeypatch, mocker, sample_ci_response_safe):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_ci_response_safe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--ci", "--format", "json"], input=whatif_input)
        assert result.exit_code == 0

    def test_ci_mode_unsafe_exit_1(self, clean_env, monkeypatch, mocker, sample_ci_response_unsafe):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_ci_response_unsafe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")
        whatif_input = "Resource changes: 1\n- Microsoft.Sql/servers/databases/prod-db"
        result = runner.invoke(main, ["--ci", "--format", "json"], input=whatif_input)
        assert result.exit_code == 1

    def test_ci_mode_no_block_exit_0(self, clean_env, monkeypatch, mocker, sample_ci_response_unsafe):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_ci_response_unsafe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")
        whatif_input = "Resource changes: 1\n- Microsoft.Sql/test"
        result = runner.invoke(main, ["--ci", "--no-block", "--format", "json"], input=whatif_input)
        assert result.exit_code == 0

    def test_ci_mode_skip_all_buckets_exits_2(self, clean_env, monkeypatch, mocker):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(
            main,
            ["--ci", "--skip-drift", "--skip-intent", "--skip-operations"],
            input=whatif_input,
        )
        assert result.exit_code == 2

    def test_invalid_json_response_exits_1(self, clean_env, monkeypatch, mocker):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from tests.conftest import MockProvider
        provider = MockProvider(response="This is not valid JSON at all")
        mocker.patch("bicep_whatif_advisor.cli.get_provider", return_value=provider)

        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--format", "json"], input=whatif_input)
        assert result.exit_code == 1

    def test_noise_file_not_found_exits_2(self, clean_env, monkeypatch, mocker):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(
            main,
            ["--noise-file", "/nonexistent/patterns.txt"],
            input=whatif_input,
        )
        assert result.exit_code == 2

    def test_verbose_flag_accepted(self, clean_env, monkeypatch, mocker, sample_standard_response):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--verbose", "--format", "json"], input=whatif_input)
        assert result.exit_code == 0

    def test_provider_flag(self, clean_env, monkeypatch, mocker, sample_standard_response):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_get = mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(main, ["--provider", "anthropic", "--format", "json"], input=whatif_input)
        assert result.exit_code == 0
        mock_get.assert_called_once_with("anthropic", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_provider(response: dict):
    """Create a MockProvider that returns the given response dict."""
    from tests.conftest import MockProvider
    return MockProvider(response=response)
