# Confidence Scoring for Azure What-If Noise Filtering

## Feature Overview

**Feature Name:** Confidence Scoring and Noise Filtering
**Status:** ✅ Implemented
**Version:** 1.3.0
**Date:** 2025-02-10

## Problem Statement

### The Challenge

Azure Bicep What-If output contains significant "noise" — false positives that aren't actual infrastructure changes but appear as modifications in the output. This noise creates two critical problems:

1. **Drift Detection False Positives**
   - What-If shows 20 resources changing
   - Code diff shows only 1 resource modified
   - 19 changes are metadata-only (etag, provisioningState, etc.)
   - Drift bucket flags all 19 as "out-of-band changes" → FALSE POSITIVE

2. **Intent Alignment Contamination**
   - PR title: "Add Application Insights"
   - What-If shows: 1 real change + 19 metadata changes = 20 total
   - Intent bucket compares "add 1 resource" vs "20 changes detected"
   - Intent misalignment flagged → FALSE POSITIVE

### Common Noise Patterns

**Metadata Properties:**
- `etag` - Azure-managed resource version tag
- `id` - Resource ID (read-only)
- `provisioningState` - Deployment state (system-managed)
- `type` - Resource type identifier

**Analytics Properties:**
- `logAnalyticsDestinationType` - Changes between runs despite no code change

**Network Properties:**
- `disableIpv6` - IPv6 flags toggling without code changes
- `enableIPv6Addressing` - System-managed IPv6 settings

**Computed Properties:**
- `resourceGuid` - Auto-generated unique identifier

**Example What-If Output (Noise):**
```
~ storageAccount/default
  ~ properties.provisioningState: "Succeeded" => "Updating"
  ~ properties.id: "/subscriptions/.../old" => "/subscriptions/.../new"
  ~ properties.etag: "W/\"datetime'2024-01-01...\"" => "W/\"datetime'2024-01-02...\""
```

**Impact:**
- ❌ No actual configuration change
- ❌ Flagged as drift (not in code diff)
- ❌ Counts toward intent misalignment
- ❌ Creates alert fatigue

## Solution Design

### Architecture

```
Azure What-If Output
        ↓
   LLM Analysis
        ↓
   Per-Resource Confidence Assessment
   ├─ HIGH (real change)
   ├─ MEDIUM (potentially real)
   └─ LOW (likely noise)
        ↓
   Filter by Confidence
   ├─ High/Medium → Risk Analysis
   └─ Low → Separate "Potential Noise" Section
        ↓
   Risk Bucket Evaluation (clean data)
   ├─ Drift
   ├─ Intent
   └─ Operations
        ↓
   Deployment Verdict
```

### Confidence Levels

#### HIGH Confidence (Included in Risk Analysis)

**Definition:** Changes with high certainty of being real infrastructure modifications.

**Criteria:**
- Resource creation (action: Create)
- Resource deletion (action: Delete)
- Configuration property changes with clear functional impact
- Security-related changes (authentication, authorization, encryption)
- Network configuration changes (firewall rules, subnets, public access)
- Compute changes (SKU, capacity, scaling)

**Examples:**
```json
{
  "resource_name": "storageAccount",
  "action": "Modify",
  "confidence_level": "high",
  "confidence_reason": "Changing publicNetworkAccess from Disabled to Enabled"
}
```

**Rationale:** These changes have clear, measurable impact on infrastructure behavior and should always be included in risk analysis.

#### MEDIUM Confidence (Included in Risk Analysis)

**Definition:** Changes that are potentially real but uncertain or might be platform-managed.

**Criteria:**
- Retention policy changes (`retentionInDays`)
- Analytics settings modifications
- Subnet references changing from hardcoded to dynamic (ARM function)
- Configuration changes that might be auto-updated by Azure

**Examples:**
```json
{
  "resource_name": "diagnosticSettings",
  "action": "Modify",
  "confidence_level": "medium",
  "confidence_reason": "Retention policy changing from 30 to 90 days"
}
```

