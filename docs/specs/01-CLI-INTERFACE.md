# 01 - CLI Interface and Orchestration

## Purpose

The `cli.py` module serves as the main entry point and orchestrates the entire analysis pipeline. It handles command-line argument parsing, smart defaults, platform auto-detection, LLM invocation, confidence filtering, CI mode logic, and exit code handling.

**File:** `bicep_whatif_advisor/cli.py` (634 lines)

## Implementation Overview

### Entry Point

The tool is invoked via console script (defined in `pyproject.toml`):
```bash
bicep-whatif-advisor [OPTIONS]
```

This maps to the `main()` function decorated with `@click.command()`.

### Core Function Signature

```python
@click.command()
@click.option(...)  # 22 options total
@click.version_option(version=__version__)
def main(
    provider: str,
    model: str,
    format: str,
    verbose: bool,
    no_color: bool,
    ci: bool,
    diff: str,
    diff_ref: str,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str,
    post_comment: bool,
    pr_url: str,
    bicep_dir: str,
    pr_title: str,
    pr_description: str,
    no_block: bool,
    comment_title: str,
    noise_file: str,
    noise_threshold: int,
    no_builtin_patterns: bool
):
    """Analyze Azure What-If deployment output using LLMs."""
```

## Command-Line Options

### LLM Provider Configuration

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--provider`, `-p` | Choice | `anthropic` | LLM provider: `anthropic`, `azure-openai`, `ollama` |
| `--model`, `-m` | String | `None` | Override default model for provider |

**Implementation:**
```python
@click.option(
    "--provider", "-p",
    type=click.Choice(["anthropic", "azure-openai", "ollama"], case_sensitive=False),
    default="anthropic",
    help="LLM provider to use"
)
@click.option(
    "--model", "-m",
    type=str,
    default=None,
    help="Override the default model for the provider"
)
```

**Usage:**
```bash
bicep-whatif-advisor --provider anthropic  # Default
bicep-whatif-advisor --provider azure-openai --model gpt-4
bicep-whatif-advisor --provider ollama --model llama3.1
```

### Output Formatting

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--format`, `-f` | Choice | `table` | Output format: `table`, `json`, `markdown` |
| `--verbose`, `-v` | Boolean | `False` | Include property-level change details for modified resources |
| `--no-color` | Boolean | `False` | Disable colored output |

**Implementation:**
```python
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format"
)
@click.option("--verbose", "-v", is_flag=True, help="Include property-level change details for modified resources")
@click.option("--no-color", is_flag=True, help="Disable colored output")
```

**Usage:**
```bash
bicep-whatif-advisor --format json | jq '.resources[].resource_name'
bicep-whatif-advisor --verbose  # Show property-level changes
bicep-whatif-advisor --no-color  # For piping to files
```

### CI/CD Mode

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--ci` | Boolean | `False` | Enable CI mode with risk assessment |
| `--diff`, `-d` | String | `None` | Path to git diff file |
| `--diff-ref` | String | `HEAD~1` | Git reference to diff against |
| `--drift-threshold` | Choice | `high` | Fail if drift risk ≥ threshold (`low`/`medium`/`high`) |
| `--intent-threshold` | Choice | `high` | Fail if intent risk ≥ threshold |
| `--operations-threshold` | Choice | `high` | Fail if operations risk ≥ threshold |
| `--no-block` | Boolean | `False` | Report findings without failing pipeline |

**Implementation:**
```python
@click.option("--ci", is_flag=True, help="Enable CI mode with risk assessment and deployment gate")
@click.option("--diff", "-d", type=str, default=None, help="Path to git diff file (CI mode only)")
@click.option("--diff-ref", type=str, default="HEAD~1", help="Git reference to diff against (default: HEAD~1)")
@click.option(
    "--drift-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if drift risk meets or exceeds this level (CI mode only)"
)
# ... similar for intent-threshold and operations-threshold
@click.option("--no-block", is_flag=True, help="Don't fail pipeline even if deployment is unsafe - only report findings (CI mode only)")
```

**Usage:**
```bash
# Basic CI mode
az deployment group what-if ... | bicep-whatif-advisor --ci

