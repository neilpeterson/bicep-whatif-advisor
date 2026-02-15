# 04 - Prompt Engineering

## Purpose

The `prompt.py` module constructs system and user prompts for LLM analysis. It implements dynamic schema generation based on operating mode (standard vs. CI) and available metadata (PR title/description), ensuring the LLM receives appropriate instructions and context.

**File:** `bicep_whatif_advisor/prompt.py` (315 lines)

## Module Overview

The module provides two public functions:

```python
def build_system_prompt(
    verbose: bool = False,
    ci_mode: bool = False,
    pr_title: str = None,
    pr_description: str = None
) -> str

def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None
) -> str
```

And two private helper functions:

```python
def _build_standard_system_prompt(verbose: bool) -> str
def _build_ci_system_prompt(pr_title: str = None, pr_description: str = None) -> str
```

## System Prompt Construction

### Entry Point (lines 4-24)

```python
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
```

**Routing Logic:**
- **Standard mode:** Calls `_build_standard_system_prompt()`
- **CI mode:** Calls `_build_ci_system_prompt()`

## Standard Mode System Prompt

### Implementation (lines 27-85)

The standard mode prompt defines a simple JSON response schema for resource change analysis.

#### Base Schema (lines 29-41)

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

**Resource Fields:**
- `resource_name`: Short name (e.g., "myStorageAccount")
- `resource_type`: Abbreviated type (e.g., "Storage Account")
- `action`: One of: Create, Modify, Delete, Deploy, NoChange, Ignore
- `summary`: Plain English change description
- `confidence_level`: LLM's assessment of whether change is real vs. noise
- `confidence_reason`: Explanation for confidence level

#### Verbose Addition (lines 43-46)

When `verbose=True`:

```
For resources with action "Modify", also include a "changes" field:
an array of strings describing each property-level change.
```

**Purpose:** Provides detailed property-level changes for modified resources (e.g., "httpsOnly: false → true").

#### Confidence Assessment Instructions (lines 48-71)

```
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

Use your judgment - these are guidelines, not rigid patterns.
```

**Key Design:** Provides examples but emphasizes LLM judgment ("these are guidelines, not rigid patterns").

**Why Confidence Scoring?**
- Azure What-If output contains significant noise (spurious changes)
- LLM can use context to judge whether changes are meaningful
- Enables filtering without brittle regex patterns

#### Complete Standard Prompt (lines 73-85)

```python
prompt = f'''You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{base_schema}'''

if verbose:
    prompt += "\n" + verbose_addition

prompt += confidence_instructions

return prompt
```

**Structure:**
1. Role definition ("Azure infrastructure expert")
2. Task definition ("analyze What-If output")
3. Output format requirement ("ONLY valid JSON")
4. Schema definition
5. Optional verbose addition
6. Confidence assessment guidelines

## CI Mode System Prompt

### Implementation (lines 88-255)

CI mode prompts are more complex, defining a three-bucket risk assessment framework with dynamic schema generation.

#### Base Introduction (lines 90-104)

```python
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
```

**Dynamic Content:**
- Item #3 (PR intent) only added if `pr_title` or `pr_description` provided
- Sets expectation for "three independent risk buckets"

#### Dynamic Schema Generation (lines 106-137)

**With PR metadata (3 buckets):**

```json
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
}
```

**Without PR metadata (2 buckets):**

```json
"risk_assessment": {
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
}
```

**Key Design:** Schema adapts to available input. If no PR metadata, `intent` bucket is excluded.

#### Risk Bucket Instructions

**Bucket 1: Infrastructure Drift (lines 140-154)**

```
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
```

**Purpose:** Detect changes not caused by the current PR (infrastructure drift).

**Bucket 2: Risky Operations (lines 156-168)**

```
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
  modifying descriptions
```

**Purpose:** Assess inherent risk of Azure operations (e.g., deleting a database is risky regardless of intent).

**Bucket 3: Intent Alignment (lines 171-192)**

**With PR metadata:**

```
## Risk Bucket 3: Pull Request Intent Alignment

Compare the What-If output to the PR title and description. Flag any changes that:
- Are NOT mentioned in the PR description
- Do not align with the stated purpose
- Seem unrelated or unexpected given the PR intent
- Are destructive (Delete actions) but not explicitly mentioned

Risk levels for intent:
- high: Destructive changes (Delete) not mentioned in PR, security/auth changes not mentioned
- medium: Resource modifications not aligned with PR intent, unexpected resource types
- low: New resources not mentioned but aligned with intent, minor scope differences
```

