# Phase 2 Implementation Prompt: Prompt Engineering and Output Rendering

## Objective

Implement LLM prompt construction, API communication, JSON response parsing, and multi-format output rendering (table, JSON, markdown).

## Context

Building on Phase 1's core foundation, this phase adds the intelligence layer: constructing effective prompts for LLMs to analyze What-If output, calling the LLM providers, parsing structured responses, and rendering results in user-friendly formats.

## Specifications to Reference

Read these specification files before starting:
- `specifications/03-PROMPT-ENGINEERING.md` - Prompt construction and schema
- `specifications/04-OUTPUT-RENDERING.md` - Output formatting details

## Tasks

### Task 1: Prompt Construction (prompt.py)

Create `bicep_whatif_advisor/prompt.py`:

#### Step 1.1: Standard Mode System Prompt

**Create `_build_standard_system_prompt()` function:**

```python
def _build_standard_system_prompt(verbose: bool = False) -> str:
    """Build system prompt for standard analysis mode.

    Args:
        verbose: Include property-level changes in schema

    Returns:
        System prompt string with JSON schema
    """
```

**Prompt Structure:**

1. **Persona:**
   ```
   You are an Azure infrastructure expert. You analyze Azure Resource Manager
   What-If deployment output and produce concise, accurate summaries.
   ```

2. **Response Format Instruction:**
   ```
   You must respond with ONLY valid JSON matching this schema, no other text:
   ```

3. **JSON Schema:**
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

4. **Verbose Mode Addition:** If `verbose=True`, add to schema:
   ```
   For resources with action "Modify", also include a "changes" field:
   an array of strings describing each property-level change.
   ```

5. **Confidence Assessment Guidelines:**
   ```
   ## Confidence Assessment

   Evaluate each resource change to determine if it's a real change or likely Azure What-If noise:

   HIGH confidence (real changes):
   - Resource creation, deletion, or state changes
   - Configuration modifications with clear intent
   - Security, networking, or compute changes

   MEDIUM confidence (potentially real but uncertain):
   - Retention policies or analytics settings
   - Subnet references changing from hardcoded to dynamic
   - Configuration changes that might be platform-managed

   LOW confidence (likely What-If noise):
   - Metadata-only changes (etag, id, provisioningState, type)
   - logAnalyticsDestinationType property changes
   - IPv6 flags (disableIpv6, enableIPv6Addressing)
   - Computed properties (resourceGuid)
   - Read-only or system-managed properties

   IMPORTANT: Use your judgment - these are GUIDELINES, not rigid patterns.
   ```

#### Step 1.2: CI Mode System Prompt

**Create `_build_ci_system_prompt()` function:**

```python
def _build_ci_system_prompt(pr_title: str = None, pr_description: str = None) -> str:
    """Build system prompt for CI mode deployment safety review.

    Args:
        pr_title: Pull request title (optional)
        pr_description: Pull request description (optional)

    Returns:
        System prompt with risk assessment schema
    """
```

**Prompt Structure:**

1. **Persona:**
   ```
   You are an Azure infrastructure deployment safety reviewer. You are given:
   1. The Azure What-If output showing planned infrastructure changes
   2. The source code diff (Bicep/ARM template changes) that produced these changes
   ```

   If `pr_title` or `pr_description` provided, add:
   ```
   3. The pull request title and description stating the INTENDED purpose of this change
   ```

2. **Task:**
   ```
   Evaluate the deployment for safety and correctness across three independent risk buckets:
   ```

3. **Risk Bucket Definitions:**

   Include detailed definitions for:
   - Bucket 1: Infrastructure Drift
   - Bucket 2: Risky Azure Operations
   - Bucket 3: Pull Request Intent Alignment (ONLY if PR metadata provided)

