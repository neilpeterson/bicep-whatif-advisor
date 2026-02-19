# 09 - PR Integration (Comment Posting)

## Purpose

The PR integration module posts What-If analysis results as Pull Request comments on GitHub and Azure DevOps. This provides code reviewers with automated deployment safety analysis directly in their review workflow.

**Files:**
- `bicep_whatif_advisor/ci/github.py` (85 lines) - GitHub REST API integration
- `bicep_whatif_advisor/ci/azdevops.py` (93 lines) - Azure DevOps REST API integration

## GitHub Integration

### post_github_comment() Function (lines 8-84)

Posts markdown comment to GitHub PR via REST API:

```python
def post_github_comment(markdown: str, pr_url: str = None) -> bool:
    """Post a comment to a GitHub PR.

    Args:
        markdown: Comment content in markdown format
        pr_url: Optional PR URL (auto-detected from env if not provided)

    Returns:
        True if successful, False otherwise
    """
```

**Parameters:**
- `markdown`: Formatted markdown content (from `render_markdown()`)
- `pr_url`: Optional PR URL override

**Returns:** `True` if comment posted successfully, `False` otherwise.

### GitHub API Details

**Endpoint:**
```
POST https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments
```

**Authentication:**
```python
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json"
}
```

**Payload:**
```python
payload = {"body": markdown}
```

**Why `/issues/` endpoint?** GitHub PRs are implemented as issues with attached patches. The issues API is used for commenting.

### PR Identification

**Two Methods:**

#### 1. Manual PR URL (`--pr-url` flag)

**Format:** `https://github.com/owner/repo/pull/123`

**Parsing:**
```python
match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
if match:
    owner, repo, pr_number = match.groups()
```

**Use Case:** Manual invocation or non-standard GitHub Actions setups.

#### 2. Auto-Detection (Environment Variables)

**Variables:**
- `GITHUB_REPOSITORY` - Format: `owner/repo`
- `GITHUB_REF` - Format: `refs/pull/123/merge`

**Extraction:**
```python
repository = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
github_ref = os.environ.get("GITHUB_REF")  # "refs/pull/123/merge"

pr_match = re.search(r'refs/pull/(\d+)/', github_ref)
if pr_match:
    pr_number = pr_match.group(1)

owner, repo = repository.split("/")
```

**Validation:**
```python
parts = repository.split("/")
if len(parts) != 2 or not parts[0] or not parts[1]:
    sys.stderr.write("Warning: Invalid GITHUB_REPOSITORY format...")
    return False
```

**Use Case:** Standard GitHub Actions PR workflows.

### Environment Variables

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `GITHUB_TOKEN` | ✅ Yes | API authentication | `ghp_...` or `${{ secrets.GITHUB_TOKEN }}` |
| `GITHUB_REPOSITORY` | Auto-detect only | Repository identifier | `anthropics/bicep-whatif-advisor` |
| `GITHUB_REF` | Auto-detect only | PR reference | `refs/pull/123/merge` |

**Token Permissions:** `issues: write` (or `pull-requests: write`).

**Setting Token in Workflow:**
```yaml
env:
  GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### Error Handling

**Missing Dependency:**
```python
try:
    import requests
except ImportError:
    sys.stderr.write("Warning: requests package not installed...")
    return False
```

**Missing Token:**
```python
token = os.environ.get("GITHUB_TOKEN")
if not token:
    sys.stderr.write("Warning: GITHUB_TOKEN not set...")
    return False
```

**Invalid PR URL:**
```python
if not match:
    sys.stderr.write(f"Warning: Invalid GitHub PR URL: {pr_url}\n")
    return False
```

**API Errors:**
```python
try:
    response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
    response.raise_for_status()
    return True
except requests.exceptions.HTTPError as e:
    sys.stderr.write(f"Warning: GitHub API error: {e}\n")
    return False
```

**Design:** Non-fatal failures (return `False`, log warning, continue execution).

### GitHub API Request

```python
url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
headers = {
    "Authorization": f"Bearer {token}",
    "Accept": "application/vnd.github.v3+json"
}
payload = {"body": markdown}

