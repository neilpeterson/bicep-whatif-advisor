# Feature Specification: Output Rendering

## Overview

This module formats LLM analysis results into three output formats:
1. **Table:** Rich library colored table for terminal display (85% terminal width)
2. **JSON:** Pretty-printed JSON for programmatic consumption
3. **Markdown:** Formatted tables for PR comments

All formats support both standard and CI mode, with optional display of low-confidence resources (Azure What-If noise).

## Module Location

**File:** `bicep_whatif_advisor/render.py`

**Dependencies:**
- `rich`: Terminal table rendering with colors
- `shutil`: Terminal size detection
- `json`: JSON formatting

**Exports:**
- `render_table(data, verbose, no_color, ci_mode, low_confidence_data) -> None`
- `render_json(data, low_confidence_data) -> None`
- `render_markdown(data, ci_mode, custom_title, no_block, low_confidence_data) -> str`

## Constants

### Action Styles

**Dictionary:** `ACTION_STYLES`

Maps action types to (symbol, color) tuples:
```python
ACTION_STYLES = {
    "Create": ("✅", "green"),
    "Modify": ("✏️", "yellow"),
    "Delete": ("❌", "red"),
    "Deploy": ("🔄", "blue"),
    "NoChange": ("➖", "dim"),
    "Ignore": ("⬜", "dim"),
}
```

**Usage:** Standard and markdown output use symbols, table output uses colors

### Risk Styles

**Dictionary:** `RISK_STYLES`

Maps risk levels to (symbol, color) tuples:
```python
RISK_STYLES = {
    "high": ("🔴", "red"),
    "medium": ("🟡", "yellow"),
    "low": ("🟢", "green"),
}
```

**Usage:** CI mode displays risk levels with color coding

## Table Rendering

### Function: `render_table()`

**Signature:**
```python
def render_table(
    data: dict,
    verbose: bool = False,
    no_color: bool = False,
    ci_mode: bool = False,
    low_confidence_data: dict = None
) -> None
```

**Behavior:**

1. **Determine color usage:**
   ```python
   use_color = not no_color and sys.stdout.isatty()
   ```
   - Disable colors if `no_color=True`
   - Disable colors if output is not a TTY (piped/redirected)

2. **Calculate table width:**
   ```python
   terminal_width = shutil.get_terminal_size().columns
   reduced_width = int(terminal_width * 0.85)  # 85% of terminal width
   ```
   - Reduces width by 15% for improved readability
   - Prevents text wrapping issues at terminal edges

3. **Create Rich console:**
   ```python
   console = Console(
       force_terminal=use_color,
       no_color=not use_color,
       width=reduced_width
   )
   ```

4. **Print risk bucket summary (CI mode only):**
   - Call `_print_risk_bucket_summary()` before main table
   - Shows three risk buckets in separate table

5. **Create main table:**
   ```python
   table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))
   ```
   - `box.ROUNDED`: Rounded corners for better aesthetics
   - `show_lines=True`: Horizontal lines between rows
   - `padding=(0, 1)`: No vertical padding, 1 space horizontal padding

6. **Add columns:**
   ```python
   table.add_column("#", style="dim", width=4)
   table.add_column("Resource", style="bold")
   table.add_column("Type")
   table.add_column("Action", justify="center")
   if ci_mode:
       table.add_column("Risk", justify="center")
   table.add_column("Summary")
   ```

7. **Add rows:**
   - Iterate resources with 1-based index
   - Apply color to action and risk columns using `_colorize()`
   - Colors only applied if `use_color=True`

8. **Print table and overall summary:**
   ```python
   console.print(table)
   console.print()
   console.print(f"Summary: {overall_summary}")
   ```

9. **Print verbose details (standard mode only):**
   - Call `_print_verbose_details()` if `verbose=True`
   - Shows property-level changes for modified resources

10. **Print CI verdict (CI mode only):**
    - Call `_print_ci_verdict()`
    - Shows safe/unsafe status, risk level, reasoning

11. **Print low-confidence resources:**
    - Call `_print_noise_section()` if low-confidence data provided
    - Displays excluded resources in separate table

### Helper: `_colorize()`

**Signature:**
```python
def _colorize(text: str, color: str, use_color: bool) -> str
```

**Behavior:**
- If `use_color=True`: Return `[{color}]{text}[/{color}]` (Rich markup)
- Otherwise: Return plain `text`
- Used for conditional color application

