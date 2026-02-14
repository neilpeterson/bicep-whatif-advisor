# Phase 5 Implementation Prompt: Noise Filtering and PR Comments

## Objective

Implement two-phase noise filtering (LLM confidence scoring + pattern matching), re-analysis workflow for CI mode, and PR comment posting for GitHub/Azure DevOps.

## Context

This phase adds the final production-ready features: filtering Azure What-If noise using LLM confidence scores and optional user-defined patterns, re-analyzing filtered data in CI mode to ensure clean risk assessment, and posting formatted results as PR comments.

## Specifications to Reference

Read these specification files before starting:
- `specifications/08-NOISE-FILTERING.md` - Noise filtering system
- `specifications/07-PR-COMMENTS.md` - PR comment posting

## Tasks

### Task 1: Noise Filtering Module

Create `bicep_whatif_advisor/noise_filter.py`:

#### Step 1.1: Pattern Loading

```python
"""Azure What-If noise filtering using LLM confidence scores and pattern matching."""

from pathlib import Path
from difflib import SequenceMatcher
from typing import List


def load_noise_patterns(file_path: str) -> List[str]:
    """Load noise patterns from text file.

    File format:
    - One pattern per line
    - Lines starting with # are comments (ignored)
    - Blank lines ignored

    Args:
        file_path: Path to noise patterns file

    Returns:
        List of pattern strings

    Raises:
        FileNotFoundError: If file doesn't exist
        IOError: If file can't be read
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Noise patterns file not found: {file_path}")

    patterns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    return patterns
```

#### Step 1.2: Fuzzy Matching

```python
def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two strings.

    Uses difflib.SequenceMatcher (Ratcliff/Obershelp algorithm).
    Case-insensitive comparison.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity ratio (0.0 to 1.0, where 1.0 = identical)
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def match_noise_pattern(
    summary: str,
    patterns: List[str],
    threshold: float = 0.80
) -> bool:
    """Check if summary matches any noise pattern.

    Args:
        summary: Resource summary text from LLM
        patterns: List of noise pattern strings
        threshold: Similarity threshold (0.0-1.0, default 0.80)

    Returns:
        True if summary matches at least one pattern above threshold
    """
    if not summary or not patterns:
        return False

    for pattern in patterns:
        similarity = calculate_similarity(summary, pattern)
        if similarity >= threshold:
            return True

    return False
```

#### Step 1.3: Apply Pattern Filtering

```python
def apply_noise_filtering(
    data: dict,
    noise_file: str,
    threshold: float = 0.80
) -> dict:
    """Apply pattern-based noise filtering to LLM response.

    Modifies confidence_level to "noise" for resources matching patterns.

    Args:
        data: Parsed LLM response with resources list
        noise_file: Path to noise patterns file
        threshold: Similarity threshold for matching (0.0-1.0)

    Returns:
        Modified data dict (same object, modified in-place)

    Raises:
        FileNotFoundError: If noise_file doesn't exist
        IOError: If noise_file can't be read
    """
    patterns = load_noise_patterns(noise_file)
    if not patterns:
        return data  # No patterns, return unchanged

    resources = data.get("resources", [])
    for resource in resources:
        summary = resource.get("summary", "")

        if match_noise_pattern(summary, patterns, threshold):
            resource["confidence_level"] = "noise"

    return data
```

### Task 2: Confidence Filtering in CLI

Update `bicep_whatif_advisor/cli.py` to add confidence-based filtering:

#### Step 2.1: Add filter_by_confidence() Function

Add near the top of `cli.py`, after imports:

```python
def filter_by_confidence(data: dict) -> tuple[dict, dict]:
    """Split resources by confidence level.

    Separates low/noise confidence resources from medium/high confidence.

    Args:
        data: Parsed LLM response

    Returns:
        Tuple of (high_confidence_data, low_confidence_data)
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

    # Build high-confidence data dict
    high_confidence_data = {
        "resources": high_confidence_resources,
        "overall_summary": data.get("overall_summary", "")
    }

    # Preserve CI mode fields in high-confidence data
    if "risk_assessment" in data:
        high_confidence_data["risk_assessment"] = data["risk_assessment"]
    if "verdict" in data:
        high_confidence_data["verdict"] = data["verdict"]

    # Build low-confidence data dict
    low_confidence_data = {
        "resources": low_confidence_resources,
        "overall_summary": ""  # No separate summary for noise
    }

    return high_confidence_data, low_confidence_data
```

