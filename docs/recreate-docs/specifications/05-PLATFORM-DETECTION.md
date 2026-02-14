# Feature Specification: Platform Detection

## Overview

Unified CI/CD platform detection system that auto-detects GitHub Actions or Azure DevOps environments and extracts PR metadata, branch information, and repository details from environment variables and event files.

This enables zero-configuration CI mode where the tool automatically collects all necessary context without requiring manual CLI flags.

## Module Location

**File:** `bicep_whatif_advisor/ci/platform.py`

**Dependencies:**
- `os`: Environment variable access
- `json`: GitHub event file parsing
- `sys`: Error output
- `dataclasses`: PlatformContext structure
- `typing`: Type hints

**Exports:**
- `PlatformType`: Type alias for "github" | "azuredevops" | "local"
- `PlatformContext`: Dataclass with platform metadata
- `detect_platform() -> PlatformContext`

## Type Definitions

### PlatformType

**Type Alias:**
```python
PlatformType = Literal["github", "azuredevops", "local"]
```

**Valid Values:**
- `"github"`: GitHub Actions environment
- `"azuredevops"`: Azure DevOps Pipelines environment
- `"local"`: Local development (no CI/CD detected)

## Data Structures

### PlatformContext Dataclass

**Definition:**
```python
@dataclass
class PlatformContext:
    """Unified context for CI/CD platforms.

    Attributes:
        platform: Detected platform type
        pr_number: Pull request number/ID
        pr_title: Pull request title
        pr_description: Pull request description/body
        base_branch: Target/base branch for the PR
        source_branch: Source/head branch for the PR
        repository: Repository name
    """
    platform: PlatformType
    pr_number: Optional[str] = None
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    base_branch: Optional[str] = None
    source_branch: Optional[str] = None
    repository: Optional[str] = None
```

**Field Details:**

- **platform**: Detected environment (required)
- **pr_number**: PR number (GitHub) or PR ID (Azure DevOps)
- **pr_title**: PR title from metadata (GitHub only, ADO requires API call)
- **pr_description**: PR body/description (GitHub only, ADO requires API call)
- **base_branch**: Target branch (e.g., "main", "refs/heads/main")
- **source_branch**: Source/head branch (e.g., "feature/my-feature")
- **repository**: Repository identifier (GitHub: "owner/repo", ADO: repo name)

### Method: `has_pr_metadata()`

**Signature:**
```python
def has_pr_metadata(self) -> bool
```

**Returns:** True if PR number and at least one of title/description is available

**Logic:**
```python
return bool(self.pr_number and (self.pr_title or self.pr_description))
```

**Usage:** Determines whether intent bucket should be included in CI mode risk assessment

### Method: `get_diff_ref()`

**Signature:**
```python
def get_diff_ref(self) -> str
```

**Returns:** Git reference suitable for `git diff` command

**Logic:**
```python
if self.base_branch:
    # Remove refs/heads/ prefix if present (common in ADO)
    branch = self.base_branch.replace("refs/heads/", "")
    return f"origin/{branch}"
return "HEAD~1"  # fallback to previous commit
```

**Examples:**
- If `base_branch="main"`: Returns `"origin/main"`
- If `base_branch="refs/heads/develop"`: Returns `"origin/develop"`
- If `base_branch=None`: Returns `"HEAD~1"`

## Platform Detection

### Function: `detect_platform()`

**Signature:**
```python
def detect_platform() -> PlatformContext
```

**Behavior:**

1. **Check for GitHub Actions:**
   ```python
   if os.environ.get("GITHUB_ACTIONS") == "true":
       return _detect_github()
   ```

2. **Check for Azure DevOps:**
   ```python
   if os.environ.get("TF_BUILD") == "True" or os.environ.get("AGENT_ID"):
       return _detect_azuredevops()
   ```
   - `TF_BUILD`: Set by Azure Pipelines (stands for "Team Foundation Build")
   - `AGENT_ID`: Alternative ADO indicator

3. **Default to local:**
   ```python
   return PlatformContext(platform="local")
   ```

**Returns:** Fully populated PlatformContext with platform-specific metadata

## GitHub Actions Detection

### Function: `_detect_github()`

**Signature:**
```python
def _detect_github() -> PlatformContext
```

**Environment Variables Used:**

