# 06 - Noise Filtering (Confidence-Based)

## Purpose

The noise filtering system reduces false positives from Azure What-If output by combining:
1. **LLM confidence scoring** - LLM assigns confidence levels to each resource change
2. **Pattern matching** - User-provided patterns matched against LLM summaries using fuzzy matching
3. **Split rendering** - High-confidence and low-confidence resources displayed separately
4. **CI mode re-analysis** - Risk assessment recalculated after filtering to prevent stale verdicts

**Files:**
- `bicep_whatif_advisor/noise_filter.py` (120 lines) - Pattern matching and filtering
- `bicep_whatif_advisor/cli.py` (lines 81-127, 382-408, 410-478) - Confidence splitting and re-analysis

## Problem Statement

Azure What-If output contains significant noise:
- Spurious property changes (IPv6 flags, metadata fields)
- Read-only computed properties (resourceGuid, etag)
- Platform-managed settings (logAnalyticsDestinationType)
- Cosmetic changes that don't affect functionality

**Impact:** False positives in CI mode can block safe deployments.

**Solution:** Two-tier filtering:
1. LLM judges confidence for each resource (high/medium/low)
2. Optional user-provided patterns override LLM confidence

## Architecture

```
LLM Response
    ↓
noise_filter.py:apply_noise_filtering()
    ├── Load patterns from file
    ├── For each resource:
    │   ├── Match summary against patterns (fuzzy)
    │   └── If match: override confidence_level to "noise"
    └── Return modified data
    ↓
cli.py:filter_by_confidence()
    ├── Split resources by confidence_level
    ├── high/medium → high_confidence_data
    └── low/noise → low_confidence_data
    ↓
[If CI mode and resources filtered]
    ↓
cli.py: Re-analysis (lines 410-478)
    ├── Reconstruct What-If output (high-confidence only)
    ├── Re-call LLM
    └── Update risk_assessment and verdict
    ↓
Separate rendering
    ├── high_confidence_data → Main table
    └── low_confidence_data → "Potential Noise" section
```

## Confidence Levels

### LLM-Assigned Levels

Defined in prompt (see [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md)):

| Level | Meaning | Examples |
|-------|---------|----------|
| **high** | Real, meaningful changes | Resource creation/deletion, security changes, networking changes |
| **medium** | Potentially real but uncertain | Retention policies, dynamic subnet references, platform-managed configs |
| **low** | Likely What-If noise | Metadata changes (etag, id), IPv6 flags, computed properties |

### Pattern-Matched Level

```python
resource["confidence_level"] = "noise"
```

**Special value:** "noise" indicates pattern-matched resource (treated as lower than "low").

## Noise Pattern File Format

### File Structure

```
# Noise patterns file
# Lines starting with # are comments
# Blank lines are ignored

Change to IPv6 settings
Change to metadata properties
Update to system-managed configuration
Modification of read-only property
```

**Format:**
- One pattern per line
- Comments start with `#`
- Blank lines ignored
- Case-insensitive matching

### Example Pattern File

```
# IPv6-related noise
Change to IPv6 addressing
IPv6 flag modification
Update IPv6 configuration

# Metadata noise
Update to etag property
Change to resourceGuid
Modification of provisioningState

# Log Analytics noise
Change to logAnalyticsDestinationType
```

## Pattern Matching Implementation

### load_noise_patterns() (lines 12-38)

```python
def load_noise_patterns(file_path: str) -> list[str]:
    """Load noise patterns from a text file.

    Returns:
        List of noise pattern strings (one per line, comments and blank lines removed)

    Raises:
        FileNotFoundError: If file_path does not exist
        IOError: If file cannot be read
    """
    patterns = []
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Noise patterns file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            # Remove whitespace and skip comments/empty lines
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    return patterns
```

**Features:**
- Strip whitespace from each line
- Filter out comments (`#` prefix)
- Filter out blank lines
- Return list of clean pattern strings

**Error Handling:**
- `FileNotFoundError` if file doesn't exist
- `IOError` if file can't be read (permissions, encoding issues)

### calculate_similarity() (lines 41-54)

