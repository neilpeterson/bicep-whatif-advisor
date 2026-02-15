# 02 - Input Validation

## Purpose

The `input.py` module provides robust stdin validation for Azure What-If deployment output. It handles TTY detection, empty input checking, size truncation, and soft validation of What-If format markers.

**File:** `bicep_whatif_advisor/input.py` (66 lines)

## Implementation Overview

### Module Structure

```python
"""Input validation and stdin reading for bicep-whatif-advisor."""

import sys

class InputError(Exception):
    """Exception raised for input validation errors."""
    pass

def read_stdin(max_chars: int = 100000) -> str:
    """Read and validate What-If output from stdin."""
```

## InputError Exception

### Definition (lines 6-8)

```python
class InputError(Exception):
    """Exception raised for input validation errors."""
    pass
```

**Purpose:** Custom exception to distinguish input validation errors from other errors.

**Usage in CLI:**
```python
try:
    whatif_content = read_stdin()
except InputError as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(2)  # Exit code 2 for invalid input
```

**Why Separate Exception?**
- Enables specific exit code (2) for input errors
- Clearer error reporting
- Allows callers to handle input errors differently from API/network errors

## read_stdin() Function

### Function Signature (line 11)

```python
def read_stdin(max_chars: int = 100000) -> str:
    """Read and validate What-If output from stdin.

    Args:
        max_chars: Maximum characters to read before truncating (default: 100,000)

    Returns:
        Validated What-If content as string

    Raises:
        InputError: If stdin is a TTY, empty, or doesn't look like What-If output
    """
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `max_chars` | `int` | `100000` | Maximum characters to read before truncating |

**Rationale for 100,000 characters:**
- Handles deployments with 50+ resources
- Prevents LLM context overflow
- Balances detail vs. token limits

### Return Value

**Type:** `str`

**Content:** Raw Azure What-If output text, potentially truncated

### Validation Pipeline

The function performs four validation steps in order:

## 1. TTY Detection (lines 23-28)

### Purpose

Prevent users from running the command without piping input.

### Implementation

```python
# Check if stdin is a TTY (interactive terminal, not piped)
if sys.stdin.isatty():
    raise InputError(
        "No input detected. Pipe Azure What-If output to this command:\n"
        "  az deployment group what-if ... | bicep-whatif-advisor"
    )
```

### Behavior

| Scenario | Result |
|----------|--------|
| User runs `bicep-whatif-advisor` in terminal | Raises `InputError` with usage hint |
| User pipes input: `az ... \| bicep-whatif-advisor` | Passes check |
| User redirects file: `bicep-whatif-advisor < file.txt` | Passes check |

**Error Message:**
```
Error: No input detected. Pipe Azure What-If output to this command:
  az deployment group what-if ... | bicep-whatif-advisor
```

**Design Note:** The error message includes an example to guide users toward correct usage.

## 2. Empty Input Check (lines 30-35)

### Purpose

Catch cases where stdin is connected but contains no data.

### Implementation

```python
# Read all stdin
content = sys.stdin.read()

# Check if empty
if not content or not content.strip():
    raise InputError("No What-If output received. Input is empty.")
```

### Behavior

| Input | Result |
|-------|--------|
| Empty string | Raises `InputError` |
| Whitespace only (`"   \n  \t"`) | Raises `InputError` |
| Non-empty content | Passes check |

**Error Message:**
```
Error: No What-If output received. Input is empty.
```

## 3. Size Truncation (lines 37-43)

### Purpose

Prevent extremely large inputs from exceeding LLM context limits or causing memory issues.

### Implementation

```python
# Truncate if too large
if len(content) > max_chars:
    sys.stderr.write(
        f"Warning: Input truncated to {max_chars:,} characters "
        f"(original: {len(content):,} characters)\n"
    )
    content = content[:max_chars]
```

### Behavior

| Input Size | Result |
|------------|--------|
| ≤ 100,000 chars | No truncation |
| > 100,000 chars | Truncated to 100,000 chars, warning written to stderr |

**Example Warning:**
```
Warning: Input truncated to 100,000 characters (original: 150,234 characters)
```

**Key Design:**
- **Non-fatal:** Warns but proceeds (graceful degradation)
- **Formatted numbers:** Uses commas for readability (`100,000` vs `100000`)
- **Stderr output:** Doesn't pollute stdout (which may contain JSON output)

**Truncation Strategy:** Simple prefix truncation (first 100,000 characters). This ensures the header and early resources are preserved, which typically contain the most important context.

## 4. What-If Marker Validation (lines 45-63)

### Purpose

Provide early warning if input doesn't look like Azure What-If output.

### Implementation

```python
# Basic validation: check for What-If markers
# This is a soft check - we warn but don't fail
whatif_markers = [
    "Resource changes:",
    "+ Create",
    "~ Modify",
    "- Delete",
    "Resource and property changes",
    "Scope:",
]

has_marker = any(marker in content for marker in whatif_markers)

if not has_marker:
    sys.stderr.write(
        "Warning: Input may not be Azure What-If output. "
        "Expected to find markers like 'Resource changes:' or '+ Create'. "
        "Attempting to proceed anyway.\n"
    )

