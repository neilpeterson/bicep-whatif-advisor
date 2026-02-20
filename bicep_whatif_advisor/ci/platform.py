"""Unified CI/CD platform detection for GitHub Actions and Azure DevOps."""

import json
import os
import sys
from dataclasses import dataclass
from typing import Literal, Optional

PlatformType = Literal["github", "azuredevops", "local"]


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

    def has_pr_metadata(self) -> bool:
        """Check if PR metadata is available.

        Returns:
            True if PR number and at least one of title/description is available
        """
        return bool(self.pr_number and (self.pr_title or self.pr_description))

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
                with open(event_path, "r", encoding="utf-8") as f:
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
                sys.stderr.write(f"Warning: Could not read GitHub event file: {e}\n")

    return ctx


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


def _fetch_ado_pr_metadata(ctx: PlatformContext) -> tuple[Optional[str], Optional[str]]:
    """Fetch PR title and description from Azure DevOps REST API.

    Args:
        ctx: Platform context with PR number and repository info

    Returns:
        Tuple of (pr_title, pr_description), or (None, None) if fetch fails
    """
    import requests

    # Get required environment variables
    access_token = os.environ.get("SYSTEM_ACCESSTOKEN")
    collection_uri = os.environ.get("SYSTEM_COLLECTIONURI")
    team_project = os.environ.get("SYSTEM_TEAMPROJECT")
    repo_id = os.environ.get("BUILD_REPOSITORY_ID")

    # Validate required variables
    if not all([access_token, collection_uri, team_project, ctx.pr_number]):
        sys.stderr.write(
            "Warning: Missing Azure DevOps environment variables for PR metadata fetch. "
            "PR title/description will not be available.\n"
        )
        return None, None

    # Build API URL
    # API: {collection_uri}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}
    # If repo_id not available, use repository name
    repo_identifier = repo_id or ctx.repository
    if not repo_identifier:
        sys.stderr.write(
            "Warning: Could not determine repository ID or name for Azure DevOps API call.\n"
        )
        return None, None

    api_url = (
        f"{collection_uri.rstrip('/')}/{team_project}/_apis/git/repositories/"
        f"{repo_identifier}/pullrequests/{ctx.pr_number}?api-version=7.0"
    )

    # Make API request
    try:
        headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()

        pr_data = response.json()

        # Extract title and description
        pr_title = pr_data.get("title")
        pr_description = pr_data.get("description")

        # Log success
        if pr_title:
            title_preview = pr_title[:60] + "..." if len(pr_title) > 60 else pr_title
            sys.stderr.write(f"✅ Fetched PR title from Azure DevOps API: {title_preview}\n")

        if pr_description:
            desc_lines = len(pr_description.splitlines())
            sys.stderr.write(
                f"✅ Fetched PR description from Azure DevOps API ({desc_lines} lines)\n"
            )

        return pr_title, pr_description

    except requests.exceptions.RequestException as e:
        sys.stderr.write(
            f"Warning: Failed to fetch PR metadata from Azure DevOps API: {e}\n"
            "PR title/description will not be available for intent analysis.\n"
        )
        return None, None
    except (KeyError, ValueError) as e:
        sys.stderr.write(
            f"Warning: Failed to parse PR metadata from Azure DevOps API response: {e}\n"
        )
        return None, None
