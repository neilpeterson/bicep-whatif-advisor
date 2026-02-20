"""Pre-LLM noise filtering for Azure What-If output.

Filters known noisy property lines from raw What-If text before the content is
sent to the LLM for analysis. This is more reliable than post-LLM summary
matching because:

  1. Property names in What-If output are deterministic, not LLM-generated.
  2. Short keywords match broadly across all resource types without needing to
     anticipate the LLM's exact phrasing.
  3. The LLM never sees the noise, so it cannot misreport it as a real change.

Pattern file format (one pattern per line, # for comments):

  Plain text (default)  — case-insensitive substring anywhere in the line
  regex: <pattern>      — Python re.search(), case-insensitive
  fuzzy: <pattern>      — legacy fuzzy similarity (SequenceMatcher)

Only property-change lines are eligible for filtering. These are lines indented
4+ spaces that begin with a ~ / + / - change symbol. Resource-level header lines
and resource attribute lines (id:, name:, type:) are never touched.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

# Minimum leading-space indent for a property change line.
# Resource-level lines use 2 spaces; property-level lines use 6+.
_PROPERTY_INDENT_MIN = 4

# Change symbols that mark the start of a property change line.
_CHANGE_SYMBOLS = frozenset({"+", "-", "~"})


@dataclass
class ParsedPattern:
    """A noise pattern parsed from a patterns file."""

    raw: str  # Original line from the file
    pattern_type: str  # "keyword", "regex", or "fuzzy"
    value: str  # The pattern value to match against


# ---------------------------------------------------------------------------
# Pattern loading
# ---------------------------------------------------------------------------


def _parse_pattern_line(line: str) -> ParsedPattern:
    """Parse a single patterns-file line, detecting its prefix type."""
    if line.startswith("regex:"):
        return ParsedPattern(raw=line, pattern_type="regex", value=line[len("regex:") :].strip())
    if line.startswith("fuzzy:"):
        return ParsedPattern(raw=line, pattern_type="fuzzy", value=line[len("fuzzy:") :].strip())
    return ParsedPattern(raw=line, pattern_type="keyword", value=line)


def _load_patterns_from_path(path: Path) -> list:
    """Load and parse patterns from a file path."""
    patterns = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(_parse_pattern_line(line))
    return patterns


def load_builtin_patterns() -> list:
    """Load the bundled built-in noise patterns from the package data directory.

    Returns an empty list if the file cannot be found or read (fail-safe).
    """
    try:
        data_path = Path(__file__).parent / "data" / "builtin_noise_patterns.txt"
        return _load_patterns_from_path(data_path)
    except (FileNotFoundError, IOError):
        return []


def load_user_patterns(file_path: str) -> list:
    """Load user-provided noise patterns from a file.

    Args:
        file_path: Path to the patterns file

    Returns:
        List of ParsedPattern objects

    Raises:
        FileNotFoundError: If file_path does not exist
        IOError: If the file cannot be read
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Noise patterns file not found: {file_path}")
    return _load_patterns_from_path(path)


# ---------------------------------------------------------------------------
# Line classification and matching
# ---------------------------------------------------------------------------


def _is_property_change_line(line: str) -> bool:
    """Return True if this line is a property-level change line in What-If output.

    Property change lines are indented 4+ spaces and begin with ~, +, or -.

    Resource-level header lines (e.g., '  + Microsoft.Storage/...') are at
    2-space indent. Resource attribute lines (id:, name:, type:, location:)
    are indented but carry no change symbol — they show the resource's values,
    not property diffs.
    """
    stripped = line.lstrip(" ")
    indent = len(line) - len(stripped)
    if indent < _PROPERTY_INDENT_MIN or not stripped:
        return False
    return stripped[0] in _CHANGE_SYMBOLS


def _matches_pattern(line: str, pattern: ParsedPattern, fuzzy_threshold: float = 0.80) -> bool:
    """Check if a line matches a pattern using the pattern's strategy.

    Args:
        line: The What-If line to test
        pattern: The parsed pattern to match against
        fuzzy_threshold: Similarity ratio for fuzzy patterns (0.0–1.0)

    Returns:
        True if the line matches the pattern
    """
    if pattern.pattern_type == "keyword":
        return pattern.value.lower() in line.lower()
    if pattern.pattern_type == "regex":
        try:
            return bool(re.search(pattern.value, line, re.IGNORECASE))
        except re.error:
            return False
    if pattern.pattern_type == "fuzzy":
        ratio = SequenceMatcher(None, pattern.value.lower(), line.lower()).ratio()
        return ratio >= fuzzy_threshold
    return False


# ---------------------------------------------------------------------------
# Main filtering function
# ---------------------------------------------------------------------------


def filter_whatif_text(
    whatif_content: str,
    patterns: list,
    fuzzy_threshold: float = 0.80,
) -> tuple:
    """Filter noisy property lines from raw What-If text before LLM analysis.

    Scans each line. Lines that appear to be property-change lines (indented
    4+ spaces with a change symbol) are checked against all patterns. Matching
    lines are suppressed from the output.

    Args:
        whatif_content: Raw What-If output text
        patterns: List of ParsedPattern objects to match against
        fuzzy_threshold: Similarity threshold for fuzzy patterns (0.0–1.0)

    Returns:
        Tuple of (filtered_text, num_lines_removed)
    """
    if not patterns:
        return whatif_content, 0

    lines = whatif_content.splitlines(keepends=True)
    filtered_lines = []
    removed = 0

    for line in lines:
        if _is_property_change_line(line):
            if any(_matches_pattern(line, p, fuzzy_threshold) for p in patterns):
                removed += 1
                continue  # suppress this line
        filtered_lines.append(line)

    return "".join(filtered_lines), removed


# ---------------------------------------------------------------------------
# Legacy helpers — kept for backwards compatibility with any external callers
# ---------------------------------------------------------------------------


def load_noise_patterns(file_path: str) -> list:
    """Load raw pattern strings from a file (legacy helper).

    Returns list of plain string values, comments and blank lines removed.
    """
    patterns = load_user_patterns(file_path)
    return [p.value for p in patterns]


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two strings (legacy helper)."""
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def match_noise_pattern(summary: str, patterns: list, threshold: float = 0.80) -> bool:
    """Check if a summary matches any pattern using fuzzy matching (legacy helper)."""
    if not summary or not patterns:
        return False
    for pattern in patterns:
        if calculate_similarity(summary, pattern) >= threshold:
            return True
    return False


def apply_noise_filtering(data: dict, noise_file: str, threshold: float = 0.80) -> dict:
    """Apply post-LLM summary-based noise filtering (legacy).

    This approach is superseded by filter_whatif_text(), which filters property
    lines before LLM analysis. Kept for backwards compatibility only.
    """
    raw_patterns = load_noise_patterns(noise_file)
    if not raw_patterns:
        return data
    for resource in data.get("resources", []):
        summary = resource.get("summary", "")
        if match_noise_pattern(summary, raw_patterns, threshold):
            resource["confidence_level"] = "noise"
    return data