# Strict thresholds
bicep-whatif-advisor --ci \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Report-only mode (no blocking)
bicep-whatif-advisor --ci --no-block
```

### PR Integration

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--post-comment` | Boolean | `False` | Post summary as PR comment (auto-enabled if token detected) |
| `--pr-url` | String | `None` | PR URL for posting comments (auto-detected) |
| `--pr-title` | String | `None` | PR title for intent analysis (auto-detected) |
| `--pr-description` | String | `None` | PR description for intent analysis (auto-detected) |
| `--comment-title` | String | `None` | Custom title for PR comment (default: "What-If Deployment Review") |

**Implementation:**
```python
@click.option("--post-comment", is_flag=True, help="Post summary as PR comment (CI mode only)")
@click.option("--pr-url", type=str, default=None, help="PR URL for posting comments (auto-detected if not provided)")
@click.option("--pr-title", type=str, default=None, help="Pull request title for intent analysis (CI mode only)")
@click.option("--pr-description", type=str, default=None, help="Pull request description for intent analysis (CI mode only)")
@click.option("--comment-title", type=str, default=None, help="Custom title for PR comment (default: 'What-If Deployment Review')")
```

**Usage:**
```bash
# Auto-detect PR metadata in GitHub Actions
bicep-whatif-advisor --ci --post-comment

# Manual PR metadata
bicep-whatif-advisor --ci \
  --pr-title "Add monitoring resources" \
  --pr-description "This PR adds Application Insights"
```

### Advanced Options

| Flag | Type | Default | Description |
|------|------|---------|-------------|
| `--bicep-dir` | String | `.` | Path to Bicep source files for context |
| `--noise-file` | String | `None` | Path to custom noise patterns file (additive with built-ins) |
| `--noise-threshold` | Integer | `80` | Similarity threshold % for `fuzzy:` prefix patterns only (0-100) |
| `--no-builtin-patterns` | Flag | `False` | Disable the bundled built-in noise patterns |
| `--include-whatif` | Flag | `False` | Include raw What-If output in markdown/PR comment as collapsible section |

**Implementation:**
```python
@click.option("--bicep-dir", type=str, default=".", help="Path to Bicep source files for context (CI mode only)")
@click.option("--noise-file", type=str, default=None, help="Path to additional noise patterns file (additive with built-in patterns)")
@click.option("--noise-threshold", type=int, default=80, help="Similarity threshold percentage for 'fuzzy:' prefix patterns only (default: 80)")
@click.option("--no-builtin-patterns", is_flag=True, help="Disable the built-in Azure What-If noise patterns")
@click.option("--include-whatif", is_flag=True, help="Include raw What-If output in PR comment as collapsible section")
```

**Usage:**
```bash
# Load Bicep source for context
bicep-whatif-advisor --ci --bicep-dir ./infrastructure

# Add custom noise patterns (built-ins still active)
bicep-whatif-advisor --noise-file ./patterns.txt

# Use only custom patterns, disable built-ins
bicep-whatif-advisor --no-builtin-patterns --noise-file ./patterns.txt --noise-threshold 90

# Include raw What-If output in PR comment for reviewer reference
bicep-whatif-advisor --ci --post-comment --include-whatif
```

## Orchestration Flow

### Main Execution Pipeline (lines 282-521)

