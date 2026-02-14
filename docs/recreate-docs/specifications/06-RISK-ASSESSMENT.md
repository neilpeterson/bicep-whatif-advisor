# Feature Specification: Risk Assessment

## Overview

CI mode deployment gate system using a three-bucket risk model. Each bucket evaluates a different safety dimension, with independent configurable thresholds. Deployment is blocked if ANY bucket exceeds its threshold.

**Critical:** Risk assessment operates on PRE-FILTERED data containing only medium/high-confidence resources. Low-confidence resources (Azure What-If noise) must be filtered out before risk evaluation to prevent noise from contaminating safety decisions.

## Module Location

**Files:**
- `bicep_whatif_advisor/ci/risk_buckets.py`: Bucket evaluation logic
- `bicep_whatif_advisor/ci/verdict.py`: Risk level constants

**Exports:**
- `RISK_LEVELS`: Ordered list of risk levels
- `evaluate_risk_buckets(data, drift_threshold, intent_threshold, operations_threshold) -> (is_safe, failed_buckets, risk_assessment)`

## Risk Level Constants

**File:** `bicep_whatif_advisor/ci/verdict.py`

**Definition:**
```python
RISK_LEVELS = ["low", "medium", "high"]
```

**Usage:**
- Index-based comparison for threshold evaluation
- Higher index = higher risk
- Used by `_exceeds_threshold()` function

## Three-Bucket Risk Model

The risk assessment evaluates three INDEPENDENT dimensions:

### Bucket 1: Infrastructure Drift

**Question:** Are resources changing that weren't modified in the code diff?

**Purpose:** Detect out-of-band infrastructure changes (manual portal edits, other automation)

**Risk Levels:**
- **High:** Critical resources drifting (security, identity, stateful resources like databases/storage), broad scope drift affecting many resources
- **Medium:** Multiple resources drifting, configuration drift on important resources (networking, compute)
- **Low:** Minor drift (tags, display names, descriptions), single non-critical resource drifting

**Examples:**
- High: Production database connection string changed but not in diff
- Medium: Three VNets showing subnet changes not in code
- Low: Resource tags updated outside of this deployment

### Bucket 2: Pull Request Intent Alignment

**Question:** Do the changes match what the PR says it's doing?

**Purpose:** Catch unintended changes, scope creep, destructive changes not mentioned

**Risk Levels:**
- **High:** Destructive changes (Delete) not mentioned in PR, security/authentication changes not mentioned
- **Medium:** Resource modifications not aligned with PR intent, unexpected resource types being deployed
- **Low:** New resources not mentioned but aligned with stated intent, minor scope differences

**Examples:**
- High: PR says "add monitoring" but What-If shows database deletion
- Medium: PR says "update API" but What-If shows storage account modifications
- Low: PR says "add logging" and What-If shows diagnostic settings plus minor related resources

**IMPORTANT:** This bucket is OPTIONAL. It's only evaluated if PR title or description is provided. If no PR metadata available, this bucket is skipped entirely.

### Bucket 3: Risky Operations

**Question:** Are the operations inherently dangerous regardless of intent?

**Purpose:** Flag operations that always need human review due to risk

**Risk Levels:**
- **High:** Deletion of stateful resources (databases, storage accounts, key vaults), deletion of identity/RBAC assignments, broad network security changes opening access, encryption configuration changes, SKU downgrades
- **Medium:** Behavioral modifications to existing resources (policy changes, scaling config), new public endpoints, firewall rule changes
- **Low:** Adding new resources, tags, diagnostic/monitoring resources, description/metadata changes

**Examples:**
- High: Deleting production Key Vault, downgrading database from S3 to S1
- Medium: Opening firewall to 0.0.0.0/0, changing backup retention from 30 days to 7
- Low: Creating new Application Insights, adding cost center tag

## Risk Bucket Evaluation

### Function: `evaluate_risk_buckets()`

**Signature:**
```python
def evaluate_risk_buckets(
    data: dict,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str
) -> Tuple[bool, List[str], Dict[str, Any]]
```

**CRITICAL INPUT REQUIREMENT:**

This function expects PRE-FILTERED data containing ONLY medium/high-confidence resources. The caller must filter out low-confidence resources (Azure What-If noise) before calling this function. If low-confidence resources are included, they will contaminate the risk assessment.