response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
response.raise_for_status()
```

**Configuration:**
- **Timeout:** 30 seconds
- **SSL Verification:** Enabled (`verify=True`)
- **API Version:** v3 (via Accept header)

## Azure DevOps Integration

### post_azdevops_comment() Function (lines 7-92)

Posts markdown comment as thread to Azure DevOps PR:

```python
def post_azdevops_comment(markdown: str) -> bool:
    """Post a comment thread to an Azure DevOps PR.

    Args:
        markdown: Comment content in markdown format

    Returns:
        True if successful, False otherwise
    """
```

**Note:** No `pr_url` parameter - always uses environment-based detection.

### Azure DevOps API Details

**Endpoint:**
```
POST {collection_uri}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0
```

**Example:**
```
POST https://dev.azure.com/myorg/myproject/_apis/git/repositories/abc123/pullRequests/456/threads?api-version=7.0
```

**Authentication:**
```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}
```

**Payload Structure:**
```python
payload = {
    "comments": [
        {
            "parentCommentId": 0,
            "content": markdown,
            "commentType": 1  # 1 = text
        }
    ],
    "status": 1  # 1 = active
}
```

**Why Thread Structure?** Azure DevOps uses "threads" (conversation chains) instead of flat comments.

**Fields:**
- `parentCommentId: 0` - Top-level comment (not a reply)
- `commentType: 1` - Text comment (vs. code comment)
- `status: 1` - Active thread (vs. resolved)

### Environment Variables

| Variable | Required | Purpose | Example |
|----------|----------|---------|---------|
| `SYSTEM_ACCESSTOKEN` | ✅ Yes | API authentication | Auto-set by Azure DevOps |
| `SYSTEM_COLLECTIONURI` | ✅ Yes | Organization URL | `https://dev.azure.com/myorg/` |
| `SYSTEM_TEAMPROJECT` | ✅ Yes | Project name | `MyProject` |
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | ✅ Yes | PR ID | `456` |
| `BUILD_REPOSITORY_ID` | ✅ Yes | Repository GUID | `abc123-...` |

**All Required:** Azure DevOps doesn't provide PR URLs, so all environment variables are mandatory.

**Enabling Token:**
```yaml
# In azure-pipelines.yml
steps:
- script: |
    ...
  env:
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

**Permissions (CRITICAL):**
The build service account must have **"Contribute to pull requests"** permission on the repository. Without this, API calls will fail with `403 Forbidden`.

**How to grant:**
1. Project Settings → Repositories → Security
2. Find: `{ProjectName} Build Service ({OrgName})`
3. Set **"Contribute to pull requests"** to **Allow**

See [CICD_INTEGRATION.md - Azure DevOps Setup](../guides/CICD_INTEGRATION.md#step-1-configure-build-service-permissions) for detailed instructions.

### Error Handling

**Missing Environment Variables:**
```python
missing = []
if not token:
    missing.append("SYSTEM_ACCESSTOKEN")
# ... (check all required vars)

if missing:
    sys.stderr.write(
        f"Warning: Cannot post Azure DevOps comment. "
        f"Missing environment variables: {', '.join(missing)}\n"
    )
    return False
```

**HTTPS Validation:**
```python
if not collection_uri.startswith('https://'):
    sys.stderr.write(
        f"Warning: SYSTEM_COLLECTIONURI must use HTTPS. Got: {collection_uri}\n"
    )
    return False
```

**Rationale:** Prevent sending auth tokens over HTTP.

**API Errors:**
```python
try:
    response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
    response.raise_for_status()
    return True
except requests.exceptions.HTTPError as e:
    sys.stderr.write(f"Warning: Azure DevOps API error: {e}\n")
    if hasattr(e.response, 'status_code'):
        sys.stderr.write(f"Status code: {e.response.status_code}\n")
    return False
```

**Extra Context:** Prints HTTP status code on error for debugging.

### Azure DevOps API Request

```python
url = (
    f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories/"
    f"{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0"
)

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

payload = {
    "comments": [{
        "parentCommentId": 0,
        "content": markdown,
        "commentType": 1
    }],
    "status": 1
}

