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
      "resource_type": "string — the Azure resource type, abbreviated for readability",
      "action": "string — one of: Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — 1-2 sentence plain English explanation of what this resource is and what the change does"
    }
  ],
  "overall_summary": "string — a brief overall summary of the deployment, including counts by action type and the overall intent"
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
        base_prompt += '''\n3. The pull request title and description stating the INTENDED purpose of this change'''

    base_prompt += '''\n\nEvaluate the deployment for safety and correctness.'''

    # Add intent analysis instructions if PR metadata is provided
    intent_instructions = ""
    if pr_title or pr_description:
        intent_instructions = '''

IMPORTANT - Intent Analysis:
You have been provided with the pull request title and/or description. Use this to understand
the STATED INTENT of the change. Flag any changes in the What-If output that:
- Are NOT mentioned in the PR description
- Do not align with the stated purpose
- Seem unrelated or unexpected given the PR intent
- Are destructive (Delete actions) but not explicitly mentioned

Treat intent mismatches as elevated risk:
- Destructive changes (Delete) not mentioned in PR = CRITICAL risk
- Security/auth changes not mentioned in PR = HIGH risk
- Resource modifications not aligned with PR intent = MEDIUM risk
- New resources not mentioned but aligned with intent = LOW risk'''

    return base_prompt + intent_instructions + '''

Respond with ONLY valid JSON matching this schema:

{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — what this change does",
      "risk_level": "string — none, low, medium, high, critical",
      "risk_reason": "string or null — why this is risky, if applicable"
    }
  ],
  "overall_summary": "string",
  "verdict": {
    "safe": true/false,
    "risk_level": "string — none, low, medium, high, critical (highest individual risk)",
    "reasoning": "string — 2-3 sentence explanation of the verdict",
    "concerns": ["string — list of specific concerns, if any"],
    "recommendations": ["string — list of recommendations, if any"]
  }
}

Apply these risk classifications:

- critical: Deletion of stateful resources (databases, storage accounts, key vaults),
  deletion of identity/RBAC resources, changes to network security rules that open
  broad access, modifications to encryption settings
- high: Deletion of any production resource, modifications to authentication/authorization
  config, changes to firewall rules, SKU downgrades on critical services
- medium: Modifications to existing resources that change behavior (policy changes,
  scaling config, diagnostic settings), new public endpoints
- low: Adding new resources, adding tags, adding diagnostic/monitoring resources,
  modifying descriptions or display names
- none: NoChange, Ignore, cosmetic-only changes'''


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
