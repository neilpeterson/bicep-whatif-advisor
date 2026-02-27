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
    def test_registry_has_two_builtin_buckets(self):
        assert len(RISK_BUCKETS) == 2

    def test_registry_keys(self):
        assert set(RISK_BUCKETS.keys()) == {"drift", "intent"}

    def test_all_buckets_are_risk_bucket_instances(self):
        for bucket in RISK_BUCKETS.values():
            assert isinstance(bucket, RiskBucket)

    def test_intent_bucket_is_optional(self):
        assert RISK_BUCKETS["intent"].optional is True

    def test_drift_not_optional(self):
        assert RISK_BUCKETS["drift"].optional is False

    def test_get_bucket_existing(self):
        bucket = get_bucket("drift")
        assert bucket is not None
        assert bucket.id == "drift"

    def test_get_bucket_nonexistent(self):
        assert get_bucket("nonexistent") is None


@pytest.mark.unit
class TestGetEnabledBuckets:
    def test_default_no_pr_metadata(self):
        """Without PR metadata or agents, only drift is enabled."""
        result = get_enabled_buckets()
        assert result == ["drift"]

    def test_with_operations_agent(self):
        """With operations as a bundled agent, drift + operations are enabled."""
        result = get_enabled_buckets(custom_agent_ids=["operations"])
        assert result == ["drift", "operations"]

    def test_with_pr_metadata_and_operations(self):
        """With PR metadata and operations agent, all three buckets enabled."""
        result = get_enabled_buckets(has_pr_metadata=True, custom_agent_ids=["operations"])
        assert result == ["drift", "intent", "operations"]

    def test_skip_drift(self):
        result = get_enabled_buckets(skip_drift=True, custom_agent_ids=["operations"])
        assert "drift" not in result
        assert "operations" in result

    def test_skip_operations_via_skip_agents(self):
        """Operations is skipped via --skip-agent operations."""
        result = get_enabled_buckets(custom_agent_ids=["operations"], skip_agents=["operations"])
        assert "drift" in result
        assert "operations" not in result

    def test_skip_intent_with_pr_metadata(self):
        result = get_enabled_buckets(skip_intent=True, has_pr_metadata=True)
        assert "intent" not in result
        assert "drift" in result

    def test_skip_all_returns_empty(self):
        result = get_enabled_buckets(
            skip_drift=True,
            skip_intent=True,
            custom_agent_ids=["operations"],
            skip_agents=["operations"],
        )
        assert result == []

    def test_intent_not_enabled_without_pr_metadata_even_if_not_skipped(self):
        result = get_enabled_buckets(skip_intent=False, has_pr_metadata=False)
        assert "intent" not in result

    def test_custom_agents_appended(self):
        result = get_enabled_buckets(custom_agent_ids=["operations", "compliance", "cost"])
        assert result == ["drift", "operations", "compliance", "cost"]

    def test_custom_agents_with_skip(self):
        result = get_enabled_buckets(
            custom_agent_ids=["compliance", "cost"],
            skip_agents=["cost"],
        )
        assert "compliance" in result
        assert "cost" not in result

    def test_custom_agents_all_skipped(self):
        result = get_enabled_buckets(
            custom_agent_ids=["compliance"],
            skip_agents=["compliance"],
        )
        assert result == ["drift"]

    def test_custom_agents_none_is_noop(self):
        result = get_enabled_buckets(custom_agent_ids=None)
        assert result == ["drift"]

    def test_custom_agents_empty_list(self):
        result = get_enabled_buckets(custom_agent_ids=[])
        assert result == ["drift"]


@pytest.mark.unit
class TestRiskBucketFields:
    def test_default_threshold_defaults_to_high(self):
        bucket = RiskBucket(
            id="test",
            display_name="Test",
            description="",
            prompt_instructions="",
        )
        assert bucket.default_threshold == "high"

    def test_custom_defaults_to_false(self):
        bucket = RiskBucket(
            id="test",
            display_name="Test",
            description="",
            prompt_instructions="",
        )
        assert bucket.custom is False

    def test_builtin_buckets_not_custom(self):
        for bucket_id in ("drift", "intent"):
            assert RISK_BUCKETS[bucket_id].custom is False