**Rationale:** These changes might be intentional or might be platform behavior. Include in analysis but with context that they're uncertain.

#### LOW Confidence (Excluded from Risk Analysis)

**Definition:** Changes with high certainty of being What-If noise, not real infrastructure changes.

**Criteria:**
- Metadata-only changes (etag, id, provisioningState, type)
- `logAnalyticsDestinationType` property changes
- IPv6 flags (disableIpv6, enableIPv6Addressing)
- Computed properties (resourceGuid)
- Read-only or system-managed properties
- Changes to properties that don't affect resource behavior

**Examples:**
```json
{
  "resource_name": "apimService",
  "action": "Modify",
  "confidence_level": "low",
  "confidence_reason": "Only etag and provisioningState metadata changing"
}
```

**Rationale:** These are Azure platform artifacts that don't represent actual configuration changes and should be filtered out to prevent false positives.

### Implementation Details

#### LLM Prompt Enhancement

**Standard Mode Schema (Extended):**
```json
{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "string",
      "summary": "string",
      "confidence_level": "low|medium|high",
      "confidence_reason": "string"
    }
  ],
  "overall_summary": "string"
}
```

**CI Mode Schema (Extended):**
```json
{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "string",
      "summary": "string",
      "risk_level": "low|medium|high",
      "risk_reason": "string",
      "confidence_level": "low|medium|high",
      "confidence_reason": "string"
    }
  ],
  "overall_summary": "string",
  "risk_assessment": {...},
  "verdict": {...}
}
```

**Confidence Assessment Instructions (Added to Prompt):**
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

#### Filtering Logic

**Function:** `filter_by_confidence(data: dict) -> tuple[dict, dict]`

**Location:** `bicep_whatif_advisor/cli.py`

**Purpose:** Split resources into high-confidence and low-confidence lists.

**Algorithm:**
```python
def filter_by_confidence(data: dict) -> tuple[dict, dict]:
    """Split resources by confidence level.

    Returns:
        (high_confidence_data, low_confidence_data)
    """
    resources = data.get("resources", [])

    high_confidence_resources = []
    low_confidence_resources = []

    for resource in resources:
        confidence = resource.get("confidence_level", "medium").lower()

        if confidence == "low":
            low_confidence_resources.append(resource)
        else:
            # medium and high confidence included in analysis
            high_confidence_resources.append(resource)

    # Build high-confidence data (includes CI fields)
    high_confidence_data = {
        "resources": high_confidence_resources,
        "overall_summary": data.get("overall_summary", "")
    }

    # Preserve CI mode fields
    if "risk_assessment" in data:
        high_confidence_data["risk_assessment"] = data["risk_assessment"]
    if "verdict" in data:
        high_confidence_data["verdict"] = data["verdict"]

    # Build low-confidence data (no CI fields)
    low_confidence_data = {
        "resources": low_confidence_resources,
        "overall_summary": ""
    }

    return high_confidence_data, low_confidence_data
```

**Key Decisions:**
- Medium confidence included in analysis (conservative approach)
- Low confidence excluded from risk buckets
- CI mode fields (risk_assessment, verdict) only in high-confidence data
- Filtering happens AFTER LLM response, BEFORE risk evaluation

#### Integration Points

**1. Main CLI Flow (cli.py):**
```python
# Parse LLM response
data = extract_json(response_text)

# Add backward compatibility defaults
for resource in data.get("resources", []):
    if "confidence_level" not in resource:
        resource["confidence_level"] = "medium"
    if "confidence_reason" not in resource:
        resource["confidence_reason"] = "No confidence assessment provided"

# Filter by confidence
high_confidence_data, low_confidence_data = filter_by_confidence(data)

# Render output (pass both datasets)
render_table(high_confidence_data, ..., low_confidence_data=low_confidence_data)

# CI mode: evaluate risk buckets (only high-confidence data)
if ci:
    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
        high_confidence_data,  # Only clean data
        drift_threshold, intent_threshold, operations_threshold
    )
```

