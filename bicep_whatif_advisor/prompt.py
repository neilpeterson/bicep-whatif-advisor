"""Prompt construction for LLM analysis of What-If output."""


def build_system_prompt(
    verbose: bool = False,
    ci_mode: bool = False,
    pr_title: str = None,
    pr_description: str = None
) -> str:
    """Build the system prompt for the LLM.

    Args:
        verbose: Include property-level change details for modified resources
        ci_mode: Enable CI mode with risk assessment and verdict
        pr_title: Pull request title for intent analysis (CI mode only)
        pr_description: Pull request description for intent analysis (CI mode only)

    Returns:
        System prompt string
    """
    if ci_mode:
        return _build_ci_system_prompt(pr_title, pr_description)
    else:
        return _build_standard_system_prompt(verbose)


def _build_standard_system_prompt(verbose: bool) -> str:
    """Build system prompt for standard (non-CI) mode."""
    base_schema = '''{
  "resources": [
    {
      "resource_name": "string — the short resource name",
      "resource_type": "string — the Azure resource type, abbreviated",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — plain English explanation of this change"
    }
  ],
  "overall_summary": "string — brief summary with action counts and intent"
}'''

    verbose_addition = '''
For resources with action "Modify", also include a "changes" field:
an array of strings describing each property-level change.
'''

    prompt = f'''You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{base_schema}'''

    if verbose:
        prompt += "\n" + verbose_addition

    return prompt


def _build_ci_system_prompt(pr_title: str = None, pr_description: str = None) -> str:
    """Build system prompt for CI mode with risk assessment."""
    base_prompt = '''You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes'''

    # Add PR intent context if available
    if pr_title or pr_description:
        base_prompt += (
            '\n3. The pull request title and description stating the '
            'INTENDED purpose of this change'
        )

    base_prompt += (
        '\n\nEvaluate the deployment for safety and correctness across '
        'three independent risk buckets:'
    )

    # Build schema based on whether intent bucket is included
    if pr_title or pr_description:
        risk_assessment_schema = '''"risk_assessment": {
    "drift": {
      "risk_level": "low|medium|high",
      "concerns": ["string — list of specific drift concerns"],
      "reasoning": "string — explanation of drift risk"
    },
    "intent": {
      "risk_level": "low|medium|high",
      "concerns": ["string — list of intent misalignment concerns"],
      "reasoning": "string — explanation of intent risk"
    },
    "operations": {
      "risk_level": "low|medium|high",
      "concerns": ["string — list of risky operation concerns"],
      "reasoning": "string — explanation of operations risk"
    }
  }'''
    else:
        risk_assessment_schema = '''"risk_assessment": {
    "drift": {
      "risk_level": "low|medium|high",
      "concerns": ["string — list of specific drift concerns"],
      "reasoning": "string — explanation of drift risk"
    },
    "operations": {
      "risk_level": "low|medium|high",
      "concerns": ["string — list of risky operation concerns"],
      "reasoning": "string — explanation of operations risk"
    }
  }'''

    # Build bucket-specific instructions
    bucket_instructions = '''

## Risk Bucket 1: Infrastructure Drift

Compare the What-If output to the code diff. Identify any resources
changing that are NOT modified in the diff. This indicates infrastructure
drift (out-of-band changes made outside of this PR).

Risk levels for drift:
- high: Critical resources drifting (security, identity, stateful),
  broad scope drift
- medium: Multiple resources drifting, configuration drift on
  important resources
- low: Minor drift (tags, display names), single resource drift on
  non-critical resources

## Risk Bucket 2: Risky Azure Operations

Evaluate the inherent risk of the operations being performed,
regardless of intent.

Risk levels for operations:
- high: Deletion of stateful resources (databases, storage, vaults),
  deletion of identity/RBAC, network security changes that open broad
  access, encryption modifications, SKU downgrades
- medium: Modifications to existing resources that change behavior
  (policy changes, scaling config), new public endpoints, firewall changes
- low: Adding new resources, tags, diagnostic/monitoring resources,
  modifying descriptions'''

    # Add intent bucket instructions only if PR metadata provided
    if pr_title or pr_description:
        bucket_instructions += '''

## Risk Bucket 3: Pull Request Intent Alignment

Compare the What-If output to the PR title and description. Flag any changes that:
- Are NOT mentioned in the PR description
- Do not align with the stated purpose
- Seem unrelated or unexpected given the PR intent
- Are destructive (Delete actions) but not explicitly mentioned

Risk levels for intent:
- high: Destructive changes (Delete) not mentioned in PR, security/auth changes not mentioned
- medium: Resource modifications not aligned with PR intent, unexpected resource types
- low: New resources not mentioned but aligned with intent, minor scope differences'''
    else:
        bucket_instructions += '''

## Risk Bucket 3: Pull Request Intent Alignment

NOTE: PR title and description were not provided, so intent alignment analysis is SKIPPED.
Do NOT include the "intent" bucket in your risk_assessment response.'''

    # Build verdict schema
    if pr_title or pr_description:
        verdict_schema = '''"verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|intent|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "string — 2-3 sentence explanation considering all buckets"
  }'''
    else:
        verdict_schema = '''"verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "string — 2-3 sentence explanation considering all buckets"
  }'''

    return base_prompt + bucket_instructions + f'''

Respond with ONLY valid JSON matching this schema:

{{
  "resources": [
    {{
      "resource_name": "string",
      "resource_type": "string",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — what this change does",
      "risk_level": "low|medium|high",
      "risk_reason": "string or null — why this is risky, if applicable"
    }}
  ],
  "overall_summary": "string",
  {risk_assessment_schema},
  {verdict_schema}
}}'''


def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None
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
        prompt = f'''Review this Azure deployment for safety.'''

        # Add PR intent context if available
        if pr_title or pr_description:
            prompt += f'''

<pull_request_intent>
Title: {pr_title or "Not provided"}
Description: {pr_description or "Not provided"}
</pull_request_intent>'''

        prompt += f'''

<whatif_output>
{whatif_content}
</whatif_output>

<code_diff>
{diff_content}
</code_diff>'''

        if bicep_content:
            prompt += f'''

<bicep_source>
{bicep_content}
</bicep_source>'''

        return prompt
    else:
        # Standard mode
        return f'''Analyze the following Azure What-If output:

<whatif_output>
{whatif_content}
</whatif_output>'''
