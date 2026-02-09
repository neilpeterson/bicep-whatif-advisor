"""Risk bucket evaluation for CI mode deployment gates."""

from typing import Tuple, List, Dict, Any

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
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Evaluate risk buckets and determine if deployment is safe.

    Args:
        data: Parsed LLM response with risk_assessment
        drift_threshold: Risk threshold for infrastructure drift bucket
        intent_threshold: Risk threshold for PR intent alignment bucket
        operations_threshold: Risk threshold for risky operations bucket

    Returns:
        Tuple of (is_safe: bool, failed_buckets: list, risk_assessment: dict)
    """
    risk_assessment = data.get("risk_assessment", {})

    if not risk_assessment:
        # No risk assessment provided - assume safe but warn
        return True, [], {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"}
        }

    # Extract bucket assessments
    drift_bucket = risk_assessment.get("drift", {})
    intent_bucket = risk_assessment.get("intent")  # May be None if not evaluated
    operations_bucket = risk_assessment.get("operations", {})

    # Validate and normalize risk levels
    drift_risk = _validate_risk_level(drift_bucket.get("risk_level", "low"))
    operations_risk = _validate_risk_level(operations_bucket.get("risk_level", "low"))

    # Evaluate each bucket against its threshold
    failed_buckets = []

    # Drift bucket
    if _exceeds_threshold(drift_risk, drift_threshold):
        failed_buckets.append("drift")

    # Intent bucket (only if evaluated)
    if intent_bucket is not None:
        intent_risk = _validate_risk_level(intent_bucket.get("risk_level", "low"))
        if _exceeds_threshold(intent_risk, intent_threshold):
            failed_buckets.append("intent")

    # Operations bucket
    if _exceeds_threshold(operations_risk, operations_threshold):
        failed_buckets.append("operations")

    # Overall safety: all buckets must pass
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
