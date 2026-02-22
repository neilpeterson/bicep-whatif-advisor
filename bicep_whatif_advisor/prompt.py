"""Prompt construction for LLM analysis of What-If output."""


def build_system_prompt(
    verbose: bool = False,
    ci_mode: bool = False,
    pr_title: str = None,
    pr_description: str = None,
    enabled_buckets: list = None,
) -> str:
    """Build the system prompt for the LLM.

    Args:
        verbose: Include property-level change details for modified resources
        ci_mode: Enable CI mode with risk assessment and verdict
        pr_title: Pull request title for intent analysis (CI mode only)
        pr_description: Pull request description for intent analysis (CI mode only)
        enabled_buckets: List of bucket IDs to include (e.g., ["drift", "operations"])
                        If None, defaults to all buckets

    Returns:
        System prompt string
    """
    if ci_mode:
        return _build_ci_system_prompt(pr_title, pr_description, enabled_buckets)
    else:
        return _build_standard_system_prompt(verbose)


def _build_standard_system_prompt(verbose: bool) -> str:
    """Build system prompt for standard (non-CI) mode."""
    base_schema = """{
  "resources": [
    {
      "resource_name": "string — the short resource name",
      "resource_type": "string — the Azure resource type, abbreviated",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — plain English explanation of this change",
      "confidence_level": "low|medium|high — confidence this is a real change vs What-If noise",
      "confidence_reason": "string — brief explanation of confidence assessment"
    }
  ],
  "overall_summary": "string — brief summary with action counts and intent"
}"""

    verbose_addition = """
For resources with action "Modify", also include a "changes" field:
an array of strings describing each property-level change.
"""

    confidence_instructions = """

## Confidence Assessment

For each resource, assess confidence that the change is REAL vs Azure What-If noise:

**HIGH confidence (real changes):**
- Resource creation, deletion, or state changes
- Configuration modifications with clear intent
- Security, networking, or compute changes

**MEDIUM confidence (potentially real but uncertain):**
- Retention policies or analytics settings
- Subnet references changing from hardcoded to dynamic
- Configuration changes that might be platform-managed

**LOW confidence (likely What-If noise):**
- Metadata-only changes (etag, id, provisioningState, type)
- logAnalyticsDestinationType property changes
- IPv6 flags (disableIpv6, enableIPv6Addressing)
- Computed properties (resourceGuid)
- Read-only or system-managed properties

Use your judgment - these are guidelines, not rigid patterns."""

    prompt = f"""You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{base_schema}"""

    if verbose:
        prompt += "\n" + verbose_addition

    prompt += confidence_instructions

    return prompt