#### Step 2.2: Add CLI Flags

```python
@click.command()
# ... existing options ...
@click.option("--noise-filter", type=str, default=None,
              help="Path to noise patterns file for additional filtering")
@click.option("--noise-threshold", type=float, default=0.80,
              help="Similarity threshold for noise pattern matching (0.0-1.0)")
def main(provider, model, format, verbose, ci, diff_ref, pr_title, pr_description,
         drift_threshold, intent_threshold, operations_threshold,
         noise_filter, noise_threshold):
    """Analyze Azure What-If deployment output using LLMs."""
```

#### Step 2.3: Update Standard Mode

```python
else:
    # Standard mode
    system_prompt = build_system_prompt(verbose=verbose)
    user_prompt = build_user_prompt(whatif_content)

    response_text = llm_provider.complete(system_prompt, user_prompt)
    data = extract_json(response_text)

    # Apply pattern-based noise filtering (if enabled)
    if noise_filter:
        from .noise_filter import apply_noise_filtering
        try:
            data = apply_noise_filtering(data, noise_filter, noise_threshold)
        except (FileNotFoundError, IOError) as e:
            sys.stderr.write(f"Warning: Noise filtering failed: {e}\n")

    # Filter by confidence
    high_conf_data, low_conf_data = filter_by_confidence(data)

    # Render output
    if format == "table":
        render_table(high_conf_data, verbose=verbose, low_confidence_data=low_conf_data)
    elif format == "json":
        render_json(high_conf_data, low_confidence_data=low_conf_data)
    elif format == "markdown":
        markdown = render_markdown(high_conf_data, low_confidence_data=low_conf_data)
        print(markdown)

    sys.exit(0)
```

#### Step 2.4: Update CI Mode with Re-analysis

**CRITICAL WORKFLOW:** In CI mode, after filtering, re-analyze ONLY high-confidence resources to get clean risk assessment.

```python
if ci:
    # Use auto-detected values as defaults, allow CLI overrides
    diff_ref = diff_ref or platform_ctx.get_diff_ref()
    pr_title = pr_title or platform_ctx.pr_title
    pr_description = pr_description or platform_ctx.pr_description

    # Get git diff
    from .ci.diff import get_diff
    diff_content = get_diff(diff_ref)

    if diff_content is None:
        sys.stderr.write("Error: Could not get git diff. CI mode requires git diff.\n")
        sys.exit(2)

    # Build CI prompts
    system_prompt = build_system_prompt(
        ci_mode=True,
        pr_title=pr_title,
        pr_description=pr_description
    )
    user_prompt = build_user_prompt(
        whatif_content,
        diff_content=diff_content,
        pr_title=pr_title,
        pr_description=pr_description
    )

    # Initial LLM call with confidence scoring
    response_text = llm_provider.complete(system_prompt, user_prompt)
    data = extract_json(response_text)

    # Apply pattern-based noise filtering (if enabled)
    if noise_filter:
        from .noise_filter import apply_noise_filtering
        try:
            data = apply_noise_filtering(data, noise_filter, noise_threshold)
        except (FileNotFoundError, IOError) as e:
            sys.stderr.write(f"Warning: Noise filtering failed: {e}\n")

    # Filter by confidence
    high_conf_data, low_conf_data = filter_by_confidence(data)

    # RE-ANALYZE high-confidence resources for clean risk assessment
    # (Only if we actually filtered something out)
    if low_conf_data["resources"]:
        # Build What-If content with ONLY high-confidence resources
        # This is simplified - in production, would reconstruct What-If format
        # For now, just re-run with note about filtering
        filtered_note = f"\nNote: {len(low_conf_data['resources'])} low-confidence resources were filtered out as likely Azure What-If noise.\n"
        user_prompt_filtered = build_user_prompt(
            whatif_content + filtered_note,
            diff_content=diff_content,
            pr_title=pr_title,
            pr_description=pr_description
        )

        try:
            response_text_filtered = llm_provider.complete(system_prompt, user_prompt_filtered)
            high_conf_data = extract_json(response_text_filtered)
        except Exception as e:
            sys.stderr.write(f"Warning: Re-analysis failed, using initial assessment: {e}\n")
            # Fallback to initial high_conf_data if re-analysis fails

    # Now evaluate risk buckets on CLEAN data
    from .ci.risk_buckets import evaluate_risk_buckets
    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
        high_conf_data,
        drift_threshold,
        intent_threshold,
        operations_threshold
    )

    # Render output
    if format == "table":
        render_table(high_conf_data, ci_mode=True, low_confidence_data=low_conf_data)
    elif format == "json":
        render_json(high_conf_data, low_confidence_data=low_conf_data)
    elif format == "markdown":
        markdown = render_markdown(high_conf_data, ci_mode=True, low_confidence_data=low_conf_data)
        print(markdown)

    # Print verdict
    print()
    if is_safe:
        print("✅ SAFE: All risk buckets within acceptable thresholds")
        sys.exit(0)
    else:
        print(f"❌ UNSAFE: Failed buckets: {', '.join(failed_buckets)}")
        sys.exit(1)
```

