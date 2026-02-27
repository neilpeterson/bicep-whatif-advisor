# 08 - Risk Assessment (Multi-Bucket Model)

## Purpose

The risk assessment system evaluates Azure deployments across independent risk dimensions (buckets), each with its own configurable threshold. Two buckets are built-in (drift and intent), and additional buckets can be added via custom agents (`--agents-dir`). Deployments are blocked only if ANY bucket exceeds its threshold, ensuring comprehensive safety checks.

**Files:**
- `bicep_whatif_advisor/ci/risk_buckets.py` (97 lines) - Bucket evaluation logic
- `bicep_whatif_advisor/ci/verdict.py` (4 lines) - Risk level constants

## Multi-Bucket Model

### Built-in Risk Dimensions

| Bucket | Question | Purpose |
|--------|----------|---------|
| **Drift** | Does What-If differ from code changes? | Detects infrastructure drift (out-of-band changes) |
| **Intent** | Does What-If align with PR description? | Catches unintended changes (scope creep) |

Additional risk dimensions can be added via custom agents (e.g., risky operations, compliance, cost analysis). See the custom agents documentation for details.

**Key Design:** Buckets are **independent** - each has its own threshold and evaluation criteria.

**Safety Contract:** Deployment blocked if **ANY** bucket exceeds threshold (AND logic).

### Why Multiple Buckets?

**Problem:** Single "risk score" conflates different concerns:
- Infrastructure drift ≠ intent misalignment
- Different teams need fine-grained control

**Solution:** Separate buckets enable:
- **Independent tuning:** Strict on drift, lenient on intent
- **Clear reasoning:** "Blocked due to high drift risk" vs. vague "unsafe"
- **Targeted analysis:** LLM evaluates each dimension separately
- **Extensibility:** Custom agents add new risk dimensions

## Implementation

### Risk Levels (verdict.py)

```python
"""Risk level constants for CI mode deployment gates."""

# Risk level ordering (higher index = higher risk)
RISK_LEVELS = ["low", "medium", "high"]
```

**Ordinal Scale:**
- `low` (index 0) - Minimal risk, safe to proceed
- `medium` (index 1) - Moderate risk, review recommended
- `high` (index 2) - Significant risk, careful review required

**Used For:**
1. Threshold comparison (≥ logic)
2. Risk level validation
3. Index-based comparison

### evaluate_risk_buckets() Function (lines 22-81)

Main evaluation function called by CLI:

```python
def evaluate_risk_buckets(
    data: dict,
    enabled_buckets: list,
    drift_threshold: str,
    intent_threshold: str,
    custom_thresholds: dict = None
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Evaluate risk buckets and determine if deployment is safe.

    NOTE: This function expects pre-filtered data containing only medium/high-confidence
    resources. Low-confidence resources (likely Azure What-If noise) should be filtered
    out before calling this function to avoid noise contaminating risk assessment.

    Args:
        data: Parsed LLM response with risk_assessment (should contain only high-confidence resources)
        enabled_buckets: List of bucket IDs to evaluate
        drift_threshold: Risk threshold for infrastructure drift bucket
        intent_threshold: Risk threshold for PR intent alignment bucket
        custom_thresholds: Dict of custom agent thresholds (agent_id -> level)

    Returns:
        Tuple of (is_safe: bool, failed_buckets: list, risk_assessment: dict)
    """
```

**Parameters:**

| Parameter | Type | Example | Purpose |
|-----------|------|---------|---------|
| `data` | `dict` | `{"risk_assessment": {...}}` | Parsed LLM response with risk buckets |
| `enabled_buckets` | `list` | `["drift", "intent"]` | Bucket IDs to evaluate |
| `drift_threshold` | `str` | `"high"` | Fail if drift risk ≥ threshold |
| `intent_threshold` | `str` | `"high"` | Fail if intent risk ≥ threshold |
| `custom_thresholds` | `dict` | `{"compliance": "medium"}` | Custom agent thresholds |

