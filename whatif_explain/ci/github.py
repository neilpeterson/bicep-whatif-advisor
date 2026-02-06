"""GitHub PR comment posting for CI mode."""

import os
import sys
import re


def post_github_comment(markdown: str, pr_url: str = None) -> bool:
    """Post a comment to a GitHub PR.

    Args:
        markdown: Comment content in markdown format
        pr_url: Optional PR URL (auto-detected from env if not provided)

    Returns:
        True if successful, False otherwise
    """
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

    # Get repository and PR number
    if pr_url:
        # Parse from URL: https://github.com/owner/repo/pull/123
        match = re.search(r'github\.com/([^/]+)/([^/]+)/pull/(\d+)', pr_url)
        if not match:
            sys.stderr.write(f"Warning: Invalid GitHub PR URL: {pr_url}\n")
            return False
        owner, repo, pr_number = match.groups()
    else:
        # Auto-detect from environment
        repository = os.environ.get("GITHUB_REPOSITORY")  # format: owner/repo

        # Try to get PR number from GITHUB_REF (format: refs/pull/123/merge)
        github_ref = os.environ.get("GITHUB_REF", "")
        pr_match = re.search(r'refs/pull/(\d+)/', github_ref)

        if not repository or not pr_match:
            sys.stderr.write(
                "Warning: Cannot auto-detect GitHub PR. "
                "Set GITHUB_REPOSITORY and GITHUB_REF or provide --pr-url.\n"
            )
            return False

        # Validate GITHUB_REPOSITORY format
        parts = repository.split("/")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            sys.stderr.write(
                f"Warning: Invalid GITHUB_REPOSITORY format: '{repository}'. "
                "Expected format: 'owner/repo'\n"
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
