"""Tests for bicep_whatif_advisor.render module."""

import json

import pytest

from bicep_whatif_advisor.render import (
    _colorize,
    _render_agent_detail_sections,
    render_json,
    render_markdown,
    render_table,
)


@pytest.mark.unit
class TestColorize:
    def test_colorize_enabled(self):
        result = _colorize("hello", "red", use_color=True)
        assert result == "[red]hello[/red]"

    def test_colorize_disabled(self):
        result = _colorize("hello", "red", use_color=False)
        assert result == "hello"


@pytest.mark.unit
class TestRenderJson:
    def test_basic_json_output(self, capsys):
        data = {"resources": [], "overall_summary": "Nothing"}
        render_json(data)
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert "high_confidence" in parsed
        assert parsed["high_confidence"]["overall_summary"] == "Nothing"

    def test_json_includes_low_confidence(self, capsys):
        data = {"resources": [], "overall_summary": ""}
        low = {"resources": [{"resource_name": "noise"}]}
        render_json(data, low_confidence_data=low)
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert "low_confidence" in parsed
        assert len(parsed["low_confidence"]["resources"]) == 1

    def test_json_no_low_confidence(self, capsys):
        data = {"resources": [], "overall_summary": ""}
        render_json(data)
        output = capsys.readouterr().out
        parsed = json.loads(output)
        assert "low_confidence" not in parsed