### Helper: `_print_risk_bucket_summary()`

**Signature:**
```python
def _print_risk_bucket_summary(console: Console, risk_assessment: dict, use_color: bool) -> None
```

**Behavior:**

1. Create risk bucket table:
   ```python
   bucket_table = Table(box=box.ROUNDED, show_header=True, padding=(0, 1))
   bucket_table.add_column("Risk Bucket", style="bold")
   bucket_table.add_column("Risk Level", justify="center")
   bucket_table.add_column("Status", justify="center")
   bucket_table.add_column("Key Concerns")
   ```

2. Add row for drift bucket:
   - Extract `risk_assessment["drift"]`
   - Get risk level and apply color
   - Show first concern from concerns array
   - Status column shows colored dot: `●`

3. Add row for intent bucket (if exists):
   - Check if `risk_assessment.get("intent")` is not None
   - If exists: Show risk level and concern
   - If None: Show "Not evaluated" with dim color and "No PR metadata provided"

4. Add row for operations bucket:
   - Extract `risk_assessment["operations"]`
   - Same format as drift bucket

5. Print table with blank line after

**Example Output:**
```
╭───────────────────────┬────────────┬────────┬─────────────────────────╮
│ Risk Bucket           │ Risk Level │ Status │ Key Concerns            │
├───────────────────────┼────────────┼────────┼─────────────────────────┤
│ Infrastructure Drift  │ Low        │ ●      │ None                    │
│ PR Intent Alignment   │ Medium     │ ●      │ Public IP not mentioned │
│ Risky Operations      │ Medium     │ ●      │ Exposing public IP      │
╰───────────────────────┴────────────┴────────┴─────────────────────────╯
```

### Helper: `_print_verbose_details()`

**Signature:**
```python
def _print_verbose_details(console: Console, resources: list, use_color: bool) -> None
```

**Behavior:**

1. Filter resources to only "Modify" actions with "changes" field
2. Print header: "Property-Level Changes:"
3. For each modified resource:
   ```
     • resource_name:
       - property change 1
       - property change 2
   ```
4. Bullet symbol (•) colored yellow if use_color enabled

### Helper: `_print_ci_verdict()`

**Signature:**
```python
def _print_ci_verdict(console: Console, verdict: dict, use_color: bool) -> None
```

**Behavior:**

1. Extract verdict fields:
   ```python
   safe = verdict.get("safe", True)
   overall_risk = verdict.get("overall_risk_level", "low")
   highest_bucket = verdict.get("highest_risk_bucket", "none")
   reasoning = verdict.get("reasoning", "")
   ```

2. Print verdict header:
   - If safe: `Verdict: SAFE` (green bold)
   - If unsafe: `Verdict: UNSAFE` (red bold)

3. Print overall risk level:
   - Format: `Overall Risk Level: {risk.capitalize()}`

4. Print highest risk bucket (if not "none"):
   - Format: `Highest Risk Bucket: {bucket.capitalize()}`

5. Print reasoning:
   - Format: `Reasoning: {reasoning}`

**Example Output:**
```
Verdict: UNSAFE

Overall Risk Level: Medium
Highest Risk Bucket: Intent
Reasoning: Multiple medium-risk concerns detected. The public IP change appears to be infrastructure drift not captured in the code diff, and it's not mentioned in the PR intent.
```

### Helper: `_print_noise_section()`

**Signature:**
```python
def _print_noise_section(console: Console, low_confidence_data: dict, use_color: bool, ci_mode: bool) -> None
```

**Behavior:**

1. Print warning header:
   ```
   ⚠️  Potential Azure What-If Noise (Low Confidence)
   The following changes were flagged as likely What-If noise and excluded from risk analysis:
   ```

2. Create noise table:
   ```python
   noise_table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))
   noise_table.add_column("#", style="dim", width=4)
   noise_table.add_column("Resource", style="bold")
   noise_table.add_column("Type")
   noise_table.add_column("Action", justify="center")
   noise_table.add_column("Confidence Reason")
   ```

3. Add rows for each low-confidence resource:
   - Show resource name, type, action
   - Show confidence_reason explaining why it's likely noise

4. Print table

## JSON Rendering

### Function: `render_json()`

**Signature:**
```python
def render_json(data: dict, low_confidence_data: dict = None) -> None
```

**Behavior:**

1. Build output structure:
   ```python
   output = {
       "high_confidence": data,
   }
   if low_confidence_data:
       output["low_confidence"] = low_confidence_data
   ```