```python
def main(...):
    try:
        # 1. Read stdin
        whatif_content = read_stdin()  # Line 284

        # 2. Auto-detect platform context
        platform_ctx = detect_platform()  # Line 287

        # 3. Apply smart defaults based on platform
        if platform_ctx.platform != "local":  # Lines 290-326
            # Auto-enable CI mode
            # Auto-set diff reference
            # Auto-populate PR metadata
            # Auto-enable PR comments if token available

        # 4. Get diff content if CI mode
        if ci:  # Lines 328-338
            diff_content = get_diff(diff, diff_ref)
            bicep_content = _load_bicep_files(bicep_dir)

        # 5. Apply pre-LLM noise filtering
        noise_patterns = load_builtin_patterns()  # Always loaded unless --no-builtin-patterns
        if noise_file:
            noise_patterns += load_user_patterns(noise_file)  # Additive with built-ins
        whatif_content, num_filtered = filter_whatif_text(whatif_content, noise_patterns)

        # 6. Get LLM provider
        llm_provider = get_provider(provider, model)

        # 7. Build prompts (receives already-cleaned whatif_content)
        system_prompt = build_system_prompt(...)
        user_prompt = build_user_prompt(...)

        # 8. Call LLM
        response_text = llm_provider.complete(system_prompt, user_prompt)

        # 9. Parse JSON response
        data = extract_json(response_text)

        # 10. Validate required fields
        if "resources" not in data:
            # Warn and add empty list

        # 11. Filter by LLM-assigned confidence
        high_confidence_data, low_confidence_data = filter_by_confidence(data)

        # 12. Re-analyze if noise filtered in CI mode
        if ci and low_confidence_data.get("resources"):  # Lines 413-478
            # Reconstruct filtered What-If output
            # Re-call LLM with high-confidence resources only
            # Update risk_assessment and verdict

        # 13. Render output
        if format == "table":  # Lines 480-486
            render_table(...)
        elif format == "json":
            render_json(...)
        elif format == "markdown":
            render_markdown(...)

        # 14. CI mode: evaluate verdict and post comment
        if ci:  # Lines 489-518
            is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(...)

            if post_comment:
                _post_pr_comment(...)

            # Exit with appropriate code
            if is_safe:
                sys.exit(0)
            else:
                if no_block:
                    sys.exit(0)  # Report only
                else:
                    sys.exit(1)  # Block deployment

        # 15. Standard mode: exit successfully
        sys.exit(0)  # Line 521

    except InputError as e:  # Lines 523-533
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(2)

    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.\n")
        sys.exit(130)

    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
```

## Smart Defaults (Platform Auto-Detection)

### Implementation (lines 286-326)

When a CI/CD platform is detected, the CLI automatically:

1. **Auto-enables CI mode**
   ```python
   if platform_ctx.platform != "local":
       if not ci:
           platform_name = ("GitHub Actions" if platform_ctx.platform == "github" else "Azure DevOps")
           sys.stderr.write(f"🤖 Auto-detected {platform_name} environment - enabling CI mode\n")
           ci = True
   ```

2. **Auto-sets diff reference**
   ```python
   if diff_ref == "HEAD~1" and platform_ctx.base_branch:
       diff_ref = platform_ctx.get_diff_ref()  # e.g., "origin/main"
       sys.stderr.write(f"📊 Auto-detected diff reference: {diff_ref}\n")
   ```

3. **Auto-populates PR metadata**
   ```python
   if not pr_title and platform_ctx.pr_title:
       pr_title = platform_ctx.pr_title
       title_preview = pr_title[:60] + "..." if len(pr_title) > 60 else pr_title
       sys.stderr.write(f"📝 Auto-detected PR title: {title_preview}\n")

   if not pr_description and platform_ctx.pr_description:
       pr_description = platform_ctx.pr_description
       desc_lines = len(pr_description.splitlines())
       sys.stderr.write(f"📄 Auto-detected PR description ({desc_lines} lines)\n")
   ```

4. **Auto-enables PR comments if auth token detected**
   ```python
   if not post_comment:
       has_token = (
           (platform_ctx.platform == "github" and os.environ.get("GITHUB_TOKEN")) or
           (platform_ctx.platform == "azuredevops" and os.environ.get("SYSTEM_ACCESSTOKEN"))
       )
       if has_token:
           sys.stderr.write("💬 Auto-enabling PR comments (auth token detected)\n")
           post_comment = True
   ```

**Result:** Users can run `bicep-whatif-advisor` with no flags in CI pipelines and get full functionality.

## Confidence Filtering

### filter_by_confidence() Function (lines 81-127)

Splits LLM response into high-confidence and low-confidence resources:

```python
def filter_by_confidence(data: dict) -> tuple[dict, dict]:
    """Filter resources by confidence level.

    Splits resources into high-confidence (medium/high) and low-confidence (low) lists.
    Low-confidence resources are likely Azure What-If noise and should be excluded
    from risk analysis but displayed separately.
    """
    resources = data.get("resources", [])

    high_confidence_resources = []
    low_confidence_resources = []

    for resource in resources:
        confidence = resource.get("confidence_level", "medium").lower()

        if confidence in ("low", "noise"):
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

    # Build low-confidence data dict (no CI fields)
    low_confidence_data = {
        "resources": low_confidence_resources,
        "overall_summary": ""
    }

    return high_confidence_data, low_confidence_data
```

**Key Design:** CI mode fields (`risk_assessment`, `verdict`) only preserved in high-confidence data.

## CI Mode Re-Analysis (lines 410-478)

### Problem

When confidence filtering removes resources, the LLM's `risk_assessment` becomes stale (generated before filtering).