**Without PR metadata:**

```
## Risk Bucket 3: Pull Request Intent Alignment

NOTE: PR title and description were not provided, so intent alignment analysis is SKIPPED.
Do NOT include the "intent" bucket in your risk_assessment response.
```

**Key Design:** Explicit instruction to LLM to skip intent bucket if no metadata available.

#### Verdict Schema (lines 194-208)

**With PR metadata:**

```json
"verdict": {
  "safe": true/false,
  "highest_risk_bucket": "drift|intent|operations|none",
  "overall_risk_level": "low|medium|high",
  "reasoning": "string — 2-3 sentence explanation considering all buckets"
}
```

**Without PR metadata:**

```json
"verdict": {
  "safe": true/false,
  "highest_risk_bucket": "drift|operations|none",
  "overall_risk_level": "low|medium|high",
  "reasoning": "string — 2-3 sentence explanation considering all buckets"
}
```

**Difference:** `highest_risk_bucket` options exclude "intent" when PR metadata unavailable.

#### Confidence Instructions (lines 210-233)

CI mode includes identical confidence assessment instructions as standard mode (lines 48-71).

#### Complete CI Prompt Assembly (lines 235-255)

```python
return base_prompt + bucket_instructions + confidence_instructions + f'''

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
}}'''
```

**Structure:**
1. Role and context ("deployment safety reviewer")
2. Risk bucket instructions (drift, operations, intent)
3. Confidence assessment guidelines
4. JSON schema with dynamic risk_assessment and verdict fields

**Additional Resource Fields in CI Mode:**
- `risk_level`: Per-resource risk (low/medium/high)
- `risk_reason`: Explanation of why resource is risky

## User Prompt Construction

### Implementation (lines 258-314)

The user prompt contains the actual data to analyze (What-If output, diff, etc.).

```python
def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None
) -> str:
    """Build the user prompt with What-If output and optional context."""
```

### CI Mode User Prompt (lines 277-307)

When `diff_content` is provided (CI mode):

```python
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
```

**XML-Style Tags:** Data is wrapped in clear delimiters:
- `<pull_request_intent>` - PR title and description (optional)
- `<whatif_output>` - Azure What-If output (required)
- `<code_diff>` - Git diff (required in CI mode)
- `<bicep_source>` - Bicep source files (optional)

**Why XML-style tags?**
- Clear boundaries for multiline content
- Reduces LLM confusion about where sections start/end
- Industry standard for structured prompts

### Standard Mode User Prompt (lines 309-314)

When `diff_content` is `None` (standard mode):

```python
return f'''Analyze the following Azure What-If output:

<whatif_output>
{whatif_content}
</whatif_output>'''
```

**Simple structure:** Just the What-If output, no additional context.

## Dynamic Schema Generation

### Key Innovation

The prompt system **dynamically adjusts the response schema** based on available inputs:

| Input | Schema Includes |
|-------|-----------------|
| Standard mode | resources, overall_summary |
| CI mode (no PR metadata) | resources, overall_summary, risk_assessment (drift + operations), verdict (drift\|operations) |
| CI mode (with PR metadata) | resources, overall_summary, risk_assessment (drift + intent + operations), verdict (drift\|intent\|operations) |

**Why Dynamic?**
- Prevents LLM from hallucinating intent analysis when no PR metadata available
- Ensures strict adherence to available data
- Avoids "Not provided" values in structured output

### Schema Adaptation Logic

```python
# In _build_ci_system_prompt()
if pr_title or pr_description:
    risk_assessment_schema = '''... includes intent bucket ...'''
    verdict_schema = '''... highest_risk_bucket includes "intent" ...'''
else:
    risk_assessment_schema = '''... excludes intent bucket ...'''
    verdict_schema = '''... highest_risk_bucket excludes "intent" ...'''
```

**Explicit Instruction When Skipping Intent:**
```
NOTE: PR title and description were not provided, so intent alignment analysis is SKIPPED.
Do NOT include the "intent" bucket in your risk_assessment response.
```

## Prompt Design Principles

### 1. Strict JSON Output

All prompts include:
```
You must respond with ONLY valid JSON matching this schema, no other text:
```

**Rationale:**
- Enables reliable parsing with `extract_json()`
- Prevents LLM from adding explanatory text outside JSON
- Critical for automation/scripting

### 2. Detailed Schema Documentation

