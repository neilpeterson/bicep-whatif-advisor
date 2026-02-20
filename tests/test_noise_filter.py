"""Tests for bicep_whatif_advisor.noise_filter module."""

import pytest

from bicep_whatif_advisor.noise_filter import (
    ParsedPattern,
    _is_property_change_line,
    _matches_pattern,
    _parse_pattern_line,
    calculate_similarity,
    filter_whatif_text,
    load_builtin_patterns,
    load_user_patterns,
    match_noise_pattern,
)

# ---------------------------------------------------------------------------
# Pattern parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParsePatternLine:
    def test_keyword_pattern(self):
        p = _parse_pattern_line("etag")
        assert p.pattern_type == "keyword"
        assert p.value == "etag"

    def test_regex_pattern(self):
        p = _parse_pattern_line("regex: ^foo.*bar$")
        assert p.pattern_type == "regex"
        assert p.value == "^foo.*bar$"

    def test_fuzzy_pattern(self):
        p = _parse_pattern_line("fuzzy: provisioningState change")
        assert p.pattern_type == "fuzzy"
        assert p.value == "provisioningState change"

    def test_keyword_preserves_value(self):
        p = _parse_pattern_line("logAnalyticsDestinationType")
        assert p.value == "logAnalyticsDestinationType"

    def test_raw_field_preserved(self):
        p = _parse_pattern_line("regex: test")
        assert p.raw == "regex: test"


# ---------------------------------------------------------------------------
# Property change line detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsPropertyChangeLine:
    def test_property_modify_line(self):
        assert _is_property_change_line('      ~ properties.etag: "old" => "new"') is True

    def test_property_add_line(self):
        assert _is_property_change_line('      + properties.newField: "value"') is True

    def test_property_remove_line(self):
        assert _is_property_change_line('      - properties.oldField: "value"') is True

    def test_resource_header_line_rejected(self):
        """Resource-level header (2-space indent) should not match."""
        assert _is_property_change_line("  + Microsoft.Storage/storageAccounts/test") is False

    def test_attribute_line_rejected(self):
        """Attribute lines (no change symbol) should not match."""
        assert _is_property_change_line('      id:   "/subscriptions/123"') is False

    def test_empty_line_rejected(self):
        assert _is_property_change_line("") is False

    def test_no_indent_rejected(self):
        assert _is_property_change_line("~ properties.etag") is False

    def test_three_space_indent_rejected(self):
        assert _is_property_change_line("   ~ properties.etag") is False


# ---------------------------------------------------------------------------
# Pattern matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMatchesPattern:
    def test_keyword_match_case_insensitive(self):
        p = ParsedPattern(raw="etag", pattern_type="keyword", value="etag")
        assert _matches_pattern("      ~ properties.ETAG: old => new", p) is True

    def test_keyword_no_match(self):
        p = ParsedPattern(raw="etag", pattern_type="keyword", value="etag")
        assert _matches_pattern("      ~ properties.name: old => new", p) is False

    def test_regex_match(self):
        p = ParsedPattern(raw="regex: ipv6", pattern_type="regex", value="ipv6")
        assert _matches_pattern("      ~ properties.enableIPv6: false => true", p) is True

    def test_regex_invalid_pattern_returns_false(self):
        p = ParsedPattern(raw="regex: [invalid", pattern_type="regex", value="[invalid")
        assert _matches_pattern("anything", p) is False

    def test_fuzzy_match_above_threshold(self):
        p = ParsedPattern(
            raw="fuzzy: provisioningState",
            pattern_type="fuzzy",
            value="provisioningState",
        )
        line = "      ~ properties.provisioningState: Succeeded => Updating"
        assert _matches_pattern(line, p, fuzzy_threshold=0.3) is True

    def test_fuzzy_no_match_below_threshold(self):
        p = ParsedPattern(
            raw="fuzzy: provisioningState",
            pattern_type="fuzzy",
            value="provisioningState",
        )
        line = "      ~ properties.completely.different.thing"
        assert _matches_pattern(line, p, fuzzy_threshold=0.99) is False


