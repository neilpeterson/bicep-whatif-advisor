# Phase 3 Implementation Prompt: CI/CD Platform Detection

## Objective

Implement automatic CI/CD platform detection, PR metadata extraction, and git diff collection to enable zero-configuration CI mode.

## Context

This phase builds the intelligence layer for CI/CD environments. The tool will automatically detect whether it's running in GitHub Actions or Azure DevOps, extract PR metadata from environment variables and event files, and collect git diff context - all without requiring manual CLI flags.

## Specifications to Reference

Read these specification files before starting:
- `specifications/05-PLATFORM-DETECTION.md` - Platform detection logic
- `specifications/00-OVERVIEW.md` - Overall architecture

## Tasks

### Task 1: Platform Context Data Structure

Create `bicep_whatif_advisor/ci/` directory and `bicep_whatif_advisor/ci/__init__.py`:

```python
"""CI/CD integration modules."""
```

Create `bicep_whatif_advisor/ci/platform.py`:

#### Step 1.1: Type Definitions and Imports

```python
"""CI/CD platform detection and context extraction."""

import os
import json
import sys
from dataclasses import dataclass
from typing import Optional, Literal

PlatformType = Literal["github", "azuredevops", "local"]
```

#### Step 1.2: PlatformContext Dataclass

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

    def has_pr_metadata(self) -> bool:
        """Check if PR metadata is available for intent analysis.

        Returns:
            True if PR number and at least one of title/description available
        """
        return bool(self.pr_number and (self.pr_title or self.pr_description))

    def get_diff_ref(self) -> str:
        """Get git reference for diff command.

        Returns:
            Git reference like "origin/main" or "HEAD~1"
        """
        if self.base_branch:
            # Remove refs/heads/ prefix if present (common in Azure DevOps)
            branch = self.base_branch.replace("refs/heads/", "")
            return f"origin/{branch}"
        return "HEAD~1"  # fallback to previous commit
```

### Task 2: Platform Detection Functions

#### Step 2.1: Main Detection Function

Add to `platform.py`:

```python
def detect_platform() -> PlatformContext:
    """Auto-detect CI/CD platform from environment variables.

    Returns:
        PlatformContext with platform-specific metadata
    """
    # Check for GitHub Actions
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return _detect_github()

    # Check for Azure DevOps
    if os.environ.get("TF_BUILD") == "True" or os.environ.get("AGENT_ID"):
        return _detect_azuredevops()

    # Default to local development
    return PlatformContext(platform="local")
```

#### Step 2.2: GitHub Detection

```python
def _detect_github() -> PlatformContext:
    """Detect GitHub Actions environment and extract metadata.

    Returns:
        PlatformContext for GitHub
    """
    ctx = PlatformContext(platform="github")

    # Extract repository
    ctx.repository = os.environ.get("GITHUB_REPOSITORY")

    # Extract branches
    ctx.base_branch = os.environ.get("GITHUB_BASE_REF")
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

                    pr_number = pr_data.get("number")
                    if pr_number:
                        ctx.pr_number = str(pr_number)

                    ctx.pr_title = pr_data.get("title")
                    ctx.pr_description = pr_data.get("body")

            except (OSError, json.JSONDecodeError) as e:
                sys.stderr.write(f"Warning: Could not read GitHub event file: {e}\n")

    return ctx
```

#### Step 2.3: Azure DevOps Detection

```python
def _detect_azuredevops() -> PlatformContext:
    """Detect Azure DevOps environment and extract metadata.

    Note: Azure DevOps does NOT expose PR title/description in environment
    variables. Would need REST API call to fetch (not implemented).

    Returns:
        PlatformContext for Azure DevOps
    """
    ctx = PlatformContext(platform="azuredevops")

    # Extract PR number
    ctx.pr_number = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")

    # Extract branches
    ctx.base_branch = os.environ.get("SYSTEM_PULLREQUEST_TARGETBRANCH")
    ctx.source_branch = os.environ.get("SYSTEM_PULLREQUEST_SOURCEBRANCH")

    # Extract repository
    ctx.repository = os.environ.get("BUILD_REPOSITORY_NAME")

    # Note: PR title/description not available from env vars
    # TODO: Optionally fetch via REST API if SYSTEM_ACCESSTOKEN available

    return ctx
```

### Task 3: Git Diff Collection

Create `bicep_whatif_advisor/ci/diff.py`:

```python
"""Git diff collection for CI mode."""

import subprocess
import sys
from typing import Optional


def get_diff(diff_ref: str = "origin/main", max_size: int = 50000) -> Optional[str]:
    """Get git diff for CI mode analysis.

    Args:
        diff_ref: Git reference to diff against (e.g., "origin/main")
        max_size: Maximum diff size in characters

    Returns:
        Git diff output, or None if git command fails
    """
    try:
        result = subprocess.run(
            ["git", "diff", diff_ref],
            capture_output=True,
            text=True,
            timeout=30,
            check=False
        )

        if result.returncode != 0:
            sys.stderr.write(f"Warning: git diff failed: {result.stderr}\n")
            return None

        diff_content = result.stdout

        # Truncate if too large
        if len(diff_content) > max_size:
            sys.stderr.write(
                f"Warning: Git diff truncated from {len(diff_content)} "
                f"to {max_size} characters\n"
            )
            diff_content = diff_content[:max_size]

        return diff_content

    except subprocess.TimeoutExpired:
        sys.stderr.write("Warning: git diff command timed out\n")
        return None
    except FileNotFoundError:
        sys.stderr.write("Warning: git command not found\n")
        return None
    except Exception as e:
        sys.stderr.write(f"Warning: Failed to get git diff: {e}\n")
        return None
