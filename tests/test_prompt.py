"""Tests for bicep_whatif_advisor.prompt module."""

import pytest

from bicep_whatif_advisor.prompt import build_system_prompt, build_user_prompt


@pytest.mark.unit
class TestBuildSystemPrompt:
    def test_standard_mode_returns_string(self):
        result = build_system_prompt()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_standard_mode_contains_json_schema(self):
        result = build_system_prompt()
        assert "resource_name" in result
        assert "resource_type" in result
        assert "action" in result
        assert "confidence_level" in result

    def test_standard_mode_verbose_includes_changes(self):
        result = build_system_prompt(verbose=True)
        assert "changes" in result.lower()

    def test_standard_mode_non_verbose_no_changes_field(self):
        result = build_system_prompt(verbose=False)
        assert 'also include a "changes" field' not in result

    def test_ci_mode_includes_risk_assessment(self):
        result = build_system_prompt(ci_mode=True)
        assert "risk_assessment" in result
        assert "verdict" in result

    def test_ci_mode_includes_drift_and_operations(self):
        result = build_system_prompt(ci_mode=True)
        assert "Infrastructure Drift" in result
        assert "Risky Operations" in result

    def test_ci_mode_no_intent_without_pr(self):
        result = build_system_prompt(ci_mode=True, pr_title=None)
        assert "PR Intent Alignment" not in result

    def test_ci_mode_with_intent_when_pr_title(self):
        result = build_system_prompt(ci_mode=True, pr_title="Add storage")
        assert "PR Intent Alignment" in result
        assert "intent" in result

    def test_ci_mode_with_intent_when_pr_description(self):
        result = build_system_prompt(ci_mode=True, pr_description="Some desc")
        assert "PR Intent Alignment" in result

    def test_ci_mode_custom_enabled_buckets(self):
        result = build_system_prompt(ci_mode=True, enabled_buckets=["operations"])
        assert "Risky Operations" in result
        assert "Infrastructure Drift" not in result

    def test_ci_mode_schema_has_risk_level(self):
        result = build_system_prompt(ci_mode=True)
        assert "risk_level" in result
        assert "risk_reason" in result

    def test_confidence_section_always_present(self):
        for mode in [False, True]:
            result = build_system_prompt(ci_mode=mode)
            assert "Confidence Assessment" in result

    def test_ci_mode_dynamic_bucket_count(self):
        result = build_system_prompt(ci_mode=True, enabled_buckets=["drift", "operations"])
        assert "2 independent risk buckets" in result

    def test_ci_mode_single_bucket_wording(self):
        result = build_system_prompt(ci_mode=True, enabled_buckets=["operations"])
        assert "1 independent risk bucket:" in result


@pytest.mark.unit
class TestBuildUserPrompt:
    def test_standard_mode_wraps_whatif(self):
        result = build_user_prompt(whatif_content="Resource changes: 1")
        assert "<whatif_output>" in result
        assert "Resource changes: 1" in result
        assert "Analyze the following Azure What-If output" in result

    def test_ci_mode_includes_diff(self):
        result = build_user_prompt(whatif_content="changes", diff_content="diff --git a/main.bicep")
        assert "<code_diff>" in result
        assert "diff --git" in result

    def test_ci_mode_includes_bicep(self):
        result = build_user_prompt(
            whatif_content="changes",
            diff_content="diff",
            bicep_content="param location string",
        )
        assert "<bicep_source>" in result
        assert "param location string" in result

    def test_ci_mode_no_bicep_when_none(self):
        result = build_user_prompt(
            whatif_content="changes", diff_content="diff", bicep_content=None
        )
        assert "<bicep_source>" not in result

    def test_pr_metadata_in_prompt(self):
        result = build_user_prompt(
            whatif_content="changes",
            diff_content="diff",
            pr_title="Add storage",
            pr_description="Adding new storage account",
        )
        assert "<pull_request_intent>" in result
        assert "Add storage" in result
        assert "Adding new storage account" in result

    def test_pr_title_only(self):
        result = build_user_prompt(
            whatif_content="changes",
            diff_content="diff",
            pr_title="Add storage",
        )
        assert "Add storage" in result
        assert "Not provided" in result  # description defaults

    def test_standard_mode_no_pr_metadata(self):
        result = build_user_prompt(whatif_content="changes")
        assert "<pull_request_intent>" not in result
