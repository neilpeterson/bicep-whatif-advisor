"""Output rendering for bicep-whatif-advisor in various formats."""

import json
import shutil
import sys

from rich import box
from rich.console import Console
from rich.table import Table


def print_banner() -> None:
    """Print ASCII banner to identify tool output in CI/CD logs."""
    banner = """
┌─────────────────────────────────────────────────────────┐
│  🛡️  BICEP WHAT-IF ADVISOR                              │
│     AI-Powered Deployment Safety Review                 │
└─────────────────────────────────────────────────────────┘
"""
    print(banner, file=sys.stderr)


# Action symbols and colors
ACTION_STYLES = {
    "Create": ("✅", "green"),
    "Modify": ("✏️", "yellow"),
    "Delete": ("❌", "red"),
    "Deploy": ("🔄", "blue"),
    "NoChange": ("➖", "dim"),
    "Ignore": ("⬜", "dim"),
}

# Risk level symbols and colors for CI mode
RISK_STYLES = {
    "high": ("🔴", "red"),
    "medium": ("🟡", "yellow"),
    "low": ("🟢", "green"),
}


def _colorize(text: str, color: str, use_color: bool) -> str:
    """Apply color formatting if use_color is True.

    Args:
        text: Text to colorize
        color: Color name (e.g., "red", "green", "yellow")
        use_color: Whether to apply color formatting

    Returns:
        Formatted text with color markup if use_color, otherwise plain text
    """
    return f"[{color}]{text}[/{color}]" if use_color else text


def render_table(
    data: dict,
    verbose: bool = False,
    no_color: bool = False,
    ci_mode: bool = False,
    low_confidence_data: dict = None,
) -> None:
    """Render output as a colored table using Rich.

    Args:
        data: Parsed LLM response with resources and overall_summary
        verbose: Show property-level changes for modified resources
        no_color: Disable colored output
        ci_mode: Include risk assessment columns
        low_confidence_data: Optional dict with low-confidence resources (potential noise)
    """
    # Determine if we should use colors
    use_color = not no_color and sys.stdout.isatty()

    # Calculate 85% of terminal width (15% reduction)
    terminal_width = shutil.get_terminal_size().columns
    reduced_width = int(terminal_width * 0.85)

    console = Console(force_terminal=use_color, no_color=not use_color, width=reduced_width)

    # Print risk bucket summary in CI mode
    if ci_mode:
        enabled_buckets = data.get("_enabled_buckets")
        _print_risk_bucket_summary(
            console, data.get("risk_assessment", {}), use_color, enabled_buckets
        )

    # Print overall summary after risk assessment table
    overall_summary = data.get("overall_summary", "")
    if overall_summary:
        summary_label = _colorize("Summary:", "bold", use_color)
        console.print(f"{summary_label} {overall_summary}")
        console.print()

    # Create table
    table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))

    # Add columns
    table.add_column("#", style="dim", width=4)
    table.add_column("Resource", style="bold")
    table.add_column("Type")
    table.add_column("Action", justify="center")

    if ci_mode:
        table.add_column("Risk", justify="center")

    table.add_column("Summary")

    # Add rows
    resources = data.get("resources", [])
    for idx, resource in enumerate(resources, 1):
        resource_name = resource.get("resource_name", "Unknown")
        resource_type = resource.get("resource_type", "Unknown")
        action = resource.get("action", "Unknown")
        summary = resource.get("summary", "No summary provided")

        # Get action color
        _, color = ACTION_STYLES.get(action, ("?", "white"))
        action_display = action

        row = [
            str(idx),
            resource_name,
            resource_type,
            _colorize(action_display, color, use_color),
        ]

        if ci_mode:
            risk_level = resource.get("risk_level", "none")
            _, risk_color = RISK_STYLES.get(risk_level, ("?", "white"))
            risk_display = risk_level.capitalize()
            row.append(_colorize(risk_display, risk_color, use_color))

        row.append(summary)
        table.add_row(*row)

    # Print table with high confidence label and count
    resource_count = len(resources)
    high_conf_label = _colorize(
        f"High Confidence Resources ({resource_count})", "bold cyan", use_color
    )
    console.print(high_conf_label)
    console.print(table)
    console.print()

    # Print verbose details if requested
    if verbose and not ci_mode:
        _print_verbose_details(console, resources, use_color)

    # Print CI verdict if in CI mode
    if ci_mode:
        _print_ci_verdict(console, data.get("verdict", {}), use_color)

    # Print low-confidence resources as "Potential Noise" section
    if low_confidence_data and low_confidence_data.get("resources"):
        _print_noise_section(console, low_confidence_data, use_color, ci_mode)