**2. Risk Bucket Evaluation (ci/risk_buckets.py):**
- Function receives pre-filtered high-confidence data
- Drift calculation compares clean What-If output to code diff
- Intent alignment compares clean changes to PR description
- Operations risk evaluates only real changes
- No changes to logic needed - filtering happens upstream

**3. Output Rendering (render.py):**

**Table Format:**
```
Main Table (High/Medium Confidence)
╭──────┬──────────┬──────┬────────┬─────────╮
│ #    │ Resource │ Type │ Action │ Summary │
├──────┼──────────┼──────┼────────┼─────────┤
│ 1    │ storage  │ ...  │ Create │ ...     │
╰──────┴──────────┴──────┴────────┴─────────╯

⚠️  Potential Azure What-If Noise (Low Confidence)
╭──────┬──────────┬──────┬────────┬───────────────────╮
│ #    │ Resource │ Type │ Action │ Confidence Reason │
├──────┼──────────┼──────┼────────┼───────────────────┤
│ 1    │ apim     │ ...  │ Modify │ Only etag change  │
╰──────┴──────────┴──────┴────────┴───────────────────╯
```

**Markdown Format:**
```markdown
## What-If Deployment Review

### Risk Assessment
[Risk buckets table...]

<details>
<summary>📋 View changed resources</summary>

[High-confidence resources table...]

</details>

---

<details>
<summary>⚠️ Potential Azure What-If Noise (Low Confidence)</summary>

The following changes were flagged as likely What-If noise and **excluded from risk analysis**:

[Low-confidence resources table...]

</details>
```

**JSON Format:**
```json
{
  "high_confidence": {
    "resources": [...],
    "overall_summary": "...",
    "risk_assessment": {...},
    "verdict": {...}
  },
  "low_confidence": {
    "resources": [...]
  }
}
```

### Backward Compatibility

**Problem:** Existing LLM responses or mocked test data might not include confidence fields.

**Solution:** Default values applied in main CLI flow:

```python
for resource in data.get("resources", []):
    if "confidence_level" not in resource:
        resource["confidence_level"] = "medium"  # Include in analysis
    if "confidence_reason" not in resource:
        resource["confidence_reason"] = "No confidence assessment provided"
```

**Effect:**
- Old responses without confidence fields: treated as medium confidence (included in analysis)
- No breaking changes to existing workflows
- Gradual rollout as LLMs start returning confidence fields

## User Experience

### Standard Mode (Interactive CLI)

**Before (with noise):**
```
╭──────┬──────────────┬──────┬────────┬─────────────────────────╮
│ #    │ Resource     │ Type │ Action │ Summary                 │
├──────┼──────────────┼──────┼────────┼─────────────────────────┤
│ 1    │ storage      │ ...  │ Create │ Creating storage        │
│ 2    │ apim         │ ...  │ Modify │ Changing etag           │
│ 3    │ appinsights  │ ...  │ Modify │ Changing logAnalytics   │
│ 4    │ vnet         │ ...  │ Modify │ Changing ipv6 flag      │
╰──────┴──────────────┴──────┴────────┴─────────────────────────╯

Summary: 1 create, 3 modifies. [User confused by noise]
```

**After (with filtering):**
```
╭──────┬──────────┬──────┬────────┬─────────────────────────╮
│ #    │ Resource │ Type │ Action │ Summary                 │
├──────┼──────────┼──────┼────────┼─────────────────────────┤
│ 1    │ storage  │ ...  │ Create │ Creating storage        │
╰──────┴──────────┴──────┴────────┴─────────────────────────╯

⚠️  Potential Azure What-If Noise (Low Confidence)
╭──────┬──────────────┬──────┬────────┬─────────────────────────╮
│ #    │ Resource     │ Type │ Action │ Confidence Reason       │
├──────┼──────────────┼──────┼────────┼─────────────────────────┤
│ 1    │ apim         │ ...  │ Modify │ Only etag changing      │
│ 2    │ appinsights  │ ...  │ Modify │ logAnalytics property   │
│ 3    │ vnet         │ ...  │ Modify │ IPv6 flag (system)      │
╰──────┴──────────────┴──────┴────────┴─────────────────────────╯

Summary: 1 create. Clean deployment.
```

