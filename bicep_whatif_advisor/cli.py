"""CLI entry point for bicep-whatif-advisor."""

import os
import sys
import json
from typing import Optional
import click
from . import __version__
from .input import read_stdin, InputError
from .prompt import build_system_prompt, build_user_prompt
from .providers import get_provider
from .render import render_table, render_json, render_markdown
from .ci.platform import detect_platform


def extract_json(text: str) -> dict:
    """Attempt to extract JSON from LLM response.

    Args:
        text: Raw LLM response text

    Returns:
        Parsed JSON dict

    Raises:
        ValueError: If no valid JSON found
    """
    # Try parsing as-is first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON in the text by looking for balanced braces
    # This handles deeply nested JSON properly
    start = text.find('{')
    if start == -1:
        raise ValueError("Could not extract valid JSON from LLM response")

    # Find the matching closing brace
    brace_count = 0
    in_string = False
    escape_next = False

    for i in range(start, len(text)):
        char = text[i]

        if escape_next:
            escape_next = False
            continue

        if char == '\\':
            escape_next = True
            continue

        if char == '"' and not escape_next:
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == '{':
            brace_count += 1
        elif char == '}':
            brace_count -= 1
            if brace_count == 0:
                # Found the matching closing brace
                json_str = text[start:i+1]
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
                break

    # Failed to extract JSON
    raise ValueError("Could not extract valid JSON from LLM response")


@click.command()
@click.option(
    "--provider", "-p",
    type=click.Choice(["anthropic", "azure-openai", "ollama"], case_sensitive=False),
    default="anthropic",
    help="LLM provider to use"
)
@click.option(
    "--model", "-m",
    type=str,
    default=None,
    help="Override the default model for the provider"
)
@click.option(
    "--format", "-f",
    type=click.Choice(["table", "json", "markdown"], case_sensitive=False),
    default="table",
    help="Output format"
)
@click.option(
    "--verbose", "-v",
    is_flag=True,
    help="Include property-level change details for modified resources"
)
@click.option(
    "--no-color",
    is_flag=True,
    help="Disable colored output"
)
@click.option(
    "--ci",
    is_flag=True,
    help="Enable CI mode with risk assessment and deployment gate"
)
@click.option(
    "--diff", "-d",
    type=str,
    default=None,
    help="Path to git diff file (CI mode only)"
)
@click.option(
    "--diff-ref",
    type=str,
    default="HEAD~1",
    help="Git reference to diff against (default: HEAD~1)"
)
@click.option(
    "--drift-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if drift risk meets or exceeds this level (CI mode only)"
)
@click.option(
    "--intent-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if intent alignment risk meets or exceeds this level (CI mode only)"
)
@click.option(
    "--operations-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if operations risk meets or exceeds this level (CI mode only)"
)
@click.option(
    "--post-comment",
    is_flag=True,
    help="Post summary as PR comment (CI mode only)"
)
@click.option(
    "--pr-url",
    type=str,
    default=None,
    help="PR URL for posting comments (auto-detected if not provided)"
)
@click.option(
    "--bicep-dir",
    type=str,
    default=".",
    help="Path to Bicep source files for context (CI mode only)"
)
@click.option(
    "--pr-title",
    type=str,
    default=None,
    help="Pull request title for intent analysis (CI mode only)"
)
@click.option(
    "--pr-description",
    type=str,
    default=None,
    help="Pull request description for intent analysis (CI mode only)"
)
@click.version_option(version=__version__)
def main(
    provider: str,
    model: str,
    format: str,
    verbose: bool,
    no_color: bool,
    ci: bool,
    diff: str,
    diff_ref: str,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str,
    post_comment: bool,
    pr_url: str,
    bicep_dir: str,
    pr_title: str,
    pr_description: str
):
    """Analyze Azure What-If deployment output using LLMs.

    Pipe Azure What-If output to this command:

        az deployment group what-if ... | bicep-whatif-advisor

    Example:

        az deployment group what-if \\
          --resource-group my-rg \\
          --template-file main.bicep \\
          --parameters params.json | bicep-whatif-advisor
    """
    try:
        # Read stdin
        whatif_content = read_stdin()

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

        # Get diff content if CI mode
        diff_content = None
        bicep_content = None

        if ci:
            from .ci.diff import get_diff
            diff_content = get_diff(diff, diff_ref)

            # Optionally load Bicep source files
            if bicep_dir:
                bicep_content = _load_bicep_files(bicep_dir)

        # Get provider
        llm_provider = get_provider(provider, model)

        # Build prompts
        system_prompt = build_system_prompt(
            verbose=verbose,
            ci_mode=ci,
            pr_title=pr_title,
            pr_description=pr_description
        )
        user_prompt = build_user_prompt(
            whatif_content=whatif_content,
            diff_content=diff_content,
            bicep_content=bicep_content,
            pr_title=pr_title,
            pr_description=pr_description
        )

        # Call LLM
        response_text = llm_provider.complete(system_prompt, user_prompt)

        # Parse JSON response
        try:
            data = extract_json(response_text)
        except ValueError:
            # Truncate response to prevent exposing sensitive data
            truncated = response_text[:500] + "..." if len(response_text) > 500 else response_text
            sys.stderr.write(
                "Error: LLM did not return valid JSON.\n"
                f"Raw response (first 500 chars):\n{truncated}\n"
            )
            sys.exit(1)

        # Validate required fields
        if "resources" not in data:
            sys.stderr.write("Warning: LLM response missing 'resources' field. Using empty list.\n")
            data["resources"] = []

        if "overall_summary" not in data:
            sys.stderr.write("Warning: LLM response missing 'overall_summary' field.\n")
            data["overall_summary"] = "No summary provided."

        # Render output
        if format == "table":
            render_table(data, verbose=verbose, no_color=no_color, ci_mode=ci)
        elif format == "json":
            render_json(data)
        elif format == "markdown":
            markdown = render_markdown(data, ci_mode=ci)
            print(markdown)

        # CI mode: evaluate verdict and post comment
        if ci:
            from .ci.risk_buckets import evaluate_risk_buckets

            is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
                data, drift_threshold, intent_threshold, operations_threshold
            )

            # Post comment if requested
            if post_comment:
                markdown = render_markdown(data, ci_mode=True)
                _post_pr_comment(markdown, pr_url)

            # Exit with appropriate code
            if is_safe:
                sys.exit(0)  # Safe to deploy
            else:
                # Show which buckets failed
                if failed_buckets:
                    bucket_names = ", ".join(failed_buckets)
                    sys.stderr.write(f"Deployment blocked: Failed risk buckets: {bucket_names}\n")
                sys.exit(1)  # Unsafe, block deployment

        # Standard mode: exit successfully
        sys.exit(0)

    except InputError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(2)

    except KeyboardInterrupt:
        sys.stderr.write("\nInterrupted by user.\n")
        sys.exit(130)

    except Exception as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)