response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
```

**Configuration:**
- **API Version:** 7.0 (latest stable)
- **Timeout:** 30 seconds
- **SSL Verification:** Enabled

## CLI Integration

### _post_pr_comment() Router (cli.py lines 599-629)

Routes to appropriate platform:

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

**Auto-Detection:** Uses token presence to determine platform.

**Error Handling:** Warns but doesn't fail on comment posting errors.

### Usage in CLI

```python
# CI mode: evaluate verdict and post comment
if ci:
    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(...)

    if post_comment:
        markdown = render_markdown(high_confidence_data, ci_mode=True, ...)
        _post_pr_comment(markdown, pr_url)

    # Exit with appropriate code
    ...
```

**Flow:**
1. Evaluate risk buckets
2. If `--post-comment` flag set:
   - Render markdown
   - Post to PR
3. Exit with status code

**Note:** Comment posting happens **before** exit code, ensuring comment posted even if deployment blocked.

## Example Comments

### Standard Comment (No Blocking)

```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | Low | No drift detected |
| PR Intent Alignment | Low | Changes match PR |
| Risky Operations | Medium | New public endpoint |

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

### Blocked Deployment

```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | High | Critical resources drifting |
| PR Intent Alignment | Low | Changes match PR |
| Risky Operations | Low | No risky operations |

**Summary:** Critical infrastructure drift detected.

<details>
<summary>📋 View changed resources (High Confidence)</summary>

...

</details>

---

### Verdict: ❌ UNSAFE
**Reasoning:** Detected drift on critical security resources not modified in this PR.
```

## Benefits

### 1. Code Review Integration

Reviewers see analysis in PR:
- No need to check CI logs
- Risk assessment visible to all reviewers
- Decision context preserved in PR history

### 2. Automated Documentation

PR comments serve as deployment audit trail:
- What was analyzed
- What was the verdict
- Why deployment was blocked/approved

### 3. Asynchronous Review

Comments posted even if pipeline blocked:
- Developers can see why deployment failed
- No need to re-run pipeline to get analysis

## Design Principles

### 1. Platform Abstraction

```python
# Router abstracts platform differences
_post_pr_comment(markdown)  # Works on both platforms
```

**Benefits:**
- CLI doesn't need platform-specific logic
- Easy to add new platforms

### 2. Non-Fatal Failures

Comment posting failures don't fail pipeline:
```python
if not success:
    sys.stderr.write("Warning: Failed to post comment...")
    # Continue execution
```

**Rationale:** Deployment decision more important than comment posting.

### 3. Auto-Detection

No manual configuration needed:
- Token presence determines platform
- Environment variables provide metadata
- Fallback to manual `--pr-url` if needed

### 4. Structured Errors

Clear, actionable error messages:
```
Warning: Cannot post Azure DevOps comment. Missing environment variables: SYSTEM_ACCESSTOKEN, BUILD_REPOSITORY_ID
```

Not:
```
Error: Failed to post comment
```

## Performance Characteristics

- **Network latency:** ~200-500ms per API call
- **Timeout:** 30 seconds
- **Impact on pipeline:** Minimal (non-blocking, runs at end)

## Testing Strategy

### Unit Tests

```python
# Mock requests library
import unittest.mock as mock

with mock.patch('requests.post') as mock_post:
    mock_post.return_value.status_code = 201
    result = post_github_comment("# Test", "https://github.com/owner/repo/pull/123")
    assert result == True
```

### Integration Tests

- Real GitHub API calls (with test token)
- Real Azure DevOps API calls (with test org)
- Verify comment appears in PR
- Test error handling (invalid token, missing vars)

## Future Improvements

1. **Comment Updates:** Update existing comment instead of posting new one
2. **Thread Replies:** Reply to existing threads (Azure DevOps)
3. **Rich Formatting:** Use GitHub/ADO-specific markdown features
4. **Comment Cleanup:** Delete old bot comments
5. **Reaction Indicators:** Add emoji reactions to signal status

## Next Steps

For details on related modules:
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - How `render_markdown()` generates comment content
- [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) - How PR metadata is auto-detected
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - How `_post_pr_comment()` is called
