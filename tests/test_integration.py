"""Integration tests — end-to-end pipelines through the CLI."""

import json

import pytest
from click.testing import CliRunner

from bicep_whatif_advisor.cli import main
from conftest import MockProvider


def _runner():
    return CliRunner(mix_stderr=False)


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
                "operations": {"risk_level": "medium", "concerns": ["vnet"], "reasoning": ""},
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "operations",
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
                "operations": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
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