### Task 3: PR Comment Posting

#### Step 3.1: GitHub PR Comments

Create `bicep_whatif_advisor/ci/github.py`:

```python
"""GitHub PR comment posting."""

import os
import sys
import re


def post_github_comment(markdown: str, pr_url: str = None) -> bool:
    """Post comment to GitHub PR.

    Args:
        markdown: Comment content in markdown format
        pr_url: Optional PR URL like "https://github.com/owner/repo/pull/123"

    Returns:
        True if comment posted successfully, False otherwise
    """
    # Check for requests library
    try:
        import requests
    except ImportError:
        sys.stderr.write("Warning: requests package not installed. Cannot post PR comment.\n")
        return False

    # Get GitHub token
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.stderr.write("Warning: GITHUB_TOKEN not set. Cannot post PR comment.\n")
        return False

    # Determine repository and PR number
    if pr_url:
        # Parse URL: https://github.com/owner/repo/pull/123
        match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
        if not match:
            sys.stderr.write(f"Warning: Invalid GitHub PR URL: {pr_url}\n")
            return False
        owner, repo, pr_number = match.groups()
    else:
        # Auto-detect from environment
        repository = os.environ.get("GITHUB_REPOSITORY")
        github_ref = os.environ.get("GITHUB_REF", "")

        # Extract PR number from ref (format: refs/pull/123/merge)
        pr_match = re.search(r'refs/pull/(\d+)/', github_ref)

        if not repository or not pr_match:
            sys.stderr.write(
                "Warning: Cannot auto-detect GitHub PR. "
                "Set GITHUB_REPOSITORY and GITHUB_REF or use --pr-url flag.\n"
            )
            return False

        # Validate repository format
        parts = repository.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            sys.stderr.write(
                f"Warning: Invalid GITHUB_REPOSITORY format: '{repository}'. "
                "Expected 'owner/repo'.\n"
            )
            return False

        owner, repo = parts
        pr_number = pr_match.group(1)

    # Post comment via GitHub API
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

#### Step 3.2: Azure DevOps PR Comments

Create `bicep_whatif_advisor/ci/azdevops.py`:

```python
"""Azure DevOps PR comment posting."""

import os
import sys


def post_azdevops_comment(markdown: str) -> bool:
    """Post comment to Azure DevOps PR.

    Args:
        markdown: Comment content in markdown format

    Returns:
        True if comment posted successfully, False otherwise
    """
    # Check for requests library
    try:
        import requests
    except ImportError:
        sys.stderr.write("Warning: requests package not installed. Cannot post PR comment.\n")
        return False

    # Get required environment variables
    token = os.environ.get("SYSTEM_ACCESSTOKEN")
    collection_uri = os.environ.get("SYSTEM_COLLECTIONURI")
    project = os.environ.get("SYSTEM_TEAMPROJECT")
    pr_id = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")
    repo_id = os.environ.get("BUILD_REPOSITORY_ID")

    # Validate all required variables
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

    # Validate HTTPS
    if not collection_uri.startswith('https://'):
        sys.stderr.write(
            f"Warning: SYSTEM_COLLECTIONURI must use HTTPS. Got: {collection_uri}\n"
        )
        return False

    # Build API URL
    url = (
        f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories/"
        f"{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0"
    )

    # Post comment thread
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

