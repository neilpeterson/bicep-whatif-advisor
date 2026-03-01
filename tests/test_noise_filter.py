"""Tests for bicep_whatif_advisor.noise_filter module."""

import pytest

from bicep_whatif_advisor.noise_filter import (
    ParsedPattern,
    _extract_arm_type,
    _is_property_change_line,
    _is_resource_header,
    _matches_pattern,
    _matches_resource_pattern,
    _parse_pattern_line,
    _parse_resource_blocks,
    _ResourceBlock,
    calculate_similarity,
    extract_resource_patterns,
    filter_whatif_text,
    load_builtin_patterns,
    load_user_patterns,
    match_noise_pattern,
    reclassify_resource_noise,
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

    def test_resource_pattern_type_only(self):
        p = _parse_pattern_line("resource: diagnosticSettings")
        assert p.pattern_type == "resource"
        assert p.value == "diagnosticSettings"

    def test_resource_pattern_type_and_operation(self):
        p = _parse_pattern_line("resource: privateDnsZones/virtualNetworkLinks:Modify")
        assert p.pattern_type == "resource"
        assert p.value == "privateDnsZones/virtualNetworkLinks:Modify"

    def test_resource_pattern_raw_preserved(self):
        p = _parse_pattern_line("resource: diagnosticSettings")
        assert p.raw == "resource: diagnosticSettings"


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
# Resource header detection
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestIsResourceHeader:
    def test_modify_header(self):
        assert (
            _is_resource_header("  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]") is True
        )

    def test_create_header(self):
        assert (
            _is_resource_header("  + Microsoft.Storage/storageAccounts/newstorage [2023-01-01]")
            is True
        )

    def test_delete_header(self):
        assert _is_resource_header("  - Microsoft.Sql/servers/mydb [2023-01-01]") is True

    def test_legend_line_modify_rejected(self):
        """Legend lines like '  ~ Modify' have no '/' so they are excluded."""
        assert _is_resource_header("  ~ Modify") is False

    def test_legend_line_delete_rejected(self):
        assert _is_resource_header("  - Delete") is False

    def test_legend_line_create_rejected(self):
        assert _is_resource_header("  + Create") is False

    def test_property_line_rejected(self):
        assert _is_resource_header('      ~ properties.etag: "old" => "new"') is False

    def test_empty_line_rejected(self):
        assert _is_resource_header("") is False

    def test_no_indent_rejected(self):
        assert _is_resource_header("~ Microsoft.Network/test [2022-07-01]") is False


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
# ARM type extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractArmType:
    def test_simple_resource(self):
        assert (
            _extract_arm_type("Microsoft.Network/virtualNetworks/myvnet")
            == "Microsoft.Network/virtualNetworks"
        )

    def test_nested_child_resource(self):
        assert (
            _extract_arm_type("Microsoft.Storage/storageAccounts/myacct/blobServices/default")
            == "Microsoft.Storage/storageAccounts/blobServices"
        )

    def test_deeply_nested_resource(self):
        assert (
            _extract_arm_type(
                "Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net"
                "/virtualNetworkLinks/mylink"
            )
            == "Microsoft.Network/privateDnsZones/virtualNetworkLinks"
        )

    def test_namespace_only(self):
        assert _extract_arm_type("Microsoft.Storage") == "Microsoft.Storage"

    def test_type_without_name(self):
        """Single type segment with no name following."""
        assert (
            _extract_arm_type("Microsoft.Insights/diagnosticSettings")
            == "Microsoft.Insights/diagnosticSettings"
        )


# ---------------------------------------------------------------------------
# Resource pattern matching
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMatchesResourcePattern:
    def _make_block(self, resource_type, operation="Modify"):
        return _ResourceBlock(
            header_line=f"  ~ {resource_type} [2022-07-01]",
            operation=operation,
            resource_type=resource_type,
            lines=[f"  ~ {resource_type} [2022-07-01]"],
        )

    def test_type_substring_match(self):
        block = self._make_block("Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1")
        p = ParsedPattern(
            raw="resource: privateDnsZones/virtualNetworkLinks",
            pattern_type="resource",
            value="privateDnsZones/virtualNetworkLinks",
        )
        assert _matches_resource_pattern(block, p) is True

    def test_type_substring_no_match(self):
        block = self._make_block("Microsoft.Storage/storageAccounts/mystorage")
        p = ParsedPattern(
            raw="resource: privateDnsZones", pattern_type="resource", value="privateDnsZones"
        )
        assert _matches_resource_pattern(block, p) is False

    def test_case_insensitive_type_match(self):
        block = self._make_block("Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1")
        p = ParsedPattern(
            raw="resource: PRIVATEDNSZONES", pattern_type="resource", value="PRIVATEDNSZONES"
        )
        assert _matches_resource_pattern(block, p) is True

    def test_type_with_operation_match(self):
        block = self._make_block(
            "Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1", "Modify"
        )
        p = ParsedPattern(
            raw="resource: privateDnsZones:Modify",
            pattern_type="resource",
            value="privateDnsZones:Modify",
        )
        assert _matches_resource_pattern(block, p) is True

    def test_type_with_wrong_operation_no_match(self):
        block = self._make_block(
            "Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1", "Create"
        )
        p = ParsedPattern(
            raw="resource: privateDnsZones:Modify",
            pattern_type="resource",
            value="privateDnsZones:Modify",
        )
        assert _matches_resource_pattern(block, p) is False

    def test_type_only_matches_any_operation(self):
        """Without an operation suffix, pattern matches any operation."""
        for op in ["Modify", "Create", "Delete"]:
            block = self._make_block("Microsoft.Insights/diagnosticSettings/diag1", op)
            p = ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            )
            assert _matches_resource_pattern(block, p) is True

    def test_operation_case_insensitive(self):
        block = self._make_block("Microsoft.Network/test/resource1", "Modify")
        p = ParsedPattern(raw="resource: test:modify", pattern_type="resource", value="test:modify")
        assert _matches_resource_pattern(block, p) is True

    def test_invalid_operation_falls_back_to_type_match(self):
        """Invalid operation name treated as full type string match."""
        block = self._make_block("Microsoft.Network/test:notanop/resource1", "Modify")
        p = ParsedPattern(
            raw="resource: test:notanop", pattern_type="resource", value="test:notanop"
        )
        assert _matches_resource_pattern(block, p) is True

    def test_delete_operation_match(self):
        block = self._make_block("Microsoft.Sql/servers/mydb", "Delete")
        p = ParsedPattern(
            raw="resource: Sql/servers:Delete", pattern_type="resource", value="Sql/servers:Delete"
        )
        assert _matches_resource_pattern(block, p) is True

    def test_nested_child_type_via_arm_extraction(self):
        """Pattern with ARM type matches even when resource names are interleaved."""
        block = self._make_block("Microsoft.Storage/storageAccounts/myacct/blobServices/default")
        p = ParsedPattern(
            raw="resource: Microsoft.Storage/storageAccounts/blobServices",
            pattern_type="resource",
            value="Microsoft.Storage/storageAccounts/blobServices",
        )
        assert _matches_resource_pattern(block, p) is True

    def test_nested_child_type_with_operation(self):
        """Pattern with ARM type + operation matches nested child resource."""
        block = self._make_block(
            "Microsoft.Storage/storageAccounts/myacct/blobServices/default", "Modify"
        )
        p = ParsedPattern(
            raw="resource: Microsoft.Storage/storageAccounts/blobServices:Modify",
            pattern_type="resource",
            value="Microsoft.Storage/storageAccounts/blobServices:Modify",
        )
        assert _matches_resource_pattern(block, p) is True

    def test_nested_child_wrong_operation_no_match(self):
        """ARM type matches but operation doesn't — should not match."""
        block = self._make_block(
            "Microsoft.Storage/storageAccounts/myacct/blobServices/default", "Create"
        )
        p = ParsedPattern(
            raw="resource: Microsoft.Storage/storageAccounts/blobServices:Modify",
            pattern_type="resource",
            value="Microsoft.Storage/storageAccounts/blobServices:Modify",
        )
        assert _matches_resource_pattern(block, p) is False

    def test_dns_zone_nested_via_arm_extraction(self):
        """DNS zone link with realistic resource names between type segments."""
        block = self._make_block(
            "Microsoft.Network/privateDnsZones/privatelink.blob.core.windows.net"
            "/virtualNetworkLinks/myVnetLink"
        )
        p = ParsedPattern(
            raw="resource: privateDnsZones/virtualNetworkLinks",
            pattern_type="resource",
            value="privateDnsZones/virtualNetworkLinks",
        )
        assert _matches_resource_pattern(block, p) is True