| Variable | Description | Example |
|----------|-------------|---------|
| `GITHUB_REPOSITORY` | Repository in "owner/repo" format | `microsoft/bicep` |
| `GITHUB_BASE_REF` | PR target branch | `main` |
| `GITHUB_HEAD_REF` | PR source branch | `feature/my-feature` |
| `GITHUB_EVENT_NAME` | Event type | `pull_request` |
| `GITHUB_EVENT_PATH` | Path to event JSON file | `/tmp/github_event.json` |

**Behavior:**

1. **Initialize context:**
   ```python
   ctx = PlatformContext(platform="github")
   ```

2. **Extract repository:**
   ```python
   ctx.repository = os.environ.get("GITHUB_REPOSITORY")
   ```

3. **Extract branches:**
   ```python
   ctx.base_branch = os.environ.get("GITHUB_BASE_REF")
   ctx.source_branch = os.environ.get("GITHUB_HEAD_REF")
   ```

4. **Extract PR metadata from event file:**
   ```python
   event_name = os.environ.get("GITHUB_EVENT_NAME")
   if event_name in ["pull_request", "pull_request_target"]:
       event_path = os.environ.get("GITHUB_EVENT_PATH")
       if event_path and os.path.exists(event_path):
           try:
               with open(event_path, 'r', encoding='utf-8') as f:
                   event_data = json.load(f)
                   pr_data = event_data.get("pull_request", {})

                   pr_number = pr_data.get("number")
                   if pr_number:
                       ctx.pr_number = str(pr_number)

                   ctx.pr_title = pr_data.get("title")
                   ctx.pr_description = pr_data.get("body")

           except (OSError, json.JSONDecodeError) as e:
               sys.stderr.write(f"Warning: Could not read GitHub event file: {e}\n")
   ```

5. **Return populated context**

**GitHub Event File Structure:**

The `GITHUB_EVENT_PATH` file contains JSON like:
```json
{
  "action": "opened",
  "number": 123,
  "pull_request": {
    "number": 123,
    "title": "Add JWT authentication policy",
    "body": "This PR adds a new policy fragment for parsing JWT tokens",
    "base": {
      "ref": "main"
    },
    "head": {
      "ref": "feature/jwt-auth"
    }
  },
  "repository": {
    "full_name": "myorg/myrepo"
  }
}
```

**Notes:**
- Event file only available for `pull_request` and `pull_request_target` events
- File read errors are non-fatal (warning printed to stderr)
- PR metadata will be None if event file unavailable or malformed

## Azure DevOps Detection

### Function: `_detect_azuredevops()`

**Signature:**
```python
def _detect_azuredevops() -> PlatformContext
```

**Environment Variables Used:**

| Variable | Description | Example |
|----------|-------------|---------|
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | PR ID | `12345` |
| `SYSTEM_PULLREQUEST_TARGETBRANCH` | PR target branch | `refs/heads/main` |
| `SYSTEM_PULLREQUEST_SOURCEBRANCH` | PR source branch | `refs/heads/feature/my-feature` |
| `BUILD_REPOSITORY_NAME` | Repository name | `myrepo` |

**Behavior:**

1. **Initialize context:**
   ```python
   ctx = PlatformContext(platform="azuredevops")
   ```

2. **Extract PR number:**
   ```python
   ctx.pr_number = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")
   ```

3. **Extract branches:**
   ```python
   ctx.base_branch = os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH")
   ctx.source_branch = os.environ.get("SYSTEM_PULLREQUEST_SOURCEBRANCH")
   ```
   - Format: `refs/heads/branch-name` (will be stripped by `get_diff_ref()`)

4. **Extract repository:**
   ```python
   ctx.repository = os.environ.get("BUILD_REPOSITORY_NAME")
   ```

5. **Return context (PR title/description not available)**

**Important Limitation:**

Azure DevOps does NOT expose PR title/description in environment variables. To obtain this metadata, would need to call Azure DevOps REST API:

```
GET {SYSTEM_COLLECTIONURI}/{SYSTEM_TEAMPROJECT}/_apis/git/repositories/{BUILD_REPOSITORY_ID}/pullRequests/{SYSTEM_PULLREQUEST_PULLREQUESTID}?api-version=7.0
Authorization: Bearer {SYSTEM_ACCESSTOKEN}
```

**Future Enhancement:**

