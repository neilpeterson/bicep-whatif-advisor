# Feature Specification: PR Comments

## Overview

Post formatted markdown comments to GitHub PRs or Azure DevOps PRs using REST APIs. Triggered by `--post-comment` flag in CI mode. Uses platform-specific authentication and API endpoints.

## Module Location

**Files:**
- `bicep_whatif_advisor/ci/github.py`: GitHub PR comment posting
- `bicep_whatif_advisor/ci/azdevops.py`: Azure DevOps PR comment posting

**Dependencies:**
- `requests`: HTTP client (optional dependency)
- `os`: Environment variable access
- `sys`: Error output
- `re`: URL/reference parsing

**Exports:**
- `post_github_comment(markdown: str, pr_url: str = None) -> bool`
- `post_azdevops_comment(markdown: str) -> bool`

## GitHub PR Comments

### Function: `post_github_comment()`

**Signature:**
```python
def post_github_comment(markdown: str, pr_url: str = None) -> bool
```

**Parameters:**
- `markdown`: Comment content in markdown format (from `render_markdown()`)
- `pr_url`: Optional PR URL like "https://github.com/owner/repo/pull/123"

**Returns:**
- `True`: Comment posted successfully
- `False`: Failed to post (missing token, API error, etc.)

**Environment Variables:**

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `GITHUB_TOKEN` | GitHub PAT or Actions token | Yes | `ghp_xxx...` |
| `GITHUB_REPOSITORY` | Repository in "owner/repo" format | Auto-detect only | `microsoft/bicep` |
| `GITHUB_REF` | Git reference | Auto-detect only | `refs/pull/123/merge` |

**Behavior:**

1. **Check for requests library:**
   ```python
   try:
       import requests
   except ImportError:
       sys.stderr.write("Warning: requests package not installed. Cannot post PR comment.\n")
       return False
   ```

2. **Get GitHub token:**
   ```python
   token = os.environ.get("GITHUB_TOKEN")
   if not token:
       sys.stderr.write("Warning: GITHUB_TOKEN not set. Cannot post PR comment.\n")
       return False
   ```

3. **Determine repository and PR number:**

   **If pr_url provided:**
   ```python
   # Parse URL: https://github.com/owner/repo/pull/123
   match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
   if not match:
       sys.stderr.write(f"Warning: Invalid GitHub PR URL: {pr_url}\n")
       return False
   owner, repo, pr_number = match.groups()
   ```

   **If auto-detecting:**
   ```python
   repository = os.environ.get("GITHUB_REPOSITORY")  # "owner/repo"
   github_ref = os.environ.get("GITHUB_REF", "")     # "refs/pull/123/merge"

   # Extract PR number from ref
   pr_match = re.search(r'refs/pull/(\d+)/', github_ref)

   if not repository or not pr_match:
       sys.stderr.write("Warning: Cannot auto-detect GitHub PR. ...")
       return False

   # Validate repository format
   parts = repository.split("/")
   if len(parts) != 2 or not parts[0] or not parts[1]:
       sys.stderr.write(f"Warning: Invalid GITHUB_REPOSITORY format: '{repository}'. ...")
       return False

   owner, repo = parts
   pr_number = pr_match.group(1)
   ```

4. **Post comment via GitHub API:**
   ```python
   url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"

   headers = {
       "Authorization": f"Bearer {token}",
       "Accept": "application/vnd.github.v3+json"
   }

   payload = {"body": markdown}

   try:
       response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
       response.raise_for_status()
       return True

   except requests.exceptions.HTTPError as e:
       sys.stderr.write(f"Warning: GitHub API error: {e}\n")
       return False

   except Exception as e:
       sys.stderr.write(f"Warning: Failed to post GitHub comment: {e}\n")
       return False
   ```

**API Details:**

- **Endpoint:** `POST /repos/{owner}/{repo}/issues/{pr_number}/comments`
- **Authentication:** Bearer token in Authorization header
- **Accept:** `application/vnd.github.v3+json`
- **Timeout:** 30 seconds
- **SSL Verification:** Enabled (`verify=True`)

**Important Notes:**
- Uses `/issues/` endpoint (not `/pulls/`) - comments work on both
- PR number extracted from `GITHUB_REF` (format: `refs/pull/123/merge`)
- All errors are non-fatal - print warning and return False
- Token can be GitHub Actions GITHUB_TOKEN or PAT

## Azure DevOps PR Comments

### Function: `post_azdevops_comment()`

**Signature:**
```python
def post_azdevops_comment(markdown: str) -> bool
```

**Parameters:**
- `markdown`: Comment content in markdown format