#### Step 3.3: Integrate PR Comments in CLI

Add to `cli.py`:

```python
@click.option("--post-comment", is_flag=True,
              help="Post results as PR comment (CI mode only)")
@click.option("--comment-title", type=str, default=None,
              help="Custom title for PR comment")
@click.option("--pr-url", type=str, default=None,
              help="GitHub PR URL (for manual override)")
def main(provider, model, format, verbose, ci, diff_ref, pr_title, pr_description,
         drift_threshold, intent_threshold, operations_threshold,
         noise_filter, noise_threshold, post_comment, comment_title, pr_url):
```

Add after rendering in CI mode:

```python
if ci:
    # ... existing CI mode logic ...

    # Render output
    if format == "table":
        render_table(high_conf_data, ci_mode=True, low_confidence_data=low_conf_data)
    elif format == "json":
        render_json(high_conf_data, low_confidence_data=low_conf_data)
    elif format == "markdown":
        markdown = render_markdown(high_conf_data, ci_mode=True, low_confidence_data=low_conf_data)
        print(markdown)

    # Post PR comment if requested
    if post_comment:
        markdown = render_markdown(
            high_conf_data,
            ci_mode=True,
            custom_title=comment_title,
            low_confidence_data=low_conf_data
        )

        if platform_ctx.platform == "github":
            from .ci.github import post_github_comment
            success = post_github_comment(markdown, pr_url=pr_url)
            if success:
                print("Posted comment to GitHub PR")

        elif platform_ctx.platform == "azuredevops":
            from .ci.azdevops import post_azdevops_comment
            success = post_azdevops_comment(markdown)
            if success:
                print("Posted comment to Azure DevOps PR")

        else:
            sys.stderr.write("Warning: PR comments only supported in GitHub Actions or Azure DevOps\n")

    # Print verdict
    print()
    if is_safe:
        print("✅ SAFE: All risk buckets within acceptable thresholds")
        sys.exit(0)
    else:
        print(f"❌ UNSAFE: Failed buckets: {', '.join(failed_buckets)}")
        sys.exit(1)
```

### Task 4: Testing

#### Step 4.1: Unit Tests

Create `tests/test_noise_filter.py`:

```python
import pytest
from pathlib import Path
from bicep_whatif_advisor.noise_filter import (
    load_noise_patterns,
    calculate_similarity,
    match_noise_pattern,
    apply_noise_filtering,
)


def test_load_noise_patterns(tmp_path):
    """Test loading patterns from file."""
    patterns_file = tmp_path / "patterns.txt"
    patterns_file.write_text(
        "# Comment line\n"
        "\n"
        "Pattern 1\n"
        "Pattern 2\n"
    )

    patterns = load_noise_patterns(str(patterns_file))
    assert patterns == ["Pattern 1", "Pattern 2"]


def test_load_noise_patterns_file_not_found():
    """Test error when file doesn't exist."""
    with pytest.raises(FileNotFoundError):
        load_noise_patterns("/nonexistent/file.txt")


def test_calculate_similarity():
    """Test similarity calculation."""
    assert calculate_similarity("hello", "hello") == 1.0
    assert calculate_similarity("hello", "HELLO") == 1.0
    assert calculate_similarity("hello", "world") < 0.5


def test_match_noise_pattern():
    """Test pattern matching."""
    patterns = ["Computed property change", "Metadata update"]

    assert match_noise_pattern("Computed property change", patterns, 0.80) is True
    assert match_noise_pattern("Computed property changes", patterns, 0.80) is True
    assert match_noise_pattern("Creates new resource", patterns, 0.80) is False


def test_apply_noise_filtering(tmp_path):
    """Test applying noise filtering."""
    patterns_file = tmp_path / "patterns.txt"
    patterns_file.write_text("Computed property\n")

    data = {
        "resources": [
            {
                "resource_name": "res1",
                "summary": "Computed property change",
                "confidence_level": "medium"
            },
            {
                "resource_name": "res2",
                "summary": "Creates new resource",
                "confidence_level": "high"
            }
        ]
    }

    result = apply_noise_filtering(data, str(patterns_file), 0.80)

    assert result["resources"][0]["confidence_level"] == "noise"
    assert result["resources"][1]["confidence_level"] == "high"
```