4. **JSON Schema:**

   If PR metadata provided (intent bucket included):
   ```json
   {
     "resources": [ ... with risk_level and risk_reason fields ... ],
     "overall_summary": "string",
     "risk_assessment": {
       "drift": { "risk_level": "low|medium|high", "concerns": [...], "reasoning": "..." },
       "intent": { "risk_level": "low|medium|high", "concerns": [...], "reasoning": "..." },
       "operations": { "risk_level": "low|medium|high", "concerns": [...], "reasoning": "..." }
     },
     "verdict": {
       "safe": true/false,
       "highest_risk_bucket": "drift|intent|operations|none",
       "overall_risk_level": "low|medium|high",
       "reasoning": "string"
     }
   }
   ```

   If NO PR metadata (intent bucket omitted):
   ```json
   {
     "risk_assessment": {
       "drift": { ... },
       "operations": { ... }
       // NO "intent" bucket
     },
     "verdict": {
       "highest_risk_bucket": "drift|operations|none"  // NO "intent" option
     }
   }
   ```

5. **Include same confidence assessment guidelines as standard mode**

#### Step 1.3: User Prompt Construction

**Create `build_user_prompt()` function:**

```python
def build_user_prompt(
    whatif_content: str,
    diff_content: str = None,
    bicep_content: str = None,
    pr_title: str = None,
    pr_description: str = None
) -> str:
    """Build user prompt with What-If output and optional CI context.

    Args:
        whatif_content: Azure What-If output
        diff_content: Git diff (triggers CI mode)
        bicep_content: Bicep source code (optional)
        pr_title: PR title (optional)
        pr_description: PR description (optional)

    Returns:
        Formatted user prompt string
    """
```

**Standard Mode (diff_content is None):**
```
Analyze the following Azure What-If output:

<whatif_output>
{whatif_content}
</whatif_output>
```

**CI Mode (diff_content provided):**
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
- Only include PR intent section if pr_title or pr_description provided
- Only include bicep_source section if bicep_content provided
- Use XML-style tags for clear section delineation

#### Step 1.4: Public API Function

**Create `build_system_prompt()` function:**

```python
def build_system_prompt(
    verbose: bool = False,
    ci_mode: bool = False,
    pr_title: str = None,
    pr_description: str = None
) -> str:
    """Build system prompt based on mode.

    Args:
        verbose: Include property-level changes (standard mode only)
        ci_mode: Use CI mode risk assessment
        pr_title: PR title (CI mode only)
        pr_description: PR description (CI mode only)

    Returns:
        System prompt string
    """
    if ci_mode:
        return _build_ci_system_prompt(pr_title, pr_description)
    else:
        return _build_standard_system_prompt(verbose)
```

### Task 2: JSON Response Parsing (cli.py addition)

Add `extract_json()` helper function to `bicep_whatif_advisor/cli.py`:

```python
def extract_json(response_text: str) -> dict:
    """Extract JSON from LLM response text.

    Handles cases where LLM includes explanatory text before/after JSON.

    Args:
        response_text: Raw LLM response

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If no valid JSON found
    """
    # Try parsing as-is first
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # Find balanced braces
    start = response_text.find('{')
    if start == -1:
        raise ValueError("No JSON object found in response")

    # Find matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start, len(response_text)):
        char = response_text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if not in_string:
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    # Found complete JSON object
                    json_str = response_text[start:i+1]
                    try:
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        raise ValueError(f"Invalid JSON: {e}")

    raise ValueError("No complete JSON object found in response")
```

### Task 3: Output Rendering (render.py)

Create `bicep_whatif_advisor/render.py`:

#### Step 3.1: Constants and Imports

```python
"""Output rendering for table, JSON, and markdown formats."""

import json
import sys
import shutil
from rich.console import Console
from rich.table import Table
from rich import box

# Action symbol/color mapping
ACTION_STYLES = {
    "Create": ("✅", "green"),
    "Modify": ("✏️", "yellow"),
    "Delete": ("❌", "red"),
    "Deploy": ("🔄", "blue"),
    "NoChange": ("➖", "dim"),
    "Ignore": ("⬜", "dim"),
}

# Risk level symbol/color mapping
RISK_STYLES = {
    "high": ("🔴", "red"),
    "medium": ("🟡", "yellow"),
    "low": ("🟢", "green"),
}
```

