"""Central registry for risk assessment buckets."""

from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class RiskBucket:
    """Definition of a risk assessment bucket."""

    id: str  # Internal identifier: "drift", "intent", or custom agent IDs
    display_name: str  # User-facing name: "Infrastructure Drift"
    description: str  # Brief description for help text
    prompt_instructions: str  # LLM prompt instructions for this bucket
    optional: bool = False  # True if bucket can be omitted (like intent when no PR metadata)
    default_threshold: str = "high"  # Default threshold for custom agents
    custom: bool = False  # True for custom agents loaded from markdown files
    display: str = "summary"  # "summary", "table", or "list" — collapsible detail mode
    icon: str = ""  # Emoji for collapsible header (e.g., "💰")
    columns: list = None  # Custom column definitions for table/list display


# Central registry of all risk assessment buckets
RISK_BUCKETS: Dict[str, RiskBucket] = {
    "drift": RiskBucket(
        id="drift",
        display_name="Infrastructure Drift",
        description="Compares What-If output to code diff to detect out-of-band changes",
        prompt_instructions="""
**Infrastructure Drift Risk:**
Detect infrastructure drift — cases where live Azure resources have
been manually changed outside of the Bicep/ARM deployment process.

IMPORTANT distinction between the inputs you receive:
- <code_diff> = ONLY the lines changed in THIS pull request
- <bicep_source> = the FULL Bicep/ARM codebase (for context only)
- For drift detection, you MUST use <code_diff> to determine what
  changed in this PR. Do NOT use <bicep_source> for drift analysis.
  A resource being defined in <bicep_source> does NOT mean it was
  changed in this PR.

How to detect drift:
1. Look at each Modify (~) action in the What-If output.
2. Check whether the <code_diff> changes that specific resource or
   property. The resource name or its properties must appear as added
   or modified lines in the diff.
3. If the <code_diff> does NOT change that resource but What-If shows
   it being modified, this is DRIFT. It means someone changed the live
   resource manually (e.g., in the Azure portal) and the deployment
   will revert those manual changes back to what the code defines.
4. Pay special attention to property reversions — when What-If shows
   a value changing (e.g., "Enabled" => "Disabled") on a resource that
   the <code_diff> did not touch, the live value was manually changed
   and the deployment will overwrite it.

Key principle: If a resource appears as Modify in What-If but was NOT
modified in the <code_diff>, the Modify is caused by out-of-band changes
to the live resource. This IS drift, even though the deployment will
"fix" it — operators need to know manual changes will be reverted.

Risk levels for drift:
- high: Critical resources drifting (security, identity, network access,
  stateful resources like databases/storage), broad scope drift (many
  resources), drift that could cause data loss or security exposure,
  security controls being reverted (e.g., publicNetworkAccess, firewall
  rules, RBAC settings)
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
}


def get_enabled_buckets(
    skip_drift: bool = False,
    skip_intent: bool = False,
    has_pr_metadata: bool = False,
    custom_agent_ids: List[str] = None,
    skip_agents: List[str] = None,
) -> List[str]:
    """Get list of enabled bucket IDs based on skip flags and context.

    Args:
        skip_drift: True to disable drift bucket
        skip_intent: True to disable intent bucket
        has_pr_metadata: True if PR title/description available (controls intent bucket)
        custom_agent_ids: List of registered custom agent IDs to include
        skip_agents: List of custom agent IDs to skip (e.g., ["compliance"])

    Returns:
        List of bucket IDs that should be evaluated (e.g., ["drift", "compliance"])
    """
    enabled = []

    if not skip_drift:
        enabled.append("drift")

    # Intent bucket only enabled if PR metadata exists AND not skipped
    if not skip_intent and has_pr_metadata:
        enabled.append("intent")

    # Append custom/bundled agents (respecting skip list)
    skip_set = set(skip_agents or [])
    if custom_agent_ids:
        for agent_id in custom_agent_ids:
            if agent_id not in skip_set:
                enabled.append(agent_id)

    return enabled


def get_bucket(bucket_id: str) -> Optional[RiskBucket]:
    """Get bucket definition by ID."""
    return RISK_BUCKETS.get(bucket_id)