def _print_noise_section(
    console: Console, low_confidence_data: dict, use_color: bool, ci_mode: bool
) -> None:
    """Print low-confidence resources as potential Azure What-If noise."""
    resources = low_confidence_data.get("resources", [])
    if not resources:
        return

    # Add spacing before noise section
    console.print()

    # Print header with count
    resource_count = len(resources)
    header = _colorize(
        f"⚠️  Potential Azure What-If Noise ({resource_count} Low Confidence)",
        "yellow bold",
        use_color,
    )
    console.print(header)
    console.print(
        _colorize(
            "The following changes were flagged as likely What-If noise"
            " and excluded from risk analysis:",
            "dim",
            use_color,
        )
    )
    console.print()

    # Create noise table
    noise_table = Table(box=box.ROUNDED, show_lines=False, padding=(0, 1))
    noise_table.add_column("#", style="dim", width=4)
    noise_table.add_column("Resource", style="bold")
    noise_table.add_column("Type")
    noise_table.add_column("Action", justify="center")
    noise_table.add_column("Confidence Reason")

    # Add rows
    for idx, resource in enumerate(resources, 1):
        resource_name = resource.get("resource_name", "Unknown")
        resource_type = resource.get("resource_type", "Unknown")
        action = resource.get("action", "Unknown")
        confidence_reason = resource.get("confidence_reason", "No reason provided")

        # Get action color
        _, color = ACTION_STYLES.get(action, ("?", "white"))
        action_display = action

        noise_table.add_row(
            str(idx),
            resource_name,
            resource_type,
            _colorize(action_display, color, use_color),
            confidence_reason,
        )

    # Print table
    console.print(noise_table)
    console.print()


def _print_risk_bucket_summary(
    console: Console, risk_assessment: dict, use_color: bool, enabled_buckets: list = None
) -> None:
    """Print risk bucket summary table in CI mode.

    Args:
        console: Rich console for output
        risk_assessment: Risk assessment dict from LLM
        use_color: Whether to use color output
        enabled_buckets: List of bucket IDs that were evaluated (e.g., ["drift", "operations"])
                        If None, defaults to all buckets present in risk_assessment
    """
    if not risk_assessment:
        return

    from .ci.buckets import RISK_BUCKETS

    # If enabled_buckets not provided, use all buckets present in risk_assessment
    if enabled_buckets is None:
        enabled_buckets = list(risk_assessment.keys())

    # Create risk bucket table
    bucket_table = Table(box=box.ROUNDED, show_header=True, padding=(0, 1))
    bucket_table.add_column("Risk Assessment", style="bold")
    bucket_table.add_column("Risk Level", justify="center")
    bucket_table.add_column("Status", justify="center")
    bucket_table.add_column("Key Concerns")

    # Render only enabled buckets
    for bucket_id in enabled_buckets:
        bucket = RISK_BUCKETS[bucket_id]
        bucket_data = risk_assessment.get(bucket_id, {})

        if bucket_data:
            risk_level = bucket_data.get("risk_level", "low")
            _, risk_color = RISK_STYLES.get(risk_level, ("?", "white"))
            concerns = bucket_data.get("concerns", [])
            concern_text = concerns[0] if concerns else "None"

            bucket_table.add_row(
                bucket.display_name,
                _colorize(risk_level.capitalize(), risk_color, use_color),
                _colorize("●", risk_color, use_color),
                concern_text,
            )

    # Print the bucket table
    console.print(bucket_table)
    console.print()