### Solution

Re-prompt the LLM with only high-confidence resources to get an accurate risk assessment:

```python
if ci and low_confidence_data.get("resources"):
    num_filtered = len(low_confidence_data["resources"])
    num_remaining = len(high_confidence_data.get("resources", []))

    sys.stderr.write(
        f"🔄 Recalculating risk assessment: {num_filtered} low-confidence resources "
        f"filtered, {num_remaining} high-confidence resources remain\n"
    )

    # Reconstruct a minimal What-If output from high-confidence resources
    filtered_whatif_lines = ["Resource changes:"]
    for resource in high_confidence_data.get("resources", []):
        action_symbol = {
            "create": "+", "modify": "~", "delete": "-",
            "deploy": "=", "nochange": "*", "ignore": "x"
        }.get(resource.get("action", "").lower(), "~")

        filtered_whatif_lines.append(f"{action_symbol} {resource['resource_name']}")
        filtered_whatif_lines.append(f"  Summary: {resource['summary']}")

    filtered_whatif_content = "\n".join(filtered_whatif_lines)

    # Re-build prompts with filtered data
    filtered_system_prompt = build_system_prompt(...)
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

**Key Insight:** This prevents false positives where noise resources influence risk buckets.

## JSON Extraction (lines 17-78)

### extract_json() Function

Handles malformed LLM responses by attempting to extract JSON from text:

```python
def extract_json(text: str) -> dict:
    """Attempt to extract JSON from LLM response.

    Raises:
        ValueError: If no valid JSON found
    """
    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find JSON by balanced brace matching
    start = text.find('{')
    if start == -1:
        raise ValueError("Could not extract valid JSON from LLM response")

    # Find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                break

    raise ValueError("Could not extract valid JSON from LLM response")
```

**Features:**
- Handles string escaping correctly
- Supports deeply nested JSON
- Fails gracefully with clear error message

## Exit Code Logic

### Exit Codes (lines 489-530)

| Code | Condition | Implementation |
|------|-----------|----------------|
| `0` | Success (safe deployment) | `sys.exit(0)` at line 503, 516, 521 |
| `1` | Unsafe deployment (CI mode) | `sys.exit(1)` at line 518 |
| `2` | Invalid input | `sys.exit(2)` at line 525 |
| `130` | User interrupt (Ctrl+C) | `sys.exit(130)` at line 529 |

### CI Mode Exit Code Logic

```python
if ci:
    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(...)

    if post_comment:
        _post_pr_comment(...)

    if is_safe:
        sys.exit(0)  # Safe to deploy
    else:
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

**Note:** Exit code `1` is used for unsafe deployments in CI mode (not `2`), to distinguish from input validation errors.

## Helper Functions

### _load_bicep_files() (lines 536-596)

Loads Bicep source files for LLM context:

```python
def _load_bicep_files(bicep_dir: str) -> Optional[str]:
    """Load all Bicep files from directory for context.

    Returns:
        Combined content of all .bicep files, or None if no files found
    """
    from pathlib import Path

    # Resolve to absolute path and validate
    base_path = Path(bicep_dir).resolve()

    if not base_path.exists() or not base_path.is_dir():
        sys.stderr.write(f"Warning: Bicep directory does not exist...\n")
        return None

    # Find all .bicep files recursively
    bicep_files = []
    for file_path in base_path.rglob("*.bicep"):
        # Security: Ensure file is within base_path (prevent path traversal)
        try:
            file_path.resolve().relative_to(base_path)
        except ValueError:
            sys.stderr.write(f"Warning: Skipping file outside base directory: {file_path}\n")
            continue

        # Security: Skip symbolic links
        if file_path.is_symlink():
            sys.stderr.write(f"Warning: Skipping symbolic link: {file_path}\n")
            continue

        bicep_files.append(file_path)

    # Read file contents (limit to 5 files to avoid huge context)
    contents = []
    for file_path in bicep_files[:5]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                rel_path = file_path.relative_to(base_path)
                contents.append(f"// File: {rel_path}\n{f.read()}")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Warning: Could not read {file_path}: {e}\n")
            continue

    return "\n\n".join(contents) if contents else None
```

**Security Features:**
- Path traversal protection
- Symbolic link filtering
- Encoding error handling
- 5-file limit to prevent context overflow

### _post_pr_comment() (lines 599-629)

