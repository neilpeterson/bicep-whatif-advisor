# Feature Specification: Noise Filtering

## Overview

Two-phase approach to filtering Azure What-If noise:

1. **Phase 1 - LLM Confidence Scoring:** LLM assigns confidence levels (low/medium/high) to each resource based on whether it's a real change or likely Azure What-If noise
2. **Phase 2 - Pattern Matching (Optional):** User-provided patterns matched against LLM summaries using fuzzy string matching to catch additional noise

**Critical Integration:** In CI mode, after filtering low-confidence resources, the LLM is called AGAIN to re-analyze only the high-confidence resources. This ensures risk assessment operates on clean data without noise contamination.

## Module Location

**File:** `bicep_whatif_advisor/noise_filter.py`

**Dependencies:**
- `difflib`: SequenceMatcher for fuzzy string matching
- `pathlib`: Path handling

**Exports:**
- `load_noise_patterns(file_path: str) -> list[str]`
- `calculate_similarity(text1: str, text2: str) -> float`
- `match_noise_pattern(summary: str, patterns: list[str], threshold: float) -> bool`
- `apply_noise_filtering(data: dict, noise_file: str, threshold: float) -> dict`

## Phase 1: LLM Confidence Scoring

### Confidence Levels

LLM assigns one of three confidence levels to each resource:

**high** - Real changes with clear intent:
- Resource creation, deletion, or state changes
- Configuration modifications with concrete value changes
- Security, networking, or compute changes
- Property changes that affect resource behavior

**medium** - Potentially real but uncertain:
- Retention policies or analytics settings
- Subnet references changing from hardcoded to dynamic
- Configuration changes that might be platform-managed
- Borderline cases requiring human judgment

**low** - Likely Azure What-If noise:
- Metadata-only changes (etag, id, provisioningState, type)
- logAnalyticsDestinationType property changes
- IPv6 flags (disableIpv6, enableIPv6Addressing)
- Computed properties (resourceGuid)
- Read-only or system-managed properties

**IMPORTANT:** The LLM prompt explicitly states these are GUIDELINES, not rigid patterns. The LLM should use judgment.

### Confidence Field in LLM Response

**Standard Mode:**
```json
{
  "resources": [
    {
      "resource_name": "vnet-subnet-001",
      "resource_type": "Subnet",
      "action": "Modify",
      "summary": "Changes subnet reference from hardcoded to dynamic",
      "confidence_level": "low",
      "confidence_reason": "Computed property change (resourceGuid)"
    }
  ]
}
```

**CI Mode:**
```json
{
  "resources": [
    {
      "resource_name": "production-db",
      "resource_type": "SQL Database",
      "action": "Delete",
      "summary": "Deletes production database",
      "risk_level": "high",
      "risk_reason": "Destructive operation on stateful resource",
      "confidence_level": "high",
      "confidence_reason": "Clear destructive operation"
    }
  ]
}
```

### Function: `filter_by_confidence()`

**Location:** `bicep_whatif_advisor/cli.py` (not in noise_filter.py)

**Signature:**
```python
def filter_by_confidence(data: dict) -> tuple[dict, dict]
```

**Behavior:**

1. **Extract resources:**
   ```python
   resources = data.get("resources", [])
   ```

2. **Split by confidence level:**
   ```python
   high_confidence_resources = []
   low_confidence_resources = []

   for resource in resources:
       confidence = resource.get("confidence_level", "medium").lower()

       if confidence in ("low", "noise"):
           low_confidence_resources.append(resource)
       else:
           # medium and high confidence included in analysis
           high_confidence_resources.append(resource)
   ```

3. **Build high-confidence data dict:**
   ```python
   high_confidence_data = {
       "resources": high_confidence_resources,
       "overall_summary": data.get("overall_summary", "")
   }

   # Preserve CI mode fields in high-confidence data
   if "risk_assessment" in data:
       high_confidence_data["risk_assessment"] = data["risk_assessment"]
   if "verdict" in data:
       high_confidence_data["verdict"] = data["verdict"]
   ```

4. **Build low-confidence data dict:**
   ```python
   low_confidence_data = {
       "resources": low_confidence_resources,
       "overall_summary": ""  # No separate summary for noise
   }
   ```