**Returns:** Tuple of:
1. `is_safe` (`bool`) - Whether deployment is safe to proceed
2. `failed_buckets` (`List[str]`) - List of bucket names that failed (empty if safe)
3. `risk_assessment` (`dict`) - Complete risk assessment data

**Critical Note:** Expects **pre-filtered data** (high-confidence resources only).
- Called after `filter_by_confidence()` in CLI
- Ensures risk assessment not contaminated by noise

### Evaluation Algorithm (lines 43-81)

```python
risk_assessment = data.get("risk_assessment", {})

if not risk_assessment:
    # No risk assessment provided - default all enabled buckets to safe
    default_ra = {}
    for bucket_id in enabled_buckets:
        default_ra[bucket_id] = {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"}
    return True, [], default_ra

# Evaluate each enabled bucket against its threshold
failed_buckets = []

for bucket_id in enabled_buckets:
    bucket_data = risk_assessment.get(bucket_id, {})
    risk_level = _validate_risk_level(bucket_data.get("risk_level", "low"))

    # Determine threshold for this bucket
    threshold = custom_thresholds.get(bucket_id) if custom_thresholds else None
    if threshold is None:
        threshold = thresholds.get(bucket_id, "high")  # Built-in thresholds map

    if _exceeds_threshold(risk_level, threshold):
        failed_buckets.append(bucket_id)

# Overall safety: all buckets must pass
is_safe = len(failed_buckets) == 0

return is_safe, failed_buckets, risk_assessment
```

**Logic Flow:**

```
Input: data + enabled_buckets + thresholds
    ↓
Extract risk_assessment dict
    ↓
If missing → default all enabled buckets to safe
    ↓
For each enabled bucket:
    ├── Extract risk_level (default to "low")
    ├── Look up threshold (custom → built-in → default "high")
    ├── Compare risk_level vs threshold
    └── If exceeds → add to failed_buckets
    ↓
is_safe = (failed_buckets is empty)
    ↓
Return (is_safe, failed_buckets, risk_assessment)
```

### Intent Bucket Handling

```python
intent_bucket = risk_assessment.get("intent")  # May be None if not evaluated

if intent_bucket is not None:
    intent_risk = _validate_risk_level(intent_bucket.get("risk_level", "low"))
    if _exceeds_threshold(intent_risk, intent_threshold):
        failed_buckets.append("intent")
```

**Design:** Intent bucket optional (not evaluated if no PR metadata).

**Behavior:**
- Intent bucket present → Evaluate against threshold
- Intent bucket missing → Skip (not counted as failure)

**See:** [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) and [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) for how intent bucket is conditionally included.

### _exceeds_threshold() Function (lines 84-96)

Threshold comparison using ordinal risk levels:

```python
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
```

**Algorithm:** Index-based comparison using `RISK_LEVELS = ["low", "medium", "high"]`.

**Examples:**

| Risk Level | Threshold | Result | Reasoning |
|------------|-----------|--------|-----------|
| `low` | `high` | `False` | 0 >= 2 is False |
| `medium` | `high` | `False` | 1 >= 2 is False |
| `high` | `high` | `True` | 2 >= 2 is True (equal counts as exceeding) |
| `high` | `medium` | `True` | 2 >= 1 is True |
| `medium` | `low` | `True` | 1 >= 0 is True |

**Key Behavior:** Equal risk level counts as **exceeding** (>= not >).

**Rationale:** Threshold represents "fail if risk is AT LEAST this level".

### _validate_risk_level() Function (lines 9-19)

Normalizes and validates risk levels:

```python
def _validate_risk_level(risk_level: str) -> str:
    """Validate and normalize risk level.

    Args:
        risk_level: Risk level string to validate

    Returns:
        Validated risk level, defaults to "low" if invalid
    """
    risk = risk_level.lower()
    return risk if risk in RISK_LEVELS else "low"
```