return content
```

### Marker List

| Marker | Indicates |
|--------|-----------|
| `"Resource changes:"` | Standard What-If header |
| `"+ Create"` | Resource creation operations |
| `"~ Modify"` | Resource modification operations |
| `"- Delete"` | Resource deletion operations |
| `"Resource and property changes"` | Alternative header format |
| `"Scope:"` | Deployment scope information |

**Validation Logic:**
- **Any match:** If any marker is found, validation passes silently
- **No match:** Warning written to stderr, but processing continues

**Example Warning:**
```
Warning: Input may not be Azure What-If output. Expected to find markers like 'Resource changes:' or '+ Create'. Attempting to proceed anyway.
```

### Soft vs. Hard Validation

**Why Soft?**
- Azure What-If output format may change across CLI versions
- Users might provide legitimate non-standard input
- LLM can handle varied formats better than strict regex
- False positives are less harmful than false negatives

**Trade-off:** Risk of processing invalid input vs. risk of rejecting valid edge cases. The tool prioritizes usability.

## Error Handling

### Exception Hierarchy

```
Exception
└── InputError (custom)
    ├── TTY detected
    ├── Empty input
    └── (Marker validation is soft - no exception)
```

### CLI Integration

```python
# In cli.py
try:
    whatif_content = read_stdin()
except InputError as e:
    sys.stderr.write(f"Error: {e}\n")
    sys.exit(2)  # Exit code 2 for invalid input
```

**Exit Code:** `2` specifically for input validation errors (distinct from general errors which use exit code `1`).

## Data Flow

```
User Command
     │
     │ stdin pipe
     ▼
┌─────────────────────┐
│ sys.stdin.isatty()  │──── Yes ──→ InputError: "No input detected"
└─────────┬───────────┘
          │ No
          ▼
┌─────────────────────┐
│ sys.stdin.read()    │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Empty check         │──── Yes ──→ InputError: "Input is empty"
└─────────┬───────────┘
          │ No
          ▼
┌─────────────────────┐
│ Size check          │──── > 100K ──→ Truncate + warn
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ Marker validation   │──── No markers ──→ Warn to stderr
└─────────┬───────────┘
          │
          ▼
  Return validated content
```

## Integration Points

### Imports

```python
import sys  # For stdin, stderr, and isatty()
```

**No external dependencies:** Pure Python stdlib implementation.

### Called By

- `cli.py:main()` (line 284): `whatif_content = read_stdin()`

### Calls

- `sys.stdin.isatty()` - TTY detection
- `sys.stdin.read()` - Read all stdin
- `sys.stderr.write()` - Warning output

## Configuration

### Environment Variables

None. The function operates independently of environment state.

### Default Values

| Parameter | Default | Configurable? |
|-----------|---------|---------------|
| `max_chars` | `100000` | Yes (via function parameter) |
| `whatif_markers` | Hardcoded list | No (internal implementation detail) |

**Note:** The CLI doesn't expose `max_chars` as a command-line flag. The default is considered sufficient for all practical deployments.

## Testing Strategy

### Test Cases

#### TTY Detection
```python
# Simulate TTY
sys.stdin.isatty() = True
→ Expect InputError with usage hint
```

#### Empty Input
```python
# Empty string
content = ""
→ Expect InputError

# Whitespace only
content = "   \n\t  "
→ Expect InputError
```

#### Size Truncation
```python
# Large input
content = "x" * 150000
→ Expect truncation warning
→ Expect return value length == 100000
```

#### Marker Validation
```python
# Valid What-If output
content = "Resource changes:\n+ Create\n  resourceGroup/myResource"
→ No warning, return content

# Invalid input
content = "This is not What-If output"
→ Warning to stderr, return content anyway
```

### Fixture Examples

**File:** `tests/fixtures/create_only.txt`
```
Resource changes: 2 to create.

+ Microsoft.Storage/storageAccounts/myaccount
  Location: eastus
  SKU: Standard_LRS
```

**File:** `tests/fixtures/mixed_changes.txt`
```
Resource changes: 5 to modify, 2 to create, 1 to delete.

~ Microsoft.Web/sites/myapp
  - properties.httpsOnly: false
  + properties.httpsOnly: true
```

## Performance Characteristics

- **Memory:** Reads entire stdin into memory (up to 100KB)
- **Time complexity:** O(n) where n is input length
- **I/O operations:** 1 read from stdin, 0-2 writes to stderr

**Optimization Note:** For extremely large inputs (> 100KB), only the first 100KB is processed, preventing memory bloat.

## Design Principles

### 1. Fail Fast

TTY and empty input checks happen immediately, before reading stdin or doing expensive validation.

### 2. Clear Error Messages

Error messages include:
- What went wrong
- How to fix it (usage examples)

### 3. Graceful Degradation

Soft marker validation allows processing of edge cases while still warning users.

### 4. Stderr for Warnings

Warnings go to stderr to avoid polluting stdout (which may be piped to `jq` or other tools).

### 5. No Silent Failures

Every validation issue either raises an exception or writes a warning. No silent data loss.

## Known Limitations

### 1. Truncation Loses Context

Truncating at 100KB may cut off important resources in very large deployments.

**Mitigation:** 100KB is sufficient for 50+ resources. Most deployments are smaller.

### 2. Marker List May Be Incomplete

Azure CLI may introduce new What-If output formats that don't include the known markers.

**Mitigation:** Soft validation warns but proceeds, allowing LLM to attempt analysis.

### 3. No Encoding Detection

Assumes UTF-8 encoding. May fail on non-UTF-8 input.

**Mitigation:** Azure CLI outputs UTF-8 by default. Edge case unlikely in practice.

## Future Improvements

Potential enhancements (not currently implemented):

1. **Configurable max_chars:** Expose as CLI flag for power users
2. **Streaming validation:** Process stdin in chunks to reduce memory usage
3. **Format detection:** Auto-detect ARM JSON vs. What-If text
4. **Encoding handling:** Explicitly handle different encodings

## Next Steps

For details on what happens after validation:
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - How validated content is included in LLM prompts
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - How `InputError` is handled in the main CLI
