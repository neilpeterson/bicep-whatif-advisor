"""Input validation and stdin reading for bicep-whatif-advisor."""

import sys


class InputError(Exception):
    """Exception raised for input validation errors."""
    pass


def read_stdin(max_chars: int = 100000) -> str:
    """Read and validate What-If output from stdin.

    Args:
        max_chars: Maximum characters to read before truncating (default: 100,000)

    Returns:
        Validated What-If content as string

    Raises:
        InputError: If stdin is a TTY, empty, or doesn't look like What-If output
    """
    # Check if stdin is a TTY (interactive terminal, not piped)
    if sys.stdin.isatty():
        raise InputError(
            "No input detected. Pipe Azure What-If output to this command:\n"
            "  az deployment group what-if ... | bicep-whatif-advisor"
        )

    # Read all stdin
    content = sys.stdin.read()

    # Check if empty
    if not content or not content.strip():
        raise InputError("No What-If output received. Input is empty.")

    # Truncate if too large
    if len(content) > max_chars:
        sys.stderr.write(
            f"Warning: Input truncated to {max_chars:,} characters "
            f"(original: {len(content):,} characters)\n"
        )
        content = content[:max_chars]

    # Basic validation: check for What-If markers
    # This is a soft check - we warn but don't fail
    whatif_markers = [
        "Resource changes:",
        "+ Create",
        "~ Modify",
        "- Delete",
        "Resource and property changes",
        "Scope:",
    ]

    has_marker = any(marker in content for marker in whatif_markers)

    if not has_marker:
        sys.stderr.write(
            "Warning: Input may not be Azure What-If output. "
            "Expected to find markers like 'Resource changes:' or '+ Create'. "
            "Attempting to proceed anyway.\n"
        )

    return content
