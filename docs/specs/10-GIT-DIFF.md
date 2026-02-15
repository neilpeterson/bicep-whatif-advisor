# 10 - Git Diff Collection

## Purpose

The git diff module collects code changes for CI mode drift detection. It supports both file-based input and direct git command execution, enabling comparison between What-If output and actual code modifications.

**File:** `bicep_whatif_advisor/ci/diff.py` (69 lines)

## Implementation

### get_diff() Function (lines 8-68)

```python
def get_diff(diff_path: str = None, diff_ref: str = "HEAD~1") -> str:
    """Get git diff content for CI mode analysis.

    Args:
        diff_path: Path to diff file, or None to run git diff
        diff_ref: Git reference to diff against (default: HEAD~1)

    Returns:
        Diff content as string (may be empty if no changes)

    Raises:
        SystemExit: If git is not available or diff file not found
    """
```

**Parameters:**
- `diff_path`: Optional path to pre-generated diff file
- `diff_ref`: Git reference for diff comparison (default: `HEAD~1`)

**Returns:** Diff content as string (unified diff format).

**Design:** Two modes - file-based or git command-based.

## Mode 1: File-Based Diff

### Usage

```bash
git diff origin/main > changes.diff
az deployment group what-if ... | bicep-whatif-advisor --ci --diff changes.diff
```

### Implementation (lines 21-32)

```python
if diff_path:
    # Read from file
    if not os.path.exists(diff_path):
        sys.stderr.write(f"Error: Diff file not found: {diff_path}\n")
        sys.exit(1)

    try:
        with open(diff_path, 'r') as f:
            return f.read()
    except Exception as e:
        sys.stderr.write(f"Error reading diff file: {e}\n")
        sys.exit(1)
```

**Error Handling:**
- File not found → Exit code 1
- Read error (permissions, encoding) → Exit code 1

**Use Cases:**
- Pre-generated diffs in CI pipelines
- Custom diff generation (filtered files, specific commits)
- Testing with known diff content

## Mode 2: Git Command Execution

### Usage

```bash
az deployment group what-if ... | bicep-whatif-advisor --ci --diff-ref origin/main
```

### Implementation (lines 34-68)

```python
else:
    # Run git diff
    try:
        result = subprocess.run(
            ["git", "diff", diff_ref],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            # Git failed - could be not a repo, or ref doesn't exist
            sys.stderr.write(
                f"Warning: git diff failed (exit code {result.returncode}).\n"
                f"Error: {result.stderr}\n"
                f"Proceeding without diff context.\n"
            )
            return ""

        return result.stdout

    except FileNotFoundError:
        sys.stderr.write(
            "Error: git command not found.\n"
            "Install git or provide diff via --diff flag.\n"
        )
        sys.exit(1)

    except subprocess.TimeoutExpired:
        sys.stderr.write("Error: git diff command timed out.\n")
        sys.exit(1)

    except Exception as e:
        sys.stderr.write(f"Error running git diff: {e}\n")
        sys.exit(1)
```

**Command:** `git diff {diff_ref}`

**Configuration:**
- `capture_output=True` - Capture stdout/stderr
- `text=True` - Return strings (not bytes)
- `timeout=30` - 30-second timeout

### Error Handling

| Error | Behavior |
|-------|----------|
| Git not installed | Exit code 1, suggest installing git or using `--diff` |
| Invalid git ref | Warning, proceed with empty diff |
| Not a git repository | Warning, proceed with empty diff |
| Timeout (30s) | Exit code 1 |
| Other exceptions | Exit code 1 |

**Graceful Degradation:** Invalid refs return empty diff (not fatal).

**Rationale:** Better to analyze without drift detection than fail entirely.

## Diff Reference Examples

| Ref | Compares Against |
|-----|------------------|
| `HEAD~1` | Previous commit (default) |
| `origin/main` | Main branch on remote |
| `origin/develop` | Develop branch on remote |
| `abc123` | Specific commit hash |
| `v1.0.0` | Tag |

**Platform Auto-Detection:**
- GitHub Actions: `origin/{GITHUB_BASE_REF}` (e.g., `origin/main`)
- Azure DevOps: `origin/{stripped base branch}` (e.g., `origin/main`)
- Local: `HEAD~1` (default)

**See:** [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) for `PlatformContext.get_diff_ref()`.

## Integration with CLI

### Usage in cli.py (lines 328-334)