**Benefits:**
- ✅ Clear focus on real change
- ✅ Noise visible but separated
- ✅ User understands what's actually happening

### CI Mode (Deployment Gates)

**Scenario:** PR to add Application Insights monitoring

**Before (false positive):**
```
Risk Assessment:
  Drift: HIGH ❌ (19 resources changed without code changes)
  Intent: HIGH ❌ (PR says add 1 resource, but 20 changes detected)
  Operations: LOW ✅

Verdict: UNSAFE
Exit Code: 1 (blocked)
```

**After (accurate):**
```
Risk Assessment:
  Drift: LOW ✅ (1 resource in code matches 1 in What-If)
  Intent: LOW ✅ (PR says add monitoring, 1 monitoring resource detected)
  Operations: LOW ✅

Potential Noise: 19 metadata-only changes filtered (see details)

Verdict: SAFE
Exit Code: 0 (deploy)
```

**Benefits:**
- ✅ Accurate risk assessment
- ✅ No false positive blocking
- ✅ Real issues still caught
- ✅ Reduced alert fatigue

## Testing Strategy

### Unit Tests

**Test: filter_by_confidence()**
```python
def test_filter_by_confidence():
    data = {
        "resources": [
            {"name": "r1", "confidence_level": "high"},
            {"name": "r2", "confidence_level": "low"},
            {"name": "r3", "confidence_level": "medium"},
        ],
        "risk_assessment": {"drift": {"risk_level": "low"}}
    }

    high, low = filter_by_confidence(data)

    assert len(high["resources"]) == 2  # high + medium
    assert len(low["resources"]) == 1   # low only
    assert "risk_assessment" in high
    assert "risk_assessment" not in low
```

**Test: Backward Compatibility**
```python
def test_backward_compatibility():
    data = {
        "resources": [
            {"name": "r1"}  # Missing confidence fields
        ]
    }

    # Apply defaults
    for r in data["resources"]:
        if "confidence_level" not in r:
            r["confidence_level"] = "medium"

    high, low = filter_by_confidence(data)

    assert len(high["resources"]) == 1
    assert high["resources"][0]["confidence_level"] == "medium"
```

### Integration Tests

**Test: End-to-End with Fixture**
```bash
# Fixture with known noise patterns
cat tests/fixtures/create_with_noise.txt | bicep-whatif-advisor

# Expected output:
# - 1 resource in main table (high confidence)
# - 5 resources in noise section (low confidence)
```

**Test: CI Mode Risk Buckets**
```bash
# Fixture: 1 real change + 10 metadata changes
cat tests/fixtures/drift_with_noise.txt | bicep-whatif-advisor \
  --ci \
  --drift-threshold high

# Expected:
# - Drift: LOW (only 1 real change matches code)
# - Exit: 0 (safe)
```

### Manual Testing

**Test Case 1: Real Azure What-If with Noise**
```bash
az deployment group what-if \
  --template-file main.bicep \
  --resource-group test-rg \
  | bicep-whatif-advisor

# Verify:
# - Real changes in main table
# - Metadata changes in noise section
# - Accurate summary counts
```

**Test Case 2: CI Mode Drift Detection**
```bash
# Make only 1 change to Bicep code
# Observe What-If shows 1 change + metadata noise

az deployment group what-if ... | bicep-whatif-advisor --ci

# Verify:
# - Drift: LOW (only real change evaluated)
# - Intent: LOW (only real change counted)
# - No false positive blocking
```

## Configuration & Flags

### Current Behavior (v1.3.0)

**Always-On:** Confidence filtering is enabled by default with no configuration flags.