**Behavior:**
- Valid risk level → Lowercase normalized
- Invalid risk level → Default to `"low"` (safe default)

**Handles:**
- Case variations: `"HIGH"`, `"High"`, `"high"` → `"high"`
- Typos: `"hgh"`, `"medum"` → `"low"`
- Missing values: `None`, `""` → `"low"`

**Why Default to "low"?**
- Fail-safe: Invalid input shouldn't block deployments
- LLM output should always be valid (validated by schema), so this is edge case handling

## Integration with CLI

### Usage in cli.py (lines 489-518)

```python
# CI mode: evaluate verdict and post comment
if ci:
    from .ci.risk_buckets import evaluate_risk_buckets

    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
        high_confidence_data, enabled_buckets, drift_threshold, intent_threshold,
        custom_thresholds=custom_thresholds,
    )

    # Post comment if requested
    if post_comment:
        markdown = render_markdown(high_confidence_data, ci_mode=True, custom_title=comment_title, no_block=no_block, low_confidence_data=low_confidence_data)
        _post_pr_comment(markdown, pr_url)

    # Exit with appropriate code
    if is_safe:
        sys.exit(0)  # Safe to deploy
    else:
        # Show which buckets failed
        if failed_buckets:
            bucket_names = ", ".join(failed_buckets)
            if no_block:
                sys.stderr.write(f"⚠️  Warning: Failed risk buckets: {bucket_names} (pipeline not blocked due to --no-block)\n")
            else:
                sys.stderr.write(f"❌ Deployment blocked: Failed risk buckets: {bucket_names}\n")

        # Exit with 0 if --no-block is set, otherwise exit with 1
        if no_block:
            sys.stderr.write("ℹ️  CI mode: Reporting findings only (--no-block enabled)\n")
            sys.exit(0)  # Don't block pipeline
        else:
            sys.exit(1)  # Unsafe, block deployment
```

### CLI Flags

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--drift-threshold` | Choice | `high` | Fail if drift risk ≥ threshold |
| `--intent-threshold` | Choice | `high` | Fail if intent risk ≥ threshold |
| `--agent-threshold` | String | — | Set threshold for a custom agent (repeatable) |
| `--no-block` | Boolean | `False` | Report findings without blocking |

**Valid Choices:** `low`, `medium`, `high` (case-insensitive).

### Exit Codes

| Scenario | Exit Code | Meaning |
|----------|-----------|---------|
| All buckets pass | `0` | Safe to deploy |
| Any bucket fails + `--no-block` | `0` | Report only, don't block |
| Any bucket fails + no `--no-block` | `1` | Unsafe, block deployment |

**Note:** Exit code `1` used for unsafe deployments (not `2`).

**See:** [00-OVERVIEW.md](00-OVERVIEW.md) for complete exit code contract.

## Bucket Configuration

### Skipping Risk Buckets

As of version 1.6.0, individual risk buckets can be disabled using skip flags:

| Flag | Purpose |
|------|---------|
| `--skip-drift` | Skip infrastructure drift risk assessment |
| `--skip-intent` | Skip PR intent alignment risk assessment |
| `--skip-agent <id>` | Skip a custom agent by ID (repeatable) |

**Implementation:**
- Bucket registry: `bicep_whatif_advisor/ci/buckets.py` - Central registry with bucket metadata
- Dynamic evaluation: Only enabled buckets are evaluated by `evaluate_risk_buckets()`
- Dynamic prompt generation: LLM only receives prompts for enabled buckets
- Dynamic rendering: Output only displays enabled buckets

**Validation:** At least one bucket must remain enabled in CI mode. Attempting to skip all buckets results in exit code 2 with error message.

**Use Cases:**

| Scenario | Recommended Skip Flags |
|----------|----------------------|
| Infrastructure managed outside of code | `--skip-drift` |
| Automated dependency update PRs | `--skip-intent` |
| Focus only on drift detection | `--skip-intent` |
| Skip a specific custom agent | `--skip-agent <agent_id>` |

**Example:**
```bash
# Only evaluate infrastructure drift
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --skip-intent
```

### Bucket Registry (buckets.py)

**Purpose:** Centralize all bucket metadata in one location to eliminate hardcoded string duplication.

**Structure:**
```python
@dataclass
class RiskBucket:
    id: str                     # Internal identifier: "drift", "intent"
    display_name: str           # User-facing name: "Infrastructure Drift"
    description: str            # Brief description for help text
    prompt_instructions: str    # LLM prompt instructions for this bucket
    optional: bool = False      # True if bucket can be omitted (like intent)
    custom: bool = False        # True for user-created agents