def _build_ci_system_prompt(
    pr_title: str = None, pr_description: str = None, enabled_buckets: list = None
) -> str:
    """Build system prompt for CI mode with risk assessment.

    Args:
        pr_title: Optional PR title
        pr_description: Optional PR description
        enabled_buckets: List of bucket IDs to include (e.g., ["drift", "operations"])
                        If None, defaults to all buckets

    Returns:
        System prompt string with dynamic bucket configuration
    """
    from .ci.buckets import RISK_BUCKETS, get_enabled_buckets

    # Default to all buckets if not specified
    if enabled_buckets is None:
        enabled_buckets = get_enabled_buckets(has_pr_metadata=bool(pr_title or pr_description))

    base_prompt = """You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes"""

    # Add PR intent context if available and intent bucket is enabled
    if (pr_title or pr_description) and "intent" in enabled_buckets:
        base_prompt += (
            "\n3. The pull request title and description stating the "
            "INTENDED purpose of this change"
        )

    # Dynamic bucket count
    bucket_count = len(enabled_buckets)
    bucket_word = "bucket" if bucket_count == 1 else "buckets"
    base_prompt += (
        f"\n\nEvaluate the deployment for safety and correctness across "
        f"{bucket_count} independent risk {bucket_word}:"
    )

    # Build risk_assessment schema dynamically based on enabled buckets
    risk_buckets_schema = []
    for bucket_id in enabled_buckets:
        bucket = RISK_BUCKETS[bucket_id]
        risk_buckets_schema.append(f'''    "{bucket_id}": {{
      "risk_level": "low|medium|high",
      "concerns": ["array of specific concerns"],
      "concern_summary": "1-2 sentence summary of all concerns for display in a table cell, or 'None' if no concerns",
      "reasoning": "explanation of risk assessment"
    }}''')

    risk_assessment_block = ",\n".join(risk_buckets_schema)
    risk_assessment_schema = f""""risk_assessment": {{
{risk_assessment_block}
  }}"""

    # Build instructions for each enabled bucket
    bucket_instructions_list = []
    for i, bucket_id in enumerate(enabled_buckets, 1):
        bucket = RISK_BUCKETS[bucket_id]
        bucket_instructions_list.append(f"""
## Risk Bucket {i}: {bucket.display_name}
{bucket.prompt_instructions}""")

    bucket_instructions = "\n".join(bucket_instructions_list)

    # Build verdict schema with dynamic highest_risk_bucket options
    bucket_options = "|".join(enabled_buckets)
    verdict_schema = f'''"verdict": {{
    "safe": true/false,
    "highest_risk_bucket": "{bucket_options}|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "string — 2-3 sentence explanation considering all buckets"
  }}'''

    confidence_instructions = """

## Confidence Assessment

For each resource, assess confidence that the change is REAL vs Azure What-If noise:

**HIGH confidence (real changes):**
- Resource creation, deletion, or state changes
- Configuration modifications with clear intent
- Security, networking, or compute changes

**MEDIUM confidence (potentially real but uncertain):**
- Retention policies or analytics settings
- Subnet references changing from hardcoded to dynamic
- Configuration changes that might be platform-managed

**LOW confidence (likely What-If noise):**
- Metadata-only changes (etag, id, provisioningState, type)
- logAnalyticsDestinationType property changes
- IPv6 flags (disableIpv6, enableIPv6Addressing)
- Computed properties (resourceGuid)
- Read-only or system-managed properties

Use your judgment - these are guidelines, not rigid patterns."""

    return (
        base_prompt
        + bucket_instructions
        + confidence_instructions
        + f"""

Respond with ONLY valid JSON matching this schema:

{{
  "resources": [
    {{
      "resource_name": "string",
      "resource_type": "string",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — what this change does",
      "risk_level": "low|medium|high",
      "risk_reason": "string or null — why this is risky, if applicable",
      "confidence_level": "low|medium|high — confidence this is a real change vs What-If noise",
      "confidence_reason": "string — brief explanation of confidence assessment"
    }}
  ],
  "overall_summary": "string",
  {risk_assessment_schema},
  {verdict_schema}
}}"""
    )


def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None,
) -> str:
    """Build the user prompt with What-If output and optional context.

    Args:
        whatif_content: Azure What-If output text
        diff_content: Git diff content (CI mode only)
        bicep_content: Bicep source files content (CI mode only)
        pr_title: Pull request title (CI mode only)
        pr_description: Pull request description (CI mode only)

    Returns:
        User prompt string
    """
    if diff_content is not None:
        # CI mode with diff
        prompt = """Review this Azure deployment for safety."""

        # Add PR intent context if available
        if pr_title or pr_description:
            prompt += f"""

<pull_request_intent>
Title: {pr_title or "Not provided"}
Description: {pr_description or "Not provided"}
</pull_request_intent>"""

        prompt += f"""

<whatif_output>
{whatif_content}
</whatif_output>

<code_diff>
{diff_content}
</code_diff>"""

        if bicep_content:
            prompt += f"""

<bicep_source>
{bicep_content}
</bicep_source>"""

        return prompt
    else:
        # Standard mode
        return f"""Analyze the following Azure What-If output:

<whatif_output>
{whatif_content}
</whatif_output>"""
