"""Tests for bicep_whatif_advisor.ci.risk_buckets module."""

import pytest

from bicep_whatif_advisor.ci.risk_buckets import (
    _exceeds_threshold,
    _validate_risk_level,
    evaluate_risk_buckets,
)


@pytest.mark.unit
class TestValidateRiskLevel:
    def test_valid_low(self):
        assert _validate_risk_level("low") == "low"

    def test_valid_medium(self):
        assert _validate_risk_level("medium") == "medium"

    def test_valid_high(self):
        assert _validate_risk_level("high") == "high"

    def test_mixed_case(self):
        assert _validate_risk_level("HIGH") == "high"

    def test_invalid_defaults_to_low(self):
        assert _validate_risk_level("extreme") == "low"


# Parameterized test for all 9 combinations of _exceeds_threshold
@pytest.mark.unit
@pytest.mark.parametrize(
    "risk_level, threshold, expected",
    [
        ("low", "low", True),
        ("low", "medium", False),
        ("low", "high", False),
        ("medium", "low", True),
        ("medium", "medium", True),
        ("medium", "high", False),
        ("high", "low", True),
        ("high", "medium", True),
        ("high", "high", True),
    ],
)
def test_exceeds_threshold(risk_level, threshold, expected):
    assert _exceeds_threshold(risk_level, threshold) is expected


@pytest.mark.unit
class TestEvaluateRiskBuckets:
    def test_safe_all_low(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "operations": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(data, ["drift", "operations"], "high", "high")
        assert is_safe is True
        assert failed == []

    def test_unsafe_operations_high(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "operations": {"risk_level": "high", "concerns": ["db delete"], "reasoning": "bad"},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data,
            ["drift", "operations"],
            "high",
            "high",
            custom_thresholds={"operations": "high"},
        )
        assert is_safe is False
        assert "operations" in failed

    def test_unsafe_drift_medium_with_medium_threshold(self):
        data = {
            "risk_assessment": {
                "drift": {
                    "risk_level": "medium",
                    "concerns": ["drift found"],
                    "reasoning": "drift",
                },
                "operations": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(data, ["drift", "operations"], "medium", "high")
        assert is_safe is False
        assert "drift" in failed

    def test_multiple_failed_buckets(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "high", "concerns": [], "reasoning": ""},
                "operations": {"risk_level": "high", "concerns": [], "reasoning": ""},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data,
            ["drift", "operations"],
            "high",
            "high",
            custom_thresholds={"operations": "high"},
        )
        assert is_safe is False
        assert set(failed) == {"drift", "operations"}

    def test_no_risk_assessment_defaults_safe(self):
        data = {}
        is_safe, failed, ra = evaluate_risk_buckets(data, ["drift", "operations"], "high", "high")
        assert is_safe is True
        assert failed == []
        # Default assessment should contain enabled buckets
        assert "drift" in ra
        assert "operations" in ra

    def test_missing_bucket_in_assessment_skipped(self):
        data = {
            "risk_assessment": {
                "operations": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(data, ["drift", "operations"], "high", "high")
        assert is_safe is True

    def test_with_intent_bucket(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": ""},
                "intent": {"risk_level": "high", "concerns": ["unintended"], "reasoning": ""},
                "operations": {"risk_level": "low", "concerns": [], "reasoning": ""},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data, ["drift", "intent", "operations"], "high", "high"
        )
        assert is_safe is False
        assert "intent" in failed

    def test_invalid_risk_level_defaults_to_low(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "EXTREME", "concerns": [], "reasoning": ""},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(data, ["drift"], "high", "high")
        assert is_safe is True  # Invalid -> "low" -> below "high" threshold

    def test_custom_threshold_overrides_default(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
                "compliance": {
                    "risk_level": "medium",
                    "concerns": ["issue"],
                    "reasoning": "medium risk",
                },
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data,
            ["drift", "compliance"],
            "high",
            "high",
            custom_thresholds={"compliance": "medium"},
        )
        assert is_safe is False
        assert "compliance" in failed

    def test_custom_threshold_pass(self):
        data = {
            "risk_assessment": {
                "compliance": {
                    "risk_level": "medium",
                    "concerns": [],
                    "reasoning": "ok",
                },
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data,
            ["compliance"],
            "high",
            "high",
            custom_thresholds={"compliance": "high"},
        )
        assert is_safe is True
        assert failed == []

    def test_custom_bucket_falls_back_to_default_high(self):
        """Custom bucket without explicit threshold defaults to 'high'."""
        data = {
            "risk_assessment": {
                "custom_bucket": {
                    "risk_level": "medium",
                    "concerns": [],
                    "reasoning": "ok",
                },
            }
        }
        # No custom_thresholds provided, bucket not in built-in map
        # Falls back to "high" default
        is_safe, failed, ra = evaluate_risk_buckets(data, ["custom_bucket"], "high", "high")
        assert is_safe is True
        assert failed == []

    def test_custom_thresholds_none_is_noop(self):
        data = {
            "risk_assessment": {
                "drift": {"risk_level": "low", "concerns": [], "reasoning": "ok"},
            }
        }
        is_safe, failed, ra = evaluate_risk_buckets(
            data, ["drift"], "high", "high", custom_thresholds=None
        )
        assert is_safe is True