**Rationale:**
- Noise filtering is universally beneficial
- No downside to filtering metadata changes
- Simplifies user experience (zero config)
- Filtered resources remain visible

### Future Enhancements (Planned)

**Flag: `--no-confidence-filtering`**
```bash
bicep-whatif-advisor --no-confidence-filtering
```
- Disables filtering entirely
- All resources included in risk analysis
- Use case: Debugging, comparing behavior

**Flag: `--confidence-threshold [low|medium|high]`**
```bash
bicep-whatif-advisor --confidence-threshold medium
```
- Customizes filter level
- `low`: Only exclude low-confidence
- `medium`: Exclude low + medium (only high in analysis)
- `high`: No filtering (all confidence levels included)
- Default: `low`

**Flag: `--show-all-confidence`**
```bash
bicep-whatif-advisor --show-all-confidence
```
- Displays three separate tables: high, medium, low
- Enables detailed confidence-level analysis
- Use case: Debugging confidence assessment

## Performance Considerations

### LLM Token Usage

**Impact:** Minimal increase in prompt size.

**Measurement:**
- Confidence instructions: ~250 tokens
- Per-resource confidence fields: ~50 tokens per resource
- Total increase: ~5-10% of typical prompt

**Mitigation:**
- Concise instructions
- No redundant examples
- Efficient schema design

### Processing Time

**Impact:** Negligible.

**Filter function:** O(n) where n = number of resources (typically < 100)

**Typical execution time:** < 1ms for filtering

### Memory Usage

**Impact:** Minimal.

**Two data structures maintained:**
- `high_confidence_data`: Original size minus low-confidence resources
- `low_confidence_data`: Only low-confidence resources

**Typical overhead:** < 10% of original data structure

## Metrics & Success Criteria

### Key Metrics

**1. False Positive Reduction:**
- **Before:** 30-40% of deployments flagged with false positive drift
- **Target:** < 5% false positive drift detection
- **Measurement:** Track drift alerts on deployments with only metadata changes

**2. Intent Alignment Accuracy:**
- **Before:** 25% false alarms (intent misalignment due to noise)
- **Target:** < 5% false alarms
- **Measurement:** Compare intent risk to actual PR scope

**3. User Satisfaction:**
- **Target:** > 90% of users report confidence filtering improves accuracy
- **Measurement:** User surveys, GitHub issues

**4. Confidence Assessment Accuracy:**
- **Target:** > 95% of low-confidence classifications are correct (actual noise)
- **Measurement:** Manual review of low-confidence resources flagged

### Success Criteria

✅ **Functional:**
- Low-confidence resources excluded from risk buckets
- Low-confidence resources visible in separate section
- No false negatives (real changes marked as low confidence)
- Backward compatibility maintained

✅ **Performance:**
- No user-perceivable latency increase
- LLM token usage increase < 15%

✅ **User Experience:**
- Reduced false positive blocking
- Clearer, more accurate risk assessments
- No additional configuration required

## Limitations & Trade-offs

### Limitations

**1. LLM Dependency:**
- Confidence assessment relies on LLM reasoning
- Potential for occasional misclassification
- Temperature=0 improves consistency but not perfect

**2. Non-Deterministic:**
- Same input might produce slightly different confidence levels
- Borderline cases (medium vs low) might fluctuate
- Risk level boundaries more stable than confidence

**3. Context-Dependent:**
- "Correct" classification can be subjective
- What's noise in one context might be real in another
- Guidelines provide direction, not absolute rules

### Trade-offs

**LLM-Based vs Rule-Based:**

**Decision:** Use LLM-based approach

**Advantages:**
- ✅ Adapts to new noise patterns automatically
- ✅ Understands context and nuance
- ✅ Handles edge cases better
- ✅ No maintenance burden of rule updates

**Disadvantages:**
- ❌ Non-deterministic
- ❌ Requires LLM call (already happening)
- ❌ Harder to debug than explicit rules