```python
def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two strings.

    Uses Python's difflib.SequenceMatcher for fuzzy string matching.
    Comparison is case-insensitive.

    Returns:
        Similarity ratio between 0.0 and 1.0 (1.0 = identical)
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
```

**Algorithm:** Python's `difflib.SequenceMatcher`
- Uses Ratcliff/Obershelp algorithm
- Returns ratio of matching characters to total characters
- Range: 0.0 (completely different) to 1.0 (identical)

**Case Handling:** Both strings lowercased before comparison.

**Example Similarities:**

| String 1 | String 2 | Similarity |
|----------|----------|------------|
| "Change to IPv6 settings" | "Change to IPv6 settings" | 1.00 |
| "Change to IPv6 settings" | "Change to ipv6 settings" | 1.00 (case-insensitive) |
| "Change to IPv6 configuration" | "Change to IPv6 settings" | 0.81 |
| "Modify IPv6 flag" | "Change to IPv6 settings" | 0.57 |
| "Update storage account" | "Change to IPv6 settings" | 0.26 |

**Why Fuzzy Matching?**
- LLM summaries vary slightly in wording
- Prevents brittle exact-match patterns
- Tolerates minor phrasing differences

### match_noise_pattern() (lines 57-76)

```python
def match_noise_pattern(summary: str, patterns: list[str], threshold: float = 0.80) -> bool:
    """Check if summary matches any noise pattern using fuzzy matching.

    Args:
        summary: Resource summary text from LLM
        patterns: List of noise pattern strings
        threshold: Similarity threshold (0.0-1.0, default 0.80)

    Returns:
        True if any pattern matches above threshold, False otherwise
    """
    if not summary or not patterns:
        return False

    for pattern in patterns:
        similarity = calculate_similarity(summary, pattern)
        if similarity >= threshold:
            return True

    return False
```

**Logic:**
1. Return False if summary or patterns list is empty
2. For each pattern:
   - Calculate similarity to summary
   - If similarity ≥ threshold, return True (match found)
3. If no patterns match, return False

**Default Threshold:** 0.80 (80% similarity required)

**Threshold Tuning:**
- **0.90+** - Very strict, requires near-exact match
- **0.80** - Default, tolerates minor wording differences
- **0.70** - Lenient, catches broader variations
- **< 0.70** - Too loose, risk of false positives

### apply_noise_filtering() (lines 79-119)

Main filtering function called by CLI:

```python
def apply_noise_filtering(
    data: dict, noise_file: str, threshold: float = 0.80
) -> dict:
    """Apply noise pattern filtering to LLM response data.

    For each resource, if the summary matches any noise pattern (above threshold),
    the confidence_level is overridden to "noise".

    Args:
        data: Parsed LLM response with resources list
        noise_file: Path to noise patterns file
        threshold: Similarity threshold for matching (0.0-1.0)

    Returns:
        Modified data dict with confidence_level overridden for matched resources

    Raises:
        FileNotFoundError: If noise_file does not exist
        IOError: If noise_file cannot be read
    """
    # Load noise patterns
    patterns = load_noise_patterns(noise_file)

    if not patterns:
        # No patterns loaded, return data unchanged
        return data

    # Process each resource
    resources = data.get("resources", [])
    for resource in resources:
        summary = resource.get("summary", "")

        # Check if summary matches any noise pattern
        if match_noise_pattern(summary, patterns, threshold):
            # Override confidence to very low (10 when converted to numeric)
            resource["confidence_level"] = "noise"

    return data
```

**Algorithm:**
1. Load patterns from file
2. If no patterns, return data unchanged
3. For each resource:
   - Get resource summary
   - Check if summary matches any pattern
   - If match: override `confidence_level` to "noise"
4. Return modified data dict

**Key Design:** Modifies data dict in-place and returns it.

**Graceful Handling:**
- Empty pattern file → No filtering applied
- Missing summary field → No match (empty string)
- Already low-confidence resource → Overridden to "noise" if matched

## Confidence Splitting in CLI

### filter_by_confidence() (cli.py lines 81-127)

Splits LLM response into high-confidence and low-confidence resources:

