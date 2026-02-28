"""Tests for --config-file CLI option."""

import pytest
import yaml
from click.testing import CliRunner

from bicep_whatif_advisor.cli import _load_config_file, main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_runner():
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


def _mock_provider(response: dict):
    from conftest import MockProvider

    return MockProvider(response=response)


WHATIF_INPUT = "Resource changes: 1 to create.\n+ Microsoft.Storage/test"


# ---------------------------------------------------------------------------
# _load_config_file callback unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadConfigFileCallback:
    def test_none_value_returns_early(self):
        """Callback is a no-op when no config file is provided."""

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        result = _load_config_file(ctx, None, None)
        assert result is None
        assert ctx.default_map is None

    def test_loads_valid_yaml(self, tmp_path):
        """Valid YAML file is loaded into ctx.default_map."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("provider: ollama\nmodel: llama3\n")

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        _load_config_file(ctx, None, str(cfg))
        assert ctx.default_map == {"provider": "ollama", "model": "llama3"}

    def test_file_not_found_raises_bad_parameter(self):
        from click import BadParameter

        class FakeCtx:
            default_map = None

        with pytest.raises(BadParameter, match="not found"):
            _load_config_file(FakeCtx(), None, "/nonexistent/config.yaml")

    def test_invalid_yaml_raises_bad_parameter(self, tmp_path):
        from click import BadParameter

        cfg = tmp_path / "bad.yaml"
        cfg.write_text("provider: [\ninvalid yaml")

        class FakeCtx:
            default_map = None

        with pytest.raises(BadParameter, match="Invalid YAML"):
            _load_config_file(FakeCtx(), None, str(cfg))

    def test_empty_file_is_noop(self, tmp_path):
        """Empty YAML file does not set default_map."""
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("")

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        _load_config_file(ctx, None, str(cfg))
        assert ctx.default_map is None

    def test_non_dict_raises_bad_parameter(self, tmp_path):
        from click import BadParameter

        cfg = tmp_path / "list.yaml"
        cfg.write_text("- item1\n- item2\n")

        class FakeCtx:
            default_map = None

        with pytest.raises(BadParameter, match="mapping"):
            _load_config_file(FakeCtx(), None, str(cfg))

    def test_unknown_keys_warned_and_removed(self, tmp_path, capsys):
        """Unknown keys produce a stderr warning and are removed."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text("provider: anthropic\nfoo_bar: baz\n")

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        _load_config_file(ctx, None, str(cfg))
        assert "foo_bar" not in ctx.default_map
        assert ctx.default_map == {"provider": "anthropic"}
        captured = capsys.readouterr()
        assert "foo_bar" in captured.err

    def test_list_to_tuple_conversion(self, tmp_path):
        """agent_threshold and skip_agent lists become tuples."""
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "agent_threshold": ["compliance=medium", "cost=low"],
                    "skip_agent": ["naming"],
                }
            )
        )

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        _load_config_file(ctx, None, str(cfg))
        assert ctx.default_map["agent_threshold"] == (
            "compliance=medium",
            "cost=low",
        )
        assert ctx.default_map["skip_agent"] == ("naming",)

    def test_all_known_keys_accepted(self, tmp_path):
        """Every known key is accepted without warnings."""
        cfg = tmp_path / "config.yaml"
        config = {
            "provider": "anthropic",
            "model": "claude-sonnet-4-20250514",
            "format": "json",
            "verbose": True,
            "no_color": False,
            "ci": True,
            "diff": None,
            "diff_ref": "origin/main",
            "drift_threshold": "high",
            "intent_threshold": "medium",
            "post_comment": False,
            "pr_url": None,
            "bicep_dir": ".",
            "pr_title": "Test PR",
            "pr_description": "Desc",
            "no_block": False,
            "skip_drift": False,
            "skip_intent": False,
            "comment_title": "Review",
            "noise_file": None,
            "noise_threshold": 80,
            "no_builtin_patterns": False,
            "include_whatif": False,
            "agents_dir": None,
            "agent_threshold": [],
            "skip_agent": [],
        }
        cfg.write_text(yaml.dump(config))

        class FakeCtx:
            default_map = None

        ctx = FakeCtx()
        _load_config_file(ctx, None, str(cfg))
        assert "provider" in ctx.default_map
        assert ctx.default_map["provider"] == "anthropic"


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfigFileCLI:
    def test_config_sets_provider(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_get = mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("provider: ollama\n")
        result = runner.invoke(
            main,
            ["--config-file", str(cfg), "--format", "json"],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0
        mock_get.assert_called_once_with("ollama", None)

    def test_cli_flag_overrides_config(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        """Explicit CLI flag takes precedence over config file."""
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_get = mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("provider: ollama\nmodel: llama3\n")
        result = runner.invoke(
            main,
            ["--config-file", str(cfg), "--provider", "anthropic", "--format", "json"],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0
        mock_get.assert_called_once_with("anthropic", "llama3")

    def test_config_sets_format(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("format: markdown\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0
        assert "| #" in result.output  # markdown table

    def test_config_sets_thresholds(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_ci_response_safe
    ):
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_ci_response_safe),
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff content",
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("ci: true\ndrift_threshold: medium\nformat: json\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0

    def test_config_enables_ci_mode(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_ci_response_safe
    ):
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_ci_response_safe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")
        cfg = tmp_path / "config.yaml"
        cfg.write_text("ci: true\nformat: json\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0
        # CI mode prints a Rich banner to stdout before JSON, so use
        # extract_json (same approach as test_cli.py) instead of json.loads.
        from bicep_whatif_advisor.cli import extract_json

        parsed = extract_json(result.output)
        assert "high_confidence" in parsed

    def test_missing_config_file_exits_error(self, clean_env):
        runner = _make_runner()
        result = runner.invoke(
            main,
            ["--config-file", "/nonexistent/config.yaml"],
            input=WHATIF_INPUT,
        )
        assert result.exit_code != 0

    def test_invalid_yaml_config_exits_error(self, clean_env, tmp_path):
        runner = _make_runner()
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("provider: [\ninvalid")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code != 0

    def test_invalid_choice_in_config_exits_error(
        self, clean_env, monkeypatch, tmp_path
    ):
        """Invalid choice value in config is caught by Click."""
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        cfg = tmp_path / "config.yaml"
        cfg.write_text("provider: not-a-provider\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code != 0

    def test_config_sets_multiple_options(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        """Config file can set multiple options at once."""
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_get = mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            "provider: anthropic\nmodel: claude-haiku\n"
            "format: json\nverbose: true\n"
        )
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0
        mock_get.assert_called_once_with("anthropic", "claude-haiku")

    def test_config_with_boolean_flags(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        """Boolean flags like verbose and no_color work from config."""
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("verbose: true\nno_color: true\nformat: json\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0

    def test_config_with_noise_threshold(
        self, clean_env, monkeypatch, mocker, tmp_path, sample_standard_response
    ):
        """noise_threshold integer value works from config."""
        runner = _make_runner()
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=_mock_provider(sample_standard_response),
        )
        cfg = tmp_path / "config.yaml"
        cfg.write_text("noise_threshold: 90\nformat: json\n")
        result = runner.invoke(
            main, ["--config-file", str(cfg)], input=WHATIF_INPUT
        )
        assert result.exit_code == 0