2. Print with 2-space indentation:
   ```python
   print(json.dumps(output, indent=2))
   ```

**Example Output:**
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
        "resource_name": "vnet-subnet-001",
        "resource_type": "Subnet",
        "action": "Modify",
        "summary": "Changes subnet reference from hardcoded to dynamic",
        "confidence_level": "low",
        "confidence_reason": "Computed property change (resourceGuid)"
      }
    ],
    "overall_summary": ""
  }
}
```

## Markdown Rendering

### Function: `render_markdown()`

**Signature:**
```python
def render_markdown(
    data: dict,
    ci_mode: bool = False,
    custom_title: str = None,
    no_block: bool = False,
    low_confidence_data: dict = None
) -> str
```

**Returns:** Markdown-formatted string (not printed, returned for PR comment posting)

**Behavior:**

1. **Add title (CI mode only):**
   ```markdown
   ## What-If Deployment Review
   ```
   - Use custom_title if provided, otherwise "What-If Deployment Review"
   - Append " (non-blocking)" if `no_block=True`

2. **Add risk assessment table (CI mode only):**
   ```markdown
   ### Risk Assessment

   | Risk Bucket | Risk Level | Key Concerns |
   |-------------|------------|--------------|
   | Infrastructure Drift | Low | None |
   | PR Intent Alignment | Not evaluated | No PR metadata provided |
   | Risky Operations | Medium | Exposing public IP |
   ```
   - Extract from `data["risk_assessment"]`
   - If intent bucket is None, show "Not evaluated"

3. **Add collapsible resource changes section:**
   ```markdown
   <details>
   <summary>📋 View changed resources</summary>

   | # | Resource | Type | Action | Risk | Summary |
   |---|----------|------|--------|------|---------|
   | 1 | parse-jwt-from-header | Policy Fragment | Create | Low | Creates JWT authentication policy fragment |
   | 2 | production-api | API Management API | Modify | Medium | Enables public IP addressing |

   </details>
   ```
   - Use `<details>` for collapsibility
   - Standard mode omits Risk column
   - Escape pipe characters in summary: `.replace("|", "\\|")`

4. **Add overall summary:**
   ```markdown
   **Summary:** 1 create, 1 modify: Adds JWT policy and enables public IP
   ```

5. **Add low-confidence section (if data provided):**
   ```markdown
   ---

   <details>
   <summary>⚠️ Potential Azure What-If Noise (Low Confidence)</summary>

   The following changes were flagged as likely What-If noise and **excluded from risk analysis**:

   | # | Resource | Type | Action | Confidence Reason |
   |---|----------|------|--------|-------------------|
   | 1 | vnet-subnet-001 | Subnet | Modify | Computed property change (resourceGuid) |

   </details>
   ```

6. **Add verdict (CI mode only):**
   ```markdown
   ### Verdict: ✅ SAFE

   **Overall Risk Level:** Low
   **Highest Risk Bucket:** None
   **Reasoning:** All risk buckets are within acceptable thresholds. No blocking concerns detected.
   ```
   - Use ✅ for safe, ❌ for unsafe

7. **Add footer (CI mode only):**
   ```markdown
   ---
   *Generated by [bicep-whatif-advisor](https://github.com/yourorg/bicep-whatif-advisor)*
   ```

## Implementation Requirements

1. **Table width must be 85% of terminal:** Prevents wrapping issues
2. **ROUNDED box style required:** Better aesthetics than simple borders
3. **show_lines=True:** Horizontal lines improve row separation
4. **Color detection:** Auto-disable if no TTY or if `no_color=True`
5. **Markdown escaping:** Pipe characters in summaries must be escaped (`\|`)
6. **Collapsible sections:** Use `<details>/<summary>` for long tables in markdown
7. **Low-confidence display:** Always separate from main results, clearly labeled as "Potential Noise"
8. **Intent bucket handling:** Show "Not evaluated" if intent bucket is None

## Edge Cases

1. **Empty resources list:** Display empty table with headers
2. **Missing fields:** Use defaults (e.g., "Unknown" for resource_name)
3. **No low-confidence data:** Skip noise section entirely
4. **No risk_assessment in CI mode:** Skip risk bucket table (defensive coding)
5. **Very long summaries:** Rich library handles wrapping automatically
6. **Non-TTY output:** Disable colors but preserve structure
7. **Markdown special characters:** Escape pipes in summaries, leave other chars as-is