The module includes commented-out placeholder for API fetching:
```python
# TODO: Optionally fetch PR metadata via Azure DevOps REST API
# if os.environ.get("SYSTEM_ACCESSTOKEN"):
#     ctx.pr_title, ctx.pr_description = _fetch_ado_pr_metadata(ctx)
```

This is NOT currently implemented. Users must provide `--pr-title` and `--pr-description` via CLI flags for Azure DevOps if intent analysis is desired.

## Usage Examples

### GitHub Actions Example

**Environment:**
```bash
GITHUB_ACTIONS=true
GITHUB_REPOSITORY=myorg/myrepo
GITHUB_BASE_REF=main
GITHUB_HEAD_REF=feature/jwt-auth
GITHUB_EVENT_NAME=pull_request
GITHUB_EVENT_PATH=/tmp/github_event.json
```

**Detection:**
```python
ctx = detect_platform()
print(ctx.platform)         # "github"
print(ctx.repository)       # "myorg/myrepo"
print(ctx.pr_number)        # "123" (from event file)
print(ctx.pr_title)         # "Add JWT authentication policy" (from event file)
print(ctx.base_branch)      # "main"
print(ctx.get_diff_ref())   # "origin/main"
print(ctx.has_pr_metadata()) # True
```

### Azure DevOps Example

**Environment:**
```bash
TF_BUILD=True
SYSTEM_PULLREQUEST_PULLREQUESTID=12345
SYSTEM_PULLREQUEST_TARGETBRANCH=refs/heads/main
SYSTEM_PULLREQUEST_SOURCEBRANCH=refs/heads/feature/jwt-auth
BUILD_REPOSITORY_NAME=myrepo
```

**Detection:**
```python
ctx = detect_platform()
print(ctx.platform)         # "azuredevops"
print(ctx.repository)       # "myrepo"
print(ctx.pr_number)        # "12345"
print(ctx.pr_title)         # None (not available from env vars)
print(ctx.base_branch)      # "refs/heads/main"
print(ctx.get_diff_ref())   # "origin/main" (refs/heads/ stripped)
print(ctx.has_pr_metadata()) # False (no title/description)
```

### Local Development Example

**Environment:** (no CI variables)

**Detection:**
```python
ctx = detect_platform()
print(ctx.platform)         # "local"
print(ctx.repository)       # None
print(ctx.pr_number)        # None
print(ctx.has_pr_metadata()) # False
print(ctx.get_diff_ref())   # "HEAD~1"
```

## Integration with CLI

The CLI uses platform detection in CI mode:

```python
from .ci.platform import detect_platform

def main():
    # Auto-detect platform
    platform_ctx = detect_platform()

    # Use auto-detected values as defaults, allow CLI overrides
    if ci_mode:
        diff_ref = cli_diff_ref or platform_ctx.get_diff_ref()
        pr_title = cli_pr_title or platform_ctx.pr_title
        pr_description = cli_pr_description or platform_ctx.pr_description

        # Determine if intent bucket should be included
        include_intent = bool(pr_title or pr_description)

        # Build prompts with auto-detected metadata
        system_prompt = build_system_prompt(
            ci_mode=True,
            pr_title=pr_title,
            pr_description=pr_description
        )
```

## Implementation Requirements

1. **Environment variable checks must be exact:** `GITHUB_ACTIONS == "true"` (string comparison)
2. **Event file read must be non-fatal:** Print warning on error, continue with None values
3. **JSON parsing must handle malformed data:** Use try/except with JSONDecodeError
4. **Branch name normalization:** Strip `refs/heads/` prefix in `get_diff_ref()`
5. **Optional metadata handling:** All fields except platform should be Optional[str]
6. **UTF-8 encoding:** Use `encoding='utf-8'` when reading event file
7. **Type safety:** Use Literal type for platform enum
8. **Future-proof API calls:** Include TODO comments for Azure DevOps API integration

## Edge Cases

1. **Missing environment variables:** Fields default to None (graceful degradation)
2. **Event file doesn't exist:** Print warning, continue with None values
3. **Malformed event JSON:** Catch JSONDecodeError, print warning
4. **Both GitHub and ADO variables present:** GitHub takes precedence (checked first)
5. **Wrong event type:** PR metadata only extracted for pull_request events
6. **Empty PR title/description:** Stored as empty string, not None (if present in JSON)
7. **Branch format variations:** Handle both "main" and "refs/heads/main" formats
