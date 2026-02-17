# 07 - Platform Detection (CI/CD Auto-Detection)

## Purpose

The platform detection module automatically identifies the CI/CD environment (GitHub Actions, Azure DevOps, or local) and extracts pull request metadata, branch information, and repository details without requiring manual CLI flags.

**File:** `bicep_whatif_advisor/ci/platform.py` (172 lines)

**Goal:** Enable zero-configuration CI mode - users run `bicep-whatif-advisor` with no flags and get full functionality.

## Implementation Overview

```python
"""Unified CI/CD platform detection for GitHub Actions and Azure DevOps."""

from dataclasses import dataclass
from typing import Optional, Literal

PlatformType = Literal["github", "azuredevops", "local"]

@dataclass
class PlatformContext:
    """Unified context for CI/CD platforms."""
    platform: PlatformType
    pr_number: Optional[str] = None
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    base_branch: Optional[str] = None
    source_branch: Optional[str] = None
    repository: Optional[str] = None

    def has_pr_metadata(self) -> bool:
        """Check if PR metadata is available."""
        return bool(self.pr_number and (self.pr_title or self.pr_description))

    def get_diff_ref(self) -> str:
        """Get the appropriate git reference for diff."""
        if self.base_branch:
            branch = self.base_branch.replace("refs/heads/", "")
            return f"origin/{branch}"
        return "HEAD~1"

def detect_platform() -> PlatformContext:
    """Auto-detect CI/CD platform and extract metadata."""
```

## Data Structures

### PlatformContext Dataclass (lines 12-52)

Unified interface for platform-specific metadata:

```python
@dataclass
class PlatformContext:
    platform: PlatformType  # "github" | "azuredevops" | "local"
    pr_number: Optional[str] = None
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None
    base_branch: Optional[str] = None
    source_branch: Optional[str] = None
    repository: Optional[str] = None
```

**Fields:**

| Field | Type | Purpose | Example |
|-------|------|---------|---------|
| `platform` | `PlatformType` | Platform identifier | `"github"` |
| `pr_number` | `Optional[str]` | Pull request number/ID | `"123"` |
| `pr_title` | `Optional[str]` | Pull request title | `"Add monitoring resources"` |
| `pr_description` | `Optional[str]` | Pull request body/description | `"This PR adds Application Insights..."` |
| `base_branch` | `Optional[str]` | Target branch for PR | `"main"` |
| `source_branch` | `Optional[str]` | Source/head branch for PR | `"feature/monitoring"` |
| `repository` | `Optional[str]` | Repository name | `"owner/repo"` (GitHub), `"MyRepo"` (Azure DevOps) |

**Why Optional?**
- Not all fields available in all platforms
- Graceful degradation when metadata missing

### has_pr_metadata() Method (lines 34-40)

```python
def has_pr_metadata(self) -> bool:
    """Check if PR metadata is available.

    Returns:
        True if PR number and at least one of title/description is available
    """
    return bool(self.pr_number and (self.pr_title or self.pr_description))
```

**Logic:** PR metadata available if:
- PR number exists
- AND (title OR description exists)

**Usage:** Determines whether to include `intent` bucket in risk assessment.

### get_diff_ref() Method (lines 42-52)

```python
def get_diff_ref(self) -> str:
    """Get the appropriate git reference for diff.

    Returns:
        Git reference suitable for git diff (e.g., 'origin/main')
    """
    if self.base_branch:
        # Remove refs/heads/ prefix if present (common in ADO)
        branch = self.base_branch.replace("refs/heads/", "")
        return f"origin/{branch}"
    return "HEAD~1"  # fallback to previous commit
```

**Branching Logic:**

| Scenario | Returns |
|----------|---------|
| `base_branch = "main"` | `"origin/main"` |
| `base_branch = "refs/heads/main"` | `"origin/main"` (Azure DevOps format) |
| `base_branch = None` | `"HEAD~1"` (local fallback) |

**Why `origin/` prefix?** Git diff needs remote ref to compare against PR base.