def _load_bicep_files(bicep_dir: str) -> Optional[str]:
    """Load all Bicep files from directory for context.

    Args:
        bicep_dir: Directory containing Bicep files

    Returns:
        Combined content of all .bicep files, or None if no files found
    """
    from pathlib import Path

    # Resolve to absolute path and validate
    try:
        base_path = Path(bicep_dir).resolve()
    except (OSError, RuntimeError) as e:
        sys.stderr.write(f"Warning: Could not resolve bicep directory: {e}\n")
        return None

    if not base_path.exists() or not base_path.is_dir():
        sys.stderr.write(
            f"Warning: Bicep directory does not exist or is not "
            f"a directory: {bicep_dir}\n"
        )
        return None

    # Find all .bicep files recursively
    bicep_files = []
    try:
        for file_path in base_path.rglob("*.bicep"):
            # Security: Ensure file is within base_path (prevent path traversal)
            try:
                file_path.resolve().relative_to(base_path)
            except ValueError:
                sys.stderr.write(f"Warning: Skipping file outside base directory: {file_path}\n")
                continue

            # Security: Skip symbolic links
            if file_path.is_symlink():
                sys.stderr.write(f"Warning: Skipping symbolic link: {file_path}\n")
                continue

            bicep_files.append(file_path)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"Warning: Error scanning bicep directory: {e}\n")
        return None

    if not bicep_files:
        return None

    # Read file contents (limit to 5 files to avoid huge context)
    contents = []
    for file_path in bicep_files[:5]:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                rel_path = file_path.relative_to(base_path)
                contents.append(f"// File: {rel_path}\n{f.read()}")
        except (OSError, UnicodeDecodeError) as e:
            sys.stderr.write(f"Warning: Could not read {file_path}: {e}\n")
            continue

    return "\n\n".join(contents) if contents else None


def _post_pr_comment(markdown: str, pr_url: str = None) -> None:
    """Post markdown comment to PR.

    Args:
        markdown: Markdown content to post
        pr_url: Optional PR URL override
    """
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


if __name__ == "__main__":
    main()
