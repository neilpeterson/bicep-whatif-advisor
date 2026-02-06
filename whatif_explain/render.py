"""Output rendering for whatif-explain in various formats."""

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
    "critical": ("🔴", "red bold"),
    "high": ("🔴", "red"),
    "medium": ("🟡", "yellow"),
    "low": ("🟢", "green"),
    "none": ("⚪", "dim"),
}


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
            f"[{color}]{action_display}[/{color}]" if use_color else action_display,
        ]

        if ci_mode:
            risk_level = resource.get("risk_level", "none")
            _, risk_color = RISK_STYLES.get(risk_level, ("?", "white"))
            risk_display = risk_level.capitalize()
            row.append(
                f"[{risk_color}]{risk_display}[/{risk_color}]"
                if use_color else risk_display
            )

        row.append(summary)
        table.add_row(*row)

    # Print table
    console.print(table)
    console.print()

    # Print overall summary
    overall_summary = data.get("overall_summary", "")
    if overall_summary:
        console.print(f"[bold]Summary:[/bold] {overall_summary}" if use_color else f"Summary: {overall_summary}")
        console.print()

    # Print verbose details if requested
    if verbose and not ci_mode:
        _print_verbose_details(console, resources, use_color)

    # Print CI verdict if in CI mode
    if ci_mode:
        _print_ci_verdict(console, data.get("verdict", {}), use_color)


def _print_verbose_details(console: Console, resources: list, use_color: bool) -> None:
    """Print verbose property-level change details."""
    modified_resources = [r for r in resources if r.get("action") == "Modify" and r.get("changes")]

    if modified_resources:
        console.print("[bold]Property-Level Changes:[/bold]" if use_color else "Property-Level Changes:")
        console.print()

        for resource in modified_resources:
            resource_name = resource.get("resource_name", "Unknown")
            console.print(f"  [yellow]•[/yellow] {resource_name}:" if use_color else f"  • {resource_name}:")

            for change in resource.get("changes", []):
                console.print(f"    - {change}")

            console.print()


def _print_ci_verdict(console: Console, verdict: dict, use_color: bool) -> None:
    """Print CI mode verdict, concerns, and recommendations."""
    if not verdict:
        return

    safe = verdict.get("safe", True)
    risk_level = verdict.get("risk_level", "none")
    reasoning = verdict.get("reasoning", "")
    concerns = verdict.get("concerns", [])
    recommendations = verdict.get("recommendations", [])

    # Verdict header
    if safe:
        verdict_text = "SAFE"
        verdict_style = "green bold"
    else:
        verdict_text = "UNSAFE"
        verdict_style = "red bold"

    console.print(
        f"[{verdict_style}]Verdict: {verdict_text}[/{verdict_style}]"
        if use_color else f"Verdict: {verdict_text}"
    )
    console.print()

    # Risk level
    console.print(f"[bold]Risk Level:[/bold] {risk_level.capitalize()}" if use_color else f"Risk Level: {risk_level.capitalize()}")

    # Reasoning
    if reasoning:
        console.print(f"[bold]Reasoning:[/bold] {reasoning}" if use_color else f"Reasoning: {reasoning}")

    console.print()

    # Concerns
    if concerns:
        console.print("[bold red]Concerns:[/bold red]" if use_color else "Concerns:")
        for concern in concerns:
            console.print(f"  - {concern}")
        console.print()

    # Recommendations
    if recommendations:
        console.print("[bold yellow]Recommendations:[/bold yellow]" if use_color else "Recommendations:")
        for rec in recommendations:
            console.print(f"  - {rec}")
        console.print()


def render_json(data: dict) -> None:
    """Render output as pretty-printed JSON.

    Args:
        data: Parsed LLM response
    """
    print(json.dumps(data, indent=2))


def render_markdown(data: dict, ci_mode: bool = False) -> str:
    """Render output as markdown table suitable for PR comments.

    Args:
        data: Parsed LLM response
        ci_mode: Include risk assessment and verdict

    Returns:
        Markdown-formatted string
    """
    lines = []

    if ci_mode:
        lines.append("## What-If Deployment Review")
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
            risk_level = verdict.get("risk_level", "none")
            reasoning = verdict.get("reasoning", "")
            concerns = verdict.get("concerns", [])
            recommendations = verdict.get("recommendations", [])

            # Verdict header
            verdict_text = "SAFE" if safe else "UNSAFE"
            lines.append(f"### Verdict: {verdict_text}")
            lines.append("")

            lines.append(f"**Risk Level:** {risk_level.capitalize()}")
            if reasoning:
                lines.append(f"**Reasoning:** {reasoning}")
            lines.append("")

            if concerns:
                lines.append("**Concerns:**")
                for concern in concerns:
                    lines.append(f"- {concern}")
                lines.append("")

            if recommendations:
                lines.append("**Recommendations:**")
                for rec in recommendations:
                    lines.append(f"- {rec}")
                lines.append("")

    if ci_mode:
        lines.append("---")
        lines.append("*Generated by [whatif-explain](https://github.com/yourorg/whatif-explain)*")

    return "\n".join(lines)