Routes PR comment posting to appropriate platform:

```python
def _post_pr_comment(markdown: str, pr_url: str = None) -> None:
    """Post markdown comment to PR."""
    import os

    # Detect GitHub or Azure DevOps
    if os.environ.get("GITHUB_TOKEN"):
        from .ci.github import post_github_comment
        success = post_github_comment(markdown, pr_url)
        if success:
            sys.stderr.write("Posted comment to GitHub PR.\n")
        else:
            sys.stderr.write("Warning: Failed to post comment to GitHub PR.\n")

    elif os.environ.get("SYSTEM_ACCESSTOKEN"):
        from .ci.azdevops import post_azdevops_comment
        success = post_azdevops_comment(markdown)
        if success:
            sys.stderr.write("Posted comment to Azure DevOps PR.\n")
        else:
            sys.stderr.write("Warning: Failed to post comment to Azure DevOps PR.\n")

    else:
        sys.stderr.write(
            "Warning: --post-comment requires GITHUB_TOKEN or SYSTEM_ACCESSTOKEN.\n"
            "Skipping PR comment.\n"
        )
```

**Auto-detection:** Uses environment variables to determine platform.

## Error Handling

### Exception Handling Strategy (lines 523-533)

```python
try:
    # Main execution
    ...
except InputError as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(2)  # Invalid input

except KeyboardInterrupt:
    sys.stderr.write("\nInterrupted by user.\n")
    sys.exit(130)  # Standard UNIX interrupt code

except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(1)  # General error
```

**Exit Code Contract:**
- `2` - Input validation errors (InputError)
- `130` - User interrupt
- `1` - All other errors (including API failures, JSON parsing, etc.)

## Integration Points

### Imports

```python
from . import __version__                        # Version string
from .input import read_stdin, InputError        # Input validation
from .prompt import build_system_prompt, build_user_prompt  # Prompt construction
from .providers import get_provider              # LLM provider factory
from .render import render_table, render_json, render_markdown  # Output formatting
from .ci.platform import detect_platform         # Platform auto-detection
from .noise_filter import apply_noise_filtering  # Summary-based filtering
```

### Lazy Imports (Conditional)

```python
# Only imported if CI mode enabled
from .ci.diff import get_diff                    # Git diff collection
from .ci.risk_buckets import evaluate_risk_buckets  # Risk assessment
from .ci.github import post_github_comment       # GitHub API
from .ci.azdevops import post_azdevops_comment   # Azure DevOps API
```

**Rationale:** Avoid importing CI modules in standard mode for faster startup.

## Configuration Sources

The CLI accepts configuration from multiple sources (in order of precedence):

1. **Command-line flags** (highest priority)
2. **Platform auto-detection** (smart defaults)
3. **Environment variables** (API keys, CI metadata)
4. **Hard-coded defaults** (lowest priority)

### Example Precedence

For PR title in GitHub Actions:
1. `--pr-title "Custom Title"` (explicit flag)
2. `platform_ctx.pr_title` (auto-detected from `GITHUB_EVENT_PATH`)
3. `None` (no PR title available)

## Future Improvements (TODOs in Code)

### Lines 402-405

```python
# TODO: Add --show-all-confidence flag to display medium/high/low separately
# TODO: Consider adding --confidence-threshold to make filtering configurable
# TODO: If LLM-only confidence scoring proves unreliable, evaluate hybrid
#       approach combining LLM + hardcoded noise patterns
```

These TODOs suggest potential future features for more granular confidence control.

## Next Steps

For details on specific modules called by the CLI:
- [02-INPUT-VALIDATION.md](02-INPUT-VALIDATION.md) - `read_stdin()` implementation
- [03-PROVIDER-SYSTEM.md](03-PROVIDER-SYSTEM.md) - `get_provider()` and LLM APIs
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - `build_system_prompt()` and `build_user_prompt()`
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - `render_table()`, `render_json()`, `render_markdown()`
- [06-NOISE-FILTERING.md](06-NOISE-FILTERING.md) - `apply_noise_filtering()`
- [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) - `detect_platform()` implementation
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) - `evaluate_risk_buckets()` logic
- [09-PR-INTEGRATION.md](09-PR-INTEGRATION.md) - PR comment posting
- [10-GIT-DIFF.md](10-GIT-DIFF.md) - `get_diff()` implementation