Create `tests/test_pr_comments.py`:

```python
import pytest
from unittest.mock import Mock, patch
from bicep_whatif_advisor.ci.github import post_github_comment
from bicep_whatif_advisor.ci.azdevops import post_azdevops_comment


def test_post_github_comment_success(mocker):
    """Test successful GitHub comment posting."""
    mock_response = Mock()
    mock_response.status_code = 200
    mocker.patch('requests.post', return_value=mock_response)

    mocker.patch.dict('os.environ', {
        'GITHUB_TOKEN': 'token',
        'GITHUB_REPOSITORY': 'owner/repo',
        'GITHUB_REF': 'refs/pull/123/merge'
    })

    result = post_github_comment("Test comment")
    assert result is True


def test_post_github_comment_no_token(mocker):
    """Test GitHub comment with missing token."""
    mocker.patch.dict('os.environ', {}, clear=True)

    result = post_github_comment("Test comment")
    assert result is False


def test_post_azdevops_comment_success(mocker):
    """Test successful Azure DevOps comment posting."""
    mock_response = Mock()
    mock_response.status_code = 200
    mocker.patch('requests.post', return_value=mock_response)

    mocker.patch.dict('os.environ', {
        'SYSTEM_ACCESSTOKEN': 'token',
        'SYSTEM_COLLECTIONURI': 'https://dev.azure.com/org/',
        'SYSTEM_TEAMPROJECT': 'project',
        'SYSTEM_PULLREQUEST_PULLREQUESTID': '123',
        'BUILD_REPOSITORY_ID': 'repo-id'
    })

    result = post_azdevops_comment("Test comment")
    assert result is True
```

#### Step 4.2: Manual Testing

```bash
# Test noise filtering
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor --noise-filter patterns.txt

# Test CI mode with noise filtering
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor --ci --noise-filter patterns.txt

# Test PR comment posting (requires env vars)
export GITHUB_TOKEN=...
export GITHUB_REPOSITORY=owner/repo
export GITHUB_REF=refs/pull/123/merge
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --ci --post-comment
```

## Validation Checklist

- [ ] `noise_filter.py` created
- [ ] `load_noise_patterns()` reads file correctly
- [ ] `load_noise_patterns()` filters comments and blank lines
- [ ] `calculate_similarity()` uses SequenceMatcher
- [ ] `calculate_similarity()` is case-insensitive
- [ ] `match_noise_pattern()` checks all patterns
- [ ] `match_noise_pattern()` uses threshold correctly
- [ ] `apply_noise_filtering()` modifies confidence_level
- [ ] `filter_by_confidence()` splits resources correctly
- [ ] Low-confidence includes "noise" level
- [ ] CLI `--noise-filter` flag added
- [ ] CLI `--noise-threshold` flag added
- [ ] Pattern filtering applied in standard mode
- [ ] Pattern filtering applied in CI mode
- [ ] CI mode re-analyzes after filtering
- [ ] Re-analysis only happens if resources filtered
- [ ] `ci/github.py` created
- [ ] GitHub comment posting works
- [ ] GitHub auto-detection from env vars works
- [ ] GitHub URL parsing works
- [ ] `ci/azdevops.py` created
- [ ] Azure DevOps comment posting works
- [ ] Azure DevOps validates all env vars
- [ ] Azure DevOps validates HTTPS
- [ ] CLI `--post-comment` flag added
- [ ] PR comments posted after rendering
- [ ] Platform detection used to choose comment method
- [ ] Comment posting errors are non-fatal
- [ ] Tests pass for noise filtering
- [ ] Tests pass for PR comment posting

## Next Phase

Once Phase 5 is complete and validated, proceed to Phase 6 (Testing and Documentation).

Phase 6 will add:
- Comprehensive unit tests
- Integration tests
- Test fixtures
- Documentation (README, guides)
- Final validation

## Notes

- Noise filtering is optional - tool works without it
- Re-analysis in CI mode is critical for clean risk assessment
- Pattern matching uses fuzzy matching (not exact or regex)
- Default threshold 0.80 is balanced - adjust if needed
- PR comment posting is best-effort (failures are non-fatal)
- requests library is optional - graceful degradation if not installed
- All file I/O should handle encoding explicitly (UTF-8)