def _print_verbose_details(console: Console, resources: list, use_color: bool) -> None:
    """Print verbose property-level change details."""
    modified_resources = [r for r in resources if r.get("action") == "Modify" and r.get("changes")]

    if modified_resources:
        label = _colorize("Property-Level Changes:", "bold", use_color)
        console.print(label)
        console.print()

        for resource in modified_resources:
            resource_name = resource.get("resource_name", "Unknown")
            bullet = _colorize("•", "yellow", use_color)
            console.print(f"  {bullet} {resource_name}:")

            for change in resource.get("changes", []):
                console.print(f"    - {change}")

            console.print()


def _print_ci_verdict(console: Console, verdict: dict, use_color: bool) -> None:
    """Print CI mode verdict."""
    if not verdict:
        return

    safe = verdict.get("safe", True)
    reasoning = verdict.get("reasoning", "")

    # Verdict header
    if safe:
        verdict_text = "✅ SAFE"
        verdict_style = "green bold"
    else:
        verdict_text = "❌ UNSAFE"
        verdict_style = "red bold"

    verdict_display = _colorize(f"Verdict: {verdict_text}", verdict_style, use_color)
    console.print(verdict_display)

    # Reasoning
    if reasoning:
        label = _colorize("Reasoning:", "bold", use_color)
        console.print(f"{label} {reasoning}")

    console.print()


def render_json(data: dict, low_confidence_data: dict = None) -> None:
    """Render output as pretty-printed JSON.

    Args:
        data: Parsed LLM response (high-confidence resources)
        low_confidence_data: Optional dict with low-confidence resources
    """
    output = {
        "high_confidence": data,
    }

    if low_confidence_data:
        output["low_confidence"] = low_confidence_data

    print(json.dumps(output, indent=2))


