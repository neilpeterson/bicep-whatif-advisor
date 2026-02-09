"""Azure DevOps PR comment posting for CI mode."""

import os
import sys


def post_azdevops_comment(markdown: str) -> bool:
    """Post a comment thread to an Azure DevOps PR.

    Args:
        markdown: Comment content in markdown format

    Returns:
        True if successful, False otherwise
    """
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

    # Validate all required vars are present
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

    # Validate collection_uri uses HTTPS
    if not collection_uri.startswith('https://'):
        sys.stderr.write(
            f"Warning: SYSTEM_COLLECTIONURI must use HTTPS. Got: {collection_uri}\n"
        )
        return False

    # Build API URL
    # Format: {collection_uri}{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads
    url = (
        f"{collection_uri.rstrip('/')}/{project}/_apis/git/repositories/"
        f"{repo_id}/pullRequests/{pr_id}/threads?api-version=7.0"
    )

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
