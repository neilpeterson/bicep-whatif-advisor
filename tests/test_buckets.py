"""Tests for bicep_whatif_advisor.ci.buckets module."""

import pytest

from bicep_whatif_advisor.ci.buckets import (
    RISK_BUCKETS,
    RiskBucket,
    get_bucket,
    get_enabled_buckets,
)


@pytest.mark.unit
class TestRiskBucketsRegistry:

    def test_registry_has_three_buckets(self):
        assert len(RISK_BUCKETS) == 3

    def test_registry_keys(self):
        assert set(RISK_BUCKETS.keys()) == {"drift", "intent", "operations"}

    def test_all_buckets_are_risk_bucket_instances(self):
        for bucket in RISK_BUCKETS.values():
            assert isinstance(bucket, RiskBucket)

    def test_intent_bucket_is_optional(self):
        assert RISK_BUCKETS["intent"].optional is True

    def test_drift_and_operations_not_optional(self):
        assert RISK_BUCKETS["drift"].optional is False
        assert RISK_BUCKETS["operations"].optional is False

    def test_get_bucket_existing(self):
        bucket = get_bucket("drift")
        assert bucket is not None
        assert bucket.id == "drift"

    def test_get_bucket_nonexistent(self):
        assert get_bucket("nonexistent") is None


@pytest.mark.unit
class TestGetEnabledBuckets:

    def test_default_no_pr_metadata(self):
        """Without PR metadata, intent is excluded by default."""
        result = get_enabled_buckets()
        assert result == ["drift", "operations"]

    def test_with_pr_metadata(self):
        """With PR metadata, all three buckets enabled."""
        result = get_enabled_buckets(has_pr_metadata=True)
        assert result == ["drift", "intent", "operations"]

    def test_skip_drift(self):
        result = get_enabled_buckets(skip_drift=True)
        assert "drift" not in result
        assert "operations" in result

    def test_skip_operations(self):
        result = get_enabled_buckets(skip_operations=True)
        assert "drift" in result
        assert "operations" not in result

    def test_skip_intent_with_pr_metadata(self):
        result = get_enabled_buckets(skip_intent=True, has_pr_metadata=True)
        assert "intent" not in result
        assert "drift" in result

    def test_skip_all_returns_empty(self):
        result = get_enabled_buckets(
            skip_drift=True, skip_intent=True, skip_operations=True
        )
        assert result == []

    def test_intent_not_enabled_without_pr_metadata_even_if_not_skipped(self):
        result = get_enabled_buckets(skip_intent=False, has_pr_metadata=False)
        assert "intent" not in result