```

### Task 4: CLI Integration

Update `bicep_whatif_advisor/cli.py` to add CI mode flags and smart defaults:

#### Step 4.1: Add CLI Options

```python
@click.command()
@click.option("--provider", "-p", type=click.Choice(["anthropic", "azure-openai", "ollama"]), default="anthropic")
@click.option("--model", "-m", type=str, default=None)
@click.option("--format", "-f", type=click.Choice(["table", "json", "markdown"]), default="table")
@click.option("--verbose", "-v", is_flag=True, help="Include property-level changes")
@click.option("--ci", is_flag=True, help="Enable CI mode with deployment safety review")
@click.option("--diff-ref", type=str, default=None, help="Git reference for diff (default: auto-detect)")
@click.option("--pr-title", type=str, default=None, help="PR title (default: auto-detect)")
@click.option("--pr-description", type=str, default=None, help="PR description (default: auto-detect)")
@click.version_option(version=__version__)
def main(provider, model, format, verbose, ci, diff_ref, pr_title, pr_description):
    """Analyze Azure What-If deployment output using LLMs."""
```

#### Step 4.2: Platform Detection Logic

Add near the beginning of `main()`:

```python
def main(...):
    try:
        # Auto-detect platform (always detect, even in standard mode)
        from .ci.platform import detect_platform
        platform_ctx = detect_platform()

        # Read stdin
        whatif_content = read_stdin()

        # Get provider
        llm_provider = get_provider(provider, model)

        # CI mode processing
        if ci:
            # Use auto-detected values as defaults, allow CLI overrides
            diff_ref = diff_ref or platform_ctx.get_diff_ref()
            pr_title = pr_title or platform_ctx.pr_title
            pr_description = pr_description or platform_ctx.pr_description

            # Get git diff
            from .ci.diff import get_diff
            diff_content = get_diff(diff_ref)

            if diff_content is None:
                sys.stderr.write("Warning: Could not get git diff. CI mode requires git diff.\n")
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

            # TODO: Call LLM, parse response, evaluate risk (Phase 4)
            # For now, just print a message
            print(f"CI mode enabled")
            print(f"Platform: {platform_ctx.platform}")
            print(f"PR Number: {platform_ctx.pr_number}")
            print(f"Diff ref: {diff_ref}")
            print(f"Has PR metadata: {platform_ctx.has_pr_metadata()}")
            sys.exit(0)

        else:
            # Standard mode (from Phase 2)
            system_prompt = build_system_prompt(verbose=verbose)
            user_prompt = build_user_prompt(whatif_content)

            response_text = llm_provider.complete(system_prompt, user_prompt)
            data = extract_json(response_text)

            if format == "table":
                render_table(data, verbose=verbose)
            elif format == "json":
                render_json(data)
            elif format == "markdown":
                markdown = render_markdown(data)
                print(markdown)

            sys.exit(0)

    except InputError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(2)
    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)
```

### Task 5: Testing

#### Step 5.1: Unit Tests

Create `tests/test_platform.py`:

```python
import os
import json
import pytest
from bicep_whatif_advisor.ci.platform import (
    detect_platform,
    PlatformContext,
)


def test_detect_local(monkeypatch):
    """Test local platform detection."""
    # Clear all CI env vars
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("TF_BUILD", raising=False)
    monkeypatch.delenv("AGENT_ID", raising=False)

    ctx = detect_platform()
    assert ctx.platform == "local"
    assert ctx.pr_number is None


def test_detect_github(monkeypatch, tmp_path):
    """Test GitHub Actions detection with event file."""
    # Set GitHub env vars
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
    monkeypatch.setenv("GITHUB_BASE_REF", "main")
    monkeypatch.setenv("GITHUB_HEAD_REF", "feature/test")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")

    # Create mock event file
    event_file = tmp_path / "event.json"
    event_file.write_text(json.dumps({
        "pull_request": {
            "number": 123,
            "title": "Test PR",
            "body": "Test description"
        }
    }))
    monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))

    ctx = detect_platform()
    assert ctx.platform == "github"
    assert ctx.repository == "owner/repo"
    assert ctx.base_branch == "main"
    assert ctx.pr_number == "123"
    assert ctx.pr_title == "Test PR"
    assert ctx.pr_description == "Test description"


