"""Risk bucket evaluation for CI mode deployment gates."""

from typing import Any, Dict, List, Tuple

# Import risk levels from verdict module
from .verdict import RISK_LEVELS


def _validate_risk_level(risk_level: str) -> str:
    """Validate and normalize risk level.

    Args:
        risk_level: Risk level string to validate

    Returns:
        Validated risk level, defaults to "low" if invalid
    """
    risk = risk_level.lower()
    return risk if risk in RISK_LEVELS else "low"


def evaluate_risk_buckets(
    data: dict,
    enabled_buckets: List[str],
    drift_threshold: str = "high",
    intent_threshold: str = "high",
    operations_threshold: str = "high",
    custom_thresholds: Dict[str, str] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Evaluate enabled risk buckets and determine if deployment is safe.

    NOTE: This function expects pre-filtered data containing only medium/high-confidence
    resources. Low-confidence resources (likely Azure What-If noise) should be filtered
    out before calling this function to avoid noise contaminating risk assessment.

    Args:
        data: Parsed LLM response with risk_assessment
              (should contain only high-confidence resources)
        enabled_buckets: List of bucket IDs to evaluate (e.g., ["drift", "operations"])
        drift_threshold: Risk threshold for drift bucket (only used if enabled)
        intent_threshold: Risk threshold for intent bucket (only used if enabled)
        operations_threshold: Risk threshold for operations bucket (only used if enabled)
        custom_thresholds: Dict mapping custom agent_id to threshold string.
                          Falls back to bucket's default_threshold if not specified.

    Returns:
        Tuple of (is_safe: bool, failed_buckets: list, risk_assessment: dict)
    """
    risk_assessment = data.get("risk_assessment", {})

    if not risk_assessment:
        # No risk assessment provided - build default low-risk assessment for enabled buckets
        default_assessment = {}
        for bucket_id in enabled_buckets:
            default_assessment[bucket_id] = {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "No risk assessment provided",
            }
        return True, [], default_assessment

    # Threshold map for built-in buckets
    thresholds = {
        "drift": drift_threshold,
        "intent": intent_threshold,
    }

    # Map operations_threshold for backwards compat (operations is now a bundled agent)
    if operations_threshold:
        thresholds["operations"] = operations_threshold

    # Merge custom thresholds
    if custom_thresholds:
        thresholds.update(custom_thresholds)

    # Evaluate each enabled bucket
    failed_buckets = []

    for bucket_id in enabled_buckets:
        bucket_data = risk_assessment.get(bucket_id)

        # Skip if bucket not in LLM response (shouldn't happen but fail-safe)
        if bucket_data is None:
            continue

        # Get and validate risk level
        risk_level = _validate_risk_level(bucket_data.get("risk_level", "low"))

        # Check against threshold: explicit > bucket default > "high"
        threshold = thresholds.get(bucket_id)
        if threshold is None:
            from .buckets import get_bucket

            bucket = get_bucket(bucket_id)
            threshold = bucket.default_threshold if bucket else "high"

        if _exceeds_threshold(risk_level, threshold):
            failed_buckets.append(bucket_id)

    # Overall safety: all enabled buckets must pass
    is_safe = len(failed_buckets) == 0

    return is_safe, failed_buckets, risk_assessment


def _exceeds_threshold(risk_level: str, threshold: str) -> bool:
    """Check if a risk level exceeds the threshold.

    Args:
        risk_level: Current risk level (low, medium, high)
        threshold: Threshold level (low, medium, high)

    Returns:
        True if risk_level >= threshold
    """
    risk_index = RISK_LEVELS.index(risk_level.lower())
    threshold_index = RISK_LEVELS.index(threshold.lower())
    return risk_index >= threshold_index
