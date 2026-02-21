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
  resource: <type>[:op] — remove entire resource block by type (and optionally operation)

Property-level patterns (keyword/regex/fuzzy) only match property-change lines
(indented 4+ spaces with a ~ / + / - change symbol). Resource-level header lines
and attribute lines are never touched by property patterns.

Resource-level patterns (resource:) match entire resource blocks by ARM type
substring and optional operation. When all property-change lines in a Modify
block are removed by property patterns, the entire block is also automatically
suppressed.
"""

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Optional, Tuple

# Minimum leading-space indent for a property change line.
# Resource-level lines use 2 spaces; property-level lines use 6+.
_PROPERTY_INDENT_MIN = 4

# Change symbols that mark the start of a property change line.
_CHANGE_SYMBOLS = frozenset({"+", "-", "~"})

# Map from What-If change symbols to operation names.
_SYMBOL_TO_OPERATION = {
    "~": "Modify",
    "+": "Create",
    "-": "Delete",
    "=": "Deploy",
    "*": "NoChange",
    "x": "Ignore",
}

# Valid operation names for resource: patterns.
_VALID_OPERATIONS = frozenset({"Modify", "Create", "Delete", "Deploy", "NoChange", "Ignore"})

# Regex for a resource header line: 2-space indent + change symbol + space + ARM type with /
_RESOURCE_HEADER_RE = re.compile(
    r"^  ([~+\-=*x!])\s+(\S+/\S+)"
)


@dataclass
class ParsedPattern:
    """A noise pattern parsed from a patterns file."""

    raw: str  # Original line from the file
    pattern_type: str  # "keyword", "regex", "fuzzy", or "resource"
    value: str  # The pattern value to match against


@dataclass
class _ResourceBlock:
    """A parsed resource block from What-If output."""

    header_line: str  # The resource header line (e.g., "  ~ Microsoft.Network/...")
    operation: str  # Operation name: "Modify", "Create", "Delete", etc.
    resource_type: str  # ARM resource type string from the header
    lines: List[str]  # All lines in this block (header + attributes + properties)
    property_change_indices: List[int] = field(default_factory=list)  # Indices of property-change lines within self.lines


# ---------------------------------------------------------------------------
# Pattern loading
# ---------------------------------------------------------------------------


def _parse_pattern_line(line: str) -> ParsedPattern:
    """Parse a single patterns-file line, detecting its prefix type."""
    if line.startswith("regex:"):
        return ParsedPattern(raw=line, pattern_type="regex", value=line[len("regex:"):].strip())
    if line.startswith("fuzzy:"):
        return ParsedPattern(raw=line, pattern_type="fuzzy", value=line[len("fuzzy:"):].strip())
    if line.startswith("resource:"):
        return ParsedPattern(raw=line, pattern_type="resource", value=line[len("resource:"):].strip())
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
        fuzzy_threshold: Similarity ratio for fuzzy patterns (0.0-1.0)

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
# Block parsing
# ---------------------------------------------------------------------------


def _is_resource_header(line: str) -> bool:
    """Return True if this line is a resource block header.

    Resource headers have 2-space indent, a change symbol, and an ARM resource
    type containing '/'. This distinguishes them from the legend lines at the
    top of What-If output (e.g., '  - Delete', '  ~ Modify') which have the
    same indent + symbol pattern but no '/' in the text.
    """
    return bool(_RESOURCE_HEADER_RE.match(line))


def _parse_resource_blocks(
    lines: List[str],
) -> Tuple[List[str], List[_ResourceBlock], List[str]]:
    """Parse raw What-If lines into structured resource blocks.

    Returns:
        Tuple of (preamble_lines, blocks, epilogue_lines) where preamble is
        everything before the first resource block and epilogue is everything
        after the last block.
    """
    preamble = []  # type: List[str]
    blocks = []  # type: List[_ResourceBlock]
    epilogue = []  # type: List[str]
    current_block = None  # type: Optional[_ResourceBlock]

    for line in lines:
        if _is_resource_header(line):
            # Close previous block
            if current_block is not None:
                blocks.append(current_block)

            # Parse header
            m = _RESOURCE_HEADER_RE.match(line)
            symbol = m.group(1)
            resource_type = m.group(2)
            operation = _SYMBOL_TO_OPERATION.get(symbol, "Modify")

            current_block = _ResourceBlock(
                header_line=line,
                operation=operation,
                resource_type=resource_type,
                lines=[line],
                property_change_indices=[],
            )
        elif current_block is not None:
            idx = len(current_block.lines)
            current_block.lines.append(line)
            if _is_property_change_line(line):
                current_block.property_change_indices.append(idx)
        else:
            preamble.append(line)

    # Close last block
    if current_block is not None:
        blocks.append(current_block)

    # Anything after the last block's trailing content is epilogue.
    # We detect epilogue by looking for summary lines after the last block.
    # In practice, epilogue lines are things like "Resource changes: 1 to create..."
    # They appear after the last resource block and are not indented like properties.
    # Since our parser puts everything after the first header into blocks, we need
    # to check if the last block has trailing non-block content.
    if blocks:
        last_block = blocks[-1]
        # Find where block content truly ends (last property or attribute line)
        # and split off epilogue lines (like "Resource changes: ...")
        epilogue_start = None
        for i in range(len(last_block.lines) - 1, 0, -1):
            line = last_block.lines[i]
            stripped = line.strip()
            if not stripped:
                # Blank line — could be separator, keep looking
                continue
            # If line is not indented (starts at column 0) or starts with
            # a non-whitespace char at low indent, it's epilogue
            if line and not line.startswith(" "):
                epilogue_start = i
            else:
                break

        if epilogue_start is not None:
            epilogue = last_block.lines[epilogue_start:]
            last_block.lines = last_block.lines[:epilogue_start]
            # Recompute property_change_indices
            last_block.property_change_indices = [
                j for j in last_block.property_change_indices if j < epilogue_start
            ]

    return preamble, blocks, epilogue


# ---------------------------------------------------------------------------
# Resource pattern matching
# ---------------------------------------------------------------------------


def _matches_resource_pattern(block: _ResourceBlock, pattern: ParsedPattern) -> bool:
    """Check if a resource block matches a resource: pattern.

    Pattern value format: "<type_substring>" or "<type_substring>:<Operation>"
    Type matching is case-insensitive substring.
    Operation (if present) must exactly match (case-insensitive) one of the
    valid operations.

    Args:
        block: The resource block to test
        pattern: A ParsedPattern with pattern_type == "resource"

    Returns:
        True if the block matches
    """
    value = pattern.value
    if ":" in value:
        type_part, op_part = value.rsplit(":", 1)
        type_part = type_part.strip()
        op_part = op_part.strip()

        # Validate operation — if invalid, treat as type-only (the colon may
        # be part of the type string itself, though unlikely)
        op_normalized = op_part.capitalize()
        # Handle multi-word like "NoChange"
        op_lookup = {v.lower(): v for v in _VALID_OPERATIONS}
        matched_op = op_lookup.get(op_part.lower())

        if matched_op:
            # Type substring + operation match
            if type_part.lower() not in block.resource_type.lower():
                return False
            return block.operation == matched_op
        else:
            # Invalid operation name — fall back to full value as type match
            return value.lower() in block.resource_type.lower()
    else:
        # Type-only match (any operation)
        return value.lower() in block.resource_type.lower()


# ---------------------------------------------------------------------------
# Main filtering function
# ---------------------------------------------------------------------------


def filter_whatif_text(
    whatif_content: str,
    patterns: list,
    fuzzy_threshold: float = 0.80,
) -> tuple:
    """Filter noisy property lines and resource blocks from raw What-If text.

    Uses a two-phase block-aware approach:
    1. Parse What-If text into structured resource blocks
    2. Filter: resource-level patterns first (remove entire blocks), then
       property-level patterns with automatic Modify block suppression

    When all property-change lines in a Modify block are removed by property
    patterns, the entire block is automatically suppressed. Create/Delete blocks
    are never auto-suppressed (they carry semantic meaning without property details).

    Args:
        whatif_content: Raw What-If output text
        patterns: List of ParsedPattern objects to match against
        fuzzy_threshold: Similarity threshold for fuzzy patterns (0.0-1.0)

    Returns:
        Tuple of (filtered_text, num_lines_removed)
    """
    if not patterns:
        return whatif_content, 0

    # Separate resource-level vs property-level patterns
    resource_patterns = [p for p in patterns if p.pattern_type == "resource"]
    property_patterns = [p for p in patterns if p.pattern_type != "resource"]

    # If no resource patterns and no need for block suppression, we can still
    # benefit from block parsing for auto-suppression of fully-filtered Modify blocks.
    lines = whatif_content.splitlines(keepends=True)
    preamble, blocks, epilogue = _parse_resource_blocks(lines)

    # If there are no blocks (e.g., text has no resource headers), fall back
    # to simple line-by-line filtering for backward compatibility
    if not blocks:
        filtered_lines = []
        removed = 0
        for line in lines:
            if _is_property_change_line(line):
                if any(_matches_pattern(line, p, fuzzy_threshold) for p in property_patterns):
                    removed += 1
                    continue
            filtered_lines.append(line)
        return "".join(filtered_lines), removed

    # Phase 1: Resource-level filtering
    # Phase 2: Property-level filtering + auto block suppression
    result_lines = list(preamble)
    total_removed = 0

    for block in blocks:
        # Check resource-level patterns
        if resource_patterns and any(
            _matches_resource_pattern(block, p) for p in resource_patterns
        ):
            total_removed += len(block.lines)
            continue  # Suppress entire block

        # Apply property-level patterns within this block
        if property_patterns and block.property_change_indices:
            filtered_indices = set()  # Indices of lines to remove
            for idx in block.property_change_indices:
                line = block.lines[idx]
                if any(_matches_pattern(line, p, fuzzy_threshold) for p in property_patterns):
                    filtered_indices.add(idx)

            if filtered_indices:
                # Check for auto-suppression: if ALL property-change lines in a
                # Modify block were filtered, suppress the entire block
                if (
                    block.operation == "Modify"
                    and len(filtered_indices) == len(block.property_change_indices)
                ):
                    total_removed += len(block.lines)
                    continue  # Suppress entire block

                # Otherwise keep the block but remove matched property lines
                for i, line in enumerate(block.lines):
                    if i in filtered_indices:
                        total_removed += 1
                    else:
                        result_lines.append(line)
                continue

        # No filtering needed — keep entire block
        result_lines.extend(block.lines)

    result_lines.extend(epilogue)
    return "".join(result_lines), total_removed


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
