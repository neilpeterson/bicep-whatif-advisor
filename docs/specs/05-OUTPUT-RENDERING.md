# 05 - Output Rendering

## Purpose

The `render.py` module formats LLM analysis results for three different audiences:
1. **Table** - Interactive terminal output with colors and symbols (developers)
2. **JSON** - Machine-readable structured data (scripts, automation)
3. **Markdown** - GitHub/Azure DevOps PR comments (code reviewers)

**File:** `bicep_whatif_advisor/render.py` (486 lines)

## Module Overview

### Public Functions

```python
def render_table(
    data: dict,
    verbose: bool = False,
    no_color: bool = False,
    ci_mode: bool = False,
    low_confidence_data: dict = None
) -> None

def render_json(data: dict, low_confidence_data: dict = None) -> None

def render_markdown(
    data: dict,
    ci_mode: bool = False,
    custom_title: str = None,
    no_block: bool = False,
    low_confidence_data: dict = None,
    platform: str = None,
    whatif_content: str = None
) -> str
```

### Dependencies

```python
import json                       # JSON serialization
import sys                        # stdout.isatty() detection
import shutil                     # Terminal size detection
from rich.console import Console  # Colored terminal output
from rich.table import Table      # Table rendering
from rich import box              # Box styles (ROUNDED)
```

