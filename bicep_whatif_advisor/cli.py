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
from .render import render_table, render_json, render_markdown, print_banner
from .ci.platform import detect_platform
from .noise_filter import apply_noise_filtering


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


def filter_by_confidence(data: dict) -> tuple[dict, dict]:
    """Filter resources by confidence level.

    Splits resources into high-confidence (medium/high) and low-confidence (low) lists.
    Low-confidence resources are likely Azure What-If noise and should be excluded
    from risk analysis but displayed separately.

    Args:
        data: Parsed LLM response with resources and other fields

    Returns:
        Tuple of (high_confidence_data, low_confidence_data) dicts with same structure
    """
    resources = data.get("resources", [])

    high_confidence_resources = []
    low_confidence_resources = []

    for resource in resources:
        confidence = resource.get("confidence_level", "medium").lower()

        if confidence in ("low", "noise"):
            # Low confidence and noise-matched resources excluded from analysis
            low_confidence_resources.append(resource)
        else:
            # medium and high confidence included in analysis
            high_confidence_resources.append(resource)

    # Build high-confidence data dict (includes CI fields if present)
    high_confidence_data = {
        "resources": high_confidence_resources,
        "overall_summary": data.get("overall_summary", "")
    }

    # Preserve CI mode fields in high-confidence data
    if "risk_assessment" in data:
        high_confidence_data["risk_assessment"] = data["risk_assessment"]
    if "verdict" in data:
        high_confidence_data["verdict"] = data["verdict"]

    # Build low-confidence data dict (no CI fields - these are excluded from risk analysis)
    low_confidence_data = {
        "resources": low_confidence_resources,
        "overall_summary": ""  # No separate summary for noise
    }

    return high_confidence_data, low_confidence_data


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
    help="Fail pipeline if drift risk meets or exceeds this level (only applies if drift bucket enabled)"
)
@click.option(
    "--intent-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if intent alignment risk meets or exceeds this level (only applies if intent bucket enabled)"
)
@click.option(
    "--operations-threshold",
    type=click.Choice(["low", "medium", "high"], case_sensitive=False),
    default="high",
    help="Fail pipeline if operations risk meets or exceeds this level (only applies if operations bucket enabled)"
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
@click.option(
    "--no-block",
    is_flag=True,
    help="Don't fail pipeline even if deployment is unsafe - only report findings (CI mode only)"
)
@click.option(
    "--skip-drift",
    is_flag=True,
    help="Skip infrastructure drift risk assessment (CI mode only)"
)
@click.option(
    "--skip-intent",
    is_flag=True,
    help="Skip PR intent alignment risk assessment (CI mode only)"
)
@click.option(
    "--skip-operations",
    is_flag=True,
    help="Skip risky operations risk assessment (CI mode only)"
)
@click.option(
    "--comment-title",
    type=str,
    default=None,
    help="Custom title for PR comment (default: 'What-If Deployment Review')"
)
@click.option(
    "--noise-file",
    type=str,
    default=None,
    help="Path to noise patterns file for summary-based filtering"
)
@click.option(
    "--noise-threshold",
    type=int,
    default=80,
    help="Similarity threshold percentage for noise pattern matching (default: 80)"
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
    pr_description: str,
    no_block: bool,
    skip_drift: bool,
    skip_intent: bool,
    skip_operations: bool,
    comment_title: str,
    noise_file: str,
    noise_threshold: int
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

        # Print banner in CI/CD mode only
        if ci:
            print_banner()

        # Get diff content if CI mode
        diff_content = None
        bicep_content = None

        if ci:
            from .ci.diff import get_diff
            diff_content = get_diff(diff, diff_ref)

            # Optionally load Bicep source files
            if bicep_dir:
                bicep_content = _load_bicep_files(bicep_dir)

        # Determine which risk buckets are enabled (CI mode only)
        # Do this before getting provider to validate flags early
        enabled_buckets = None
        if ci:
            from .ci.buckets import get_enabled_buckets
            enabled_buckets = get_enabled_buckets(
                skip_drift=skip_drift,
                skip_intent=skip_intent,
                skip_operations=skip_operations,
                has_pr_metadata=bool(pr_title or pr_description)
            )

            # Validation: At least one bucket must be enabled in CI mode
            if not enabled_buckets:
                sys.stderr.write("❌ Error: At least one risk assessment bucket must be enabled in CI mode\n")
                sys.stderr.write("   Remove one or more --skip-* flags to enable risk assessment.\n")
                sys.exit(2)

        # Get provider
        llm_provider = get_provider(provider, model)

        # Build prompts
        system_prompt = build_system_prompt(
            verbose=verbose,
            ci_mode=ci,
            pr_title=pr_title,
            pr_description=pr_description,
            enabled_buckets=enabled_buckets
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

        # Add backward compatibility defaults for confidence fields
        for resource in data.get("resources", []):
            if "confidence_level" not in resource:
                resource["confidence_level"] = "medium"  # Default to include in analysis
            if "confidence_reason" not in resource:
                resource["confidence_reason"] = "No confidence assessment provided"

        # Apply summary-based noise filtering (if noise file provided)
        if noise_file:
            try:
                # Convert threshold from percentage to ratio (0-1)
                threshold_ratio = noise_threshold / 100.0
                data = apply_noise_filtering(data, noise_file, threshold_ratio)
            except FileNotFoundError as e:
                sys.stderr.write(f"Error: {e}\n")
                sys.exit(2)
            except IOError as e:
                sys.stderr.write(f"Error reading noise file: {e}\n")
                sys.exit(2)

        # TODO: Add --show-all-confidence flag to display medium/high/low separately
        # TODO: Consider adding --confidence-threshold to make filtering configurable
        # TODO: If LLM-only confidence scoring proves unreliable, evaluate hybrid
        #       approach combining LLM + hardcoded noise patterns

        # Filter by confidence (always-on behavior)
        high_confidence_data, low_confidence_data = filter_by_confidence(data)

        # CRITICAL FIX: If noise filtering removed resources in CI mode, the LLM's
        # risk_assessment is stale (generated before filtering). Re-prompt the LLM
        # with only high-confidence resources to get an accurate risk assessment.
        if ci and low_confidence_data.get("resources"):
            num_filtered = len(low_confidence_data["resources"])
            num_remaining = len(high_confidence_data.get("resources", []))

            sys.stderr.write(
                f"🔄 Recalculating risk assessment: {num_filtered} low-confidence resources "
                f"filtered, {num_remaining} high-confidence resources remain\n"
            )

            # Special case: If ALL resources were filtered as noise, skip LLM recalculation
            # and set all risk buckets to low with no concerns
            if num_remaining == 0:
                sys.stderr.write("✅ All resources filtered as noise - setting all risk buckets to low\n")

                # Build a clean risk assessment with no concerns for enabled buckets only
                from .ci.buckets import RISK_BUCKETS
                high_confidence_data["risk_assessment"] = {}

                for bucket_id in enabled_buckets:
                    bucket = RISK_BUCKETS[bucket_id]
                    high_confidence_data["risk_assessment"][bucket_id] = {
                        "risk_level": "low",
                        "concerns": [],
                        "reasoning": f"All detected changes were flagged as low-confidence noise. No high-confidence {bucket.display_name.lower()} concerns to evaluate."
                    }

                # Update verdict
                high_confidence_data["verdict"] = {
                    "safe": True,
                    "highest_risk_bucket": "none",
                    "overall_risk_level": "low",
                    "reasoning": "All detected changes were identified as Azure What-If noise and excluded from risk analysis. No meaningful infrastructure changes detected."
                }
            else:

                # Build a filtered What-If output containing only high-confidence resources
                # We'll reconstruct a minimal What-If output from the high-confidence resources
                # and re-prompt the LLM for accurate risk assessment
                filtered_whatif_lines = ["Resource changes:"]
                for resource in high_confidence_data.get("resources", []):
                    # Reconstruct What-If format: "~ ResourceName"
                    action_symbol = {
                        "create": "+",
                        "modify": "~",
                        "delete": "-",
                        "deploy": "=",
                        "nochange": "*",
                        "ignore": "x"
                    }.get(resource.get("action", "").lower(), "~")

                    filtered_whatif_lines.append(f"{action_symbol} {resource['resource_name']}")
                    filtered_whatif_lines.append(f"  Summary: {resource['summary']}")

                filtered_whatif_content = "\n".join(filtered_whatif_lines)

                # Re-build prompts with filtered data
                filtered_system_prompt = build_system_prompt(
                    verbose=verbose,
                    ci_mode=ci,
                    pr_title=pr_title,
                    pr_description=pr_description,
                    enabled_buckets=enabled_buckets
                )
                filtered_user_prompt = build_user_prompt(
                    whatif_content=filtered_whatif_content,
                    diff_content=diff_content,
                    bicep_content=bicep_content,
                    pr_title=pr_title,
                    pr_description=pr_description
                )

                # Re-call LLM with filtered resources
                sys.stderr.write("📡 Re-analyzing with filtered resources for accurate risk assessment...\n")
                filtered_response_text = llm_provider.complete(filtered_system_prompt, filtered_user_prompt)

                # Parse the new response
                try:
                    filtered_data = extract_json(filtered_response_text)

                    # Extract the fresh risk_assessment and verdict
                    if "risk_assessment" in filtered_data:
                        high_confidence_data["risk_assessment"] = filtered_data["risk_assessment"]
                    if "verdict" in filtered_data:
                        high_confidence_data["verdict"] = filtered_data["verdict"]

                    sys.stderr.write("✅ Risk assessment recalculated based on high-confidence resources only\n")

                except ValueError:
                    sys.stderr.write(
                        "⚠️  Warning: Could not parse re-analysis response. "
                        "Using original risk assessment (may be inaccurate).\n"
                    )

        # Store enabled buckets in data for rendering (CI mode only)
        if ci and enabled_buckets:
            high_confidence_data["_enabled_buckets"] = enabled_buckets

        # Render output
        if format == "table":
            render_table(high_confidence_data, verbose=verbose, no_color=no_color, ci_mode=ci, low_confidence_data=low_confidence_data)
        elif format == "json":
            render_json(high_confidence_data, low_confidence_data=low_confidence_data)
        elif format == "markdown":
            markdown = render_markdown(high_confidence_data, ci_mode=ci, custom_title=comment_title, no_block=no_block, low_confidence_data=low_confidence_data)
            print(markdown)

        # CI mode: evaluate verdict and post comment
        if ci:
            from .ci.risk_buckets import evaluate_risk_buckets

            is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
                high_confidence_data,
                enabled_buckets,
                drift_threshold,
                intent_threshold,
                operations_threshold
            )

            # Post comment if requested
            if post_comment:
                markdown = render_markdown(high_confidence_data, ci_mode=True, custom_title=comment_title, no_block=no_block, low_confidence_data=low_confidence_data)
                _post_pr_comment(markdown, pr_url)

            # Exit with appropriate code
            if is_safe:
                sys.exit(0)  # Safe to deploy
            else:
                # Show which buckets failed
                if failed_buckets:
                    bucket_names = ", ".join(failed_buckets)
                    if no_block:
                        sys.stderr.write(f"⚠️  Warning: Failed risk buckets: {bucket_names} (pipeline not blocked due to --no-block)\n")
                    else:
                        sys.stderr.write(f"❌ Deployment blocked: Failed risk buckets: {bucket_names}\n")

                # Exit with 0 if --no-block is set, otherwise exit with 1
                if no_block:
                    sys.stderr.write("ℹ️  CI mode: Reporting findings only (--no-block enabled)\n")
                    sys.exit(0)  # Don't block pipeline
                else:
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