5. **Return both:**
   ```python
   return high_confidence_data, low_confidence_data
   ```

**Note:** "noise" confidence level is treated same as "low". This is set by phase 2 pattern matching.

## Phase 2: Pattern Matching

### Noise Patterns File Format

**File:** Plain text, one pattern per line

**Format:**
```
# Comments start with #
# Blank lines are ignored

Changes subnet reference from hardcoded to dynamic
Computed property change
Metadata-only update
Updates IPv6 addressing flags
```

**Rules:**
- One pattern per line
- Lines starting with `#` are comments (ignored)
- Blank lines ignored
- Patterns matched case-insensitively against LLM summaries
- No regex - plain text fuzzy matching

### Function: `load_noise_patterns()`

**Signature:**
```python
def load_noise_patterns(file_path: str) -> list[str]
```

**Behavior:**

1. **Validate file exists:**
   ```python
   path = Path(file_path)
   if not path.exists():
       raise FileNotFoundError(f"Noise patterns file not found: {file_path}")
   ```

2. **Read and parse file:**
   ```python
   patterns = []
   with open(path, "r", encoding="utf-8") as f:
       for line in f:
           line = line.strip()
           if line and not line.startswith("#"):
               patterns.append(line)
   ```

3. **Return patterns list:**
   ```python
   return patterns
   ```

**Exceptions:**
- `FileNotFoundError`: File doesn't exist
- `IOError`: File can't be read (permissions, etc.)

### Function: `calculate_similarity()`

**Signature:**
```python
def calculate_similarity(text1: str, text2: str) -> float
```

**Behavior:**
```python
return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
```

**Returns:** Similarity ratio between 0.0 and 1.0 (1.0 = identical)

**Algorithm:** Python's difflib.SequenceMatcher uses Ratcliff/Obershelp pattern recognition

**Examples:**
```python
calculate_similarity("hello world", "hello world")
# → 1.0 (exact match)

calculate_similarity("Changes subnet reference", "Change subnet references")
# → ~0.85 (very similar)

calculate_similarity("Updates IPv6 flags", "Creates new resource")
# → ~0.20 (very different)
```

**Case Insensitive:** Both strings converted to lowercase before comparison

### Function: `match_noise_pattern()`

**Signature:**
```python
def match_noise_pattern(
    summary: str,
    patterns: list[str],
    threshold: float = 0.80
) -> bool
```

**Parameters:**
- `summary`: Resource summary text from LLM
- `patterns`: List of noise pattern strings
- `threshold`: Similarity threshold (0.0-1.0, default 0.80)

**Returns:**
- `True`: Summary matches at least one pattern above threshold
- `False`: No patterns matched

**Behavior:**

1. **Handle empty inputs:**
   ```python
   if not summary or not patterns:
       return False
   ```

2. **Check each pattern:**
   ```python
   for pattern in patterns:
       similarity = calculate_similarity(summary, pattern)
       if similarity >= threshold:
           return True
   ```

3. **No match:**
   ```python
   return False
   ```

**Threshold Selection:**
- `0.80` (default): Balanced - catches similar phrases but not unrelated text
- `0.90`: Strict - requires very close match
- `0.70`: Lenient - catches more variations but higher false positives

**Examples with 0.80 threshold:**
```python
match_noise_pattern("Changes subnet reference from hardcoded to dynamic",
                   ["Changes subnet reference"], 0.80)
# → True (very similar)

match_noise_pattern("Updates IPv6 addressing flags",
                   ["Updates IPv6 flags"], 0.80)
# → True (close match)

match_noise_pattern("Creates new storage account",
                   ["Updates IPv6 flags"], 0.80)
# → False (different meaning)
```

### Function: `apply_noise_filtering()`

**Signature:**
```python
def apply_noise_filtering(
    data: dict,
    noise_file: str,
    threshold: float = 0.80
) -> dict
```

**Parameters:**
- `data`: Parsed LLM response with resources list
- `noise_file`: Path to noise patterns file
- `threshold`: Similarity threshold for matching (0.0-1.0)

**Returns:** Modified data dict with confidence_level overridden for matched resources

