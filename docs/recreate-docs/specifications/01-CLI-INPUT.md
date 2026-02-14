# Feature Specification: CLI and Input Handling

## Overview

The CLI is the entry point for all user interaction. It uses Click framework for argument parsing and provides comprehensive input validation.

## CLI Framework (Click)

### Command Definition

```python
@click.command()
@click.option("--provider", "-p", type=click.Choice([...]), default="anthropic")
@click.option("--model", "-m", type=str, default=None)
@click.option("--format", "-f", type=click.Choice([...]), default="table")
# ... many more options
@click.version_option(version=__version__)
def main(...):
    """Analyze Azure What-If deployment output using LLMs."""
```

### Required Options

None - all options have defaults or are optional.

### Key Options

**Provider Selection:**
- `--provider` / `-p`: LLM provider (anthropic|azure-openai|ollama)
- `--model` / `-m`: Override default model

**Output Format:**
- `--format` / `-f`: Output format (table|json|markdown)
- `--verbose` / `-v`: Include property-level details
- `--no-color`: Disable colored output

**CI Mode:**
- `--ci`: Enable CI mode
- `--diff` / `-d`: Path to git diff file
- `--diff-ref`: Git reference for diff (default: HEAD~1)
- `--drift-threshold`: Threshold for drift bucket (low|medium|high)
- `--intent-threshold`: Threshold for intent bucket (low|medium|high)
- `--operations-threshold`: Threshold for operations bucket (low|medium|high)
- `--post-comment`: Post summary as PR comment
- `--pr-url`: PR URL for comments (auto-detected)
- `--pr-title`: PR title for intent analysis
- `--pr-description`: PR description for intent analysis
- `--no-block`: Report findings without failing pipeline
- `--comment-title`: Custom title for PR comments
- `--bicep-dir`: Path to Bicep source files for context

**Noise Filtering:**
- `--noise-file`: Path to noise patterns file
- `--noise-threshold`: Similarity threshold percentage (default: 80)

### Version Display

```bash
bicep-whatif-advisor --version
# Output: bicep-whatif-advisor, version 1.4.0
```

Version is defined in `bicep_whatif_advisor/__init__.py`:

```python
__version__ = "1.4.0"
```

## Input Validation

### Module: `input.py`

Handles reading and validating stdin content.

### Key Functions

#### `read_stdin() -> str`

Reads What-If output from stdin with validation.

**Behavior:**

1. **TTY Detection** - If stdin is a terminal (not piped), show usage hint:
   ```
   Error: No input provided. Pipe Azure What-If output to this command:

   az deployment group what-if ... | bicep-whatif-advisor
   ```

2. **Content Validation** - Check for What-If markers:
   - Must contain "Resource changes:" or similar
   - Must contain action symbols: `+ Create`, `~ Modify`, `- Delete`, etc.

3. **Size Limits** - Truncate inputs exceeding 100,000 characters:
   ```
   Warning: Input truncated to 100,000 characters to avoid excessive API costs.
   ```

4. **Empty Input** - Reject empty or whitespace-only input

**Returns:** Validated What-If content as string

**Raises:** `InputError` if validation fails

#### Custom Exception

```python
class InputError(Exception):
    """Raised when input validation fails."""
    pass
```

### Validation Rules

**Valid What-If Indicators:**
- Contains "Resource changes:"
- Contains "Resource and property changes:"
- Contains action symbols:
  - `+ Create`
  - `~ Modify`
  - `- Delete`
  - `= Deploy`
  - `* NoChange`
  - `x Ignore`

**Invalid Inputs:**
- Empty string
- Only whitespace
- No What-If markers
- From a TTY (not piped)

## Error Handling

### Exit Codes

- **0**: Success (standard mode) or safe deployment (CI mode)
- **1**: General error or unsafe deployment (CI mode)
- **2**: Invalid input or configuration error
- **130**: Interrupted by user (Ctrl+C)

### Exception Handling

Main function wraps all logic in try/except:

```python
try:
    # ... main logic
    sys.exit(0)
except InputError as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(2)
except KeyboardInterrupt:
    sys.stderr.write("\nInterrupted by user.\n")
    sys.exit(130)
except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(1)
```

