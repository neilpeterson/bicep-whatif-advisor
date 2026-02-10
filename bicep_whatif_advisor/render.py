"""Output rendering for bicep-whatif-advisor in various formats."""

import json
import sys
import shutil
from rich.console import Console
from rich.table import Table
from rich import box


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
    ci_mode: bool = False
) -> None:
    """Render output as a colored table using Rich.

    Args:
        data: Parsed LLM response with resources and overall_summary
        verbose: Show property-level changes for modified resources
        no_color: Disable colored output
        ci_mode: Include risk assessment columns
    """
    # Determine if we should use colors
    use_color = not no_color and sys.stdout.isatty()

    # Calculate 85% of terminal width (15% reduction)
    terminal_width = shutil.get_terminal_size().columns
    reduced_width = int(terminal_width * 0.85)

    console = Console(force_terminal=use_color, no_color=not use_color, width=reduced_width)

    # Print risk bucket summary first in CI mode
    if ci_mode:
        _print_risk_bucket_summary(console, data.get("risk_assessment", {}), use_color)

    # Create table
    table = Table(box=box.ROUNDED, show_lines=True, padding=(0, 1))

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

    # Print table
    console.print(table)
    console.print()

    # Print overall summary
    overall_summary = data.get("overall_summary", "")
    if overall_summary:
        summary_label = _colorize("Summary:", "bold", use_color)
        console.print(f"{summary_label} {overall_summary}")
        console.print()

    # Print verbose details if requested
    if verbose and not ci_mode:
        _print_verbose_details(console, resources, use_color)

    # Print CI verdict if in CI mode
    if ci_mode:
        _print_ci_verdict(console, data.get("verdict", {}), use_color)