RISK_BUCKETS: Dict[str, RiskBucket] = {
    "drift": RiskBucket(...),
    "intent": RiskBucket(...),
    # Custom agents are registered dynamically from --agents-dir
}
```

**Benefits:**
- **DRY:** Bucket names, descriptions, and prompts defined once
- **Maintainability:** Easy to add new buckets in the future
- **Consistency:** All modules use same bucket definitions from registry

**See:** `bicep_whatif_advisor/ci/buckets.py` for complete implementation.

## Example Workflows

### Example 1: All Buckets Pass

**Input:**
```json
{
  "risk_assessment": {
    "drift": {"risk_level": "low"},
    "intent": {"risk_level": "low"}
  }
}
```

**Thresholds:** `--drift-threshold high --intent-threshold high`

**Evaluation:**
- Drift: `low` < `high` → Pass
- Intent: `low` < `high` → Pass

**Result:** `(True, [], {...})` → Exit code 0

### Example 2: One Bucket Fails

**Input:**
```json
{
  "risk_assessment": {
    "drift": {"risk_level": "high"},
    "intent": {"risk_level": "low"}
  }
}
```

**Thresholds:** `--drift-threshold high --intent-threshold high`

**Evaluation:**
- Drift: `high` >= `high` → **Fail**
- Intent: `low` < `high` → Pass

**Result:** `(False, ["drift"], {...})` → Exit code 1

**Output:**
```
❌ Deployment blocked: Failed risk buckets: drift
```

### Example 3: Multiple Buckets Fail

**Input:**
```json
{
  "risk_assessment": {
    "drift": {"risk_level": "high"},
    "intent": {"risk_level": "medium"}
  }
}
```

**Thresholds:** `--drift-threshold high --intent-threshold low`

**Evaluation:**
- Drift: `high` >= `high` → **Fail**
- Intent: `medium` >= `low` → **Fail**

**Result:** `(False, ["drift", "intent"], {...})` → Exit code 1

**Output:**
```
❌ Deployment blocked: Failed risk buckets: drift, intent
```

### Example 4: Strict Thresholds

**Input:**
```json
{
  "risk_assessment": {
    "drift": {"risk_level": "low"},
    "intent": {"risk_level": "medium"}
  }
}
```

**Thresholds:** `--drift-threshold low --intent-threshold medium`

**Evaluation:**
- Drift: `low` >= `low` → **Fail**
- Intent: `medium` >= `medium` → **Fail**

**Result:** `(False, ["drift", "intent"], {...})` → Exit code 1

**Why?** ALL thresholds set to block even low risk.

### Example 5: No-Block Mode

**Input:** Same as Example 2 (high drift risk)

**Flag:** `--no-block`

**Result:** `(False, ["drift"], {...})` → Exit code 0 (not blocked)

**Output:**
```
⚠️  Warning: Failed risk buckets: drift (pipeline not blocked due to --no-block)
ℹ️  CI mode: Reporting findings only (--no-block enabled)
```

## Threshold Tuning Strategies

### Conservative (Default)

```bash
--drift-threshold high \
--intent-threshold high
```

**Philosophy:** Block only critical risks.

**Use Case:** Mature teams, high-confidence deployments.

### Balanced

```bash
--drift-threshold medium \
--intent-threshold high
```

**Philosophy:** Stricter on drift, lenient on intent alignment.

**Use Case:** General production deployments.

### Strict

```bash
--drift-threshold low \
--intent-threshold low
```

**Philosophy:** Block any risk, even minor.

**Use Case:** Highly regulated environments, mission-critical systems.

### With Custom Agents

```bash
--drift-threshold medium \
--intent-threshold high \
--agent-threshold compliance=medium \
--agent-threshold cost=high
```

**Philosophy:** Built-in buckets plus custom agent thresholds.

## Benefits of Multi-Bucket Model

### 1. Separation of Concerns

- **Drift** - Infrastructure health
- **Intent** - Change control
- **Custom agents** - Additional risk dimensions (operations, compliance, cost, etc.)

Each bucket addresses a distinct risk dimension.

### 2. Independent Tuning

Teams can customize thresholds per bucket:
- Strict on drift detection (prevent out-of-band changes)
- Lenient on new resources (operations bucket)
- Moderate on intent alignment

### 3. Clear Failure Reasoning

```
❌ Deployment blocked: Failed risk buckets: drift
```

vs.

```
❌ Deployment blocked: risk score 7.5/10
```

**First is actionable, second is opaque.**

### 4. Flexible Rollout

Progressive strictness:
1. Start: All thresholds `high` (blocks only critical issues)
2. Tune: Lower thresholds based on false positives
3. Optimize: Custom thresholds per bucket

## Design Principles

### 1. Fail-Safe Defaults

- Missing risk assessment → Default to safe (with warning)
- Invalid risk level → Default to `"low"`
- Missing intent bucket → Skip (not counted as failure)

**Philosophy:** Err on side of allowing deployments when data incomplete.

### 2. AND Logic for Safety

**All buckets must pass for deployment to proceed.**

**Why?** Ensures comprehensive safety check across all dimensions.

**Trade-off:** More strict (higher false positive rate) vs. more thorough.

### 3. Explicit Threshold Comparison

```python
risk_index >= threshold_index
```

Not:
```python
risk_level == "high" and threshold == "high"
```

**Benefits:**
- Ordinal comparison (low < medium < high)
- Handles all threshold combinations
- Clear semantics (≥ means "at least this risky")

### 4. Graceful Intent Bucket Handling

```python
if intent_bucket is not None:
    # Evaluate