```python
def filter_by_confidence(data: dict) -> tuple[dict, dict]:
    """Filter resources by confidence level.

    Splits resources into high-confidence (medium/high) and low-confidence (low) lists.
    Low-confidence resources are likely Azure What-If noise and should be excluded
    from risk analysis but displayed separately.

    Returns:
        Tuple of (high_confidence_data, low_confidence_data) dicts with same structure
    """
    resources = data.get("resources", [])

    high_confidence_resources = []
    low_confidence_resources = []

    for resource in resources:
        confidence = resource.get("confidence_level", "medium").lower()

        if confidence in ("low", "noise"):
            # Low confidence and noise-matched resources excluded from analysis
            low_confidence_resources.append(resource)
        else:
            # medium and high confidence included in analysis
            high_confidence_resources.append(resource)

    # Build high-confidence data dict (includes CI fields if present)
    high_confidence_data = {
        "resources": high_confidence_resources,
        "overall_summary": data.get("overall_summary", "")
    }

    # Preserve CI mode fields in high-confidence data
    if "risk_assessment" in data:
        high_confidence_data["risk_assessment"] = data["risk_assessment"]
    if "verdict" in data:
        high_confidence_data["verdict"] = data["verdict"]

    # Build low-confidence data dict (no CI fields - these are excluded from risk analysis)
    low_confidence_data = {
        "resources": low_confidence_resources,
        "overall_summary": ""  # No separate summary for noise
    }

    return high_confidence_data, low_confidence_data
```

**Split Logic:**

| Confidence Level | Category | Included in Risk Analysis? |
|------------------|----------|----------------------------|
| `high` | High-confidence | ✅ Yes |
| `medium` | High-confidence | ✅ Yes |
| `low` | Low-confidence | ❌ No (potential noise) |
| `noise` | Low-confidence | ❌ No (pattern-matched noise) |

**Default Value:** If `confidence_level` missing, defaults to `"medium"` (included in analysis).

