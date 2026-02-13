"""Summary-based noise pattern filtering.

This module provides functionality to filter What-If analysis resources based on
user-defined noise patterns. Patterns are matched against LLM-generated resource
summaries using fuzzy string matching.
"""

from difflib import SequenceMatcher
from pathlib import Path


def load_noise_patterns(file_path: str) -> list[str]:
    """Load noise patterns from a text file.

    Args:
        file_path: Path to noise patterns file

    Returns:
        List of noise pattern strings (one per line, comments and blank lines removed)

    Raises:
        FileNotFoundError: If file_path does not exist
        IOError: If file cannot be read
    """
    patterns = []
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"Noise patterns file not found: {file_path}")

    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            # Remove whitespace and skip comments/empty lines
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)

    return patterns


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity ratio between two strings.

    Uses Python's difflib.SequenceMatcher for fuzzy string matching.
    Comparison is case-insensitive.

    Args:
        text1: First string
        text2: Second string

    Returns:
        Similarity ratio between 0.0 and 1.0 (1.0 = identical)
    """
    return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()


def match_noise_pattern(summary: str, patterns: list[str], threshold: float = 0.80) -> bool:
    """Check if summary matches any noise pattern using fuzzy matching.

    Args:
        summary: Resource summary text from LLM
        patterns: List of noise pattern strings
        threshold: Similarity threshold (0.0-1.0, default 0.80)

    Returns:
        True if any pattern matches above threshold, False otherwise
    """
    if not summary or not patterns:
        return False

    for pattern in patterns:
        similarity = calculate_similarity(summary, pattern)
        if similarity >= threshold:
            return True

    return False


def apply_noise_filtering(
    data: dict, noise_file: str, threshold: float = 0.80
) -> dict:
    """Apply noise pattern filtering to LLM response data.

    For each resource, if the summary matches any noise pattern (above threshold),
    the confidence_level is overridden to "noise" (which will be converted to
    numeric score 10 in later processing).

    Args:
        data: Parsed LLM response with resources list
        noise_file: Path to noise patterns file
        threshold: Similarity threshold for matching (0.0-1.0)

    Returns:
        Modified data dict with confidence_level overridden for matched resources

    Raises:
        FileNotFoundError: If noise_file does not exist
        IOError: If noise_file cannot be read
    """
    # Load noise patterns
    patterns = load_noise_patterns(noise_file)

    if not patterns:
        # No patterns loaded, return data unchanged
        return data

    # Process each resource
    resources = data.get("resources", [])
    for resource in resources:
        summary = resource.get("summary", "")

        # Check if summary matches any noise pattern
        if match_noise_pattern(summary, patterns, threshold):
            # Override confidence to very low (10 when converted to numeric)
            resource["confidence_level"] = "noise"
            # Note: We could add confidence_reason here, but spec says no explicit noise flag
            # The low confidence score (10) is the indicator

    return data
