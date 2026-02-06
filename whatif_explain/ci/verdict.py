"""Verdict evaluation for CI mode deployment gates."""


# Risk level ordering (higher index = higher risk)
RISK_LEVELS = ["none", "low", "medium", "high", "critical"]


def evaluate_verdict(data: dict, threshold: str) -> tuple:
    """Evaluate CI mode verdict and determine if deployment is safe.

    Args:
        data: Parsed LLM response with verdict
        threshold: Risk threshold (low, medium, high, critical)

    Returns:
        Tuple of (is_safe: bool, verdict: dict)
    """
    verdict = data.get("verdict", {})

    if not verdict:
        # No verdict provided - assume safe but warn
        return True, {
            "safe": True,
            "risk_level": "none",
            "reasoning": "No verdict provided by LLM",
            "concerns": [],
            "recommendations": []
        }

    # Get verdict fields
    safe = verdict.get("safe", True)
    risk_level = verdict.get("risk_level", "none").lower()

    # Validate risk level
    if risk_level not in RISK_LEVELS:
        risk_level = "none"

    # Compare risk level against threshold
    risk_index = RISK_LEVELS.index(risk_level)
    threshold_index = RISK_LEVELS.index(threshold.lower())

    # Deployment is safe if:
    # 1. LLM says it's safe, AND
    # 2. Risk level is below threshold
    is_safe = safe and (risk_index < threshold_index)

    return is_safe, verdict
