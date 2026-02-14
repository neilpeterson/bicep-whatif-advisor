# Feature Specification: Prompt Engineering

## Overview

This module constructs LLM prompts for analyzing Azure What-If deployment output. It provides two distinct prompt strategies:

1. **Standard Mode:** Summarize infrastructure changes in plain English
2. **CI Mode:** Comprehensive deployment safety review with risk assessment

All prompts use structured JSON output and confidence scoring to filter Azure What-If noise.

## Module Location

**File:** `bicep_whatif_advisor/prompt.py`

**Exports:**
- `build_system_prompt(verbose, ci_mode, pr_title, pr_description) -> str`
- `build_user_prompt(whatif_content, diff_content, bicep_content, pr_title, pr_description) -> str`

## System Prompt Construction

### Function: `build_system_prompt()`

**Signature:**
```python
def build_system_prompt(
    verbose: bool = False,
    ci_mode: bool = False,
    pr_title: str = None,
    pr_description: str = None
) -> str
```

**Behavior:**
- If `ci_mode=True`: Return CI mode system prompt
- Otherwise: Return standard mode system prompt
- Delegates to `_build_standard_system_prompt()` or `_build_ci_system_prompt()`

### Standard Mode System Prompt

**Function:** `_build_standard_system_prompt(verbose: bool) -> str`

**Persona:**
```
You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.
```

**Response Schema:**
```json
{
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
}
```

**Verbose Mode Addition:**
If `verbose=True`, also include this instruction:
```
For resources with action "Modify", also include a "changes" field:
an array of strings describing each property-level change.
```

**Confidence Assessment Instructions:**

The system prompt includes detailed guidance for assessing confidence levels:

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

**Critical Note:** These are GUIDELINES, not rigid patterns. The LLM should use judgment.

### CI Mode System Prompt

**Function:** `_build_ci_system_prompt(pr_title: str, pr_description: str) -> str`

**Persona:**
```
You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes
```

If PR metadata provided:
```
3. The pull request title and description stating the INTENDED purpose of this change
```

**Task:**
```
Evaluate the deployment for safety and correctness across three independent risk buckets:
```

**Risk Bucket Definitions:**

**Bucket 1: Infrastructure Drift**

Compare What-If output to code diff. Identify resources changing that are NOT modified in the diff (indicates out-of-band changes).

Risk levels:
- **high:** Critical resources drifting (security, identity, stateful), broad scope drift
- **medium:** Multiple resources drifting, configuration drift on important resources
- **low:** Minor drift (tags, display names), single resource drift on non-critical resources

**Bucket 2: Risky Azure Operations**

Evaluate inherent risk of operations, regardless of intent.

Risk levels:
- **high:** Deletion of stateful resources (databases, storage, vaults), deletion of identity/RBAC, network security changes opening broad access, encryption modifications, SKU downgrades
- **medium:** Modifications to existing resources changing behavior (policy changes, scaling config), new public endpoints, firewall changes
- **low:** Adding new resources, tags, diagnostic/monitoring resources, modifying descriptions

**Bucket 3: Pull Request Intent Alignment** *(only if PR metadata provided)*

Compare What-If output to PR title/description. Flag changes that:
- Are NOT mentioned in PR description
- Do not align with stated purpose
- Seem unrelated or unexpected given PR intent
- Are destructive (Delete) but not explicitly mentioned

Risk levels:
- **high:** Destructive changes (Delete) not mentioned in PR, security/auth changes not mentioned
- **medium:** Resource modifications not aligned with PR intent, unexpected resource types
- **low:** New resources not mentioned but aligned with intent, minor scope differences

**IMPORTANT:** If no PR title/description provided, the intent bucket is SKIPPED entirely and should NOT be included in the response.

**Response Schema (with PR metadata):**
```json
{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — what this change does",
      "risk_level": "low|medium|high",
      "risk_reason": "string or null — why this is risky, if applicable",
      "confidence_level": "low|medium|high — confidence this is a real change vs What-If noise",
      "confidence_reason": "string — brief explanation of confidence assessment"
    }
  ],
  "overall_summary": "string",
  "risk_assessment": {
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
  },
  "verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|intent|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "string — 2-3 sentence explanation considering all buckets"
  }
}
```

**Response Schema (without PR metadata):**

If no PR title/description provided, the `intent` bucket is REMOVED from both `risk_assessment` and the `highest_risk_bucket` enum:

```json
{
  "risk_assessment": {
    "drift": { ... },
    "operations": { ... }
    // NO "intent" bucket
  },
  "verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|operations|none",  // NO "intent" option
    "overall_risk_level": "low|medium|high",
    "reasoning": "string"
  }
}
```

The same confidence assessment instructions from standard mode are included in CI mode.

## User Prompt Construction

### Function: `build_user_prompt()`

**Signature:**
```python
def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None
) -> str
```

**Behavior:**

**Standard Mode** (diff_content is None):
```
Analyze the following Azure What-If output:

<whatif_output>
{whatif_content}
</whatif_output>
```

**CI Mode** (diff_content is not None):
```
Review this Azure deployment for safety.

<pull_request_intent>
Title: {pr_title or "Not provided"}
Description: {pr_description or "Not provided"}
</pull_request_intent>

<whatif_output>
{whatif_content}
</whatif_output>

<code_diff>
{diff_content}
</code_diff>

<bicep_source>
{bicep_content}
</bicep_source>
```

