"""Integration tests for custom risk assessment agents."""

import pytest
from click.testing import CliRunner
from conftest import MockProvider

from bicep_whatif_advisor.ci.buckets import RISK_BUCKETS
from bicep_whatif_advisor.cli import main


@pytest.fixture(autouse=True)
def clean_risk_buckets():
    """Restore RISK_BUCKETS to original state after each test."""
    original_keys = set(RISK_BUCKETS.keys())
    yield
    current_keys = set(RISK_BUCKETS.keys())
    for key in current_keys - original_keys:
        del RISK_BUCKETS[key]


def _runner():
    try:
        return CliRunner(mix_stderr=False)
    except TypeError:
        return CliRunner()


WHATIF_INPUT = "Resource changes: 1\n+ Microsoft.Storage/test"


@pytest.mark.integration
class TestAgentsCLIIntegration:
    def test_agents_dir_loads_and_in_prompt(self, clean_env, monkeypatch, mocker, tmp_path):
        """Custom agent instructions appear in the LLM system prompt."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "compliance.md").write_text(
            "---\nid: compliance\n"
            "display_name: Compliance Review\n"
            "default_threshold: high\n---\n"
            "Evaluate for compliance violations.\n"
        )

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
                    "reasoning": "ok",
                },
                "compliance": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "No compliance issues",
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "All safe.",
            },
        }

        provider = MockProvider(response)
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=provider,
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff content",
        )

        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--agents-dir",
                str(agents_dir),
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0

        # Verify system prompt contains custom agent instructions
        assert len(provider.calls) >= 1
        system_prompt = provider.calls[0][0]
        assert "Compliance Review" in system_prompt
        assert "compliance violations" in system_prompt

    def test_agent_threshold_blocks_pipeline(self, clean_env, monkeypatch, mocker, tmp_path):
        """--agent-threshold causes pipeline failure when exceeded."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "compliance.md").write_text(
            "---\nid: compliance\n"
            "display_name: Compliance Review\n"
            "default_threshold: high\n---\n"
            "Compliance instructions.\n"
        )

        response = {
            "resources": [
                {
                    "resource_name": "s1",
                    "resource_type": "Storage/storageAccounts",
                    "action": "Create",
                    "summary": "Creates storage",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "high",
                    "confidence_reason": "Real",
                },
            ],
            "overall_summary": "",
            "risk_assessment": {
                "drift": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "",
                },
                "compliance": {
                    "risk_level": "medium",
                    "concerns": ["policy issue"],
                    "reasoning": "medium risk",
                },
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "compliance",
                "overall_risk_level": "medium",
                "reasoning": "Compliance medium risk.",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(response),
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff",
        )

        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--agents-dir",
                str(agents_dir),
                "--agent-threshold",
                "compliance=medium",
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 1

    def test_skip_agent_excludes_from_prompt(self, clean_env, monkeypatch, mocker, tmp_path):
        """--skip-agent excludes custom agent from evaluation."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "compliance.md").write_text(
            "---\nid: compliance\ndisplay_name: Compliance Review\n---\nCompliance instructions.\n"
        )

        response = {
            "resources": [],
            "overall_summary": "",
            "risk_assessment": {
                "drift": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "",
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "none",
                "overall_risk_level": "low",
                "reasoning": "ok",
            },
        }

        provider = MockProvider(response)
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=provider,
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff",
        )

        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--agents-dir",
                str(agents_dir),
                "--skip-agent",
                "compliance",
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0
        # Verify compliance is NOT in the system prompt
        system_prompt = provider.calls[0][0]
        assert "Compliance Review" not in system_prompt

    def test_agents_dir_without_ci_warns(
        self,
        clean_env,
        monkeypatch,
        mocker,
        tmp_path,
        sample_standard_response,
    ):
        """--agents-dir without --ci shows warning and is ignored."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "compliance.md").write_text(
            "---\nid: compliance\ndisplay_name: Compliance Review\n---\nBody\n"
        )

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(sample_standard_response),
        )

        result = _runner().invoke(
            main,
            [
                "--format",
                "json",
                "--agents-dir",
                str(agents_dir),
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0

    def test_agent_table_display_findings_in_markdown_output(
        self, clean_env, monkeypatch, mocker, tmp_path
    ):
        """Custom agent with display: table renders findings in markdown."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "naming.md").write_text(
            "---\nid: naming\n"
            "display_name: Naming Convention\n"
            "default_threshold: high\n"
            'display: table\nicon: "\U0001f4db"\n---\n'
            "Check naming conventions.\n"
        )

        response = {
            "resources": [
                {
                    "resource_name": "storageaccount1",
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
                    "concern_summary": "None",
                    "reasoning": "ok",
                },
                "naming": {
                    "risk_level": "medium",
                    "concerns": ["bad name"],
                    "concern_summary": "Storage account missing CAF prefix",
                    "reasoning": "Non-standard name.",
                    "findings": [
                        {
                            "resource": "storageaccount1",
                            "issue": "No CAF prefix",
                            "recommendation": "Use st<workload><env>",
                        }
                    ],
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "naming",
                "overall_risk_level": "medium",
                "reasoning": "Naming issues found but not blocking.",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(response),
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff content",
        )

        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "markdown",
                "--agents-dir",
                str(agents_dir),
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0
        assert "Naming Convention Details" in result.output
        assert "| Resource | Issue | Recommendation |" in result.output
        assert "storageaccount1" in result.output
        assert "No CAF prefix" in result.output

    def test_default_threshold_from_agent_file(self, clean_env, monkeypatch, mocker, tmp_path):
        """Agent's default_threshold is used when no --agent-threshold."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        # Agent with default_threshold=medium
        (agents_dir / "compliance.md").write_text(
            "---\nid: compliance\n"
            "display_name: Compliance Review\n"
            "default_threshold: medium\n---\n"
            "Compliance instructions.\n"
        )

        # Risk level is medium, which matches the medium threshold
        response = {
            "resources": [
                {
                    "resource_name": "s1",
                    "resource_type": "Storage/storageAccounts",
                    "action": "Create",
                    "summary": "Creates storage",
                    "risk_level": "low",
                    "risk_reason": None,
                    "confidence_level": "high",
                    "confidence_reason": "Real",
                },
            ],
            "overall_summary": "",
            "risk_assessment": {
                "drift": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "",
                },
                "compliance": {
                    "risk_level": "medium",
                    "concerns": ["issue"],
                    "reasoning": "medium risk",
                },
            },
            "verdict": {
                "safe": False,
                "highest_risk_bucket": "compliance",
                "overall_risk_level": "medium",
                "reasoning": "Compliance medium.",
            },
        }

        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=MockProvider(response),
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff",
        )

        # No --agent-threshold, so default_threshold=medium applies
        # medium risk >= medium threshold -> FAIL
        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "json",
                "--agents-dir",
                str(agents_dir),
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 1

    def test_custom_columns_in_prompt_and_markdown(self, clean_env, monkeypatch, mocker, tmp_path):
        """Custom columns from agent frontmatter appear in LLM prompt and markdown output."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        agents_dir = tmp_path / "agents"
        agents_dir.mkdir()
        (agents_dir / "sfi.md").write_text(
            "---\nid: sfi\n"
            "display_name: Secure Infrastructure\n"
            "default_threshold: high\n"
            "display: table\n"
            'icon: "\U0001f512"\n'
            "columns:\n"
            "  - name: SFI ID and Name\n"
            "    description: taken from the title of each check\n"
            "  - name: Compliance Status\n"
            "    description: compliant or non-compliant\n"
            "  - name: Applicable\n"
            "    description: true / false\n"
            "---\n"
            "Check SFI compliance.\n"
        )

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
                    "concern_summary": "None",
                    "reasoning": "ok",
                },
                "sfi": {
                    "risk_level": "medium",
                    "concerns": ["non-compliant resource"],
                    "concern_summary": "Storage account not compliant",
                    "reasoning": "SFI issues found.",
                    "findings": [
                        {
                            "sfi_id_and_name": "[SFI-ID4.2.1] Storage Accounts",
                            "compliance_status": "non-compliant",
                            "applicable": "true",
                        }
                    ],
                },
            },
            "verdict": {
                "safe": True,
                "highest_risk_bucket": "sfi",
                "overall_risk_level": "medium",
                "reasoning": "SFI issues found but not blocking.",
            },
        }

        provider = MockProvider(response)
        mocker.patch(
            "bicep_whatif_advisor.cli.get_provider",
            return_value=provider,
        )
        mocker.patch(
            "bicep_whatif_advisor.ci.diff.get_diff",
            return_value="diff content",
        )

        result = _runner().invoke(
            main,
            [
                "--ci",
                "--format",
                "markdown",
                "--agents-dir",
                str(agents_dir),
            ],
            input=WHATIF_INPUT,
        )
        assert result.exit_code == 0

        # Verify custom columns in LLM prompt
        system_prompt = provider.calls[0][0]
        assert '"sfi_id_and_name"' in system_prompt
        assert '"compliance_status"' in system_prompt
        assert '"applicable"' in system_prompt

        # Verify custom columns in rendered markdown
        assert "| SFI ID and Name | Compliance Status | Applicable |" in result.output
        assert "[SFI-ID4.2.1] Storage Accounts" in result.output
        assert "non-compliant" in result.output
