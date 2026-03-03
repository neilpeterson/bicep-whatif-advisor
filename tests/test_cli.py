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
        text = '```json\n{"resources": []}\n```'
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
        try:
            return CliRunner(mix_stderr=False)
        except TypeError:
            return CliRunner()

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

    def test_standard_mode_table_output(
        self, clean_env, monkeypatch, mocker, sample_standard_response
    ):
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

    def test_standard_mode_markdown_output(
        self, clean_env, monkeypatch, mocker, sample_standard_response
    ):
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
        result = runner.invoke(
            main, ["--ci", "--format", "json", "--drift-threshold", "high"], input=whatif_input
        )
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

    def test_ci_mode_no_block_exit_0(
        self, clean_env, monkeypatch, mocker, sample_ci_response_unsafe
    ):
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
            ["--ci", "--skip-drift", "--skip-intent"],
            input=whatif_input,
        )
        assert result.exit_code == 2

    def test_invalid_json_response_exits_1(self, clean_env, monkeypatch, mocker):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        from conftest import MockProvider

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

    def test_include_whatif_flag_threads_content(
        self, clean_env, monkeypatch, mocker, sample_standard_response
    ):
        """--include-whatif passes raw What-If content to render_markdown."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(
            main, ["--format", "markdown", "--include-whatif"], input=whatif_input
        )
        assert result.exit_code == 0
        assert "Raw What-If Output" in result.output

    def test_include_whatif_shows_original_not_filtered(
        self, clean_env, monkeypatch, mocker, sample_standard_response, tmp_path
    ):
        """--include-whatif shows original What-If content, not noise-filtered content."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        # Create a noise file that filters the etag property
        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("etag\n")
        whatif_input = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
        )
        result = runner.invoke(
            main,
            ["--format", "markdown", "--include-whatif", "--noise-file", str(noise_file)],
            input=whatif_input,
        )
        assert result.exit_code == 0
        # Raw What-If section should contain the ORIGINAL content including etag
        assert "etag" in result.output
        assert "Raw What-If Output" in result.output

    def test_resource_pattern_demotes_not_removes(self, clean_env, monkeypatch, mocker, tmp_path):
        """Resource noise patterns should demote resources to low confidence, not remove them."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # LLM returns a resource matching the resource pattern
        response = {
            "resources": [
                {
                    "resource_name": "link1",
                    "resource_type": "Network/privateDnsZones/virtualNetworkLinks",
                    "action": "Modify",
                    "summary": "DNS zone link update",
                    "confidence_level": "high",
                    "confidence_reason": "Config change",
                },
                {
                    "resource_name": "myvnet",
                    "resource_type": "Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "Address space change",
                    "confidence_level": "high",
                    "confidence_reason": "Real config change",
                },
            ],
            "overall_summary": "2 modifications.",
        }
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )

        # Create a noise file with a resource pattern
        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("resource: privateDnsZones/virtualNetworkLinks\n")

        whatif_input = "Resource changes: 2\n~ Microsoft.Network/test\n~ Microsoft.Network/test2"
        result = runner.invoke(
            main,
            ["--format", "json", "--noise-file", str(noise_file), "--no-builtin-patterns"],
            input=whatif_input,
        )
        assert result.exit_code == 0
        # Use extract_json to handle stderr messages that may leak into output
        parsed = extract_json(result.output)

        # link1 should be demoted to low confidence (not removed)
        low_resources = parsed.get("low_confidence", {}).get("resources", [])
        high_resources = parsed.get("high_confidence", {}).get("resources", [])

        assert len(high_resources) == 1
        assert high_resources[0]["resource_name"] == "myvnet"

        assert len(low_resources) == 1
        assert low_resources[0]["resource_name"] == "link1"
        assert low_resources[0]["confidence_level"] == "low"

    def test_hide_noise_json_omits_low_confidence(self, clean_env, monkeypatch, mocker):
        """--hide-noise should omit low_confidence key from JSON output."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = {
            "resources": [
                {
                    "resource_name": "real-resource",
                    "resource_type": "Microsoft.Storage/storageAccounts",
                    "action": "Create",
                    "summary": "New storage account",
                    "confidence_level": "high",
                    "confidence_reason": "Real change",
                },
                {
                    "resource_name": "noisy-resource",
                    "resource_type": "Microsoft.Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "Etag update",
                    "confidence_level": "low",
                    "confidence_reason": "Likely noise",
                },
            ],
            "overall_summary": "One real, one noisy.",
        }
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        whatif_input = "Resource changes: 2\n+ Microsoft.Storage/test\n~ Microsoft.Network/test"
        result = runner.invoke(main, ["--format", "json", "--hide-noise"], input=whatif_input)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "low_confidence" not in parsed
        assert "high_confidence" in parsed

    def test_no_hide_noise_json_includes_low_confidence(self, clean_env, monkeypatch, mocker):
        """Without --hide-noise, low_confidence should appear in JSON output."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = {
            "resources": [
                {
                    "resource_name": "real-resource",
                    "resource_type": "Microsoft.Storage/storageAccounts",
                    "action": "Create",
                    "summary": "New storage account",
                    "confidence_level": "high",
                    "confidence_reason": "Real change",
                },
                {
                    "resource_name": "noisy-resource",
                    "resource_type": "Microsoft.Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "Etag update",
                    "confidence_level": "low",
                    "confidence_reason": "Likely noise",
                },
            ],
            "overall_summary": "One real, one noisy.",
        }
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        whatif_input = "Resource changes: 2\n+ Microsoft.Storage/test\n~ Microsoft.Network/test"
        result = runner.invoke(main, ["--format", "json"], input=whatif_input)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "low_confidence" in parsed
        assert len(parsed["low_confidence"]["resources"]) == 1

    def test_hide_noise_markdown_omits_noise_section(self, clean_env, monkeypatch, mocker):
        """--hide-noise should omit the noise section from markdown output."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        response = {
            "resources": [
                {
                    "resource_name": "real-resource",
                    "resource_type": "Microsoft.Storage/storageAccounts",
                    "action": "Create",
                    "summary": "New storage account",
                    "confidence_level": "high",
                    "confidence_reason": "Real change",
                },
                {
                    "resource_name": "noisy-resource",
                    "resource_type": "Microsoft.Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "Etag update",
                    "confidence_level": "low",
                    "confidence_reason": "Likely noise",
                },
            ],
            "overall_summary": "One real, one noisy.",
        }
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        whatif_input = "Resource changes: 2\n+ Microsoft.Storage/test\n~ Microsoft.Network/test"
        result = runner.invoke(main, ["--format", "markdown", "--hide-noise"], input=whatif_input)
        assert result.exit_code == 0
        assert "Potential Azure What-If Noise" not in result.output
        assert "Low Confidence" not in result.output

    def test_all_filtered_drift_enabled_preserves_drift(
        self, clean_env, monkeypatch, mocker, tmp_path
    ):
        """All resources filtered + drift enabled: preserves LLM's drift assessment."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # LLM returns a response where the only resource will be filtered as noise,
        # but drift is high because the resource was modified out-of-band
        response = {
            "resources": [
                {
                    "resource_name": "noisy-vnet",
                    "resource_type": "Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "etag change",
                    "risk_level": "medium",
                    "risk_reason": "vnet change",
                    "confidence_level": "low",
                    "confidence_reason": "Metadata only",
                },
            ],
            "overall_summary": "1 noisy modification",
            "risk_assessment": {
                "drift": {
                    "risk_level": "high",
                    "concerns": ["VNet modified outside of code"],
                    "reasoning": "Out-of-band change detected",
                },
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "drift",
                "overall_risk_level": "high",
                "reasoning": "Drift detected",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")

        # Create noise patterns that will filter out the vnet resource block
        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("resource: virtualNetworks\n")

        # What-If input with a resource block that matches the noise pattern
        whatif_input = (
            "Resource changes: 1 to modify.\n"
            "  ~ Microsoft.Network/virtualNetworks/myVNet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
        )
        result = runner.invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--drift-threshold",
                "high",
                "--noise-file",
                str(noise_file),
                "--no-builtin-patterns",
            ],
            input=whatif_input,
        )
        # Drift is high and threshold is high -> meets threshold -> exit 1
        assert result.exit_code == 1
        parsed = extract_json(result.output)
        ra = parsed["high_confidence"]["risk_assessment"]
        assert ra["drift"]["risk_level"] == "high"

    def test_all_filtered_drift_skipped_all_buckets_low(
        self, clean_env, monkeypatch, mocker, tmp_path
    ):
        """All resources filtered + drift skipped: all buckets set to low."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        response = {
            "resources": [
                {
                    "resource_name": "noisy-vnet",
                    "resource_type": "Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "etag change",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "low",
                    "confidence_reason": "Metadata only",
                },
            ],
            "overall_summary": "1 noisy modification",
            "risk_assessment": {
                "intent": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "ok",
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "ok",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")

        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("resource: virtualNetworks\n")

        whatif_input = (
            "Resource changes: 1 to modify.\n"
            "  ~ Microsoft.Network/virtualNetworks/myVNet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
        )
        result = runner.invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--skip-drift",
                "--pr-title",
                "Add storage",
                "--noise-file",
                str(noise_file),
                "--no-builtin-patterns",
            ],
            input=whatif_input,
        )
        assert result.exit_code == 0
        parsed = extract_json(result.output)
        ra = parsed["high_confidence"]["risk_assessment"]
        # drift bucket should not exist (skipped), intent should be low
        assert "drift" not in ra
        assert ra["intent"]["risk_level"] == "low"

    def test_all_filtered_drift_preserved_high_verdict_unsafe(
        self, clean_env, monkeypatch, mocker, tmp_path
    ):
        """All filtered + drift preserved at high with medium threshold: verdict is unsafe."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        response = {
            "resources": [
                {
                    "resource_name": "noisy-vnet",
                    "resource_type": "Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "etag change",
                    "risk_level": "medium",
                    "risk_reason": "change",
                    "confidence_level": "low",
                    "confidence_reason": "Metadata only",
                },
            ],
            "overall_summary": "1 noisy modification",
            "risk_assessment": {
                "drift": {
                    "risk_level": "high",
                    "concerns": ["Critical drift"],
                    "reasoning": "Manual changes detected",
                },
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "drift",
                "overall_risk_level": "high",
                "reasoning": "Drift detected",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(response),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")

        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("resource: virtualNetworks\n")

        whatif_input = (
            "Resource changes: 1 to modify.\n"
            "  ~ Microsoft.Network/virtualNetworks/myVNet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
        )
        result = runner.invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--drift-threshold",
                "medium",
                "--noise-file",
                str(noise_file),
                "--no-builtin-patterns",
            ],
            input=whatif_input,
        )
        # high drift >= medium threshold -> unsafe -> exit 1
        assert result.exit_code == 1

    def test_reanalysis_passes_unfiltered_content(self, clean_env, monkeypatch, mocker, tmp_path):
        """Re-analysis path includes unfiltered content in the prompt (via MockProvider.calls)."""
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # First call: mixed confidence (triggers re-analysis)
        first_response = {
            "resources": [
                {
                    "resource_name": "real-storage",
                    "resource_type": "Storage/storageAccounts",
                    "action": "Create",
                    "summary": "Creates storage",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "high",
                    "confidence_reason": "Real creation",
                },
                {
                    "resource_name": "noise-vnet",
                    "resource_type": "Network/virtualNetworks",
                    "action": "Modify",
                    "summary": "etag change",
                    "risk_level": "medium",
                    "risk_reason": "vnet change",
                    "confidence_level": "low",
                    "confidence_reason": "Metadata only",
                },
            ],
            "overall_summary": "Mixed changes",
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "ok",
            },
        }

        # Second call: re-analysis response
        second_response = {
            "resources": [
                {
                    "resource_name": "real-storage",
                    "resource_type": "Storage/storageAccounts",
                    "action": "Create",
                    "summary": "Creates storage",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "high",
                    "confidence_reason": "Real creation",
                },
            ],
            "overall_summary": "1 create",
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "ok",
            },
        }

        from conftest import MockProvider

        call_count = {"n": 0}
        responses = [first_response, second_response]

        class MultiResponseProvider(MockProvider):
            def complete(self, system_prompt, user_prompt):
                idx = min(call_count["n"], len(responses) - 1)
                call_count["n"] += 1
                self.calls.append((system_prompt, user_prompt))
                return json.dumps(responses[idx])

        provider = MultiResponseProvider()
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=provider,
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")

        # Create noise file that filters a property line (so filtering changes content)
        noise_file = tmp_path / "noise.txt"
        noise_file.write_text("etag\n")

        whatif_input = (
            "Resource changes: 2 to create/modify.\n"
            "+ Microsoft.Storage/storageAccounts/newstorage [2023-01-01]\n"
            "  ~ Microsoft.Network/virtualNetworks/myVNet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
        )
        result = runner.invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--drift-threshold",
                "high",
                "--noise-file",
                str(noise_file),
                "--no-builtin-patterns",
            ],
            input=whatif_input,
        )
        assert result.exit_code == 0
        assert call_count["n"] == 2  # initial + re-analysis

        # Both calls should include the unfiltered content tag
        for _, user_prompt in provider.calls:
            assert "<whatif_output_unfiltered>" in user_prompt
            # Unfiltered content should contain the original etag line
            assert "etag" in user_prompt

    def test_provider_flag(self, clean_env, monkeypatch, mocker, sample_standard_response):
        runner = self._make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_get = mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        whatif_input = "Resource changes: 1\n+ Microsoft.Storage/test"
        result = runner.invoke(
            main, ["--provider", "anthropic", "--format", "json"], input=whatif_input
        )
        assert result.exit_code == 0
        mock_get.assert_called_once_with("anthropic", None)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_provider(response: dict):
    """Create a MockProvider that returns the given response dict."""
    from conftest import MockProvider

    return MockProvider(response=response)
