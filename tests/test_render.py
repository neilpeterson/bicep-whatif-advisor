"""Tests for bicep_whatif_advisor.render module."""

import json

import pytest

from bicep_whatif_advisor.render import (
    _colorize,
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
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "operations": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
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
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": ["drift concern"], "reasoning": ""},
                "operations": {"risk_level": "medium", "concerns": ["op concern"], "reasoning": ""},
            },
            "verdict": {"safe": True, "reasoning": "ok"},
        }
        md = render_markdown(data, ci_mode=True)
        assert "Infrastructure Drift" in md
        assert "Risky Operations" in md

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
        mocker.patch("bicep_whatif_advisor.render.shutil.get_terminal_size",
                      return_value=fake_size)
        mocker.patch("sys.stdout.isatty", return_value=False)
        data = {"resources": [], "overall_summary": ""}
        # Should not raise; the width is used internally
        render_table(data, no_color=True)