```

Not:
```python
intent_risk = intent_bucket.get("risk_level")  # Crashes if intent_bucket is None
```

**Graceful handling** when intent bucket not evaluated (no PR metadata).

## Performance Characteristics

- **Time complexity:** O(n) - Linear in number of enabled buckets
- **Space complexity:** O(1) - Returns tuple, no additional allocations
- **Bottleneck:** None - trivial computation

**Dominates:** LLM API call, not risk evaluation.

## Testing Strategy

### Unit Tests

```python
# Test threshold comparison
assert _exceeds_threshold("low", "high") == False
assert _exceeds_threshold("high", "high") == True
assert _exceeds_threshold("medium", "low") == True

# Test risk validation
assert _validate_risk_level("HIGH") == "high"
assert _validate_risk_level("invalid") == "low"

# Test bucket evaluation
data = {
    "risk_assessment": {
        "drift": {"risk_level": "high"},
    }
}
is_safe, failed, _ = evaluate_risk_buckets(data, ["drift"], "high", "high")
assert is_safe == False
assert "drift" in failed
```

### Integration Tests

- Real LLM responses with varied risk levels
- All threshold combinations
- Missing/invalid fields
- Intent bucket present/absent

## Future Improvements

1. **Custom bucket weights:** Not all buckets equal importance
2. **Additional buckets:** Cost, compliance, blast radius
3. **Machine learning:** Learn optimal thresholds from deployment history
4. **Risk trends:** Track risk over time, alert on increasing trends

## Next Steps

For details on related modules:
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - How LLM generates risk assessments
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - How risk buckets are evaluated in CLI
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - How risk buckets are displayed