**Azure DevOps Note:** Branch refs in Azure DevOps use `refs/heads/` prefix, which must be stripped.

## Platform Detection

### detect_platform() Function (lines 55-73)

Entry point for platform auto-detection:

```python
def detect_platform() -> PlatformContext:
    """Auto-detect CI/CD platform and extract metadata.

    Detects GitHub Actions or Azure DevOps environment and extracts
    PR metadata, branch information, and repository details.

    Returns:
        PlatformContext with platform-specific metadata
    """
    # Check GitHub Actions
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return _detect_github()

    # Check Azure DevOps
    if os.environ.get("TF_BUILD") == "True" or os.environ.get("AGENT_ID"):
        return _detect_azuredevops()

    # Running locally
    return PlatformContext(platform="local")
```

**Detection Order:**
1. GitHub Actions (check `GITHUB_ACTIONS=true`)
2. Azure DevOps (check `TF_BUILD=True` or `AGENT_ID`)
3. Local (default)

**Environment Variables Used:**

| Variable | Platform | Purpose |
|----------|----------|---------|
| `GITHUB_ACTIONS` | GitHub | Set to `"true"` in GitHub Actions |
| `TF_BUILD` | Azure DevOps | Set to `"True"` in Azure DevOps pipelines |
| `AGENT_ID` | Azure DevOps | Agent identifier (fallback detection) |

**Design:** Explicit checks in order, no ambiguity.

## GitHub Actions Detection

### _detect_github() Function (lines 76-120)

Extracts metadata from GitHub Actions environment:

```python
def _detect_github() -> PlatformContext:
    """Extract metadata from GitHub Actions environment.

    Reads PR metadata from the GitHub event file and extracts
    branch information from environment variables.

    Returns:
        PlatformContext with GitHub-specific metadata
    """
    ctx = PlatformContext(platform="github")

    # Get repository (format: owner/repo)
    ctx.repository = os.environ.get("GITHUB_REPOSITORY")

    # Get base branch for PR (e.g., 'main')
    ctx.base_branch = os.environ.get("GITHUB_BASE_REF")

    # Get source/head branch (e.g., 'feature/my-feature')
    ctx.source_branch = os.environ.get("GITHUB_HEAD_REF")

    # Extract PR metadata from event file
    event_name = os.environ.get("GITHUB_EVENT_NAME")
    if event_name in ["pull_request", "pull_request_target"]:
        event_path = os.environ.get("GITHUB_EVENT_PATH")
        if event_path and os.path.exists(event_path):
            try:
                with open(event_path, 'r', encoding='utf-8') as f:
                    event_data = json.load(f)
                    pr_data = event_data.get("pull_request", {})

                    # Extract PR number, title, and description
                    pr_number = pr_data.get("number")
                    if pr_number:
                        ctx.pr_number = str(pr_number)

                    ctx.pr_title = pr_data.get("title")
                    ctx.pr_description = pr_data.get("body")

            except (OSError, json.JSONDecodeError) as e:
                # Failed to read event file - metadata unavailable
                sys.stderr.write(
                    f"Warning: Could not read GitHub event file: {e}\n"
                )

    return ctx
```

### GitHub Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `GITHUB_REPOSITORY` | Repository name | `"anthropics/bicep-whatif-advisor"` |
| `GITHUB_BASE_REF` | PR target branch | `"main"` |
| `GITHUB_HEAD_REF` | PR source branch | `"feature/monitoring"` |
| `GITHUB_EVENT_NAME` | Event type | `"pull_request"` |
| `GITHUB_EVENT_PATH` | Path to event JSON file | `"/home/runner/work/_temp/_github_workflow/event.json"` |

**Branch Variables Only Set in PR Context:**
- `GITHUB_BASE_REF` and `GITHUB_HEAD_REF` only available for PR events
- Empty/missing for push events, workflow_dispatch, etc.

### GitHub Event File Parsing