**External Dependency:** [`rich`](https://github.com/Textualize/rich) library for beautiful terminal output.

## Constants and Styles

### Action Symbols and Colors (lines 11-19)

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

| Action | Symbol | Color | Meaning |
|--------|--------|-------|---------|
| Create | ✅ | Green | New resource being created |
| Modify | ✏️ | Yellow | Existing resource being modified |
| Delete | ❌ | Red | Resource being deleted |
| Deploy | 🔄 | Blue | Resource being deployed/redeployed |
| NoChange | ➖ | Dim | No changes to resource |
| Ignore | ⬜ | Dim | Resource ignored by What-If |

### Risk Level Symbols and Colors (lines 21-26)

```python
RISK_STYLES = {
    "high": ("🔴", "red"),
    "medium": ("🟡", "yellow"),
    "low": ("🟢", "green"),
}
```

| Risk Level | Symbol | Color | Usage |
|------------|--------|-------|-------|
| High | 🔴 | Red | Critical risks requiring attention |
| Medium | 🟡 | Yellow | Moderate risks to review |
| Low | 🟢 | Green | Low risk, safe to proceed |

**Note:** Risk symbols only displayed in CI mode.

## Table Rendering

### render_table() Function (lines 43-136)

Primary rendering function for interactive terminal output.

#### Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `data` | `dict` | Required | Parsed LLM response (high-confidence resources) |
| `verbose` | `bool` | `False` | Show property-level changes for modified resources |
| `no_color` | `bool` | `False` | Disable colored output |
| `ci_mode` | `bool` | `False` | Include risk assessment columns and verdict |
| `low_confidence_data` | `dict` | `None` | Low-confidence resources (potential noise) |

#### Color Detection (lines 59-60)

```python
use_color = not no_color and sys.stdout.isatty()
```

**Logic:**
- Colors enabled if:
  - `--no-color` flag NOT set
  - AND stdout is a TTY (not piped to file)

**Why check TTY?** Prevent ANSI color codes from polluting redirected output.

#### Terminal Width Calculation (lines 62-66)

```python
# Calculate 85% of terminal width (15% reduction)
terminal_width = shutil.get_terminal_size().columns
reduced_width = int(terminal_width * 0.85)

console = Console(force_terminal=use_color, no_color=not use_color, width=reduced_width)
```

**Design Decision:** Tables render at 85% of terminal width for improved readability.

**Rationale:**
- Prevents text wrapping at edge of terminal
- Provides visual breathing room
- Matches common design practice (80-column limit)

#### Table Structure (lines 72-84)

```python
table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))

# Add columns
table.add_column("#", style="dim", width=4)
table.add_column("Resource", style="bold")
table.add_column("Type")
table.add_column("Action", justify="center")

if ci_mode:
    table.add_column("Risk", justify="center")

table.add_column("Summary")
```

**Table Configuration:**
- **Box style:** `box.ROUNDED` - Rounded corners, aesthetically pleasing
- **Show lines:** `True` - Horizontal lines between rows for clarity
- **Padding:** `(0, 1)` - 0 vertical, 1 horizontal character padding

**Columns:**

| Standard Mode | CI Mode | Width | Style | Justification |
|---------------|---------|-------|-------|---------------|
| # | # | 4 | Dim | Left |
| Resource | Resource | Auto | Bold | Left |
| Type | Type | Auto | Default | Left |
| Action | Action | Auto | Default | Center |
| - | Risk | Auto | Default | Center |
| Summary | Summary | Auto | Default | Left |

**Dynamic Columns:** Risk column only added in CI mode.

#### Row Population (lines 86-112)

```python
resources = data.get("resources", [])
for idx, resource in enumerate(resources, 1):
    resource_name = resource.get("resource_name", "Unknown")
    resource_type = resource.get("resource_type", "Unknown")
    action = resource.get("action", "Unknown")
    summary = resource.get("summary", "No summary provided")

    # Get action color
    _, color = ACTION_STYLES.get(action, ("?", "white"))
    action_display = action

    row = [
        str(idx),
        resource_name,
        resource_type,
        _colorize(action_display, color, use_color),
    ]

    if ci_mode:
        risk_level = resource.get("risk_level", "none")
        _, risk_color = RISK_STYLES.get(risk_level, ("?", "white"))
        risk_display = risk_level.capitalize()
        row.append(_colorize(risk_display, risk_color, use_color))

    row.append(summary)
    table.add_row(*row)
```

**Graceful Defaults:**
- Unknown action → "?" symbol, white color
- Missing risk level → "none"
- Missing fields → "Unknown" or "No summary provided"

#### Output Sections (lines 114-135)

The table rendering outputs multiple sections in the following order:

1. **Risk Bucket Summary** (CI mode only)
   ```python
   if ci_mode:
       _print_risk_bucket_summary(console, data.get("risk_assessment", {}), use_color)
   ```

2. **Overall Summary** (displayed before resource table)
   ```python
   overall_summary = data.get("overall_summary", "")
   if overall_summary:
       summary_label = _colorize("Summary:", "bold", use_color)
       console.print(f"{summary_label} {overall_summary}")
   ```

3. **Main Resource Table** (with "High Confidence Resources" label)
   ```python
   high_conf_label = _colorize("High Confidence Resources:", "bold cyan", use_color)
   console.print(high_conf_label)
   console.print(table)
   ```

4. **Verbose Details** (if `--verbose` flag, standard mode only)
   ```python
   if verbose and not ci_mode:
       _print_verbose_details(console, resources, use_color)
   ```

5. **CI Verdict** (CI mode only)
   ```python
   if ci_mode:
       _print_ci_verdict(console, data.get("verdict", {}), use_color)
   ```

6. **Potential Noise Section** (if low-confidence resources filtered)
   ```python
   if low_confidence_data and low_confidence_data.get("resources"):
       _print_noise_section(console, low_confidence_data, use_color, ci_mode)
   ```

**Note:** Summary is now displayed before the resource table to provide context before viewing detailed changes. The resource table is explicitly labeled as "High Confidence Resources" to distinguish it from potential noise.

### Helper Function: _print_noise_section() (lines 138-183)

Renders low-confidence resources as "Potential Azure What-If Noise":

```python
def _print_noise_section(
    console: Console,
    low_confidence_data: dict,
    use_color: bool,
    ci_mode: bool
) -> None:
```

**Output Format:**
```
⚠️  Potential Azure What-If Noise (Low Confidence)
The following changes were flagged as likely What-If noise and excluded from risk analysis:

╭───┬──────────────────┬──────────┬────────┬─────────────────────╮
│ # │ Resource         │ Type     │ Action │ Confidence Reason   │
├───┼──────────────────┼──────────┼────────┼─────────────────────┤
│ 1 │ myResource       │ Storage  │ Modify │ IPv6 flag change    │
╰───┴──────────────────┴──────────┴────────┴─────────────────────╯
```

**Table Structure:**
- Similar to main table but without Risk column
- Includes "Confidence Reason" column explaining why resource was marked low-confidence

### Helper Function: _print_risk_bucket_summary() (lines 185-252)

Renders risk bucket summary table in CI mode:

```python
def _print_risk_bucket_summary(
    console: Console,
    risk_assessment: dict,
    use_color: bool
) -> None:
```

**Output Format:**
```
╭──────────────────────┬────────────┬────────┬────────────────────╮
│ Risk Bucket          │ Risk Level │ Status │ Key Concerns       │
├──────────────────────┼────────────┼────────┼────────────────────┤
│ Infrastructure Drift │ Low        │ ●      │ No drift detected  │
│ PR Intent Alignment  │ Low        │ ●      │ Changes match PR   │
╰──────────────────────┴────────────┴────────┴────────────────────╯
```

**Columns:**
- **Risk Bucket:** Name of bucket (Drift, Intent, plus custom agents)
- **Risk Level:** Capitalized risk level with color
- **Status:** Colored dot indicator (● in risk level color)
- **Key Concerns:** First concern from concerns array

**Intent Bucket Handling:**
```python
intent = risk_assessment.get("intent")
if intent is not None:
    # Render intent bucket
else:
    # Show "Not evaluated" row
    bucket_table.add_row(
        "PR Intent Alignment",
        _colorize("Not evaluated", "dim", use_color),
        _colorize("—", "dim", use_color),
        "No PR metadata provided"
    )
```

**Design:** Explicitly shows when intent bucket is skipped (vs. omitting the row).

### Helper Function: _print_ci_verdict() (lines 270-311)

Renders deployment verdict in CI mode:

```python
def _print_ci_verdict(
    console: Console,
    verdict: dict,
    use_color: bool
) -> None:
```

**Output Format:**
```
Verdict: ✅ SAFE
Reasoning: Changes align with PR intent. Only low-risk operations detected.
```

**Verdict Display:**
- Safe → ✅ SAFE (green bold)
- Unsafe → ❌ UNSAFE (red bold)

**Note:** Overall Risk Level and Highest Risk Bucket fields have been removed from the verdict display to reduce redundancy, as this information is already shown in the Risk Assessment table above.

### Helper Function: _colorize() (lines 29-40)

Utility for conditional color application:

```python
def _colorize(text: str, color: str, use_color: bool) -> str:
    """Apply color formatting if use_color is True."""
    return f"[{color}]{text}[/{color}]" if use_color else text
```

**Rich Library Markup:** Uses `[color]text[/color]` syntax.

**Colors Supported:**
- Named colors: `red`, `green`, `yellow`, `blue`, `white`
- Styles: `bold`, `dim`
- Combined: `"yellow bold"`, `"red bold"`

## JSON Rendering

### render_json() Function (lines 314-328)

Simple JSON serialization with two-tier structure:

```python
def render_json(data: dict, low_confidence_data: dict = None) -> None:
    """Render output as pretty-printed JSON.

    Args:
        data: Parsed LLM response (high-confidence resources)
        low_confidence_data: Optional dict with low-confidence resources
    """
    output = {
        "high_confidence": data,
    }

    if low_confidence_data:
        output["low_confidence"] = low_confidence_data

    print(json.dumps(output, indent=2))
```

**Output Structure:**
```json
{
  "high_confidence": {
    "resources": [...],
    "overall_summary": "...",
    "risk_assessment": {...},
    "verdict": {...}
  },
  "low_confidence": {
    "resources": [...],
    "overall_summary": ""
  }
}
```

**Two-Tier Design:**
- **high_confidence:** Resources included in risk analysis
- **low_confidence:** Resources filtered as potential noise (optional)

**Why Separate?**
- Enables automated scripts to focus on high-confidence resources
- Preserves full LLM output for debugging
- Clear distinction for downstream processing

**Formatting:** `indent=2` for human-readable output (can be piped to `jq` for further processing).

## Markdown Rendering

### render_markdown() Function (lines 331-486)

Generates markdown suitable for GitHub/Azure DevOps PR comments.

#### Parameters

| Parameter | Type | Default | Purpose |
|-----------|------|---------|---------|
| `data` | `dict` | Required | Parsed LLM response |
| `ci_mode` | `bool` | `False` | Include risk assessment and verdict |
| `custom_title` | `str` | `None` | Custom title (default: "What-If Deployment Review") |
| `no_block` | `bool` | `False` | Append "(non-blocking)" to title |
| `low_confidence_data` | `dict` | `None` | Low-confidence resources |
| `platform` | `str` | `None` | CI/CD platform (`"github"`, `"azuredevops"`, or `None`) |
| `whatif_content` | `str` | `None` | Raw What-If output to include as collapsible section |

**Returns:** Markdown string (printed to stdout or passed to PR comment APIs).

#### Output Structure

**Standard Mode:**
```markdown
**Summary:** 1 resource created.

<details>
<summary>📋 View changed resources (High Confidence)</summary>

| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | myApp    | Web  | Create | Creates web app |

</details>
```

**CI Mode:**
```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | Low | No drift detected |
| PR Intent Alignment | Low | Changes match PR |

**Summary:** 1 resource created.

<details>
<summary>📋 View changed resources (High Confidence)</summary>

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | myApp    | Web  | Create | Low  | Creates web app |

</details>

---

### Verdict: ✅ SAFE
**Reasoning:** Changes align with PR intent. Only low-risk operations detected.
```

#### Key Features

**1. Title Customization (lines 346-350)**

```python
title = custom_title if custom_title else "What-If Deployment Review"
if no_block:
    title = f"{title} (non-blocking)"
lines.append(f"## {title}")
```

**Use Case:** Custom titles for multiple deployment stages (e.g., "Production Deployment Review").

**2. Collapsible Resource Table with High Confidence Label (lines 389-392)**

```markdown
<details>
<summary>📋 View changed resources (High Confidence)</summary>
...
</details>
```

**Rationale:**
- Reduces PR comment noise
- Allows reviewers to expand only if needed
- Keeps focus on risk assessment (CI mode)
- Explicitly labels resources as "High Confidence" to distinguish from potential noise

**3. Noise Section (lines 439-461)**

If low-confidence resources exist:
```markdown
<details>
<summary>⚠️ Potential Azure What-If Noise (excluded from analysis)</summary>

| # | Resource | Type | Action | Confidence Reason |
|---|----------|------|--------|-------------------|
| 1 | subnet   | VNET | Modify | IPv6 flag change  |

</details>
```

**Design:** Also collapsible to avoid cluttering PR comment.

**4. Raw What-If Output (`--include-whatif` flag)**

When `whatif_content` is provided (via `--include-whatif` CLI flag), the raw Azure What-If output is included as a collapsible section wrapped in a code fence:

```markdown
<details>
<summary>📄 Raw What-If Output</summary>

```
Resource changes: 2 to create.
+ Microsoft.Storage/storageAccounts/mystorage
...
```

</details>
```

**Design:**
- Opt-in only — no output when `whatif_content` is `None`
- Code fence prevents markdown injection from raw What-If text
- Positioned after noise section, before CI verdict

**5. Dynamic Risk Column (lines 395-408)**

```python
if ci_mode:
    lines.append("| # | Resource | Type | Action | Risk | Summary |")
    lines.append("|---|----------|------|--------|------|---------|")
else:
    lines.append("| # | Resource | Type | Action | Summary |")
    lines.append("|---|----------|------|--------|---------|")
```

**Table adapts** to include Risk column only in CI mode.

## Integration with CLI

### Usage in cli.py (lines 480-486)

```python
# Render output
if format == "table":
    render_table(high_confidence_data, verbose=verbose, no_color=no_color, ci_mode=ci, low_confidence_data=low_confidence_data)
elif format == "json":
    render_json(high_confidence_data, low_confidence_data=low_confidence_data)
elif format == "markdown":
    raw_whatif = whatif_content if include_whatif else None
    markdown = render_markdown(high_confidence_data, ci_mode=ci, custom_title=comment_title, no_block=no_block, low_confidence_data=low_confidence_data, platform=platform_ctx.platform, whatif_content=raw_whatif)
    print(markdown)
```

### Data Flow

```
LLM Response → extract_json() → filter_by_confidence()
    ↓
(high_confidence_data, low_confidence_data)
    ↓
render_table() / render_json() / render_markdown()
    ↓
stdout
```

## Design Principles

### 1. Progressive Disclosure

- **Table mode:** Main table shown by default, verbose details optional
- **Markdown mode:** Resource changes collapsed, expandable on demand

**Rationale:** Reduce information overload, let users drill down as needed.

### 2. Consistent Symbols

Same action symbols (✅ ✏️ ❌) used across:
- Table rendering
- Markdown rendering
- PR comments

**Benefits:**
- Users recognize patterns instantly
- Visual consistency across interfaces

### 3. Graceful Degradation

- No color codes when piped (`isatty()` check)
- Default values for missing LLM fields
- Handles missing intent bucket gracefully

**Philosophy:** Always produce usable output, even with partial data.

### 4. Audience-Specific Formatting

| Format | Audience | Features |
|--------|----------|----------|
| Table | Interactive developers | Colors, symbols, terminal-optimized |
| JSON | Automation scripts | Structured, machine-parseable |
| Markdown | Code reviewers | Collapsible sections, risk emphasis |

**Each format optimized** for its primary use case.

### 5. Two-Tier Data Structure

High-confidence and low-confidence resources separated in:
- JSON output (top-level keys)
- Table rendering (separate "Potential Noise" section)
- Markdown (separate collapsible section)

**Benefits:**
- Clear distinction between signal and noise
- Enables filtering in automation
- Preserves full LLM output for debugging

## Performance Characteristics

- **Table rendering:** O(n) where n = number of resources
- **JSON rendering:** O(n) + JSON serialization overhead
- **Markdown rendering:** O(n) + string concatenation
- **Memory:** Minimal - operates on already-parsed dict

**Bottleneck:** LLM API call, not rendering.

## Testing Strategy

### Unit Tests

```python
# Mock data
data = {
    "resources": [{
        "resource_name": "test",
        "resource_type": "Storage",
        "action": "Create",
        "summary": "Test summary"
    }],
    "overall_summary": "1 resource created"
}

# Test table rendering (capture stdout)
render_table(data, no_color=True)  # Verify table structure

# Test JSON rendering
render_json(data)  # Verify JSON structure

# Test markdown rendering
markdown = render_markdown(data, ci_mode=True)
assert "## What-If Deployment Review" in markdown
```

### Integration Tests

Verify rendering with real LLM responses:
- Large resource counts (50+ resources)
- Missing fields (graceful defaults)
- Low-confidence filtering
- CI mode vs. standard mode

## Next Steps

For details on related modules:
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - How format is selected via `--format` flag
- [06-NOISE-FILTERING.md](06-NOISE-FILTERING.md) - How `low_confidence_data` is generated
- [09-PR-INTEGRATION.md](09-PR-INTEGRATION.md) - How `render_markdown()` output is posted to PRs
