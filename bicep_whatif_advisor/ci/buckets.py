"""Central registry for risk assessment buckets."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class RiskBucket:
    """Definition of a risk assessment bucket."""

    id: str  # Internal identifier: "drift", "intent", "operations"
    display_name: str  # User-facing name: "Infrastructure Drift"
    description: str  # Brief description for help text
    prompt_instructions: str  # LLM prompt instructions for this bucket
    optional: bool = False  # True if bucket can be omitted (like intent when no PR metadata)


# Central registry of all risk assessment buckets
RISK_BUCKETS: Dict[str, RiskBucket] = {
    "drift": RiskBucket(
        id="drift",
        display_name="Infrastructure Drift",
        description="Compares What-If output to code diff to detect out-of-band changes",
        prompt_instructions="""
**Infrastructure Drift Risk:**
Compare the What-If output to the code diff. If the What-If shows
changes that aren't in the diff, this indicates infrastructure drift
(manual changes in Azure).

Risk levels for drift:
- high: Critical resources drifting (security, identity, stateful
  resources like databases/storage), broad scope drift (many
  resources), drift that could cause data loss or security issues
- medium: Multiple resources drifting, configuration drift on
  important resources, drift that could affect application behavior
- low: Minor drift (tags, display names, non-critical metadata),
  single resource drift on non-critical resources
""",
        optional=False,
    ),
    "intent": RiskBucket(
        id="intent",
        display_name="PR Intent Alignment",
        description="Compares What-If output to PR title/description to catch unintended changes",
        prompt_instructions="""
**PR Intent Alignment Risk:**
Compare the What-If output to the PR title and description. Identify
changes that seem unrelated to the stated intent.

Risk levels for intent:
- high: Destructive changes (Delete) not mentioned in PR
  title/description, security/authentication changes not mentioned,
  changes that contradict PR intent
- medium: Resource modifications not aligned with PR intent,
  unexpected resource types being modified, scope significantly
  broader than PR description
- low: New resources not mentioned but aligned with overall intent,
  minor scope differences, additional changes that support the
  main intent
""",
        optional=True,  # Only evaluated if PR metadata provided
    ),
    "operations": RiskBucket(
        id="operations",
        display_name="Risky Operations",
        description=(
            "Evaluates inherent risk of Azure operations (deletions, security changes, etc.)"
        ),
        prompt_instructions="""
**Risky Operations Risk:**
Evaluate the inherent risk of the operations being performed,
regardless of drift or intent.

Risk levels for operations:
- high: Deletion of stateful resources (databases, storage accounts,
  key vaults), deletion of identity/RBAC resources, network security
  changes that open broad access, encryption setting modifications,
  SKU downgrades that could cause data loss
- medium: Modifications to existing resources that change behavior
  (policy changes, scaling configuration), new public endpoints,
  firewall rule changes, significant configuration updates
- low: Adding new resources, modifying tags, adding
  diagnostic/monitoring resources, modifying display
  names/descriptions
""",
        optional=False,
    ),
}


def get_enabled_buckets(
    skip_drift: bool = False,
    skip_intent: bool = False,
    skip_operations: bool = False,
    has_pr_metadata: bool = False,
) -> List[str]:
    """Get list of enabled bucket IDs based on skip flags and context.

    Args:
        skip_drift: True to disable drift bucket
        skip_intent: True to disable intent bucket
        skip_operations: True to disable operations bucket
        has_pr_metadata: True if PR title/description available (controls intent bucket)

    Returns:
        List of bucket IDs that should be evaluated (e.g., ["drift", "operations"])
    """
    enabled = []

    if not skip_drift:
        enabled.append("drift")

    # Intent bucket only enabled if PR metadata exists AND not skipped
    if not skip_intent and has_pr_metadata:
        enabled.append("intent")

    if not skip_operations:
        enabled.append("operations")

    return enabled


def get_bucket(bucket_id: str) -> Optional[RiskBucket]:
    """Get bucket definition by ID."""
    return RISK_BUCKETS.get(bucket_id)