**CI Fields Handling:**
- `risk_assessment` and `verdict` only preserved in high-confidence data
- Low-confidence data excludes CI fields (these resources don't contribute to risk assessment)

## Re-Analysis in CI Mode

### Problem: Stale Risk Assessment

When resources are filtered, the LLM's original `risk_assessment` becomes stale:
- Generated before filtering
- Includes noise resources in drift/intent/operations analysis
- Verdict may be overly conservative

### Solution: Re-Prompt LLM (cli.py lines 410-478)

```python
if ci and low_confidence_data.get("resources"):
    num_filtered = len(low_confidence_data["resources"])
    num_remaining = len(high_confidence_data.get("resources", []))

    sys.stderr.write(
        f"🔄 Recalculating risk assessment: {num_filtered} low-confidence resources "
        f"filtered, {num_remaining} high-confidence resources remain\n"
    )

    # Build a filtered What-If output containing only high-confidence resources
    filtered_whatif_lines = ["Resource changes:"]
    for resource in high_confidence_data.get("resources", []):
        # Reconstruct What-If format: "~ ResourceName"
        action_symbol = {
            "create": "+",
            "modify": "~",
            "delete": "-",
            "deploy": "=",
            "nochange": "*",
            "ignore": "x"
        }.get(resource.get("action", "").lower(), "~")

        filtered_whatif_lines.append(f"{action_symbol} {resource['resource_name']}")
        filtered_whatif_lines.append(f"  Summary: {resource['summary']}")

    filtered_whatif_content = "\n".join(filtered_whatif_lines)

    # Re-build prompts with filtered data
    filtered_system_prompt = build_system_prompt(
        verbose=verbose,
        ci_mode=ci,
        pr_title=pr_title,
        pr_description=pr_description
    )
    filtered_user_prompt = build_user_prompt(
        whatif_content=filtered_whatif_content,
        diff_content=diff_content,
        bicep_content=bicep_content,
        pr_title=pr_title,
        pr_description=pr_description
    )

    # Re-call LLM with filtered resources
    sys.stderr.write("📡 Re-analyzing with filtered resources for accurate risk assessment...\n")
    filtered_response_text = llm_provider.complete(filtered_system_prompt, filtered_user_prompt)

    # Parse the new response
    try:
        filtered_data = extract_json(filtered_response_text)

        # Extract the fresh risk_assessment and verdict
        if "risk_assessment" in filtered_data:
            high_confidence_data["risk_assessment"] = filtered_data["risk_assessment"]
        if "verdict" in filtered_data:
            high_confidence_data["verdict"] = filtered_data["verdict"]

        sys.stderr.write("✅ Risk assessment recalculated based on high-confidence resources only\n")

    except ValueError:
        sys.stderr.write(
            "⚠️  Warning: Could not parse re-analysis response. "
            "Using original risk assessment (may be inaccurate).\n"
        )
```

**Algorithm:**
1. **Check if re-analysis needed:** CI mode + resources filtered
2. **Reconstruct What-If output:** Build minimal What-If text from high-confidence resources
3. **Re-build prompts:** Same system/user prompts but with filtered What-If content
4. **Re-call LLM:** Get fresh analysis of high-confidence resources only
5. **Extract risk fields:** Update `risk_assessment` and `verdict` in high-confidence data
6. **Graceful failure:** If re-analysis fails, use original (with warning)

**Why Reconstruct What-If?**
- LLM needs What-If format input (not structured JSON)
- Maintains consistency with initial prompt structure
- Simpler than building new prompt format

**Cost Trade-off:** Extra LLM API call, but ensures accurate risk assessment.

## CLI Integration

### Usage Flow

```bash
# With noise patterns file
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --noise-file ./patterns.txt \
  --noise-threshold 80
```

### CLI Options

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--noise-file` | String | `None` | Path to noise patterns file |
| `--noise-threshold` | Integer | `80` | Similarity threshold percentage (0-100) |

**Threshold Conversion:**
```python
# CLI accepts percentage (80)
threshold_ratio = noise_threshold / 100.0  # Convert to 0.80
data = apply_noise_filtering(data, noise_file, threshold_ratio)
```

### Integration Points (cli.py)

**1. Apply pattern filtering (lines 390-400):**
```python
if noise_file:
    try:
        threshold_ratio = noise_threshold / 100.0
        data = apply_noise_filtering(data, noise_file, threshold_ratio)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(2)
    except IOError as e:
        sys.stderr.write(f"Error reading noise file: {e}\n")
        sys.exit(2)
```

**2. Split by confidence (line 408):**
```python
high_confidence_data, low_confidence_data = filter_by_confidence(data)
```

**3. Re-analyze if filtered in CI mode (lines 413-478):**
```python
if ci and low_confidence_data.get("resources"):
    # Re-analysis logic
```

**4. Render both datasets (lines 480-486):**
```python
render_table(high_confidence_data, ..., low_confidence_data=low_confidence_data)
render_json(high_confidence_data, low_confidence_data=low_confidence_data)
render_markdown(high_confidence_data, ..., low_confidence_data=low_confidence_data)
```

## Example Workflow

### Input: LLM Response

```json
{
  "resources": [
    {
      "resource_name": "myStorageAccount",
      "action": "Create",
      "summary": "Creates new storage account",
      "confidence_level": "high"
    },
    {
      "resource_name": "mySubnet",
      "action": "Modify",
      "summary": "Change to IPv6 addressing configuration",
      "confidence_level": "medium"
    },
    {
      "resource_name": "myResource",
      "action": "Modify",
      "summary": "Update to etag property",
      "confidence_level": "low"
    }
  ],
  "risk_assessment": {...},
  "verdict": {...}
}
```

### Noise Patterns File

```
# patterns.txt
Change to IPv6
Update to etag
```

### After apply_noise_filtering()

```json
{
  "resources": [
    {
      "resource_name": "myStorageAccount",
      "action": "Create",
      "summary": "Creates new storage account",
      "confidence_level": "high"
    },
    {
      "resource_name": "mySubnet",
      "action": "Modify",
      "summary": "Change to IPv6 addressing configuration",
      "confidence_level": "noise"  // ← Overridden
    },
    {
      "resource_name": "myResource",
      "action": "Modify",
      "summary": "Update to etag property",
      "confidence_level": "noise"  // ← Overridden
    }
  ],
  "risk_assessment": {...},
  "verdict": {...}
}
```

### After filter_by_confidence()

**high_confidence_data:**
```json
{
  "resources": [
    {
      "resource_name": "myStorageAccount",
      "action": "Create",
      "summary": "Creates new storage account",
      "confidence_level": "high"
    }
  ],
  "risk_assessment": {...},  // Stale - includes filtered resources
  "verdict": {...}
}
```

**low_confidence_data:**
```json
{
  "resources": [
    {
      "resource_name": "mySubnet",
      "action": "Modify",
      "summary": "Change to IPv6 addressing configuration",
      "confidence_level": "noise"
    },
    {
      "resource_name": "myResource",
      "action": "Modify",
      "summary": "Update to etag property",
      "confidence_level": "noise"
    }
  ]
}
```

### After Re-Analysis (CI Mode)

LLM re-prompted with only "myStorageAccount" → fresh `risk_assessment` and `verdict`.

## Benefits

### 1. Reduces False Positives

Pattern matching catches LLM mistakes:
- LLM assigns "medium" to IPv6 changes → Pattern overrides to "noise"
- Prevents blocking deployments on cosmetic changes

### 2. User Control

Teams can define their own noise patterns:
- Project-specific noise patterns
- Evolve patterns over time as Azure changes
- Share patterns across teams

### 3. Accurate CI Verdicts

Re-analysis ensures risk assessment reflects only high-confidence resources:
- Prevents "high drift" verdicts caused by noise
- More reliable deployment gates

### 4. Transparency

Low-confidence resources still displayed:
- Users see what was filtered
- Can verify filtering is correct
- Debug if real changes incorrectly filtered

## Design Principles

### 1. LLM First, Patterns Second

- LLM provides baseline confidence assessment
- Patterns override LLM judgement when needed
- Hybrid approach: combine LLM reasoning with user knowledge

### 2. Fuzzy Matching Over Exact Matching

- LLM summaries vary in wording
- 80% threshold tolerates minor differences
- More robust than brittle regex patterns

### 3. Graceful Degradation

- Empty pattern file → No filtering
- Missing summary → No match
- Re-analysis failure → Use original (with warning)

### 4. Non-Destructive Filtering

- Low-confidence resources preserved and displayed separately
- Users can review filtered resources
- Enables debugging and verification

## Performance Characteristics

- **Pattern loading:** O(n) where n = number of patterns
- **Similarity calculation:** O(m*n) where m = summary length, n = pattern length
- **Per-resource filtering:** O(p) where p = number of patterns
- **Total filtering:** O(r*p*m*n) where r = number of resources

**Bottleneck:** Similarity calculation for many patterns/large summaries.

**Optimization:** Stop at first match (doesn't compare against all patterns).

## Testing Strategy

### Unit Tests

```python
# Test similarity calculation
assert calculate_similarity("Change to IPv6", "change to ipv6") == 1.0
assert calculate_similarity("Change to IPv6", "Modify IPv6 flag") > 0.5

# Test pattern matching
patterns = ["Change to IPv6", "Update to etag"]
assert match_noise_pattern("Change to IPv6 settings", patterns, 0.80) == True
assert match_noise_pattern("Create storage account", patterns, 0.80) == False

# Test filtering
data = {"resources": [{"summary": "Change to IPv6", "confidence_level": "medium"}]}
filtered = apply_noise_filtering(data, "patterns.txt", 0.80)
assert filtered["resources"][0]["confidence_level"] == "noise"
```

### Integration Tests

- Large pattern files (100+ patterns)
- Various threshold values (0.7, 0.8, 0.9)
- Real LLM responses with mixed confidence
- Re-analysis in CI mode

## Future Improvements

1. **Regex patterns:** Support regex in addition to fuzzy matching
2. **Resource-type-specific patterns:** Different patterns for different Azure resource types
3. **Confidence threshold:** Make confidence split threshold configurable (`--confidence-threshold medium`)
4. **Pattern suggestions:** Analyze historical false positives and suggest patterns
5. **Negative patterns:** Explicitly mark resources as NOT noise

## Next Steps

For details on related modules:
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - How confidence levels are defined in prompts
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - How low-confidence resources are displayed
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - CLI flags and re-analysis logic