**Behavior:**

1. **Load patterns:**
   ```python
   patterns = load_noise_patterns(noise_file)
   if not patterns:
       return data  # No patterns, return unchanged
   ```

2. **Process each resource:**
   ```python
   resources = data.get("resources", [])
   for resource in resources:
       summary = resource.get("summary", "")

       if match_noise_pattern(summary, patterns, threshold):
           resource["confidence_level"] = "noise"
   ```

3. **Return modified data:**
   ```python
   return data
   ```

**Important Notes:**
- Modifies `data` dict in-place
- Overwrites existing `confidence_level` field
- "noise" level converted to score 10 when filtering (treated as very low confidence)
- No explicit noise flag added - low confidence score is the indicator

**Exceptions:**
- Propagates `FileNotFoundError` if noise_file doesn't exist
- Propagates `IOError` if noise_file can't be read

## Two-Phase Workflow

### Standard Mode

```python
# 1. Get LLM response with confidence scoring
system_prompt = build_system_prompt(verbose=False, ci_mode=False)
user_prompt = build_user_prompt(whatif_content)
llm_response = provider.complete(system_prompt, user_prompt)
data = extract_json(llm_response)

# 2. Apply pattern-based noise filtering (if enabled)
if noise_file:
    data = apply_noise_filtering(data, noise_file, threshold=0.80)

# 3. Filter by confidence
high_conf_data, low_conf_data = filter_by_confidence(data)

# 4. Display both sets
render_table(high_conf_data, low_confidence_data=low_conf_data)
```

### CI Mode with Re-analysis

**CRITICAL:** In CI mode, after filtering, the LLM must re-analyze ONLY the high-confidence resources to ensure risk assessment isn't contaminated by noise.

```python
# 1. Get initial LLM response with confidence scoring
system_prompt = build_system_prompt(verbose=False, ci_mode=True, pr_title=..., pr_description=...)
user_prompt = build_user_prompt(whatif_content, diff_content, ...)
llm_response = provider.complete(system_prompt, user_prompt)
data = extract_json(llm_response)

# 2. Apply pattern-based noise filtering (if enabled)
if noise_file:
    data = apply_noise_filtering(data, noise_file, threshold=0.80)

# 3. Filter by confidence
high_conf_data, low_conf_data = filter_by_confidence(data)

# 4. RE-ANALYZE high-confidence resources in CI mode
if ci_mode and low_conf_data["resources"]:
    # Build What-If content with ONLY high-confidence resources
    filtered_whatif = rebuild_whatif_from_resources(high_conf_data["resources"])

    # Call LLM again with filtered What-If output
    user_prompt_filtered = build_user_prompt(filtered_whatif, diff_content, ...)
    llm_response_filtered = provider.complete(system_prompt, user_prompt_filtered)
    high_conf_data = extract_json(llm_response_filtered)

    # Now high_conf_data has clean risk assessment without noise

# 5. Evaluate risk buckets (operates on clean data)
is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
    high_conf_data,
    drift_threshold, intent_threshold, operations_threshold
)

# 6. Display both sets
render_table(high_conf_data, ci_mode=True, low_confidence_data=low_conf_data)
```

**Why Re-analysis in CI Mode:**

If we don't re-analyze, the risk assessment from step 1 includes evaluation of low-confidence resources (noise). This contaminates the drift, intent, and operations buckets with false positives.

By re-analyzing only high-confidence resources, we ensure:
- Drift bucket only compares real changes to code diff
- Intent bucket only checks real changes against PR description
- Operations bucket only evaluates real risky operations

**Performance Note:** This requires two LLM calls in CI mode when noise filtering is enabled. This is acceptable because accuracy is more important than speed for deployment gates.

## CLI Integration

**CLI Flags:**
```bash
--noise-filter FILE      # Path to noise patterns file (optional)
--noise-threshold FLOAT  # Similarity threshold (default: 0.80)
```

**Usage Example:**
```bash
# Standard mode with noise filtering
az deployment group what-if ... | bicep-whatif-advisor --noise-filter noise-patterns.txt

# CI mode with noise filtering
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --noise-filter noise-patterns.txt \
  --noise-threshold 0.85
```