@pytest.mark.unit
class TestRenderMarkdown:
    def test_standard_mode_has_table(self):
        data = {
            "resources": [
                {
                    "resource_name": "myvm",
                    "resource_type": "Compute/virtualMachines",
                    "action": "Create",
                    "summary": "Creates a VM",
                }
            ],
            "overall_summary": "1 resource created.",
        }
        md = render_markdown(data)
        assert "| # |" in md
        assert "myvm" in md
        assert "1 resource created." in md

    def test_ci_mode_has_verdict(self):
        data = {
            "resources": [],
            "overall_summary": "",
            "_enabled_buckets": ["drift"],
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            },
            "verdict": {"safe": True, "reasoning": "All safe"},
        }
        md = render_markdown(data, ci_mode=True)
        assert "SAFE" in md
        assert "What-If Deployment Review" in md

    def test_ci_mode_custom_title(self):
        data = {"resources": [], "overall_summary": "", "verdict": {}}
        md = render_markdown(data, ci_mode=True, custom_title="My Review")
        assert "## My Review" in md

    def test_no_block_appends_label(self):
        data = {"resources": [], "overall_summary": "", "verdict": {}}
        md = render_markdown(data, ci_mode=True, no_block=True)
        assert "(non-blocking)" in md

    def test_unsafe_verdict(self):
        data = {
            "resources": [],
            "overall_summary": "",
            "verdict": {"safe": False, "reasoning": "Dangerous operation"},
        }
        md = render_markdown(data, ci_mode=True)
        assert "UNSAFE" in md
        assert "Dangerous operation" in md

    def test_low_confidence_noise_section(self):
        data = {"resources": [], "overall_summary": ""}
        low = {
            "resources": [
                {
                    "resource_name": "noisyvm",
                    "resource_type": "Compute/vms",
                    "action": "Modify",
                    "confidence_reason": "Metadata noise",
                }
            ]
        }
        md = render_markdown(data, low_confidence_data=low)
        assert "Potential Azure What-If Noise" in md
        assert "noisyvm" in md
        assert "Metadata noise" in md

    def test_standard_mode_collapsible(self):
        data = {
            "resources": [
                {
                    "resource_name": "r1",
                    "resource_type": "T",
                    "action": "Create",
                    "summary": "s",
                }
            ],
            "overall_summary": "",
        }
        md = render_markdown(data)
        assert "<details>" in md
        assert "<summary>" in md

    def test_ci_mode_risk_column(self):
        data = {
            "resources": [
                {
                    "resource_name": "r1",
                    "resource_type": "T",
                    "action": "Delete",
                    "summary": "s",
                    "risk_level": "high",
                }
            ],
            "overall_summary": "",
        }
        md = render_markdown(data, ci_mode=True)
        assert "Risk" in md
        assert "High" in md

    def test_pipe_in_summary_escaped(self):
        data = {
            "resources": [
                {
                    "resource_name": "r",
                    "resource_type": "T",
                    "action": "Create",
                    "summary": "a|b",
                }
            ],
            "overall_summary": "",
        }
        md = render_markdown(data)
        assert "a\\|b" in md

    def test_risk_assessment_table_in_markdown(self):
        data = {
            "resources": [],
            "overall_summary": "",
            "_enabled_buckets": ["drift", "intent"],
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": ["drift concern"], "reasoning": ""},
                "intent": {"risk_level": "medium", "concerns": ["intent concern"], "reasoning": ""},
            },
            "verdict": {"safe": True, "reasoning": "ok"},
        }
        md = render_markdown(data, ci_mode=True)
        assert "Infrastructure Drift" in md
        assert "PR Intent Alignment" in md

    def test_github_no_br_between_details(self):
        """GitHub platform should not include <br> between collapsible sections."""
        data = {"resources": [], "overall_summary": ""}
        low = {
            "resources": [
                {
                    "resource_name": "noisy",
                    "resource_type": "T",
                    "action": "Modify",
                    "confidence_reason": "noise",
                }
            ]
        }
        md = render_markdown(data, low_confidence_data=low, platform="github")
        # Should have both details sections but no <br> between them
        assert md.count("<details>") == 2
        assert "<br>" not in md

    def test_azuredevops_br_between_details(self):
        """Azure DevOps platform should include <br> between collapsible sections."""
        data = {"resources": [], "overall_summary": ""}
        low = {
            "resources": [
                {
                    "resource_name": "noisy",
                    "resource_type": "T",
                    "action": "Modify",
                    "confidence_reason": "noise",
                }
            ]
        }
        md = render_markdown(data, low_confidence_data=low, platform="azuredevops")
        assert md.count("<details>") == 2
        assert "<br>" in md

    def test_default_platform_br_between_details(self):
        """Default (no platform) should include <br> for backward compatibility."""
        data = {"resources": [], "overall_summary": ""}
        low = {
            "resources": [
                {
                    "resource_name": "noisy",
                    "resource_type": "T",
                    "action": "Modify",
                    "confidence_reason": "noise",
                }
            ]
        }
        md = render_markdown(data, low_confidence_data=low)
        assert "<br>" in md

    def test_include_whatif_collapsible_section(self):
        """When whatif_content is provided, a collapsible section with the raw output appears."""
        data = {"resources": [], "overall_summary": ""}
        raw = "Resource changes: 1 to create.\n+ Microsoft.Storage/storageAccounts/mystorage"
        md = render_markdown(data, whatif_content=raw)
        assert "<details>" in md
        assert "Raw What-If Output" in md
        assert raw in md

    def test_include_whatif_none_no_section(self):
        """When whatif_content is None, no raw What-If section appears."""
        data = {"resources": [], "overall_summary": ""}
        md = render_markdown(data, whatif_content=None)
        assert "Raw What-If Output" not in md

    def test_include_whatif_code_fence(self):
        """Raw What-If content should be wrapped in a code fence."""
        data = {"resources": [], "overall_summary": ""}
        raw = "Resource changes: 1\n+ Microsoft.Storage/test"
        md = render_markdown(data, whatif_content=raw)
        assert "```\n" + raw + "\n```" in md

    def test_footer_in_ci_mode(self):
        data = {"resources": [], "overall_summary": "", "verdict": {}}
        md = render_markdown(data, ci_mode=True)
        assert "bicep-whatif-advisor" in md
        assert "---" in md