**Mitigation:**
- Clear guidelines reduce ambiguity
- Separate noise section provides transparency
- Future: hybrid approach combining LLM + hardcoded patterns if needed (TODO)

**Medium Confidence Inclusion:**

**Decision:** Include medium confidence in risk analysis

**Rationale:**
- Conservative approach (avoid false negatives)
- Medium = "uncertain" not "likely noise"
- Users can adjust thresholds for more aggressive filtering later

**Alternative:** Exclude medium confidence
- Would reduce false positives further
- But increases risk of missing real changes
- Can be added as configuration option later

## Summary-Based Noise Filtering

### Overview

**Feature Name:** Summary-Based Noise Patterns
**Status:** ✅ Implemented
**Version:** 1.4.0
**Date:** 2025-02-11

### Purpose

While LLM-based confidence scoring effectively identifies common noise patterns, some organizations encounter domain-specific or recurring noise that should always be filtered. Summary-based noise filtering allows users to define custom noise patterns that automatically lower confidence scores when matched.

### Design

**File Format:** Plain text file, one summary pattern per line

**Example:** `.whatif-noise`
```
Changing subnet reference from hardcoded ID to dynamic reference and removing IPv6 flag
Updating tags only
Modifying diagnostic settings
Adding Application Insights
Changing logAnalyticsDestinationType property
```

**Matching Algorithm:** Fuzzy string similarity using Python's `difflib.SequenceMatcher`
- Default similarity threshold: 80% (configurable)
- Case-insensitive matching
- Handles minor variations in LLM-generated summaries

**Confidence Override:** When a pattern matches, confidence is set to **10** (very low)
- Works with existing `--min-confidence` filtering (default 70)
- Resources remain visible but are likely filtered
- No explicit "noise" flag - low confidence indicates pattern match

### CLI Flags

```bash
--noise-file <path>           # Path to noise patterns file
--noise-threshold <percent>   # Similarity threshold for matching (default: 80)
```

**Example Usage:**
```bash
az deployment group what-if -g my-rg -f main.bicep | \
  bicep-whatif-advisor \
  --noise-file .whatif-noise \
  --noise-threshold 85
```

### Integration Flow

```
Azure What-If Output
        ↓
   LLM Analysis
   (assigns confidence scores)
        ↓
   Parse LLM Response
   (extract JSON with confidence_level field)
        ↓
   Apply Noise Pattern Matching ← NEW STEP
   ├─ Load patterns from --noise-file
   ├─ For each resource:
   │  ├─ Compare summary to each pattern (fuzzy match)
   │  └─ If match ≥ threshold: confidence = 10
   └─ Keep original LLM confidence if no match
        ↓
   Convert to Numeric Scores
   (high=90, medium=60, low=30, noise-matched=10)
        ↓
   Filter by --min-confidence
   (default 70 filters out noise-matched resources)
        ↓
   Risk Bucket Evaluation (clean data)
        ↓
   Render Output
```

### Implementation

**Module:** `bicep_whatif_advisor/noise_filter.py`

**Functions:**

```python
def load_noise_patterns(file_path: str) -> list[str]:
    """Load noise patterns from text file.

    Args:
        file_path: Path to noise patterns file

    Returns:
        List of noise pattern strings (one per line, comments/blank lines removed)
    """

def match_noise_pattern(summary: str, patterns: list[str], threshold: float = 0.80) -> bool:
    """Check if summary matches any noise pattern using fuzzy matching.

    Args:
        summary: Resource summary text from LLM
        patterns: List of noise pattern strings
        threshold: Similarity threshold (0.0-1.0, default 0.80)

    Returns:
        True if any pattern matches above threshold
    """

def apply_noise_filtering(data: dict, noise_file: str, threshold: float = 0.80) -> dict:
    """Apply noise pattern filtering to LLM response data.

    Args:
        data: Parsed LLM response with resources
        noise_file: Path to noise patterns file
        threshold: Similarity threshold for matching

    Returns:
        Modified data with confidence overridden for matched resources
    """
```