# ---------------------------------------------------------------------------
# Block parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseResourceBlocks:
    def test_parses_single_block(self):
        lines = [
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n",
            '      id:   "/subscriptions/123"\n',
            '      ~ properties.etag: "old" => "new"\n',
        ]
        preamble, blocks, epilogue = _parse_resource_blocks(lines)
        assert len(preamble) == 0
        assert len(blocks) == 1
        assert blocks[0].operation == "Modify"
        assert "virtualNetworks" in blocks[0].resource_type
        assert blocks[0].property_change_indices == [2]

    def test_parses_preamble(self):
        lines = [
            "Resource and property changes are indicated with these symbols:\n",
            "  - Delete\n",
            "  ~ Modify\n",
            "\n",
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n",
            '      ~ properties.etag: "old"\n',
        ]
        preamble, blocks, epilogue = _parse_resource_blocks(lines)
        assert len(preamble) == 4
        assert len(blocks) == 1

    def test_parses_epilogue(self):
        lines = [
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n",
            '      ~ properties.etag: "old"\n',
            "\n",
            "Resource changes: 1 to modify.\n",
        ]
        preamble, blocks, epilogue = _parse_resource_blocks(lines)
        assert len(blocks) == 1
        assert len(epilogue) == 1
        assert "Resource changes" in epilogue[0]

    def test_parses_multiple_blocks(self):
        lines = [
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n",
            '      ~ properties.etag: "old"\n',
            "\n",
            "  + Microsoft.Storage/storageAccounts/newstorage [2023-01-01]\n",
            '      id: "/subscriptions/123"\n',
        ]
        preamble, blocks, epilogue = _parse_resource_blocks(lines)
        assert len(blocks) == 2
        assert blocks[0].operation == "Modify"
        assert blocks[1].operation == "Create"

    def test_create_block_operation(self):
        lines = [
            "  + Microsoft.Storage/storageAccounts/newstorage [2023-01-01]\n",
            '      id: "/subscriptions/123"\n',
        ]
        _, blocks, _ = _parse_resource_blocks(lines)
        assert blocks[0].operation == "Create"

    def test_delete_block_operation(self):
        lines = [
            "  - Microsoft.Sql/servers/mydb [2023-01-01]\n",
            '      id: "/subscriptions/123"\n',
        ]
        _, blocks, _ = _parse_resource_blocks(lines)
        assert blocks[0].operation == "Delete"