#### Step 3.2: Table Rendering

**Create `render_table()` function:**

```python
def render_table(
    data: dict,
    verbose: bool = False,
    no_color: bool = False,
    ci_mode: bool = False,
    low_confidence_data: dict = None
) -> None:
    """Render results as Rich table.

    Args:
        data: Parsed LLM response
        verbose: Show property-level changes
        no_color: Disable colors
        ci_mode: Include risk assessment
        low_confidence_data: Filtered noise resources
    """
```

**Implementation:**

1. Determine color usage:
   ```python
   use_color = not no_color and sys.stdout.isatty()
   ```

2. Calculate 85% terminal width:
   ```python
   terminal_width = shutil.get_terminal_size().columns
   reduced_width = int(terminal_width * 0.85)
   ```

3. Create console:
   ```python
   console = Console(
       force_terminal=use_color,
       no_color=not use_color,
       width=reduced_width
   )
   ```

4. Print risk bucket summary (CI mode only):
   ```python
   if ci_mode and "risk_assessment" in data:
       _print_risk_bucket_summary(console, data["risk_assessment"], use_color)
   ```

5. Create main table:
   ```python
   table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))
   table.add_column("#", style="dim", width=4)
   table.add_column("Resource", style="bold")
   table.add_column("Type")
   table.add_column("Action", justify="center")
   if ci_mode:
       table.add_column("Risk", justify="center")
   table.add_column("Summary")
   ```

6. Add rows with color:
   ```python
   resources = data.get("resources", [])
   for idx, resource in enumerate(resources, 1):
       action = resource.get("action", "Unknown")
       symbol, color = ACTION_STYLES.get(action, ("", ""))

       row = [
           str(idx),
           resource.get("resource_name", ""),
           resource.get("resource_type", ""),
           _colorize(f"{symbol} {action}", color, use_color),
       ]

       if ci_mode:
           risk = resource.get("risk_level", "low")
           risk_symbol, risk_color = RISK_STYLES.get(risk, ("", ""))
           row.append(_colorize(f"{risk_symbol} {risk.capitalize()}", risk_color, use_color))

       row.append(resource.get("summary", ""))
       table.add_row(*row)
   ```

7. Print table and summary
8. Print verbose details (if enabled)
9. Print CI verdict (if CI mode)
10. Print low-confidence section (if data provided)

**Helper Functions:**

Create `_colorize()`, `_print_risk_bucket_summary()`, `_print_verbose_details()`, `_print_ci_verdict()`, `_print_noise_section()` following specification.

#### Step 3.3: JSON Rendering

**Create `render_json()` function:**

```python
def render_json(data: dict, low_confidence_data: dict = None) -> None:
    """Render results as JSON.

    Args:
        data: Parsed LLM response
        low_confidence_data: Filtered noise resources
    """
    output = {
        "high_confidence": data,
    }
    if low_confidence_data:
        output["low_confidence"] = low_confidence_data

    print(json.dumps(output, indent=2))
```

#### Step 3.4: Markdown Rendering

**Create `render_markdown()` function:**

```python
def render_markdown(
    data: dict,
    ci_mode: bool = False,
    custom_title: str = None,
    no_block: bool = False,
    low_confidence_data: dict = None
) -> str:
    """Render results as markdown for PR comments.

    Args:
        data: Parsed LLM response
        ci_mode: Include risk assessment
        custom_title: Override default title
        no_block: Mark as non-blocking
        low_confidence_data: Filtered noise resources

    Returns:
        Markdown-formatted string
    """
```

**Structure:**

1. Title (CI mode only)
2. Risk assessment table (CI mode only)
3. Collapsible resource changes section
4. Overall summary
5. Low-confidence section (if data provided)
6. Verdict (CI mode only)
7. Footer

**Important:** Escape pipe characters in summaries: `.replace("|", "\\|")`