Schema fields include inline comments:
```json
"resource_name": "string — the short resource name"
```

**Benefits:**
- LLM understands expected format and content
- Reduces schema violations
- Serves as self-documentation

### 3. Guideline-Based, Not Rule-Based

Confidence and risk guidelines end with:
```
Use your judgment - these are guidelines, not rigid patterns.
```

**Philosophy:** Trust LLM reasoning over brittle pattern matching.

### 4. Context Over Structure

Prompts provide rich context (PR intent, code diff, Bicep source) rather than asking LLM to parse structured data.

**Advantage:** LLM can use reasoning to connect What-If output, code changes, and developer intent.

### 5. Explicit Task Definition

Each prompt clearly states:
- **Role:** "You are an Azure infrastructure expert"
- **Task:** "Analyze Azure What-If output"
- **Output:** "Respond with ONLY valid JSON"

**Reduces ambiguity** and improves response quality.

## Integration with CLI

### Usage in cli.py (lines 344-356)

```python
# Build prompts
system_prompt = build_system_prompt(
    verbose=verbose,
    ci_mode=ci,
    pr_title=pr_title,
    pr_description=pr_description
)
user_prompt = build_user_prompt(
    whatif_content=whatif_content,
    diff_content=diff_content,
    bicep_content=bicep_content,
    pr_title=pr_title,
    pr_description=pr_description
)

# Call LLM
response_text = llm_provider.complete(system_prompt, user_prompt)
```

### Data Flow

```
CLI Flags + Platform Detection
     ↓
build_system_prompt() + build_user_prompt()
     ↓
Provider.complete()
     ↓
LLM Response (JSON string)
     ↓
extract_json()
     ↓
Parsed data dict
```

## Example Prompts

### Standard Mode Example

**System Prompt:**
```
You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{
  "resources": [...],
  "overall_summary": "string"
}

## Confidence Assessment
...
```

**User Prompt:**
```
Analyze the following Azure What-If output:

<whatif_output>
Resource changes: 2 to create.

+ Microsoft.Storage/storageAccounts/myaccount
  Location: eastus
  SKU: Standard_LRS
...
</whatif_output>
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
...

## Risk Bucket 2: Risky Azure Operations
...

## Risk Bucket 3: Pull Request Intent Alignment
...

Respond with ONLY valid JSON matching this schema:
{
  "resources": [...],
  "overall_summary": "string",
  "risk_assessment": {
    "drift": {...},
    "intent": {...},
    "operations": {...}
  },
  "verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|intent|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "string"
  }
}
```

**User Prompt:**
```
Review this Azure deployment for safety.

<pull_request_intent>
Title: Add Application Insights monitoring
Description: This PR adds Application Insights to the web app for observability
</pull_request_intent>

<whatif_output>
Resource changes: 1 to create, 1 to modify.

+ Microsoft.Insights/components/myapp-insights
...
</whatif_output>

<code_diff>
diff --git a/main.bicep b/main.bicep
+ resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
...
</code_diff>
```

## Testing Strategy

### Unit Tests

Mock the prompt functions and verify:
- Correct schema generation based on inputs
- Dynamic intent bucket inclusion/exclusion
- Verbose mode changes schema
- XML tags are properly formatted

### Integration Tests

Use real LLM providers and verify:
- Prompts produce valid JSON responses
- Schema compliance (no extra fields)
- Confidence levels are assigned
- Risk buckets are populated (CI mode)

## Performance Characteristics

- **Prompt generation:** O(1) - string concatenation
- **Memory:** Minimal - prompts are typically < 10KB
- **Token count:** Varies by mode:
  - Standard mode: ~500 tokens (system prompt)
  - CI mode: ~800 tokens (system prompt)
  - User prompt: Depends on What-If size (up to ~25K tokens for 100K char input)

## Future Improvements

Potential enhancements:

1. **Few-shot examples:** Include example inputs/outputs in prompts
2. **Chain-of-thought:** Ask LLM to explain reasoning before outputting JSON
3. **Schema validation:** Include JSON Schema definition for stricter validation
4. **Prompt versioning:** Track prompt changes across tool versions
5. **Custom risk guidelines:** Allow users to provide custom risk criteria

## Next Steps

For details on how prompts are used:
- [03-PROVIDER-SYSTEM.md](03-PROVIDER-SYSTEM.md) - How `complete()` receives prompts
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - How `extract_json()` parses responses
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) - How risk buckets are evaluated
