"""Integration tests — end-to-end pipelines through the CLI."""

import json

import pytest
from click.testing import CliRunner
from conftest import MockProvider

from bicep_whatif_advisor.cli import main


def _runner():
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


@pytest.mark.integration
class TestStandardModePipeline:
    def test_create_only_fixture(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_standard_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_standard_response),
        )
        result = _runner().invoke(main, ["--format", "json"], input=create_only_fixture)
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert "high_confidence" in parsed

    def test_mixed_changes_fixture(
        self, clean_env, monkeypatch, mocker, mixed_changes_fixture, sample_standard_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_standard_response),
        )
        result = _runner().invoke(main, ["--format", "json"], input=mixed_changes_fixture)
        assert result.exit_code == 0

    def test_markdown_output_format(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_standard_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_standard_response),
        )
        result = _runner().invoke(main, ["--format", "markdown"], input=create_only_fixture)
        assert result.exit_code == 0
        assert "| #" in result.output

    def test_table_output_format(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_standard_response
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_standard_response),
        )
        result = _runner().invoke(main, ["--format", "table"], input=create_only_fixture)
        assert result.exit_code == 0


@pytest.mark.integration
class TestCIModePipeline:
    def test_ci_safe_deploy(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_ci_response_safe
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_ci_response_safe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")
        result = _runner().invoke(
            main,
            ["--ci", "--format", "json"],
            input=create_only_fixture,
        )
        assert result.exit_code == 0

    def test_ci_unsafe_blocks(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_ci_response_unsafe
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_ci_response_unsafe),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff content")
        result = _runner().invoke(
            main,
            ["--ci", "--format", "json"],
            input=create_only_fixture,
        )
        assert result.exit_code == 1

    def test_ci_with_intent(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_ci_response_with_intent
    ):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_ci_response_with_intent),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")
        result = _runner().invoke(
            main,
            ["--ci", "--format", "json", "--pr-title", "Add storage", "--pr-description", "test"],
            input=create_only_fixture,
        )
        assert result.exit_code == 0


@pytest.mark.integration
class TestNoiseFilteringPipeline:
    def test_noise_filtering_with_recalculation(
        self, clean_env, monkeypatch, mocker, create_only_fixture
    ):
        """CI mode with noise resources triggers recalculation."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # First call returns response with mixed confidence
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
                "drift": {"risk_level": "medium", "concerns": ["stale"], "reasoning": ""},
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "drift",
                "overall_risk_level": "medium",
                "reasoning": "medium risk",
            },
        }

        # Second call (recalculation) returns safe assessment
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

        call_count = {"n": 0}
        responses = [first_response, second_response]

        class MultiResponseProvider(MockProvider):
            def complete(self, system_prompt, user_prompt):
                idx = min(call_count["n"], len(responses) - 1)
                call_count["n"] += 1
                return json.dumps(responses[idx])

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MultiResponseProvider(),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")

        result = _runner().invoke(
            main,
            ["--ci", "--format", "json"],
            input=create_only_fixture,
        )
        assert result.exit_code == 0
        assert call_count["n"] == 2  # Two LLM calls: initial + recalculation


@pytest.mark.integration
class TestCustomAgentBackfill:
    """Ensure custom agents appear in output even if LLM omits them."""

    def test_missing_agent_backfilled_in_json(
        self, clean_env, monkeypatch, mocker, create_only_fixture, tmp_path
    ):
        """When LLM omits a custom agent from risk_assessment, a default low entry is added."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        # Create a minimal custom agent file
        agent_file = tmp_path / "cost.md"
        agent_file.write_text(
            "---\nid: cost\ndisplay_name: Cost Impact\ndefault_threshold: high\n---\n"
            "Evaluate cost risk.\n"
        )

        # LLM response only has drift — no cost bucket
        response = {
            "resources": [
                {
                    "resource_name": "storage1",
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
                "drift": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "No drift",
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "Safe",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(response),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")

        result = _runner().invoke(
            main,
            ["--ci", "--format", "json", "--agents-dir", str(tmp_path)],
            input=create_only_fixture,
        )
        assert result.exit_code == 0

        # Extract JSON from output (CliRunner may mix in extra text on some platforms)
        from bicep_whatif_advisor.cli import extract_json

        output = extract_json(result.output)
        ra = output["high_confidence"]["risk_assessment"]
        assert "drift" in ra
        assert "cost" in ra
        assert ra["cost"]["risk_level"] == "low"

    def test_missing_agent_appears_in_markdown(
        self, clean_env, monkeypatch, mocker, create_only_fixture, tmp_path
    ):
        """Backfilled agents appear as rows in the markdown risk table."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agent_file = tmp_path / "naming.md"
        agent_file.write_text(
            "---\nid: naming\ndisplay_name: Naming Convention\n"
            "default_threshold: medium\n---\nEvaluate naming.\n"
        )

        response = {
            "resources": [
                {
                    "resource_name": "vm1",
                    "resource_type": "Compute/virtualMachines",
                    "action": "Create",
                    "summary": "Creates VM",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "high",
                    "confidence_reason": "Real",
                },
            ],
            "overall_summary": "1 VM",
            "risk_assessment": {
                "drift": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "No drift",
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "Safe",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(response),
        )
        mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")

        result = _runner().invoke(
            main,
            ["--ci", "--format", "markdown", "--agents-dir", str(tmp_path)],
            input=create_only_fixture,
        )
        assert result.exit_code == 0
        assert "Naming Convention" in result.output
        assert "Infrastructure Drift" in result.output


@pytest.mark.integration
class TestPlatformAutoDetect:
    def test_github_auto_enables_ci(
        self, clean_env, monkeypatch, mocker, create_only_fixture, sample_ci_response_safe
    ):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        monkeypatch.setenv("GITHUB_BASE_REF", "main")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        provider = MockProvider(sample_ci_response_safe)
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=provider,
        )
        mock_get_diff = mocker.patch("bicep_whatif_advisor.ci.diff.get_diff", return_value="diff")
        result = _runner().invoke(main, ["--format", "json"], input=create_only_fixture)
        assert result.exit_code == 0
        # CI mode was auto-enabled — get_diff was called (only happens in CI mode)
        mock_get_diff.assert_called_once()
        # The provider was called with CI system prompt (has risk_assessment)
        assert len(provider.calls) >= 1
        system_prompt = provider.calls[0][0]
        assert "risk_assessment" in system_prompt