# ---------------------------------------------------------------------------
# filter_whatif_text
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFilterWhatifText:
    def test_no_patterns_returns_unchanged(self):
        text = "some text\nmore lines\n"
        result, count = filter_whatif_text(text, [])
        assert result == text
        assert count == 0

    def test_filters_matching_property_lines(self):
        text = (
            "  + Microsoft.Storage/test\n"
            "      ~ properties.etag: old => new\n"
            "      ~ properties.name: myresource\n"
        )
        patterns = [ParsedPattern(raw="etag", pattern_type="keyword", value="etag")]
        result, count = filter_whatif_text(text, patterns)
        assert count == 1
        assert "etag" not in result
        assert "name: myresource" in result

    def test_preserves_resource_header_lines(self):
        """Resource header lines should never be filtered."""
        text = "  + Microsoft.Storage/storageAccounts/etag-test\n"
        patterns = [ParsedPattern(raw="etag", pattern_type="keyword", value="etag")]
        result, count = filter_whatif_text(text, patterns)
        assert count == 0
        assert "etag-test" in result

    def test_multiple_patterns(self):
        text = (
            "      ~ properties.etag: old => new\n"
            "      ~ properties.provisioningState: s => u\n"
            "      ~ properties.name: real\n"
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
            ParsedPattern(
                raw="provisioningState", pattern_type="keyword", value="provisioningState"
            ),
        ]
        result, count = filter_whatif_text(text, patterns)
        assert count == 2
        assert "name: real" in result

    def test_filters_from_noisy_fixture(self, noisy_changes_fixture):
        """Sanity check: builtin patterns filter lines from noisy fixture."""
        patterns = load_builtin_patterns()
        _, count = filter_whatif_text(noisy_changes_fixture, patterns)
        assert count > 0  # Should filter at least some noisy lines


# ---------------------------------------------------------------------------
# Pattern loading
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLoadPatterns:
    def test_builtin_patterns_load_successfully(self):
        patterns = load_builtin_patterns()
        assert len(patterns) > 0
        assert all(isinstance(p, ParsedPattern) for p in patterns)

    def test_builtin_patterns_include_etag(self):
        patterns = load_builtin_patterns()
        values = [p.value for p in patterns]
        assert "etag" in values

    def test_user_patterns_from_file(self, tmp_path):
        pfile = tmp_path / "patterns.txt"
        pfile.write_text("# comment\netag\nregex: foo.*\nfuzzy: bar baz\n")
        patterns = load_user_patterns(str(pfile))
        assert len(patterns) == 3
        types = [p.pattern_type for p in patterns]
        assert types == ["keyword", "regex", "fuzzy"]

    def test_user_patterns_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_user_patterns("/nonexistent/path/patterns.txt")

    def test_user_patterns_skips_blank_and_comments(self, tmp_path):
        pfile = tmp_path / "patterns.txt"
        pfile.write_text("# comment\n\n  \netag\n")
        patterns = load_user_patterns(str(pfile))
        assert len(patterns) == 1


# ---------------------------------------------------------------------------
# Legacy helpers
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestLegacyHelpers:
    def test_calculate_similarity_identical(self):
        assert calculate_similarity("hello", "hello") == 1.0

    def test_calculate_similarity_different(self):
        assert calculate_similarity("hello", "world") < 0.5

    def test_match_noise_pattern_matches(self):
        assert match_noise_pattern("etag update", ["etag update"], threshold=0.8) is True

    def test_match_noise_pattern_empty_summary(self):
        assert match_noise_pattern("", ["etag"], threshold=0.8) is False

    def test_match_noise_pattern_empty_patterns(self):
        assert match_noise_pattern("etag", [], threshold=0.8) is False