**Returns:**
- `True`: Comment posted successfully
- `False`: Failed to post (missing env vars, API error, etc.)

**Environment Variables:**

| Variable | Description | Required | Example |
|----------|-------------|----------|---------|
| `SYSTEM_ACCESSTOKEN` | Azure DevOps PAT | Yes | `xxx...` |
| `SYSTEM_COLLECTIONURI` | Collection URL | Yes | `https://dev.azure.com/myorg/` |
| `SYSTEM_TEAMPROJECT` | Project name | Yes | `MyProject` |
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | PR ID | Yes | `12345` |
| `BUILD_REPOSITORY_ID` | Repository GUID | Yes | `abc-123-def-456` |

**Behavior:**

1. **Check for requests library:**
   ```python
   try:
       import requests
   except ImportError:
       sys.stderr.write("Warning: requests package not installed. Cannot post PR comment.\n")
       return False
   ```

2. **Get required environment variables:**
   ```python
   token = os.environ.get("SYSTEM_ACCESSTOKEN")
   collection_uri = os.environ.get("SYSTEM_COLLECTIONURI")
   project = os.environ.get("SYSTEM_TEAMPROJECT")
   pr_id = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")
   repo_id = os.environ.get("BUILD_REPOSITORY_ID")
   ```

3. **Validate all required variables:**
   ```python
   missing = []
   if not token:
       missing.append("SYSTEM_ACCESSTOKEN")
   if not collection_uri:
       missing.append("SYSTEM_COLLECTIONURI")
   if not project:
       missing.append("SYSTEM_TEAMPROJECT")
   if not pr_id:
       missing.append("SYSTEM_PULLREQUEST_PULLREQUESTID")
   if not repo_id:
       missing.append("BUILD_REPOSITORY_ID")

   if missing:
       sys.stderr.write(
           f"Warning: Cannot post Azure DevOps comment. "
           f"Missing environment variables: {', '.join(missing)}\n"
       )
       return False
   ```

4. **Validate collection URI uses HTTPS:**
   ```python
   if not collection_uri.startswith('https://'):
       sys.stderr.write(
           f"Warning: SYSTEM_COLLECTIONURI must use HTTPS. Got: {collection_uri}\n"
       )
       return False
   ```

5. **Build API URL:**
   ```python
   url = (
       f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories/"
       f"{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0"
   )
   ```

6. **Post comment thread via Azure DevOps API:**
   ```python
   headers = {
       "Content-Type": "application/json",
       "Authorization": f"Bearer {token}"
   }

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

   try:
       response = requests.post(url, json=payload, headers=headers, timeout=30, verify=True)
       response.raise_for_status()
       return True

   except requests.exceptions.HTTPError as e:
       sys.stderr.write(f"Warning: Azure DevOps API error: {e}\n")
       if hasattr(e.response, 'status_code'):
           sys.stderr.write(f"Status code: {e.response.status_code}\n")
       return False

   except Exception as e:
       sys.stderr.write(f"Warning: Failed to post Azure DevOps comment: {e}\n")
       return False
   ```

**API Details:**

- **Endpoint:** `POST {collection_uri}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0`
- **API Version:** 7.0
- **Authentication:** Bearer token in Authorization header
- **Content-Type:** `application/json`
- **Timeout:** 30 seconds
- **SSL Verification:** Enabled (`verify=True`)

**Payload Structure:**
```json
{
  "comments": [
    {
      "parentCommentId": 0,
      "content": "markdown content here",
      "commentType": 1
    }
  ],
  "status": 1
}
```

**Field Meanings:**
- `parentCommentId: 0`: Top-level comment (not a reply)
- `commentType: 1`: Text comment (vs code comment)
- `status: 1`: Active thread (vs resolved/closed)

## CLI Integration

**CLI Flag:**
```bash
--post-comment    # Enable PR comment posting (CI mode only)
```

**Usage in CLI:**
```python
if post_comment and ci_mode:
    markdown = render_markdown(
        data,
        ci_mode=True,
        custom_title=comment_title,
        no_block=no_block,
        low_confidence_data=low_confidence_data
    )

    # Determine platform
    platform_ctx = detect_platform()

    if platform_ctx.platform == "github":
        from .ci.github import post_github_comment
        success = post_github_comment(markdown, pr_url=pr_url)
        if success:
            print("Posted comment to GitHub PR")
        # Failure already logged to stderr

    elif platform_ctx.platform == "azuredevops":
        from .ci.azdevops import post_azdevops_comment
        success = post_azdevops_comment(markdown)
        if success:
            print("Posted comment to Azure DevOps PR")
        # Failure already logged to stderr

    else:
        sys.stderr.write("Warning: PR comments only supported in GitHub Actions or Azure DevOps\n")
```