def render_markdown(
    data: dict,
    ci_mode: bool = False,
    custom_title: str = None,
    no_block: bool = False,
    low_confidence_data: dict = None,
    platform: str = None,
    whatif_content: str = None,
) -> str:
    """Render output as markdown table suitable for PR comments.

    Args:
        data: Parsed LLM response
        ci_mode: Include risk assessment and verdict
        custom_title: Custom title for the comment (default: "What-If Deployment Review")
        no_block: Append "(non-blocking)" to title if True
        low_confidence_data: Optional dict with low-confidence resources (potential noise)
        platform: CI/CD platform ("github", "azuredevops", or None for default)

    Returns:
        Markdown-formatted string
    """
    lines = []

    if ci_mode:
        title = custom_title if custom_title else "What-If Deployment Review"
        if no_block:
            title = f"{title} (non-blocking)"
        lines.append(f"## {title}")
        lines.append("")

        # Add risk bucket summary (without heading label)
        risk_assessment = data.get("risk_assessment", {})
        if risk_assessment:
            from .ci.buckets import RISK_BUCKETS

            # Get enabled buckets (default to all if not specified)
            enabled_buckets = data.get("_enabled_buckets")
            if enabled_buckets is None:
                enabled_buckets = list(risk_assessment.keys())

            lines.append("| Risk Assessment | Risk Level | Key Concerns |")
            lines.append("|-----------------|------------|--------------|")

            # Render enabled buckets dynamically
            for bucket_id in enabled_buckets:
                bucket = RISK_BUCKETS[bucket_id]
                bucket_data = risk_assessment.get(bucket_id, {})

                if bucket_data:
                    risk_level = bucket_data.get("risk_level", "low").capitalize()
                    concerns = bucket_data.get("concerns", [])
                    concern_text = concerns[0] if concerns else "None"
                    lines.append(f"| {bucket.display_name} | {risk_level} | {concern_text} |")

            lines.append("")

    # Overall summary (after risk assessment table)
    overall_summary = data.get("overall_summary", "")
    if overall_summary:
        lines.append(f"**Summary:** {overall_summary}")
        lines.append("")

    # Collapsible section for resource changes with high confidence label and count
    resource_count = len(data.get("resources", []))
    lines.append("<details>")
    lines.append(f"<summary>📋 View changed resources ({resource_count} High Confidence)</summary>")
    lines.append("")

    # Table header (with Summary column)
    if ci_mode:
        lines.append("| # | Resource | Type | Action | Risk | Summary |")
        lines.append("|---|----------|------|--------|------|---------|")
    else:
        lines.append("| # | Resource | Type | Action | Summary |")
        lines.append("|---|----------|------|--------|---------|")

    # Table rows (with summaries)
    resources = data.get("resources", [])
    for idx, resource in enumerate(resources, 1):
        resource_name = resource.get("resource_name", "Unknown")
        resource_type = resource.get("resource_type", "Unknown")
        action = resource.get("action", "Unknown")
        summary = resource.get("summary", "").replace("|", "\\|")  # Escape pipes

        # Get action display
        action_display = action

        if ci_mode:
            risk_level = resource.get("risk_level", "none")
            risk_display = risk_level.capitalize()
            lines.append(
                f"| {idx} | {resource_name} | {resource_type}"
                f" | {action_display} | {risk_display} | {summary} |"
            )
        else:
            lines.append(
                f"| {idx} | {resource_name} | {resource_type} | {action_display} | {summary} |"
            )

    lines.append("")
    lines.append("</details>")
    lines.append("")
    # Azure DevOps needs an explicit <br> for spacing between collapsible sections;
    # GitHub already adds sufficient spacing from the blank line alone.
    if platform != "github":
        lines.append("<br>")
        lines.append("")

    # Add collapsible noise section for low-confidence resources
    if low_confidence_data and low_confidence_data.get("resources"):
        low_conf_count = len(low_confidence_data.get("resources", []))
        lines.append("<details>")
        lines.append(
            f"<summary>⚠️ Potential Azure What-If Noise ({low_conf_count} Low Confidence)</summary>"
        )
        lines.append("")
        lines.append(
            "The following changes were flagged as likely What-If noise"
            " and **excluded from risk analysis**:"
        )
        lines.append("")
        lines.append("| # | Resource | Type | Action | Confidence Reason |")
        lines.append("|---|----------|------|--------|-------------------|")

        for idx, resource in enumerate(low_confidence_data.get("resources", []), 1):
            resource_name = resource.get("resource_name", "Unknown")
            resource_type = resource.get("resource_type", "Unknown")
            action = resource.get("action", "Unknown")
            confidence_reason = resource.get("confidence_reason", "No reason provided").replace(
                "|", "\\|"
            )

            lines.append(
                f"| {idx} | {resource_name} | {resource_type} | {action} | {confidence_reason} |"
            )

        lines.append("")
        lines.append("</details>")
        lines.append("")

    # Raw What-If output (opt-in collapsible section)
    if whatif_content:
        lines.append("<details>")
        lines.append("<summary>\U0001f4c4 Raw What-If Output</summary>")
        lines.append("")
        lines.append("```")
        lines.append(whatif_content)
        lines.append("```")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    # CI verdict
    if ci_mode:
        verdict = data.get("verdict", {})
        if verdict:
            safe = verdict.get("safe", True)
            reasoning = verdict.get("reasoning", "")

            # Verdict header
            verdict_text = "✅ SAFE" if safe else "❌ UNSAFE"
            lines.append(f"### Verdict: {verdict_text}")
            if reasoning:
                lines.append(f"**Reasoning:** {reasoning}")
            lines.append("")

    if ci_mode:
        lines.append("---")
        lines.append(
            "*Generated by [bicep-whatif-advisor](https://github.com/neilpeterson/bicep-whatif-advisor)*"
        )

    return "\n".join(lines)