**Event File Structure:**
```json
{
  "action": "opened",
  "number": 123,
  "pull_request": {
    "number": 123,
    "title": "Add monitoring resources",
    "body": "This PR adds Application Insights for observability...",
    "base": {
      "ref": "main"
    },
    "head": {
      "ref": "feature/monitoring"
    }
  }
}
```

**Extraction Logic:**
```python
pr_data = event_data.get("pull_request", {})
ctx.pr_number = str(pr_data.get("number"))
ctx.pr_title = pr_data.get("title")
ctx.pr_description = pr_data.get("body")
```

**Supported Events:**
- `pull_request` - Standard PR events
- `pull_request_target` - PR events with write permissions

**Error Handling:**
- File not found → Warning, continue with partial metadata
- JSON decode error → Warning, continue with partial metadata
- Missing PR fields → Fields remain `None`

## Azure DevOps Detection

### _detect_azuredevops() Function (lines 123-153)

Extracts metadata from Azure DevOps environment and optionally fetches PR title/description via REST API:

```python
def _detect_azuredevops() -> PlatformContext:
    """Extract metadata from Azure DevOps environment.

    Reads PR and branch information from Azure DevOps pipeline
    environment variables. Optionally fetches PR title and description
    from Azure DevOps REST API if SYSTEM_ACCESSTOKEN is available.

    Returns:
        PlatformContext with Azure DevOps-specific metadata
    """
    ctx = PlatformContext(platform="azuredevops")

    # Get PR number
    ctx.pr_number = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")

    # Get branches (format: refs/heads/main or refs/heads/feature/branch)
    ctx.base_branch = os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH")
    ctx.source_branch = os.environ.get("SYSTEM_PULLREQUEST_SOURCEBRANCH")

    # Get repository name
    ctx.repository = os.environ.get("BUILD_REPOSITORY_NAME")

    # Fetch PR title/description from Azure DevOps REST API if token available
    if ctx.pr_number and os.environ.get("SYSTEM_ACCESSTOKEN"):
        pr_title, pr_description = _fetch_ado_pr_metadata(ctx)
        if pr_title:
            ctx.pr_title = pr_title
        if pr_description:
            ctx.pr_description = pr_description

    return ctx
```

### Azure DevOps Environment Variables

| Variable | Purpose | Example |
|----------|---------|---------|
| `TF_BUILD` | Pipeline detection | `"True"` |
| `AGENT_ID` | Agent identifier (alternative detection) | `"1"` |
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | PR number | `"456"` |
| `SYSTEM_PULLREQUEST_TARGETBRANCH` | PR target branch | `"refs/heads/main"` |
| `SYSTEM_PULLREQUEST_SOURCEBRANCH` | PR source branch | `"refs/heads/feature/monitoring"` |
| `BUILD_REPOSITORY_NAME` | Repository name | `"MyProject/MyRepo"` |
| `SYSTEM_ACCESSTOKEN` | Azure DevOps auth token | Auto-provided in pipelines |
| `SYSTEM_COLLECTIONURI` | Organization URL | `"https://dev.azure.com/myorg/"` |
| `SYSTEM_TEAMPROJECT` | Project name | `"MyProject"` |
| `BUILD_REPOSITORY_ID` | Repository GUID | `"a1b2c3d4-..."` |

**Branch Format:** Azure DevOps uses `refs/heads/` prefix (git ref format).

**Handled by `get_diff_ref()`:**
```python
branch = self.base_branch.replace("refs/heads/", "")  # "main"
return f"origin/{branch}"  # "origin/main"
```

### PR Title/Description via REST API

**Implementation:** Automatically fetches PR metadata from Azure DevOps REST API.

**Function:** `_fetch_ado_pr_metadata()` (lines 156-227)

```python
def _fetch_ado_pr_metadata(ctx: PlatformContext) -> tuple[Optional[str], Optional[str]]:
    """Fetch PR title and description from Azure DevOps REST API.

    Args:
        ctx: Platform context with PR number and repository info

    Returns:
        Tuple of (pr_title, pr_description), or (None, None) if fetch fails
    """
```