**Implementation in CLI:**
```python
if noise_filter:
    data = apply_noise_filtering(data, noise_filter, noise_threshold)
```

## Display in Output

### Table Format

Low-confidence resources displayed in separate section:

```
╭─────────────────────────────────────────────────────────────╮
│ ⚠️  Potential Azure What-If Noise (Low Confidence)         │
╰─────────────────────────────────────────────────────────────╯
The following changes were flagged as likely What-If noise and excluded from risk analysis:

╭───┬──────────────┬────────┬────────┬─────────────────────╮
│ # │ Resource     │ Type   │ Action │ Confidence Reason   │
├───┼──────────────┼────────┼────────┼─────────────────────┤
│ 1 │ vnet-subnet  │ Subnet │ Modify │ Computed property   │
╰───┴──────────────┴────────┴────────┴─────────────────────╯
```

### JSON Format

```json
{
  "high_confidence": {
    "resources": [ ... ],
    "overall_summary": "...",
    "risk_assessment": { ... },
    "verdict": { ... }
  },
  "low_confidence": {
    "resources": [
      {
        "resource_name": "vnet-subnet",
        "resource_type": "Subnet",
        "action": "Modify",
        "summary": "Changes subnet reference",
        "confidence_level": "low",
        "confidence_reason": "Computed property change"
      }
    ],
    "overall_summary": ""
  }
}
```

### Markdown Format (PR Comments)

```markdown
---

<details>
<summary>⚠️ Potential Azure What-If Noise (Low Confidence)</summary>

The following changes were flagged as likely What-If noise and **excluded from risk analysis**:

| # | Resource | Type | Action | Confidence Reason |
|---|----------|------|--------|-------------------|
| 1 | vnet-subnet | Subnet | Modify | Computed property change |

</details>
```

## Implementation Requirements

1. **Two-phase approach:** LLM confidence scoring first, then pattern matching
2. **Re-analysis in CI mode:** Call LLM twice to get clean risk assessment
3. **Case-insensitive matching:** All similarity calculations lowercase both strings
4. **Fuzzy matching:** Use difflib.SequenceMatcher, not exact string match or regex
5. **Default threshold 0.80:** Balance between catching noise and avoiding false positives
6. **UTF-8 encoding:** Read noise patterns file with explicit encoding
7. **Graceful degradation:** Empty patterns list returns data unchanged
8. **Confidence overwrite:** Pattern matching sets confidence_level to "noise"
9. **Separate display:** Low-confidence resources shown separately, not mixed
10. **Non-blocking errors:** Pattern file errors should be caught and reported

## Edge Cases

1. **Empty patterns file:** Returns empty list, no filtering applied
2. **No resources match patterns:** All resources remain at LLM-assigned confidence
3. **All resources matched as noise:** High-confidence data has empty resources array
4. **Pattern file doesn't exist:** Raise FileNotFoundError (caller should handle)
5. **Pattern file unreadable:** Raise IOError (caller should handle)
6. **Empty summary string:** `match_noise_pattern()` returns False
7. **Threshold 0.0:** Matches everything (not recommended)
8. **Threshold 1.0:** Only exact matches (very strict)
9. **Very long patterns:** Similarity calculation still works, may be slow
10. **Special characters in patterns:** Handled correctly by SequenceMatcher
11. **Re-analysis fails:** Fallback to original data with warning
12. **Confidence already "noise":** Remains "noise" (no change)

## Performance Considerations

**Pattern Matching Complexity:**
- `O(n * m * k)` where:
  - n = number of resources
  - m = number of patterns
  - k = string length (for SequenceMatcher)

**Typical Case:**
- 20 resources × 10 patterns × ~50 char strings = ~10,000 comparisons
- SequenceMatcher is fast enough for this scale

**Re-analysis Cost:**
- CI mode with noise filtering requires TWO LLM calls
- Acceptable for accuracy in deployment gates
- Could be optimized by only re-analyzing if low-confidence resources found

**Future Optimization:**
```python
# Only re-analyze if we actually filtered something
if ci_mode and low_conf_data["resources"]:
    # Re-analysis logic
```
