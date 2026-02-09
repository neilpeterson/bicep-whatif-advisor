"""Unified CI/CD platform detection for GitHub Actions and Azure DevOps."""

import os
import json
import sys
from dataclasses import dataclass
from typing import Optional, Literal

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


def _detect_azuredevops() -> PlatformContext:
    """Extract metadata from Azure DevOps environment.

    Reads PR and branch information from Azure DevOps pipeline
    environment variables.

    Returns:
        PlatformContext with Azure DevOps-specific metadata

    Note:
        Azure DevOps does not expose PR title/description in environment
        variables. To get this metadata, would need to call the Azure DevOps
        REST API (requires SYSTEM_ACCESSTOKEN). For now, these fields will
        be None unless provided manually via CLI flags.
    """
    ctx = PlatformContext(platform="azuredevops")

    # Get PR number
    ctx.pr_number = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")

    # Get branches (format: refs/heads/main or refs/heads/feature/branch)
    ctx.base_branch = os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH")
    ctx.source_branch = os.environ.get("SYSTEM_PULLREQUEST_SOURCEBRANCH")

    # Get repository name
    ctx.repository = os.environ.get("BUILD_REPOSITORY_NAME")

    # Azure DevOps doesn't expose PR title/description in env vars
    # Would need to call Azure DevOps REST API to fetch this data
    # TODO: Optionally fetch PR metadata via Azure DevOps REST API
    # if os.environ.get("SYSTEM_ACCESSTOKEN"):
    #     ctx.pr_title, ctx.pr_description = _fetch_ado_pr_metadata(ctx)

    return ctx


# Future: Optional API call to fetch Azure DevOps PR metadata
# def _fetch_ado_pr_metadata(ctx: PlatformContext) -> tuple[Optional[str], Optional[str]]:
#     """Fetch PR title and description from Azure DevOps REST API.
#
#     Args:
#         ctx: Platform context with PR number and repository info
#
#     Returns:
#         Tuple of (pr_title, pr_description)
#     """
#     # Requires: SYSTEM_ACCESSTOKEN, SYSTEM_COLLECTIONURI, SYSTEM_TEAMPROJECT
#     # API: {collection_uri}/{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}
#     pass