## Authentication Setup

### GitHub Actions

**Workflow YAML:**
```yaml
- name: Run What-If and Review
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}  # Automatically provided
  run: |
    az deployment group what-if ... | bicep-whatif-advisor --ci --post-comment
```

**Token Permissions:**

The default `GITHUB_TOKEN` requires write permissions:
```yaml
permissions:
  pull-requests: write  # Required for posting comments
```

### Azure DevOps

**Pipeline YAML:**
```yaml
- script: |
    az deployment group what-if ... | bicep-whatif-advisor --ci --post-comment
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)  # From variable group
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
  displayName: 'Run What-If and Review'
```

**Access Token Setup:**

Enable the `System.AccessToken` variable in the pipeline:
```yaml
jobs:
- job: WhatIfReview
  pool:
    vmImage: ubuntu-latest
  steps:
  - checkout: self
    persistCredentials: true  # Required for git operations

  # System.AccessToken is automatically available
  # But needs build service permissions on repository
```

**Required Permissions:**

The build service account needs:
- **Repository:** Contribute to pull requests

Set in: Project Settings → Repositories → Your Repo → Security → Build Service

## Error Handling

**All error scenarios are non-fatal:**

1. **requests not installed:**
   ```
   Warning: requests package not installed. Cannot post PR comment.
   ```
   - Returns False
   - Tool continues, just doesn't post comment

2. **Missing token:**
   ```
   Warning: GITHUB_TOKEN not set. Cannot post PR comment.
   Warning: Cannot post Azure DevOps comment. Missing environment variables: SYSTEM_ACCESSTOKEN, ...
   ```
   - Returns False
   - Tool continues

3. **API error (401, 403, 404, etc.):**
   ```
   Warning: GitHub API error: 403 Client Error: Forbidden
   Warning: Azure DevOps API error: 401 Client Error: Unauthorized
   ```
   - Returns False
   - Tool continues

4. **Network error:**
   ```
   Warning: Failed to post GitHub comment: Connection timeout
   ```
   - Returns False
   - Tool continues

**Philosophy:** Comment posting is a nice-to-have feature. If it fails, the tool should still complete successfully. The verdict and exit code are what matter for the deployment gate.

## Comment Format

Comments are formatted markdown from `render_markdown()`:

**Standard Mode:**
```markdown
<details>
<summary>📋 View changed resources</summary>

| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | myResource | Storage Account | Create | Creates new storage account |

</details>

**Summary:** 1 create: Adds storage account for logs
```

**CI Mode:**
```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | Low | None |
| PR Intent Alignment | Medium | Public IP not mentioned in PR |
| Risky Operations | Medium | Exposing public IP address |

<details>
<summary>📋 View changed resources</summary>

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | myAPI | API Management | Modify | Medium | Enables public IP addressing |

</details>

**Summary:** 1 modify: Exposes API to public internet

### Verdict: ❌ UNSAFE

**Overall Risk Level:** Medium
**Highest Risk Bucket:** Intent
**Reasoning:** The public IP change is not mentioned in the PR description, which only talks about adding JWT authentication.

---
*Generated by [bicep-whatif-advisor](https://github.com/yourorg/bicep-whatif-advisor)*
```

## Implementation Requirements

1. **Non-fatal errors:** All failures return False, print warning, continue
2. **requests is optional:** Check for ImportError before use
3. **Token validation:** Check environment variables before API call
4. **URL validation:** Validate HTTPS for Azure DevOps, parse GitHub URLs correctly
5. **Timeout:** Use 30-second timeout for all API calls
6. **SSL verification:** Always verify=True for security
7. **Error details:** Print specific error messages to stderr
8. **Platform detection:** Use `detect_platform()` to choose correct function
9. **Auto-detect first:** Try to auto-detect from environment before requiring manual --pr-url

## Edge Cases

1. **requests not installed:** Print warning, return False
2. **Empty markdown:** Valid, post empty comment
3. **Very long markdown:** API may reject, catch HTTPError
4. **Invalid pr_url format:** Print warning, return False
5. **GITHUB_REPOSITORY wrong format:** Validate "owner/repo" format
6. **GITHUB_REF without PR number:** Print warning, return False
7. **Azure DevOps API rate limits:** Catch HTTPError 429, print warning
8. **Token expired:** Catch 401 error, print warning
9. **No PR context (e.g., push to main):** Auto-detect fails, return False
10. **Multiple comments on same PR:** Valid, API allows multiple comments