### Task 4: Update CLI (cli.py)

Update `bicep_whatif_advisor/cli.py` to integrate prompts and rendering:

1. **Add imports:**
   ```python
   from .prompt import build_system_prompt, build_user_prompt
   from .render import render_table, render_json, render_markdown
   ```

2. **Update main function:**
   ```python
   def main(provider, model, format, verbose):
       try:
           # Read stdin
           whatif_content = read_stdin()

           # Get provider
           llm_provider = get_provider(provider, model)

           # Build prompts
           system_prompt = build_system_prompt(verbose=verbose, ci_mode=False)
           user_prompt = build_user_prompt(whatif_content)

           # Call LLM
           response_text = llm_provider.complete(system_prompt, user_prompt)

           # Parse JSON
           data = extract_json(response_text)

           # Render output
           if format == "table":
               render_table(data, verbose=verbose)
           elif format == "json":
               render_json(data)
           elif format == "markdown":
               markdown = render_markdown(data)
               print(markdown)

           sys.exit(0)

       except InputError as e:
           sys.stderr.write(f"Error: {e}\n")
           sys.exit(2)
       except Exception as e:
           sys.stderr.write(f"Error: {e}\n")
           sys.exit(1)
   ```

3. **Add `--verbose` flag:**
   ```python
   @click.option("--verbose", "-v", is_flag=True, help="Include property-level changes")
   ```

### Task 5: Testing

**Create test fixtures:**

Create `tests/fixtures/create_only.txt` with sample Azure What-If output showing only Create operations.

**Manual testing:**

```bash
# Test standard mode with table output
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --format table

# Test JSON output
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --format json

# Test markdown output
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --format markdown

# Test verbose mode
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --verbose

# Test with different providers (if API keys set)
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --provider anthropic
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --provider azure-openai
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --provider ollama
```

**Verify:**

1. **Prompt construction:**
   - Add debug print to see system/user prompts
   - Verify JSON schema present
   - Verify confidence instructions included

2. **LLM response:**
   - Verify JSON extraction works
   - Verify handles text before/after JSON

3. **Table rendering:**
   - Verify 85% terminal width
   - Verify ROUNDED box style
   - Verify colored symbols
   - Verify horizontal lines between rows

4. **JSON output:**
   - Verify valid JSON (pipe to `jq`)
   - Verify has resources array
   - Verify has overall_summary

5. **Markdown output:**
   - Verify pipe characters escaped
   - Verify table format correct

## Validation Checklist

- [ ] `prompt.py` created with all prompt building functions
- [ ] Standard system prompt includes JSON schema and confidence guidelines
- [ ] CI system prompt includes risk bucket definitions
- [ ] Intent bucket conditionally included based on PR metadata
- [ ] User prompt includes XML section tags
- [ ] `extract_json()` handles text before/after JSON
- [ ] `extract_json()` handles nested JSON structures
- [ ] `render.py` created with all rendering functions
- [ ] Table rendering uses 85% terminal width
- [ ] Table uses ROUNDED box style with horizontal lines
- [ ] Action symbols and colors correct
- [ ] Risk levels displayed in CI mode
- [ ] JSON output has high_confidence/low_confidence structure
- [ ] Markdown escapes pipe characters
- [ ] Markdown uses collapsible sections
- [ ] CLI updated to call LLM and render output
- [ ] Verbose mode works
- [ ] All three output formats work
- [ ] End-to-end test with fixture passes

## Next Phase

Once Phase 2 is complete and validated, proceed to Phase 3 (CI/CD Platform Detection).

Phase 3 will add:
- Platform detection (GitHub Actions, Azure DevOps)
- PR metadata extraction
- Git diff collection
- Smart defaults based on environment

## Notes

- Use type hints for all function signatures
- Write clear docstrings for all functions
- Keep functions focused and single-purpose
- Handle malformed LLM responses gracefully
- Test with real LLM providers if API keys available, but don't require them
- Confidence scoring is critical for Phase 5 noise filtering