**Workflow in CLI:**
```python
# 1. Get LLM response with confidence scoring
llm_response = provider.complete(system_prompt, user_prompt)
data = extract_json(llm_response)

# 2. FILTER by confidence BEFORE risk assessment
high_conf_data, low_conf_data = filter_by_confidence(data)

# 3. If noise filtering enabled, re-analyze high-confidence data
if noise_file:
    high_conf_data = apply_noise_filtering(high_conf_data, noise_file)
    # Re-run LLM analysis on filtered data in CI mode
    # This ensures risk assessment operates on clean data

# 4. THEN evaluate risk buckets (only on high-confidence data)
is_safe, failed, risk_assessment = evaluate_risk_buckets(
    high_conf_data,  # Only high-confidence resources
    drift_threshold,
    intent_threshold,
    operations_threshold
)
```

**Parameters:**
- `data`: Parsed LLM response with `risk_assessment` field (high-confidence resources only)
- `drift_threshold`: "low" | "medium" | "high" - fail if drift risk >= this
- `intent_threshold`: "low" | "medium" | "high" - fail if intent risk >= this
- `operations_threshold`: "low" | "medium" | "high" - fail if operations risk >= this

**Returns:**
- `is_safe` (bool): True if all buckets pass their thresholds
- `failed_buckets` (list): Names of buckets that exceeded thresholds
- `risk_assessment` (dict): Risk assessment from LLM response

**Behavior:**

1. **Extract risk assessment from LLM response:**
   ```python
   risk_assessment = data.get("risk_assessment", {})
   ```

2. **Handle missing risk assessment:**
   ```python
   if not risk_assessment:
       return True, [], {
           "drift": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"},
           "operations": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"}
       }
   ```

3. **Extract bucket assessments:**
   ```python
   drift_bucket = risk_assessment.get("drift", {})
   intent_bucket = risk_assessment.get("intent")  # May be None
   operations_bucket = risk_assessment.get("operations", {})
   ```

4. **Validate and normalize risk levels:**
   ```python
   drift_risk = _validate_risk_level(drift_bucket.get("risk_level", "low"))
   operations_risk = _validate_risk_level(operations_bucket.get("risk_level", "low"))
   ```

5. **Evaluate each bucket against threshold:**
   ```python
   failed_buckets = []

   # Drift bucket
   if _exceeds_threshold(drift_risk, drift_threshold):
       failed_buckets.append("drift")

   # Intent bucket (only if evaluated by LLM)
   if intent_bucket is not None:
       intent_risk = _validate_risk_level(intent_bucket.get("risk_level", "low"))
       if _exceeds_threshold(intent_risk, intent_threshold):
           failed_buckets.append("intent")

   # Operations bucket
   if _exceeds_threshold(operations_risk, operations_threshold):
       failed_buckets.append("operations")
   ```

6. **Determine overall safety:**
   ```python
   is_safe = len(failed_buckets) == 0
   ```

7. **Return results:**
   ```python
   return is_safe, failed_buckets, risk_assessment
   ```

### Helper: `_validate_risk_level()`

**Signature:**
```python
def _validate_risk_level(risk_level: str) -> str
```

**Behavior:**
- Convert to lowercase
- If value in `RISK_LEVELS`, return it
- Otherwise, return "low" (defensive default)

**Purpose:** Handle malformed LLM responses gracefully

### Helper: `_exceeds_threshold()`

**Signature:**
```python
def _exceeds_threshold(risk_level: str, threshold: str) -> bool
```

**Behavior:**
```python
risk_index = RISK_LEVELS.index(risk_level.lower())
threshold_index = RISK_LEVELS.index(threshold.lower())
return risk_index >= threshold_index
```

**Examples:**
- `_exceeds_threshold("high", "high")` → True (high >= high)
- `_exceeds_threshold("medium", "high")` → False (medium < high)
- `_exceeds_threshold("medium", "medium")` → True (medium >= medium)
- `_exceeds_threshold("low", "medium")` → False (low < medium)

## Verdict Structure

The LLM generates a verdict based on all bucket assessments:

**JSON Structure:**
```json
{
  "verdict": {
    "safe": true/false,
    "highest_risk_bucket": "drift|intent|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "2-3 sentence explanation considering all buckets"
  }
}
```

**Field Definitions:**
- `safe`: Overall deployment safety determination
- `highest_risk_bucket`: Which bucket has the highest risk (or "none")
- `overall_risk_level`: Highest risk level across all buckets
- `reasoning`: Human-readable explanation of the verdict

**Note:** The LLM generates the verdict, but the Python code makes the actual pass/fail decision by comparing bucket risk levels to thresholds. The LLM's `safe` field is informational only.

## Threshold Comparison Logic

**All buckets are evaluated INDEPENDENTLY:**