**API Endpoint:**
```
GET {collection_uri}/{project}/_apis/git/repositories/{repo_id}/pullrequests/{pr_id}?api-version=7.0
```

**Required Environment Variables:**
- `SYSTEM_ACCESSTOKEN` - Auth token (auto-provided in Azure Pipelines)
- `SYSTEM_COLLECTIONURI` - Organization URL
- `SYSTEM_TEAMPROJECT` - Project name
- `BUILD_REPOSITORY_ID` or `BUILD_REPOSITORY_NAME` - Repository identifier

**Behavior:**
- If all variables available → Makes REST API call
- If any variable missing → Logs warning, returns `(None, None)`
- If API call fails → Logs warning, returns `(None, None)`
- If successful → Returns `(pr_title, pr_description)`

**Error Handling:**
```python
try:
    response = requests.get(api_url, headers=headers, timeout=10)
    response.raise_for_status()
    pr_data = response.json()
    return pr_data.get("title"), pr_data.get("description")
except requests.exceptions.RequestException as e:
    sys.stderr.write(f"Warning: Failed to fetch PR metadata: {e}\n")
    return None, None
```

**Logging:**
```
✅ Fetched PR title from Azure DevOps API: Removed mexico factory IP from NSG
✅ Fetched PR description from Azure DevOps API (1 lines)
```

**Fallback:** Users can still override via CLI flags if API fetch fails:
```bash
bicep-whatif-advisor --ci \
  --pr-title "Add monitoring" \
  --pr-description "This PR adds Application Insights"
```

## Integration with CLI

### Usage in cli.py (lines 286-326)

```python
# Auto-detect platform context (GitHub Actions, Azure DevOps, or local)
platform_ctx = detect_platform()

# Apply smart defaults based on platform detection
if platform_ctx.platform != "local":
    # Auto-enable CI mode in pipeline environments
    if not ci:
        platform_name = (
            "GitHub Actions" if platform_ctx.platform == "github"
            else "Azure DevOps"
        )
        sys.stderr.write(
            f"🤖 Auto-detected {platform_name} environment - enabling CI mode\n"
        )
        ci = True

    # Auto-set diff reference if not manually provided
    if diff_ref == "HEAD~1" and platform_ctx.base_branch:
        diff_ref = platform_ctx.get_diff_ref()
        sys.stderr.write(f"📊 Auto-detected diff reference: {diff_ref}\n")

    # Auto-populate PR metadata if not manually provided
    if not pr_title and platform_ctx.pr_title:
        pr_title = platform_ctx.pr_title
        title_preview = pr_title[:60] + "..." if len(pr_title) > 60 else pr_title
        sys.stderr.write(f"📝 Auto-detected PR title: {title_preview}\n")

    if not pr_description and platform_ctx.pr_description:
        pr_description = platform_ctx.pr_description
        desc_lines = len(pr_description.splitlines())
        sys.stderr.write(f"📄 Auto-detected PR description ({desc_lines} lines)\n")

    # Auto-enable PR comments if token available
    if not post_comment:
        has_token = (
            (platform_ctx.platform == "github" and os.environ.get("GITHUB_TOKEN")) or
            (platform_ctx.platform == "azuredevops" and os.environ.get("SYSTEM_ACCESSTOKEN"))
        )
        if has_token:
            sys.stderr.write("💬 Auto-enabling PR comments (auth token detected)\n")
            post_comment = True
```

### Auto-Configuration Logic

| Setting | Condition | Action |
|---------|-----------|--------|
| **CI Mode** | Platform != local + `--ci` not set | Enable CI mode |
| **Diff Reference** | `--diff-ref` == `HEAD~1` + `base_branch` available | Set to `platform_ctx.get_diff_ref()` |
| **PR Title** | `--pr-title` not set + `pr_title` available | Set from platform context |
| **PR Description** | `--pr-description` not set + `pr_description` available | Set from platform context |
| **PR Comments** | `--post-comment` not set + auth token available | Enable PR comments |