### User-Facing Error Messages

All error messages written to stderr with clear, actionable guidance:

```python
sys.stderr.write("Error: Missing API key. Set ANTHROPIC_API_KEY environment variable.\n")
```

## Orchestration Logic (cli.py)

### Main Flow

1. **Read stdin** → Validate What-If content
2. **Detect platform** → GitHub Actions / Azure DevOps / local
3. **Apply smart defaults** → Auto-enable CI mode, extract PR metadata
4. **Get diff** (if CI mode) → Collect git changes
5. **Get provider** → Initialize LLM provider
6. **Build prompts** → System + user prompts
7. **Call LLM** → Get response
8. **Parse JSON** → Extract structured data
9. **Add defaults** → Ensure confidence fields present
10. **Apply noise filtering** (if noise file provided)
11. **Filter by confidence** → Split high/low confidence resources
12. **Re-analyze** (if noise filtered in CI mode) → Get accurate risk assessment
13. **Render output** → Format as table/JSON/markdown
14. **Evaluate verdict** (if CI mode) → Check risk thresholds
15. **Post comment** (if CI mode + post-comment flag)
16. **Exit** → With appropriate code

### Smart Defaults (Platform Detection)

When platform detected (not local):

```python
if platform_ctx.platform != "local":
    # Auto-enable CI mode
    if not ci:
        sys.stderr.write(f"🤖 Auto-detected {platform_name} environment - enabling CI mode\n")
        ci = True

    # Auto-set diff reference
    if diff_ref == "HEAD~1" and platform_ctx.base_branch:
        diff_ref = platform_ctx.get_diff_ref()
        sys.stderr.write(f"📊 Auto-detected diff reference: {diff_ref}\n")

    # Auto-populate PR metadata
    if not pr_title and platform_ctx.pr_title:
        pr_title = platform_ctx.pr_title
        sys.stderr.write(f"📝 Auto-detected PR title: {title_preview}\n")

    # Auto-enable PR comments if token available
    if not post_comment and has_token:
        sys.stderr.write("💬 Auto-enabling PR comments (auth token detected)\n")
        post_comment = True
```

### JSON Parsing

LLM responses may include markdown fences or extra text. The `extract_json()` function:

1. Try parsing as-is first
2. Find balanced braces `{...}`
3. Handle nested JSON structures
4. Respect string escaping
5. Extract first valid JSON object

```python
def extract_json(text: str) -> dict:
    """Attempt to extract JSON from LLM response."""
    # Try as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find balanced braces
    # ... (implementation details)

    raise ValueError("Could not extract valid JSON from LLM response")
```

## Helper Functions

### `_load_bicep_files(bicep_dir: str) -> Optional[str]`

Loads Bicep source files for context in CI mode.

**Security Considerations:**
- Path traversal prevention
- Symbolic link detection
- Read permission handling
- File limit (max 5 files)

**Returns:** Combined content of .bicep files or None

### `_post_pr_comment(markdown: str, pr_url: str = None) -> None`

Posts markdown comment to GitHub or Azure DevOps PR.

Auto-detects platform based on environment variables:
- `GITHUB_TOKEN` → GitHub
- `SYSTEM_ACCESSTOKEN` → Azure DevOps

## Implementation Checklist

- [ ] Install Click framework
- [ ] Create `input.py` with `read_stdin()` and `InputError`
- [ ] Implement TTY detection
- [ ] Implement What-If marker validation
- [ ] Implement size truncation (100K chars)
- [ ] Create `cli.py` with Click command decorator
- [ ] Add all CLI options
- [ ] Implement version option
- [ ] Implement main orchestration flow
- [ ] Add smart defaults based on platform detection
- [ ] Implement `extract_json()` with balanced brace matching
- [ ] Implement error handling with proper exit codes
- [ ] Add `_load_bicep_files()` helper
- [ ] Add `_post_pr_comment()` helper
- [ ] Write stderr messages for all error conditions
- [ ] Test with sample What-If output
- [ ] Test TTY detection
- [ ] Test error conditions