@pytest.mark.unit
class TestRenderTable:
    def test_render_table_does_not_crash(self, capsys, mocker):
        """Smoke test: render_table should not raise."""
        mocker.patch("sys.stdout.isatty", return_value=False)
        data = {
            "resources": [
                {
                    "resource_name": "myvm",
                    "resource_type": "Compute/vms",
                    "action": "Create",
                    "summary": "Creates VM",
                }
            ],
            "overall_summary": "1 create.",
        }
        render_table(data, no_color=True)

    def test_render_table_ci_mode(self, capsys, mocker):
        """CI mode table includes risk column."""
        mocker.patch("sys.stdout.isatty", return_value=False)
        data = {
            "resources": [
                {
                    "resource_name": "r",
                    "resource_type": "T",
                    "action": "Delete",
                    "summary": "s",
                    "risk_level": "high",
                }
            ],
            "overall_summary": "",
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": ""},
            },
            "_enabled_buckets": ["drift"],
        }
        render_table(data, ci_mode=True, no_color=True)

    def test_terminal_width_reduction(self, mocker):
        """Table should use 85% of terminal width."""
        import os

        fake_size = os.terminal_size((100, 24))
        mocker.patch("bicep_whatif_advisor.render.shutil.get_terminal_size", return_value=fake_size)
        mocker.patch("sys.stdout.isatty", return_value=False)
        data = {"resources": [], "overall_summary": ""}
        # Should not raise; the width is used internally
        render_table(data, no_color=True)


@pytest.fixture()
def _register_custom_buckets():
    """Register custom buckets for agent detail section tests."""
    from bicep_whatif_advisor.ci.buckets import RISK_BUCKETS, RiskBucket

    RISK_BUCKETS["cost"] = RiskBucket(
        id="cost",
        display_name="Cost Impact",
        description="Custom agent",
        prompt_instructions="Check cost.",
        custom=True,
        display="summary",
        icon="\U0001f4b0",
    )
    RISK_BUCKETS["naming"] = RiskBucket(
        id="naming",
        display_name="Naming Convention",
        description="Custom agent",
        prompt_instructions="Check naming.",
        custom=True,
        display="table",
        icon="\U0001f4db",
    )
    yield
    for key in ("cost", "naming"):
        RISK_BUCKETS.pop(key, None)