def test_detect_azuredevops(monkeypatch):
    """Test Azure DevOps detection."""
    monkeypatch.setenv("TF_BUILD", "True")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_PULLREQUESTID", "12345")
    monkeypatch.setenv("SYSTEM_PULLREQUEST_TARGETBRANCH", "refs/heads/main")
    monkeypatch.setenv("BUILD_REPOSITORY_NAME", "myrepo")

    ctx = detect_platform()
    assert ctx.platform == "azuredevops"
    assert ctx.pr_number == "12345"
    assert ctx.base_branch == "refs/heads/main"
    assert ctx.repository == "myrepo"


def test_get_diff_ref():
    """Test diff reference generation."""
    ctx = PlatformContext(
        platform="github",
        base_branch="main"
    )
    assert ctx.get_diff_ref() == "origin/main"


def test_get_diff_ref_with_refs_heads():
    """Test diff ref with refs/heads/ prefix."""
    ctx = PlatformContext(
        platform="azuredevops",
        base_branch="refs/heads/develop"
    )
    assert ctx.get_diff_ref() == "origin/develop"


def test_has_pr_metadata():
    """Test PR metadata detection."""
    ctx = PlatformContext(
        platform="github",
        pr_number="123",
        pr_title="Test"
    )
    assert ctx.has_pr_metadata() is True

    ctx_no_metadata = PlatformContext(
        platform="github",
        pr_number="123"
    )
    assert ctx_no_metadata.has_pr_metadata() is False
```

Create `tests/test_diff.py`:

```python
import pytest
from unittest.mock import Mock
from bicep_whatif_advisor.ci.diff import get_diff


def test_get_diff_success(mocker):
    """Test successful git diff."""
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = "diff content here"

    mocker.patch('subprocess.run', return_value=mock_result)

    diff = get_diff("origin/main")
    assert diff == "diff content here"


def test_get_diff_failure(mocker):
    """Test git diff command failure."""
    mock_result = Mock()
    mock_result.returncode = 1
    mock_result.stderr = "error"

    mocker.patch('subprocess.run', return_value=mock_result)

    diff = get_diff("origin/main")
    assert diff is None


def test_get_diff_truncation(mocker):
    """Test diff truncation for large output."""
    large_diff = "x" * 60000
    mock_result = Mock()
    mock_result.returncode = 0
    mock_result.stdout = large_diff

    mocker.patch('subprocess.run', return_value=mock_result)

    diff = get_diff("origin/main", max_size=50000)
    assert len(diff) == 50000
```

#### Step 5.2: Manual Testing

```bash
# Test platform detection
python -c "from bicep_whatif_advisor.ci.platform import detect_platform; print(detect_platform())"

# Test in GitHub Actions simulation
export GITHUB_ACTIONS=true
export GITHUB_REPOSITORY=owner/repo
export GITHUB_BASE_REF=main
python -c "from bicep_whatif_advisor.ci.platform import detect_platform; print(detect_platform())"

# Test git diff collection
python -c "from bicep_whatif_advisor.ci.diff import get_diff; print(get_diff('HEAD~1'))"

# Test CI mode flag (incomplete, just checks detection)
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --ci
```

#### Step 5.3: Integration Test

Test auto-detection workflow:

```bash
# Simulate GitHub Actions environment
export GITHUB_ACTIONS=true
export GITHUB_REPOSITORY=myorg/myrepo
export GITHUB_BASE_REF=main
export GITHUB_HEAD_REF=feature/test

# Run in CI mode (should auto-detect platform and branches)
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --ci
```

## Validation Checklist

- [ ] `ci/` directory created
- [ ] `ci/__init__.py` created
- [ ] `ci/platform.py` created with PlatformContext dataclass
- [ ] PlatformType type alias defined
- [ ] `has_pr_metadata()` method works correctly
- [ ] `get_diff_ref()` strips refs/heads/ prefix
- [ ] `detect_platform()` detects GitHub Actions
- [ ] `detect_platform()` detects Azure DevOps
- [ ] `detect_platform()` defaults to local
- [ ] GitHub detection reads event file correctly
- [ ] GitHub detection handles missing event file gracefully
- [ ] Azure DevOps detection extracts env vars
- [ ] `ci/diff.py` created with get_diff()
- [ ] Git diff collection works
- [ ] Git diff truncation works for large diffs
- [ ] Git command errors handled gracefully
- [ ] CLI `--ci` flag added
- [ ] CLI `--diff-ref` flag added
- [ ] CLI `--pr-title` flag added
- [ ] CLI `--pr-description` flag added
- [ ] Auto-detection used as defaults
- [ ] CLI flags override auto-detection
- [ ] Platform context displayed in CI mode
- [ ] Tests pass for platform detection
- [ ] Tests pass for git diff collection

## Next Phase

Once Phase 3 is complete and validated, proceed to Phase 4 (Risk Assessment System).

Phase 4 will add:
- Three-bucket risk evaluation
- Independent threshold comparison
- Deployment safety verdict
- Exit code handling

## Notes

- Platform detection should never fail - always return a valid PlatformContext
- All file I/O errors should be non-fatal warnings
- Git command errors should be non-fatal in standard mode, fatal in CI mode
- Event file parsing errors should print warnings but continue
- Type hints are critical for PlatformType to ensure valid values
- UTF-8 encoding is important for reading event files