**Notes:**
- PR intent section only included if `pr_title` or `pr_description` provided
- Bicep source section only included if `bicep_content` provided
- XML-style tags used for clear section delineation

## Example Prompts and Responses

### Standard Mode Example

**System Prompt:**
```
You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{
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
}

## Confidence Assessment
[... detailed guidance ...]
```

**User Prompt:**
```
Analyze the following Azure What-If output:

<whatif_output>
Resource changes:

  + Create:
      apiManagementService/policies/policy-fragments/parse-jwt-from-header
        Type: Microsoft.ApiManagement/service/policies/policyFragments

  ~ Modify:
      apiManagementService/appinsights-logger
        Type: Microsoft.ApiManagement/service/loggers
        ~ properties.credentials.instrumentationKey: "old-key" => "new-key"
</whatif_output>
```

**Expected Response:**
```json
{
  "resources": [
    {
      "resource_name": "parse-jwt-from-header",
      "resource_type": "Policy Fragment",
      "action": "Create",
      "summary": "Creates new JWT parsing policy fragment for API authentication",
      "confidence_level": "high",
      "confidence_reason": "New resource creation with clear security purpose"
    },
    {
      "resource_name": "appinsights-logger",
      "resource_type": "API Management Logger",
      "action": "Modify",
      "summary": "Updates Application Insights instrumentation key",
      "confidence_level": "high",
      "confidence_reason": "Configuration change with concrete value update"
    }
  ],
  "overall_summary": "1 create, 1 modify: Adds JWT authentication policy and updates monitoring configuration"
}
```

### CI Mode Example (with PR metadata)

**System Prompt:**
```
You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes
3. The pull request title and description stating the INTENDED purpose of this change

Evaluate the deployment for safety and correctness across three independent risk buckets:

## Risk Bucket 1: Infrastructure Drift
[... detailed guidance ...]

## Risk Bucket 2: Risky Azure Operations
[... detailed guidance ...]

## Risk Bucket 3: Pull Request Intent Alignment
[... detailed guidance ...]

Respond with ONLY valid JSON matching this schema:
[... full schema with intent bucket ...]
```

**User Prompt:**
```
Review this Azure deployment for safety.

<pull_request_intent>
Title: Add JWT authentication policy
Description: This PR adds a new policy fragment for parsing JWT tokens from request headers
</pull_request_intent>

<whatif_output>
Resource changes:

  + Create:
      apiManagementService/policies/policy-fragments/parse-jwt-from-header

  ~ Modify:
      apiManagementService/production-api
        ~ properties.publicIPAddressConfiguration.enabled: false => true
</whatif_output>

<code_diff>
+++ b/main.bicep
+resource jwtPolicy 'Microsoft.ApiManagement/service/policies/policyFragments@2023-03-01-preview' = {
+  name: 'parse-jwt-from-header'
+  properties: {
+    value: loadTextContent('policies/parse-jwt.xml')
+  }
+}
</code_diff>
```

**Expected Response:**
```json
{
  "resources": [
    {
      "resource_name": "parse-jwt-from-header",
      "resource_type": "Policy Fragment",
      "action": "Create",
      "summary": "Creates JWT authentication policy fragment",
      "risk_level": "low",
      "risk_reason": null,
      "confidence_level": "high",
      "confidence_reason": "New resource creation matching code diff"
    },
    {
      "resource_name": "production-api",
      "resource_type": "API Management API",
      "action": "Modify",
      "summary": "Enables public IP addressing",
      "risk_level": "medium",
      "risk_reason": "Exposes API to public internet",
      "confidence_level": "high",
      "confidence_reason": "Clear configuration change"
    }
  ],
  "overall_summary": "1 create, 1 modify: Adds JWT policy and enables public IP",
  "risk_assessment": {
    "drift": {
      "risk_level": "medium",
      "concerns": ["production-api public IP change not in code diff"],
      "reasoning": "The public IP change appears in What-If but not in the provided diff, suggesting out-of-band modification"
    },
    "intent": {
      "risk_level": "medium",
      "concerns": ["Public IP change not mentioned in PR"],
      "reasoning": "PR description only mentions JWT policy, but deployment also enables public IP addressing"
    },
    "operations": {
      "risk_level": "medium",
      "concerns": ["Enabling public IP exposes API to internet"],
      "reasoning": "Creating new public endpoint increases attack surface"
    }
  },
  "verdict": {
    "safe": false,
    "highest_risk_bucket": "drift",
    "overall_risk_level": "medium",
    "reasoning": "Multiple medium-risk concerns detected. The public IP change appears to be infrastructure drift not captured in the code diff, and it's not mentioned in the PR intent. This should be reviewed before deployment."
  }
}
```

## Implementation Requirements

1. **Prompt must enforce JSON-only output:** "You must respond with ONLY valid JSON... no other text"
2. **Confidence instructions must be guidance, not rigid patterns:** "Use your judgment - these are guidelines, not rigid patterns"
3. **Intent bucket is conditional:** Only include intent bucket in schema if PR metadata provided
4. **XML tags for clarity:** Use `<whatif_output>`, `<code_diff>`, etc. for section markers
5. **Temperature 0:** All providers use temperature 0 for deterministic output (configured in provider layer, not prompts)

## Edge Cases

1. **No PR metadata in CI mode:** Intent bucket omitted from schema
2. **Verbose mode in standard:** Adds "changes" field requirement to schema
3. **Empty PR title/description:** Show "Not provided" in user prompt, skip intent bucket in system prompt
4. **Very long What-If output:** Truncated by input handler before reaching prompt builder