# ---------------------------------------------------------------------------
# filter_whatif_text
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFilterWhatifText:
    def test_no_patterns_returns_unchanged(self):
        text = "some text\nmore lines\n"
        result, count, blocks, removed = filter_whatif_text(text, [])
        assert result == text
        assert count == 0
        assert blocks == 0
        assert removed == []

    def test_filters_matching_property_lines(self):
        text = (
            "  + Microsoft.Storage/test\n"
            "      ~ properties.etag: old => new\n"
            "      ~ properties.name: myresource\n"
        )
        patterns = [ParsedPattern(raw="etag", pattern_type="keyword", value="etag")]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 1
        assert "etag" not in result
        assert "name: myresource" in result

    def test_preserves_resource_header_lines(self):
        """Resource header lines should never be filtered."""
        text = "  + Microsoft.Storage/storageAccounts/etag-test\n"
        patterns = [ParsedPattern(raw="etag", pattern_type="keyword", value="etag")]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 0
        assert "etag-test" in result

    def test_multiple_patterns(self):
        text = (
            "  ~ Microsoft.Network/test [2022-07-01]\n"
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
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 2
        assert "name: real" in result

    def test_filters_from_noisy_fixture(self, noisy_changes_fixture):
        """Sanity check: builtin patterns filter lines from noisy fixture."""
        patterns = load_builtin_patterns()
        _, count, _, _ = filter_whatif_text(noisy_changes_fixture, patterns)
        assert count > 0  # Should filter at least some noisy lines

    def test_no_resource_headers_falls_back_to_line_filter(self):
        """Text without resource headers still filters property-change lines."""
        text = (
            "Some preamble text\n"
            "      ~ properties.etag: old => new\n"
            "      ~ properties.name: real\n"
        )
        patterns = [ParsedPattern(raw="etag", pattern_type="keyword", value="etag")]
        result, count, blocks, _ = filter_whatif_text(text, patterns)
        assert count == 1
        assert blocks == 0
        assert "etag" not in result
        assert "name: real" in result


# ---------------------------------------------------------------------------
# Block-level suppression
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBlockLevelSuppression:
    def test_modify_block_all_filtered_suppressed(self):
        """When ALL property lines in a Modify block are filtered, suppress entire block."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      id:   "/subscriptions/123"\n'
            '      name: "myvnet"\n'
            "\n"
            '      ~ properties.etag: "old" => "new"\n'
            '      ~ properties.provisioningState: "Succeeded" => "Updating"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
            ParsedPattern(
                raw="provisioningState", pattern_type="keyword", value="provisioningState"
            ),
        ]
        result, count, blocks_removed, removed = filter_whatif_text(text, patterns)
        # Both property lines removed and entire block suppressed
        assert count == 2
        assert blocks_removed == 1
        assert "virtualNetworks" not in result
        assert "myvnet" not in result
        assert "etag" not in result
        assert "provisioningState" not in result
        # Removed resource tracked for noise section
        assert len(removed) == 1
        assert removed[0]["resource_name"] == "myvnet"
        assert removed[0]["operation"] == "Modify"

    def test_modify_block_some_survive_kept(self):
        """When only some property lines in a Modify block are filtered, keep the block."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      id:   "/subscriptions/123"\n'
            "\n"
            '      ~ properties.etag: "old" => "new"\n'
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 1
        assert "virtualNetworks" in result  # Header preserved
        assert "addressSpace" in result  # Surviving property preserved
        assert "etag" not in result

    def test_create_block_never_suppressed(self):
        """Create blocks should never be auto-suppressed even if all properties filtered."""
        text = (
            "  + Microsoft.Storage/storageAccounts/newstorage [2023-01-01]\n"
            '      id:   "/subscriptions/123"\n'
            '      + properties.etag: "abc"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 1  # Only the property line removed, not the whole block
        assert "storageAccounts" in result  # Header preserved

    def test_delete_block_never_suppressed(self):
        """Delete blocks should never be auto-suppressed even if all properties filtered."""
        text = (
            "  - Microsoft.Sql/servers/mydb [2023-01-01]\n"
            '      id:   "/subscriptions/123"\n'
            '      - properties.etag: "abc"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 1
        assert "Sql/servers" in result  # Header preserved

    def test_modify_block_no_properties_not_suppressed(self):
        """A Modify block with no property-change lines should not be suppressed."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      id:   "/subscriptions/123"\n'
            '      name: "myvnet"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert count == 0
        assert "virtualNetworks" in result

    def test_preamble_preserved(self):
        """Preamble lines before first resource block should always be preserved."""
        text = (
            "Resource and property changes are indicated with these symbols:\n"
            "  - Delete\n"
            "  ~ Modify\n"
            "\n"
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert "Resource and property changes" in result

    def test_epilogue_preserved(self):
        """Epilogue lines after the last resource block should always be preserved."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
            "\n"
            "Resource changes: 1 to modify.\n"
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, _, _ = filter_whatif_text(text, patterns)
        assert "Resource changes:" in result

    def test_multiple_blocks_independent_filtering(self):
        """Each block is filtered independently; fully-filtered Modify blocks suppressed."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
            "\n"
            "  ~ Microsoft.Insights/components/myappinsights [2020-02-02]\n"
            '      ~ properties.etag: "aaa" => "bbb"\n'
            "      ~ properties.RetentionInDays: 30 => 90\n"
        )
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, count, blocks_removed, removed = filter_whatif_text(text, patterns)
        # Both etag property lines removed
        assert count == 2
        # First block (all properties filtered) is suppressed
        assert "virtualNetworks" not in result
        assert blocks_removed == 1
        assert len(removed) == 1
        assert removed[0]["resource_name"] == "myvnet"
        # Second block (has surviving property) is kept
        assert "Insights/components" in result
        assert "RetentionInDays" in result
        assert "etag" not in result


# ---------------------------------------------------------------------------
# Resource pattern filtering
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResourcePatternFiltering:
    """Resource patterns remove entire matching blocks pre-LLM."""

    def test_resource_pattern_removes_matching_block(self):
        """filter_whatif_text should remove blocks matching resource: patterns."""
        text = (
            "  ~ Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1 [2022-07-01]\n"
            '      id:   "/subscriptions/123"\n'
            "      ~ properties.registrationEnabled: true => false\n"
        )
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones/virtualNetworkLinks",
                pattern_type="resource",
                value="privateDnsZones/virtualNetworkLinks",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 1
        assert lines == 0
        assert "privateDnsZones" not in result
        assert "registrationEnabled" not in result
        assert len(removed_info) == 1
        assert removed_info[0]["resource_name"] == "link1"
        assert removed_info[0]["operation"] == "Modify"
        assert "Microsoft.Network" in removed_info[0]["resource_type"]

    def test_resource_only_patterns_removes_block(self):
        """When only resource patterns exist, matching blocks are removed."""
        text = (
            "  ~ Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      ~ properties.logAnalyticsDestinationType: "Dedicated" => ""\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 1
        assert lines == 0
        assert "diagnosticSettings" not in result
        assert removed_info[0]["resource_name"] == "diag1"
        assert removed_info[0]["resource_type"] == "Microsoft.Insights/diagnosticSettings"

    def test_mixed_resource_and_property_patterns(self):
        """Resource pattern removes its block; property pattern filters survivors."""
        text = (
            "  ~ Microsoft.Network/privateDnsZones/virtualNetworkLinks/link1 [2022-07-01]\n"
            "      ~ properties.registrationEnabled: true => false\n"
            "\n"
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.etag: "old" => "new"\n'
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones/virtualNetworkLinks",
                pattern_type="resource",
                value="privateDnsZones/virtualNetworkLinks",
            ),
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        # Resource pattern removed first block entirely
        assert blocks == 1
        assert "privateDnsZones" not in result
        assert "registrationEnabled" not in result
        # Property pattern applied on surviving block — etag line removed
        assert lines == 1
        assert "addressSpace" in result
        assert "etag" not in result

    def test_resource_pattern_removes_create_block(self):
        """Resource patterns can remove Create blocks."""
        text = (
            "  + Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      id:   "/subscriptions/123"\n'
            '      + properties.logAnalyticsDestinationType: "Dedicated"\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 1
        assert "diagnosticSettings" not in result

    def test_resource_pattern_removes_delete_block(self):
        """Resource patterns can remove Delete blocks."""
        text = (
            "  - Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      id:   "/subscriptions/123"\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 1
        assert "diagnosticSettings" not in result

    def test_operation_specific_pattern_only_removes_matching_op(self):
        """A resource:type:Modify pattern should not remove a Create block."""
        text = (
            "  + Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      id:   "/subscriptions/123"\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings:Modify",
                pattern_type="resource",
                value="diagnosticSettings:Modify",
            ),
        ]
        result, _, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 0
        assert "diagnosticSettings" in result

    def test_non_matching_blocks_preserved(self):
        """Blocks that don't match any resource pattern remain untouched."""
        text = (
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 0
        assert lines == 0
        assert "virtualNetworks" in result
        assert "addressSpace" in result

    def test_preamble_and_epilogue_preserved_when_blocks_removed(self):
        """Preamble and epilogue survive even when resource blocks are removed."""
        text = (
            "Resource and property changes are indicated with these symbols:\n"
            "  ~ Modify\n"
            "\n"
            "  ~ Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      ~ properties.logAnalyticsDestinationType: "Dedicated" => ""\n'
            "\n"
            "Resource changes: 1 to modify.\n"
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        result, _, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 1
        assert "Resource and property changes" in result
        assert "Resource changes:" in result
        assert "diagnosticSettings" not in result

    def test_all_blocks_removed_leaves_preamble_epilogue(self):
        """When all blocks are removed, only preamble/epilogue remain."""
        text = (
            "Resource and property changes are indicated with these symbols:\n"
            "  ~ Modify\n"
            "\n"
            "  ~ Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      ~ properties.logAnalyticsDestinationType: "Dedicated" => ""\n'
            "\n"
            "  ~ Microsoft.Network/privateDnsZones/privatelink/virtualNetworkLinks/link1"
            " [2022-07-01]\n"
            "      ~ properties.registrationEnabled: true => false\n"
            "\n"
            "Resource changes: 2 to modify.\n"
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
            ParsedPattern(
                raw="resource: privateDnsZones/virtualNetworkLinks",
                pattern_type="resource",
                value="privateDnsZones/virtualNetworkLinks",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 2
        assert lines == 0
        assert "Resource and property changes" in result
        assert "Resource changes:" in result
        assert "diagnosticSettings" not in result
        assert "privateDnsZones" not in result

    def test_multiple_resource_patterns_remove_multiple_blocks(self):
        """Multiple resource patterns each remove their matching blocks."""
        text = (
            "  ~ Microsoft.Insights/diagnosticSettings/diag1 [2021-05-01]\n"
            '      ~ properties.logAnalyticsDestinationType: "Dedicated" => ""\n'
            "\n"
            "  ~ Microsoft.Network/virtualNetworks/myvnet [2022-07-01]\n"
            '      ~ properties.addressSpace: "10.0.0.0/16" => "10.0.0.0/8"\n'
            "\n"
            "  ~ Microsoft.Network/privateDnsZones/privatelink/virtualNetworkLinks/link1"
            " [2022-07-01]\n"
            "      ~ properties.registrationEnabled: true => false\n"
        )
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
            ParsedPattern(
                raw="resource: privateDnsZones/virtualNetworkLinks",
                pattern_type="resource",
                value="privateDnsZones/virtualNetworkLinks",
            ),
        ]
        result, lines, blocks, removed_info = filter_whatif_text(text, patterns)
        assert blocks == 2
        assert lines == 0
        # Only the virtualNetworks block should survive
        assert "virtualNetworks" in result
        assert "addressSpace" in result
        assert "diagnosticSettings" not in result
        assert "privateDnsZones" not in result


# ---------------------------------------------------------------------------
# extract_resource_patterns
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestExtractResourcePatterns:
    def test_separates_resource_and_property(self):
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
            ParsedPattern(raw="regex: ipv6", pattern_type="regex", value="ipv6"),
        ]
        resource_pats, property_pats = extract_resource_patterns(patterns)
        assert len(resource_pats) == 1
        assert resource_pats[0].value == "diagnosticSettings"
        assert len(property_pats) == 2

    def test_empty_list(self):
        resource_pats, property_pats = extract_resource_patterns([])
        assert resource_pats == []
        assert property_pats == []

    def test_all_resource_patterns(self):
        patterns = [
            ParsedPattern(raw="resource: dns", pattern_type="resource", value="dns"),
            ParsedPattern(
                raw="resource: diag:Modify", pattern_type="resource", value="diag:Modify"
            ),
        ]
        resource_pats, property_pats = extract_resource_patterns(patterns)
        assert len(resource_pats) == 2
        assert len(property_pats) == 0

    def test_no_resource_patterns(self):
        patterns = [
            ParsedPattern(raw="etag", pattern_type="keyword", value="etag"),
            ParsedPattern(raw="fuzzy: test", pattern_type="fuzzy", value="test"),
        ]
        resource_pats, property_pats = extract_resource_patterns(patterns)
        assert len(resource_pats) == 0
        assert len(property_pats) == 2


# ---------------------------------------------------------------------------
# Post-LLM resource reclassification
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestReclassifyResourceNoise:
    def test_demotes_matching_resource(self):
        resources = [
            {
                "resource_name": "link1",
                "resource_type": "Network/privateDnsZones/virtualNetworkLinks",
                "action": "Modify",
                "confidence_level": "medium",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones/virtualNetworkLinks",
                pattern_type="resource",
                value="privateDnsZones/virtualNetworkLinks",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 1
        assert resources[0]["confidence_level"] == "low"
        assert resources[0]["confidence_reason"] == "Matched resource noise pattern"

    def test_skips_already_low_confidence(self):
        resources = [
            {
                "resource_name": "link1",
                "resource_type": "Network/privateDnsZones/virtualNetworkLinks",
                "action": "Modify",
                "confidence_level": "low",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones",
                pattern_type="resource",
                value="privateDnsZones",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 0
        assert resources[0]["confidence_level"] == "low"

    def test_skips_noise_confidence(self):
        resources = [
            {
                "resource_name": "link1",
                "resource_type": "Network/privateDnsZones",
                "action": "Modify",
                "confidence_level": "noise",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones",
                pattern_type="resource",
                value="privateDnsZones",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 0

    def test_operation_mismatch_not_demoted(self):
        resources = [
            {
                "resource_name": "link1",
                "resource_type": "Network/privateDnsZones",
                "action": "Create",
                "confidence_level": "high",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: privateDnsZones:Modify",
                pattern_type="resource",
                value="privateDnsZones:Modify",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 0
        assert resources[0]["confidence_level"] == "high"

    def test_type_only_matches_any_action(self):
        resources = [
            {
                "resource_name": "diag1",
                "resource_type": "Insights/diagnosticSettings",
                "action": "Create",
                "confidence_level": "high",
            },
            {
                "resource_name": "diag2",
                "resource_type": "Insights/diagnosticSettings",
                "action": "Modify",
                "confidence_level": "medium",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 2
        assert all(r["confidence_level"] == "low" for r in resources)

    def test_case_insensitive_type_match(self):
        resources = [
            {
                "resource_name": "link1",
                "resource_type": "Network/PrivateDnsZones/VirtualNetworkLinks",
                "action": "Modify",
                "confidence_level": "high",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: privatednszones",
                pattern_type="resource",
                value="privatednszones",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 1
        assert resources[0]["confidence_level"] == "low"

    def test_full_pattern_matches_llm_short_type(self):
        """Pattern with Microsoft. prefix matches LLM type that omits the prefix."""
        resources = [
            {
                "resource_name": "myendpoint",
                "resource_type": "Network/privateEndpoints",
                "action": "Modify",
                "confidence_level": "high",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: Microsoft.Network/privateEndpoints:Modify",
                pattern_type="resource",
                value="Microsoft.Network/privateEndpoints:Modify",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 1
        assert resources[0]["confidence_level"] == "low"

    def test_full_pattern_matches_llm_nested_short_type(self):
        """Pattern with full ARM type matches LLM nested type without prefix."""
        resources = [
            {
                "resource_name": "default",
                "resource_type": "Storage/storageAccounts/blobServices",
                "action": "Modify",
                "confidence_level": "high",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: Microsoft.Storage/storageAccounts/blobServices:Modify",
                pattern_type="resource",
                value="Microsoft.Storage/storageAccounts/blobServices:Modify",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 1
        assert resources[0]["confidence_level"] == "low"

    def test_empty_resources(self):
        patterns = [
            ParsedPattern(raw="resource: test", pattern_type="resource", value="test"),
        ]
        count = reclassify_resource_noise([], patterns)
        assert count == 0

    def test_empty_patterns(self):
        resources = [
            {
                "resource_name": "r1",
                "resource_type": "Network/test",
                "action": "Modify",
                "confidence_level": "high",
            },
        ]
        count = reclassify_resource_noise(resources, [])
        assert count == 0
        assert resources[0]["confidence_level"] == "high"

    def test_non_matching_resource_preserved(self):
        resources = [
            {
                "resource_name": "myvnet",
                "resource_type": "Network/virtualNetworks",
                "action": "Modify",
                "confidence_level": "high",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 0
        assert resources[0]["confidence_level"] == "high"

    def test_defaults_missing_confidence_to_medium(self):
        """Resources without confidence_level default to medium (eligible for demotion)."""
        resources = [
            {
                "resource_name": "diag1",
                "resource_type": "Insights/diagnosticSettings",
                "action": "Modify",
            },
        ]
        patterns = [
            ParsedPattern(
                raw="resource: diagnosticSettings",
                pattern_type="resource",
                value="diagnosticSettings",
            ),
        ]
        count = reclassify_resource_noise(resources, patterns)
        assert count == 1
        assert resources[0]["confidence_level"] == "low"


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

    def test_user_patterns_with_resource_prefix(self, tmp_path):
        pfile = tmp_path / "patterns.txt"
        pfile.write_text("resource: diagnosticSettings\nresource: privateDnsZones:Modify\n")
        patterns = load_user_patterns(str(pfile))
        assert len(patterns) == 2
        assert all(p.pattern_type == "resource" for p in patterns)


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