@pytest.mark.unit
@pytest.mark.usefixtures("_register_custom_buckets")
class TestAgentDetailSections:
    def test_custom_agent_summary_collapsible(self):
        data = {
            "_enabled_buckets": ["drift", "cost"],
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "cost": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "Minor cost impact.",
                },
            },
        }
        lines = _render_agent_detail_sections(data)
        md = "\n".join(lines)
        assert "\U0001f4b0 Cost Impact Details" in md
        assert "<details>" in md
        assert "Minor cost impact." in md

    def test_custom_agent_table_collapsible(self):
        data = {
            "_enabled_buckets": ["drift", "naming"],
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "naming": {
                    "risk_level": "medium",
                    "concerns": ["bad names"],
                    "reasoning": "Some bad names.",
                    "findings": [
                        {
                            "resource": "storageaccount1",
                            "issue": "No CAF prefix",
                            "recommendation": "Use st<workload><env>",
                        }
                    ],
                },
            },
        }
        lines = _render_agent_detail_sections(data)
        md = "\n".join(lines)
        assert "\U0001f4db Naming Convention Details" in md
        assert "| Resource | Issue | Recommendation |" in md
        assert "storageaccount1" in md
        assert "No CAF prefix" in md

    def test_custom_columns_table_rendering(self):
        """Custom columns should be used as table headers when defined."""
        from bicep_whatif_advisor.ci.buckets import RISK_BUCKETS, RiskBucket

        RISK_BUCKETS["sfi"] = RiskBucket(
            id="sfi",
            display_name="Secure Infrastructure",
            description="Custom agent",
            prompt_instructions="Check SFI.",
            custom=True,
            display="table",
            icon="\U0001f512",
            columns=[
                {"name": "SFI ID and Name", "key": "sfi_id_and_name", "description": "check title"},
                {"name": "Compliance Status", "key": "compliance_status", "description": "status"},
                {"name": "Applicable", "key": "applicable", "description": "true/false"},
            ],
        )
        try:
            data = {
                "_enabled_buckets": ["sfi"],
                "risk_assessment": {
                    "sfi": {
                        "risk_level": "medium",
                        "concerns": ["non-compliant resources"],
                        "reasoning": "Issues found.",
                        "findings": [
                            {
                                "sfi_id_and_name": "[SFI-ID4.2.2] SQL DB",
                                "compliance_status": "non-compliant",
                                "applicable": "true",
                            }
                        ],
                    },
                },
            }
            lines = _render_agent_detail_sections(data)
            md = "\n".join(lines)
            assert "| SFI ID and Name | Compliance Status | Applicable |" in md
            assert "[SFI-ID4.2.2] SQL DB" in md
            assert "non-compliant" in md
            # Default column names should NOT appear
            assert "| Resource | Issue | Recommendation |" not in md
        finally:
            del RISK_BUCKETS["sfi"]

    def test_custom_columns_list_rendering(self):
        """Custom columns should be used in list display mode."""
        from bicep_whatif_advisor.ci.buckets import RISK_BUCKETS, RiskBucket

        RISK_BUCKETS["sfi_list"] = RiskBucket(
            id="sfi_list",
            display_name="SFI List",
            description="Custom agent",
            prompt_instructions="Check SFI.",
            custom=True,
            display="list",
            columns=[
                {"name": "SFI ID and Name", "key": "sfi_id_and_name", "description": "check title"},
                {"name": "Compliance Status", "key": "compliance_status", "description": "status"},
                {"name": "Applicable", "key": "applicable", "description": "true/false"},
            ],
        )
        try:
            data = {
                "_enabled_buckets": ["sfi_list"],
                "risk_assessment": {
                    "sfi_list": {
                        "risk_level": "medium",
                        "concerns": ["issues"],
                        "reasoning": "Issues found.",
                        "findings": [
                            {
                                "sfi_id_and_name": "[SFI-NS2.1] IP Allocations",
                                "compliance_status": "non-compliant",
                                "applicable": "true",
                            }
                        ],
                    },
                },
            }
            lines = _render_agent_detail_sections(data)
            md = "\n".join(lines)
            assert "- **[SFI-NS2.1] IP Allocations**: non-compliant" in md
            assert "  - Applicable: true" in md
        finally:
            del RISK_BUCKETS["sfi_list"]

    def test_custom_agent_list_collapsible(self):
        from bicep_whatif_advisor.ci.buckets import RISK_BUCKETS, RiskBucket

        RISK_BUCKETS["security"] = RiskBucket(
            id="security",
            display_name="Security Review",
            description="Custom agent",
            prompt_instructions="Check security.",
            custom=True,
            display="list",
            icon="\U0001f512",
        )
        try:
            data = {
                "_enabled_buckets": ["security"],
                "risk_assessment": {
                    "security": {
                        "risk_level": "high",
                        "concerns": ["open ports"],
                        "reasoning": "Open ports detected.",
                        "findings": [
                            {
                                "resource": "nsg-web",
                                "issue": "Port 22 open to internet",
                                "recommendation": "Restrict SSH access",
                            }
                        ],
                    },
                },
            }
            lines = _render_agent_detail_sections(data)
            md = "\n".join(lines)
            assert "\U0001f512 Security Review Details" in md
            assert "- **nsg-web**: Port 22 open to internet" in md
            assert "Recommendation: Restrict SSH access" in md
        finally:
            del RISK_BUCKETS["security"]

    def test_builtin_buckets_no_collapsible(self):
        """Built-in buckets (drift, intent) don't get collapsible sections."""
        data = {
            "_enabled_buckets": ["drift"],
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            },
        }
        lines = _render_agent_detail_sections(data)
        assert len(lines) == 0

    def test_table_display_empty_findings_falls_back_to_reasoning(self):
        data = {
            "_enabled_buckets": ["naming"],
            "risk_assessment": {
                "naming": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "All names follow CAF convention.",
                    "findings": [],
                },
            },
        }
        lines = _render_agent_detail_sections(data)
        md = "\n".join(lines)
        assert "All names follow CAF convention." in md
        assert "| Resource |" not in md

    def test_github_no_br_in_agent_sections(self):
        data = {
            "_enabled_buckets": ["cost"],
            "risk_assessment": {
                "cost": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "Low cost.",
                },
            },
        }
        lines = _render_agent_detail_sections(data, platform="github")
        md = "\n".join(lines)
        assert "<br>" not in md

    def test_azuredevops_br_in_agent_sections(self):
        data = {
            "_enabled_buckets": ["cost"],
            "risk_assessment": {
                "cost": {
                    "risk_level": "low",
                    "concerns": [],
                    "reasoning": "Low cost.",
                },
            },
        }
        lines = _render_agent_detail_sections(data, platform="azuredevops")
        md = "\n".join(lines)
        assert "<br>" in md