```python
drift_fails = drift_risk >= drift_threshold
intent_fails = intent_risk >= intent_threshold  # (if intent bucket present)
operations_fails = operations_risk >= operations_threshold

is_safe = not (drift_fails or intent_fails or operations_fails)
```

**Deployment is BLOCKED if ANY bucket fails:**

| Drift | Intent | Operations | Result |
|-------|--------|------------|--------|
| Low   | Low    | Low        | ✅ Safe |
| High  | Low    | Low        | ❌ Unsafe (drift) |
| Low   | High   | Low        | ❌ Unsafe (intent) |
| Low   | Low    | High       | ❌ Unsafe (operations) |
| High  | High   | High       | ❌ Unsafe (all three) |

## CLI Integration

**CLI Flags:**
```bash
--drift-threshold [low|medium|high]       # Default: high
--intent-threshold [low|medium|high]      # Default: high
--operations-threshold [low|medium|high]  # Default: high
```

**Usage Example:**
```bash
# Strict mode: fail on any medium or high risk
bicep-whatif-advisor --ci \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Lenient mode: only fail on high risk
bicep-whatif-advisor --ci \
  --drift-threshold high \
  --intent-threshold high \
  --operations-threshold high  # (default)

# Custom: strict drift detection, lenient operations
bicep-whatif-advisor --ci \
  --drift-threshold medium \
  --operations-threshold high
```

## Exit Code Behavior

**Exit Codes:**
- `0`: Safe deployment (all buckets pass)
- `1`: Unsafe deployment (at least one bucket failed)
- `2`: Error (invalid input, API failure, etc.)

**Example:**
```python
is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
    data, drift_threshold, intent_threshold, operations_threshold
)

if not is_safe:
    print(f"Deployment BLOCKED: {', '.join(failed_buckets)} bucket(s) exceeded threshold")
    sys.exit(1)
else:
    print("Deployment SAFE: All risk buckets within acceptable limits")
    sys.exit(0)
```

## Failed Buckets Reporting

**Example Output:**
```python
failed_buckets = ["drift", "operations"]

# Terminal output
print("❌ UNSAFE")
print("Failed buckets: drift, operations")
print()
print("Drift (High): Production database config changed outside of PR")
print("Operations (Medium): Public IP address being exposed")

# JSON output
{
  "verdict": {
    "safe": false,
    "highest_risk_bucket": "drift",
    "overall_risk_level": "high",
    "reasoning": "Deployment blocked due to high drift risk and medium operations risk.",
    "failed_buckets": ["drift", "operations"]  # Added by Python code
  }
}
```

## Intent Bucket Optional Behavior

**If PR metadata NOT provided:**

1. **System prompt omits intent bucket:**
   ```python
   if pr_title or pr_description:
       # Include intent bucket instructions
   else:
       # Skip intent bucket, prompt says "NOT evaluated"
   ```

2. **LLM response omits intent bucket:**
   ```json
   {
     "risk_assessment": {
       "drift": { ... },
       "operations": { ... }
       // NO "intent" key
     }
   }
   ```

3. **Python evaluation skips intent bucket:**
   ```python
   intent_bucket = risk_assessment.get("intent")
   if intent_bucket is not None:
       # Evaluate intent bucket
   else:
       # Skip intent evaluation entirely
   ```

## Implementation Requirements

1. **Pre-filtered data required:** Caller MUST filter low-confidence resources before calling `evaluate_risk_buckets()`
2. **Independent threshold evaluation:** Each bucket compared to its own threshold, not a single global threshold
3. **Any-fail-blocks-all logic:** If ANY bucket exceeds threshold, deployment is unsafe
4. **Intent bucket conditional:** Check if `intent_bucket is not None` before evaluating
5. **Graceful degradation:** Missing risk assessment returns safe verdict with warning message
6. **Risk level validation:** Normalize and validate all risk levels from LLM
7. **Index-based comparison:** Use `RISK_LEVELS.index()` for >= threshold logic
8. **Clear failure reporting:** Return list of which specific buckets failed

## Edge Cases

1. **No risk assessment in LLM response:** Return safe with warning
2. **Invalid risk level:** Default to "low" via `_validate_risk_level()`
3. **Intent bucket missing (no PR metadata):** Skip intent evaluation entirely
4. **All buckets at threshold exactly:** Fails (>= comparison)
5. **Empty concerns array:** Valid, show "None" in output
6. **Empty reasoning string:** Valid, show as-is
7. **Low-confidence resources in data:** CRITICAL BUG - must be filtered before calling this function