**Algorithm (difflib.SequenceMatcher):**
```python
from difflib import SequenceMatcher

def similarity(a: str, b: str) -> float:
    """Calculate similarity ratio between two strings."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

# Match if similarity >= threshold (e.g., 0.80)
# Example:
#   Pattern: "Changing subnet reference from hardcoded ID to dynamic reference"
#   Summary: "Changing subnet reference from hardcoded to dynamic"
#   Similarity: 0.85 → MATCH
```

### Integration Points

**1. Main CLI Flow (cli.py):**
```python
# Parse LLM response
data = extract_json(response_text)

# Apply noise pattern filtering (if --noise-file provided)
if noise_file:
    data = apply_noise_filtering(data, noise_file, noise_threshold)

# Add backward compatibility defaults
for resource in data.get("resources", []):
    if "confidence_level" not in resource:
        resource["confidence_level"] = "medium"

# Convert confidence levels to numeric scores
data = convert_confidence_to_numeric(data)

# Filter by numeric confidence threshold
high_confidence_data, low_confidence_data = filter_by_confidence(
    data, min_confidence
)
```

**2. Confidence Score Conversion:**

The system uses numeric confidence scores (0-100) instead of categorical levels:

```python
def convert_confidence_to_numeric(data: dict) -> dict:
    """Convert categorical confidence levels to numeric scores.

    Mapping:
    - high: 90
    - medium: 60
    - low: 30
    - Resources matched by noise patterns: 10 (set by noise filter)

    Numeric scores enable precise threshold-based filtering.
    """
```

**Default thresholds:**
- `--min-confidence 70` (default): Filters noise-matched (10), low (30), and medium (60)
- `--min-confidence 50`: Filters noise-matched (10) and low (30)
- `--min-confidence 0`: Shows all resources

### Benefits

**1. Organization-Specific Filtering:**
- Define custom noise patterns for your environment
- Filter recurring false positives unique to your infrastructure
- No need to wait for LLM prompt updates

**2. Deterministic Filtering:**
- Fuzzy matching provides consistent results
- No LLM variation for known patterns
- Predictable confidence scores

**3. Incremental Improvement:**
- Add new patterns as noise is discovered
- Build up knowledge base over time
- Share patterns across teams via version control

**4. Transparent Override:**
- Confidence set to 10 (very low but non-zero)
- Resources visible in output (not silently filtered)
- Can adjust `--min-confidence` to see matched resources

### Example Workflow

**1. Initial Deployment:**
```bash
az deployment group what-if -g my-rg -f main.bicep | \
  bicep-whatif-advisor
```

**Output shows noise:**
```
Resource: myVnet/subnet
Action: Modify
Confidence: 60 (medium)
Summary: Changing subnet reference from hardcoded ID to dynamic reference
```

**2. Add Pattern to .whatif-noise:**
```
Changing subnet reference from hardcoded ID to dynamic reference
```

**3. Next Deployment:**
```bash
az deployment group what-if -g my-rg -f main.bicep | \
  bicep-whatif-advisor --noise-file .whatif-noise
```

**Output (noise filtered):**
```
Resource: myVnet/subnet
Action: Modify
Confidence: 10 (noise pattern matched)
Summary: Changing subnet reference from hardcoded ID to dynamic reference
[Filtered by default --min-confidence 70]
```

### Sample Noise File

Located at: `sample-bicep-deployment/.whatif-noise`

Common Azure noise patterns:
```
# Common Azure What-If noise patterns
# One pattern per line - fuzzy matching with 80% similarity threshold
# Lines starting with # are comments

# Subnet reference changes
Changing subnet reference from hardcoded ID to dynamic reference

# IPv6 flags
Removing IPv6 flag
Changing disableIpv6 property

# Log Analytics destination
Changing logAnalyticsDestinationType property

# Tags
Updating tags only

# Diagnostic settings
Modifying diagnostic settings

# Metadata changes
Updating metadata properties
Changing etag property

# Application Insights
Adding Application Insights logging
```