**Precedence:** Manual CLI flags always override auto-detected values.

### Example GitHub Actions Workflow

**Before Auto-Detection:**
```yaml
- name: Run What-If and AI Review
  run: |
    PR_TITLE=$(gh pr view ${{ github.event.pull_request.number }} --json title -q .title)
    PR_DESC=$(gh pr view ${{ github.event.pull_request.number }} --json body -q .body)

    az deployment group what-if ... | bicep-whatif-advisor \
      --ci \
      --diff-ref origin/${{ github.base_ref }} \
      --pr-title "$PR_TITLE" \
      --pr-description "$PR_DESC" \
      --post-comment
```

**After Auto-Detection:**
```yaml
- name: Run What-If and AI Review
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor
```

**Simplification:** 90% reduction in workflow code.

## Benefits

### 1. Zero-Configuration Workflows

Users run `bicep-whatif-advisor` with no flags:
- CI mode auto-enabled
- PR metadata auto-extracted
- Diff reference auto-configured
- PR comments auto-posted

### 2. Consistent Behavior

Same workflow works across:
- GitHub Actions
- Azure DevOps
- Local development (graceful degradation)

### 3. Reduced Error Surface

No manual metadata extraction:
- No `gh pr view` commands
- No JSON parsing in workflow files
- No environment variable mistakes

### 4. Future-Proof

New platforms can be added by:
1. Add detection logic to `detect_platform()`
2. Implement `_detect_<platform>()` function
3. Update `PlatformType` literal

## Design Principles

### 1. Unified Interface

`PlatformContext` provides consistent interface regardless of platform.

**Benefits:**
- CLI code doesn't need platform-specific logic
- Easy to add new platforms
- Type-safe with dataclasses

### 2. Graceful Degradation

Missing metadata doesn't cause errors:
- Fields default to `None`
- CLI checks for availability before using
- Falls back to manual flags when needed

### 3. Explicit Over Implicit

Clear environment variable checks:
```python
if os.environ.get("GITHUB_ACTIONS") == "true":
```

Not:
```python
if "GITHUB_ACTIONS" in os.environ:
```

**Why:** Explicit value checks prevent false positives.

### 4. Fail Open, Not Closed

Event file parsing errors → warnings, not failures:
```python
except (OSError, json.JSONDecodeError) as e:
    sys.stderr.write(f"Warning: Could not read GitHub event file: {e}\n")
```

**Philosophy:** Better to proceed with partial metadata than fail entirely.

## Testing Strategy

### Unit Tests

```python
# Test platform detection
os.environ["GITHUB_ACTIONS"] = "true"
ctx = detect_platform()
assert ctx.platform == "github"

# Test diff reference generation
ctx = PlatformContext(platform="github", base_branch="main")
assert ctx.get_diff_ref() == "origin/main"

ctx = PlatformContext(platform="azuredevops", base_branch="refs/heads/main")
assert ctx.get_diff_ref() == "origin/main"

# Test PR metadata availability
ctx = PlatformContext(platform="github", pr_number="123", pr_title="Test")
assert ctx.has_pr_metadata() == True

ctx = PlatformContext(platform="github", pr_number="123")
assert ctx.has_pr_metadata() == False  # No title or description
```

### Integration Tests

- Real GitHub Actions runs
- Real Azure DevOps runs
- Verify event file parsing
- Test with missing metadata

## Future Enhancements

### Additional Platforms

- **GitLab CI/CD:** Check `GITLAB_CI` environment variable
- **Bitbucket Pipelines:** Check `BITBUCKET_BUILD_NUMBER`
- **CircleCI:** Check `CIRCLECI`

## Next Steps

For details on how platform detection integrates:
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - Smart defaults logic
- [10-GIT-DIFF.md](10-GIT-DIFF.md) - How `get_diff_ref()` is used
- [09-PR-INTEGRATION.md](09-PR-INTEGRATION.md) - How PR metadata is used for comments