```python
# Get diff content if CI mode
diff_content = None
bicep_content = None

if ci:
    from .ci.diff import get_diff
    diff_content = get_diff(diff, diff_ref)

    # Optionally load Bicep source files
    if bicep_dir:
        bicep_content = _load_bicep_files(bicep_dir)
```

**Flow:**
1. Check if CI mode enabled
2. Call `get_diff()` with user-provided flags
3. Pass diff content to `build_user_prompt()`

### CLI Flags

| Flag | Type | Default | Purpose |
|------|------|---------|---------|
| `--diff` `-d` | String | `None` | Path to diff file |
| `--diff-ref` | String | `HEAD~1` | Git reference for diff |

**Examples:**
```bash
# Use git command (default ref)
bicep-whatif-advisor --ci

# Use git command (custom ref)
bicep-whatif-advisor --ci --diff-ref origin/main

# Use diff file
bicep-whatif-advisor --ci --diff changes.diff
```

## Unified Diff Format

**Example Output:**
```diff
diff --git a/main.bicep b/main.bicep
index abc123..def456 100644
--- a/main.bicep
+++ b/main.bicep
@@ -10,6 +10,10 @@
   location: location
 }

+resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
+  name: 'myapp-insights'
+  location: location
+}
```

**Components:**
- `diff --git` - File header
- `index` - Git blob hashes
- `---`/`+++` - Old/new file paths
- `@@` - Hunk header (line numbers)
- Lines without prefix - Context
- `+` prefix - Added lines
- `-` prefix - Removed lines

**LLM Usage:** Diff passed to LLM in `<code_diff>` tags for drift analysis.

## Drift Detection Workflow

```
Code Changes (Git Diff)
    ↓
What-If Output
    ↓
LLM Analysis
    ├── Resources changed in diff? → Low drift risk
    └── Resources NOT in diff? → High drift risk
    ↓
Drift Bucket Risk Assessment
```

**Example:**

**Git Diff:**
```diff
+ resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
```

**What-If Output:**
```
+ Create Microsoft.Insights/components/myapp-insights
~ Modify Microsoft.Storage/storageAccounts/myaccount
```

**LLM Analysis:**
- AppInsights creation → In diff → Low drift risk
- Storage account modification → NOT in diff → **High drift risk**

**Verdict:** Deployment blocked due to high drift risk.

## Performance Characteristics

- **Git command:** ~50-200ms (depends on repository size)
- **File read:** ~1-10ms
- **Timeout:** 30 seconds max
- **Memory:** Holds full diff in memory

**Bottleneck:** Large diffs (100MB+) could exceed memory limits.

**Mitigation:** 30s timeout prevents hanging on huge repos.

## Design Principles

### 1. Two Input Methods

File-based and git-based modes:
- **File:** Explicit, reproducible, testable
- **Git:** Automatic, integrated, no extra steps

**Benefit:** Flexibility for different CI setups.

### 2. Graceful Degradation

Git failures don't block pipeline:
```python
if result.returncode != 0:
    sys.stderr.write("Warning: git diff failed...\n")
    return ""  # Empty diff
```

**Rationale:** Drift detection is valuable but not essential.

### 3. Clear Error Messages

```
Error: git command not found.
Install git or provide diff via --diff flag.
```

Not:
```
Error: Command failed
```

**Benefit:** Users know exactly how to fix the problem.

### 4. Sensible Defaults

- Default ref: `HEAD~1` (previous commit)
- Platform detection overrides default
- No diff → Empty string (not error)

## Testing Strategy

### Unit Tests

```python
# Test file-based diff
with open('test.diff', 'w') as f:
    f.write('diff --git a/main.bicep...')
diff = get_diff(diff_path='test.diff')
assert 'main.bicep' in diff

# Test git command (mock subprocess)
import unittest.mock as mock
with mock.patch('subprocess.run') as mock_run:
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = 'diff content'
    diff = get_diff(diff_ref='origin/main')
    assert diff == 'diff content'
```

### Integration Tests

- Real git repositories
- Various diff refs (branches, tags, commits)
- Error scenarios (missing git, invalid refs)
- Large diffs (performance testing)

## Future Improvements

1. **Diff filtering:** Exclude certain files (e.g., `*.md`)
2. **Binary diff handling:** Skip or summarize binary file changes
3. **Streaming:** Process large diffs in chunks
4. **Diff stats:** Include file count, line count in output

## Next Steps

For details on how diffs are used:
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - How diff is included in LLM prompts
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) - How drift bucket uses diff for analysis
- [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) - How `get_diff_ref()` provides smart defaults