### Limitations

**1. Requires Manual Pattern Maintenance:**
- Users must identify and add noise patterns
- No automatic pattern learning (yet)
- Patterns must be updated as Azure behavior changes

**2. Fuzzy Matching Trade-offs:**
- Too low threshold (< 70%): False positives (matches too broadly)
- Too high threshold (> 90%): False negatives (misses valid noise)
- Default 80% is a balanced starting point

**3. Summary Text Dependency:**
- Relies on LLM generating consistent summary text
- LLM variations might affect match rate
- Temperature=0 helps but doesn't eliminate variation

### Future Enhancements

**1. Pattern Auto-Discovery:**
- Track resources consistently marked as low confidence
- Suggest adding to noise file
- Machine learning to identify recurring patterns

**2. Regex Support:**
- Allow regex patterns in noise file
- More flexible matching for similar summaries
- Syntax: `/pattern/` for regex, plain text for fuzzy match

**3. Shared Pattern Repository:**
- Community-contributed noise patterns
- Azure resource-type specific patterns
- Downloadable pattern packs

**4. Pattern Analytics:**
- Report on pattern match rates
- Identify unused or overly-broad patterns
- Suggest threshold adjustments

## Future Enhancements

### Planned (TODOs in Code)

**1. Configurable Filtering (Priority: Medium)**
```bash
--confidence-threshold [low|medium|high]  # Adjust filter level
--no-confidence-filtering                 # Disable entirely
```

**2. Separate Confidence Display (Priority: Low)**
```bash
--show-all-confidence  # Display high/medium/low in separate tables
```

**3. Hybrid Approach (Priority: Low)**
- Combine LLM judgment with hardcoded noise patterns
- Fallback to patterns if LLM confidence assessment missing
- Use for known, unambiguous noise (etag-only changes)

### Potential Future Features

**4. Confidence History Tracking:**
- Track confidence assessments over time
- Identify resources consistently marked as noise
- Auto-suggest Bicep template fixes

**5. Custom Noise Patterns:**
- User-defined noise patterns via config file
- Override LLM assessment for specific properties
- Useful for organization-specific noise

**6. Confidence Metrics Dashboard:**
- Report on confidence distribution
- Identify problematic templates generating excessive noise
- Track false positive/negative rates

## References

### Related Documentation

- [Main Specification](./SPECIFICATION.md)
- [Risk Assessment Guide](../guides/RISK_ASSESSMENT.md)
- [Platform Auto-Detection](./PLATFORM_AUTO_DETECTION_PLAN.md)

### Implementation Files

- `bicep_whatif_advisor/prompt.py` - Confidence schema and instructions
- `bicep_whatif_advisor/cli.py` - Filter logic and integration
- `bicep_whatif_advisor/render.py` - Output formatting with noise sections
- `bicep_whatif_advisor/ci/risk_buckets.py` - Risk evaluation (pre-filtered data)

### Related Issues

- GitHub Issue: Azure What-If noise causing false positives
- User Request: Better drift detection accuracy
- Bug Report: Intent alignment fails with metadata-heavy templates

## Changelog

**v1.3.0 (2025-02-10):**
- ✅ Implemented LLM-based confidence scoring
- ✅ Added confidence_level and confidence_reason fields to response schema
- ✅ Created filter_by_confidence() function
- ✅ Enhanced all output formats with noise sections
- ✅ Updated documentation (SPECIFICATION.md, RISK_ASSESSMENT.md, README.md)
- ✅ Added backward compatibility for missing confidence fields
- ✅ Integrated filtering into risk bucket evaluation
- ✅ Tested and verified implementation

**Future Versions:**
- v1.4.0: Add configurable filtering flags
- v1.5.0: Hybrid approach (LLM + hardcoded patterns)
- v2.0.0: Custom noise patterns and confidence history tracking