def _print_risk_bucket_summary(console: Console, risk_assessment: dict, use_color: bool) -> None:
    """Print risk bucket summary table in CI mode."""
    if not risk_assessment:
        return

    # Create risk bucket table
    bucket_table = Table(box=box.ROUNDED, show_header=True, padding=(0, 1))
    bucket_table.add_column("Risk Bucket", style="bold")
    bucket_table.add_column("Risk Level", justify="center")
    bucket_table.add_column("Status", justify="center")
    bucket_table.add_column("Key Concerns")

    # Drift bucket
    drift = risk_assessment.get("drift", {})
    if drift:
        drift_risk = drift.get("risk_level", "low")
        _, risk_color = RISK_STYLES.get(drift_risk, ("?", "white"))
        concerns = drift.get("concerns", [])
        concern_text = concerns[0] if concerns else "None"

        bucket_table.add_row(
            "Infrastructure Drift",
            _colorize(drift_risk.capitalize(), risk_color, use_color),
            _colorize("●", risk_color, use_color),
            concern_text
        )

    # Intent bucket (may not exist if PR metadata not provided)
    intent = risk_assessment.get("intent")
    if intent is not None:
        intent_risk = intent.get("risk_level", "low")
        _, risk_color = RISK_STYLES.get(intent_risk, ("?", "white"))
        concerns = intent.get("concerns", [])
        concern_text = concerns[0] if concerns else "None"

        bucket_table.add_row(
            "PR Intent Alignment",
            _colorize(intent_risk.capitalize(), risk_color, use_color),
            _colorize("●", risk_color, use_color),
            concern_text
        )
    else:
        # Intent bucket skipped
        bucket_table.add_row(
            "PR Intent Alignment",
            _colorize("Not evaluated", "dim", use_color),
            _colorize("—", "dim", use_color),
            "No PR metadata provided"
        )

    # Operations bucket
    operations = risk_assessment.get("operations", {})
    if operations:
        operations_risk = operations.get("risk_level", "low")
        _, risk_color = RISK_STYLES.get(operations_risk, ("?", "white"))
        concerns = operations.get("concerns", [])
        concern_text = concerns[0] if concerns else "None"

        bucket_table.add_row(
            "Risky Operations",
            _colorize(operations_risk.capitalize(), risk_color, use_color),
            _colorize("●", risk_color, use_color),
            concern_text
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
    overall_risk = verdict.get("overall_risk_level", "low")
    highest_bucket = verdict.get("highest_risk_bucket", "none")
    reasoning = verdict.get("reasoning", "")

    # Verdict header
    if safe:
        verdict_text = "SAFE"
        verdict_style = "green bold"
    else:
        verdict_text = "UNSAFE"
        verdict_style = "red bold"

    verdict_display = _colorize(f"Verdict: {verdict_text}", verdict_style, use_color)
    console.print(verdict_display)
    console.print()

    # Overall risk level
    label = _colorize("Overall Risk Level:", "bold", use_color)
    console.print(f"{label} {overall_risk.capitalize()}")

    # Highest risk bucket
    if highest_bucket != "none":
        label = _colorize("Highest Risk Bucket:", "bold", use_color)
        console.print(f"{label} {highest_bucket.capitalize()}")

    # Reasoning
    if reasoning:
        label = _colorize("Reasoning:", "bold", use_color)
        console.print(f"{label} {reasoning}")

    console.print()


def render_json(data: dict) -> None:
    """Render output as pretty-printed JSON.

    Args:
        data: Parsed LLM response
    """
    print(json.dumps(data, indent=2))


def render_markdown(data: dict, ci_mode: bool = False, custom_title: str = None, no_block: bool = False) -> str:
    """Render output as markdown table suitable for PR comments.

    Args:
        data: Parsed LLM response
        ci_mode: Include risk assessment and verdict
        custom_title: Custom title for the comment (default: "What-If Deployment Review")
        no_block: Append "(non-blocking)" to title if True

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

        # Add risk bucket summary
        risk_assessment = data.get("risk_assessment", {})
        if risk_assessment:
            lines.append("### Risk Assessment")
            lines.append("")
            lines.append("| Risk Bucket | Risk Level | Key Concerns |")
            lines.append("|-------------|------------|--------------|")

            # Drift bucket
            drift = risk_assessment.get("drift", {})
            if drift:
                drift_risk = drift.get("risk_level", "low").capitalize()
                concerns = drift.get("concerns", [])
                concern_text = concerns[0] if concerns else "None"
                lines.append(f"| Infrastructure Drift | {drift_risk} | {concern_text} |")

            # Intent bucket (may not exist)
            intent = risk_assessment.get("intent")
            if intent is not None:
                intent_risk = intent.get("risk_level", "low").capitalize()
                concerns = intent.get("concerns", [])
                concern_text = concerns[0] if concerns else "None"
                lines.append(f"| PR Intent Alignment | {intent_risk} | {concern_text} |")
            else:
                lines.append("| PR Intent Alignment | Not evaluated | No PR metadata provided |")

            # Operations bucket
            operations = risk_assessment.get("operations", {})
            if operations:
                operations_risk = operations.get("risk_level", "low").capitalize()
                concerns = operations.get("concerns", [])
                concern_text = concerns[0] if concerns else "None"
                lines.append(f"| Risky Operations | {operations_risk} | {concern_text} |")

            lines.append("")
            lines.append("### Resource Changes")
            lines.append("")

    # Table header
    if ci_mode:
        lines.append("| # | Resource | Type | Action | Risk | Summary |")
        lines.append("|---|----------|------|--------|------|---------|")
    else:
        lines.append("| # | Resource | Type | Action | Summary |")
        lines.append("|---|----------|------|--------|---------|")

    # Table rows
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
                f"| {idx} | {resource_name} | {resource_type} | {action_display} | {risk_display} | {summary} |"
            )
        else:
            lines.append(
                f"| {idx} | {resource_name} | {resource_type} | {action_display} | {summary} |"
            )

    lines.append("")

    # Overall summary
    overall_summary = data.get("overall_summary", "")
    if overall_summary:
        lines.append(f"**Summary:** {overall_summary}")
        lines.append("")

    # CI verdict
    if ci_mode:
        verdict = data.get("verdict", {})
        if verdict:
            safe = verdict.get("safe", True)
            overall_risk = verdict.get("overall_risk_level", "low")
            highest_bucket = verdict.get("highest_risk_bucket", "none")
            reasoning = verdict.get("reasoning", "")

            # Verdict header
            verdict_text = "✅ SAFE" if safe else "❌ UNSAFE"
            lines.append(f"### Verdict: {verdict_text}")
            lines.append("")

            lines.append(f"**Overall Risk Level:** {overall_risk.capitalize()}")
            if highest_bucket != "none":
                lines.append(f"**Highest Risk Bucket:** {highest_bucket.capitalize()}")
            if reasoning:
                lines.append(f"**Reasoning:** {reasoning}")
            lines.append("")

    if ci_mode:
        lines.append("---")
        lines.append("*Generated by [bicep-whatif-advisor](https://github.com/yourorg/bicep-whatif-advisor)*")

    return "\n".join(lines)
