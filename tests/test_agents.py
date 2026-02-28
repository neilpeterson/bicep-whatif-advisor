"""Tests for bicep_whatif_advisor.ci.agents module."""

import pytest

from bicep_whatif_advisor.ci.agents import (
    _parse_frontmatter,
    _slugify,
    get_custom_agent_ids,
    load_agents_from_directory,
    parse_agent_file,
    register_agents,
)
from bicep_whatif_advisor.ci.buckets import (
    RISK_BUCKETS,
    RiskBucket,
    get_bucket,
)

# -------------------------------------------------------------------
# _parse_frontmatter
# -------------------------------------------------------------------


@pytest.mark.unit
class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        content = (
            "---\nid: compliance\ndisplay_name: Compliance\n"
            "default_threshold: medium\n---\nBody here."
        )
        metadata, body = _parse_frontmatter(content)
        assert metadata["id"] == "compliance"
        assert metadata["display_name"] == "Compliance"
        assert metadata["default_threshold"] == "medium"
        assert "Body here." in body

    def test_missing_opening_delimiter(self):
        with pytest.raises(ValueError, match="frontmatter"):
            _parse_frontmatter("no frontmatter here")

    def test_missing_closing_delimiter(self):
        with pytest.raises(ValueError, match="frontmatter"):
            _parse_frontmatter("---\nid: test\n")

    def test_empty_body(self):
        content = "---\nid: test\ndisplay_name: Test\n---\n"
        metadata, body = _parse_frontmatter(content)
        assert body.strip() == ""

    def test_multiline_body_preserved(self):
        content = "---\nid: test\ndisplay_name: Test\n---\nLine 1\nLine 2\nLine 3"
        _, body = _parse_frontmatter(content)
        assert "Line 1" in body
        assert "Line 2" in body
        assert "Line 3" in body

    def test_invalid_yaml_raises(self):
        content = "---\n: invalid yaml [\n---\nBody"
        with pytest.raises(ValueError):
            _parse_frontmatter(content)


# -------------------------------------------------------------------
# parse_agent_file
# -------------------------------------------------------------------


@pytest.mark.unit
class TestParseAgentFile:
    def test_valid_agent_file(self, tmp_path):
        agent_file = tmp_path / "compliance.md"
        agent_file.write_text(
            "---\nid: compliance\n"
            "display_name: Compliance Review\n"
            "default_threshold: medium\n---\n"
            "**Compliance Risk:**\n"
            "Review changes for compliance violations.\n"
        )
        bucket = parse_agent_file(agent_file)
        assert bucket.id == "compliance"
        assert bucket.display_name == "Compliance Review"
        assert bucket.default_threshold == "medium"
        assert bucket.custom is True
        assert "Compliance Risk" in bucket.prompt_instructions

    def test_missing_id_raises(self, tmp_path):
        agent_file = tmp_path / "bad.md"
        agent_file.write_text("---\ndisplay_name: Test\n---\nBody")
        with pytest.raises(ValueError, match="id"):
            parse_agent_file(agent_file)

    def test_missing_display_name_raises(self, tmp_path):
        agent_file = tmp_path / "bad.md"
        agent_file.write_text("---\nid: test\n---\nBody")
        with pytest.raises(ValueError, match="display_name"):
            parse_agent_file(agent_file)

    def test_builtin_id_collision_raises(self, tmp_path):
        agent_file = tmp_path / "bad.md"
        agent_file.write_text("---\nid: drift\ndisplay_name: X\n---\nBody")
        with pytest.raises(ValueError, match="built-in"):
            parse_agent_file(agent_file)

    def test_invalid_threshold_raises(self, tmp_path):
        agent_file = tmp_path / "bad.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: X\ndefault_threshold: extreme\n---\nBody"
        )
        with pytest.raises(ValueError, match="threshold"):
            parse_agent_file(agent_file)

    def test_default_threshold_defaults_to_high(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.default_threshold == "high"

    def test_optional_field(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\noptional: true\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.optional is True

    def test_invalid_id_characters_raises(self, tmp_path):
        agent_file = tmp_path / "bad.md"
        agent_file.write_text("---\nid: 'invalid id!'\ndisplay_name: X\n---\nBody")
        with pytest.raises(ValueError, match="invalid characters"):
            parse_agent_file(agent_file)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_agent_file(tmp_path / "nonexistent.md")

    def test_hyphen_and_underscore_in_id(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: cost-review_v2\ndisplay_name: Cost Review\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.id == "cost-review_v2"

    def test_display_field_defaults_to_summary(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.display == "summary"

    def test_display_field_table(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\ndisplay: table\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.display == "table"

    def test_display_field_list(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\ndisplay: list\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.display == "list"

    def test_invalid_display_raises(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\ndisplay: chart\n---\nBody")
        with pytest.raises(ValueError, match="display"):
            parse_agent_file(agent_file)

    def test_icon_field(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text('---\nid: test\ndisplay_name: Test\nicon: "\U0001f4b0"\n---\nBody')
        bucket = parse_agent_file(agent_file)
        assert bucket.icon == "\U0001f4b0"

    def test_icon_default_empty(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.icon == ""

    def test_enabled_true_by_default(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket is not None

    def test_enabled_false_returns_none(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\nenabled: false\n---\nBody")
        result = parse_agent_file(agent_file)
        assert result is None

    def test_enabled_true_explicit(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\nenabled: true\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket is not None
        assert bucket.id == "test"


# -------------------------------------------------------------------
# load_agents_from_directory
# -------------------------------------------------------------------


@pytest.mark.unit
class TestLoadAgentsFromDirectory:
    def test_loads_multiple_agents(self, tmp_path):
        (tmp_path / "a.md").write_text("---\nid: agent_a\ndisplay_name: A\n---\nA")
        (tmp_path / "b.md").write_text("---\nid: agent_b\ndisplay_name: B\n---\nB")
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert len(agents) == 2
        assert len(errors) == 0

    def test_skips_disabled_agents(self, tmp_path):
        (tmp_path / "a.md").write_text("---\nid: agent_a\ndisplay_name: A\n---\nA")
        (tmp_path / "b.md").write_text("---\nid: agent_b\ndisplay_name: B\nenabled: false\n---\nB")
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert len(agents) == 1
        assert agents[0].id == "agent_a"
        assert len(errors) == 0

    def test_skips_non_md_files(self, tmp_path):
        (tmp_path / "readme.txt").write_text("not an agent")
        (tmp_path / "agent.md").write_text("---\nid: agent\ndisplay_name: A\n---\nBody")
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert len(agents) == 1

    def test_collects_errors_for_invalid_files(self, tmp_path):
        (tmp_path / "good.md").write_text("---\nid: good\ndisplay_name: Good\n---\nBody")
        (tmp_path / "bad.md").write_text("no frontmatter")
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert len(agents) == 1
        assert len(errors) == 1

    def test_nonexistent_directory(self):
        agents, errors = load_agents_from_directory("/nonexistent/dir")
        assert len(agents) == 0
        assert len(errors) == 1

    def test_empty_directory(self, tmp_path):
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert len(agents) == 0
        assert len(errors) == 0

    def test_alphabetical_ordering(self, tmp_path):
        (tmp_path / "z_agent.md").write_text("---\nid: z_agent\ndisplay_name: Z\n---\nBody")
        (tmp_path / "a_agent.md").write_text("---\nid: a_agent\ndisplay_name: A\n---\nBody")
        agents, errors = load_agents_from_directory(str(tmp_path))
        assert agents[0].id == "a_agent"
        assert agents[1].id == "z_agent"

    def test_not_a_directory(self, tmp_path):
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("content")
        agents, errors = load_agents_from_directory(str(file_path))
        assert len(agents) == 0
        assert len(errors) == 1
        assert "not a directory" in errors[0]


# -------------------------------------------------------------------
# register_agents
# -------------------------------------------------------------------


@pytest.mark.unit
class TestRegisterAgents:
    def test_registers_in_global_registry(self):
        bucket = RiskBucket(
            id="test_custom",
            display_name="Test Custom",
            description="Test",
            prompt_instructions="Do test things",
            custom=True,
        )
        ids = register_agents([bucket])
        assert "test_custom" in ids
        assert "test_custom" in RISK_BUCKETS
        assert get_bucket("test_custom") is not None

    def test_builtin_collision_raises(self):
        bucket = RiskBucket(
            id="drift",
            display_name="Fake Drift",
            description="",
            prompt_instructions="",
            custom=True,
        )
        with pytest.raises(ValueError, match="built-in"):
            register_agents([bucket])

    def test_duplicate_custom_ids_raises(self):
        b1 = RiskBucket(
            id="dup",
            display_name="Dup1",
            description="",
            prompt_instructions="",
            custom=True,
        )
        b2 = RiskBucket(
            id="dup",
            display_name="Dup2",
            description="",
            prompt_instructions="",
            custom=True,
        )
        with pytest.raises(ValueError, match="[Dd]uplicate"):
            register_agents([b1, b2])

    def test_returns_registered_ids(self):
        b1 = RiskBucket(
            id="custom_a",
            display_name="A",
            description="",
            prompt_instructions="",
            custom=True,
        )
        b2 = RiskBucket(
            id="custom_b",
            display_name="B",
            description="",
            prompt_instructions="",
            custom=True,
        )
        ids = register_agents([b1, b2])
        assert ids == ["custom_a", "custom_b"]


# -------------------------------------------------------------------
# get_custom_agent_ids
# -------------------------------------------------------------------


@pytest.mark.unit
class TestGetCustomAgentIds:
    def test_returns_only_custom_ids(self):
        bucket = RiskBucket(
            id="test_get_ids",
            display_name="Test",
            description="",
            prompt_instructions="",
            custom=True,
        )
        RISK_BUCKETS["test_get_ids"] = bucket
        ids = get_custom_agent_ids()
        assert "test_get_ids" in ids
        assert "drift" not in ids
        assert "intent" not in ids

    def test_empty_when_no_custom(self):
        ids = get_custom_agent_ids()
        assert ids == []


# -------------------------------------------------------------------
# _slugify
# -------------------------------------------------------------------


@pytest.mark.unit
class TestSlugify:
    def test_basic_name(self):
        assert _slugify("Resource") == "resource"

    def test_multi_word(self):
        assert _slugify("SFI ID and Name") == "sfi_id_and_name"

    def test_special_characters(self):
        assert _slugify("Compliance Status") == "compliance_status"

    def test_consecutive_specials_collapsed(self):
        assert _slugify("a--b  c") == "a_b_c"

    def test_leading_trailing_stripped(self):
        assert _slugify(" foo ") == "foo"

    def test_mixed_case(self):
        assert _slugify("Applicable") == "applicable"

    def test_numbers_preserved(self):
        assert _slugify("SFI-ID4.2.2") == "sfi_id4_2_2"


# -------------------------------------------------------------------
# Column parsing in parse_agent_file
# -------------------------------------------------------------------


@pytest.mark.unit
class TestAgentColumns:
    def test_columns_parsed(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: table\n"
            "columns:\n"
            "  - name: SFI ID and Name\n"
            "    description: taken from check title\n"
            "  - name: Compliance Status\n"
            "    description: compliant or non-compliant\n"
            "---\nBody"
        )
        bucket = parse_agent_file(agent_file)
        assert bucket.columns is not None
        assert len(bucket.columns) == 2
        assert bucket.columns[0]["name"] == "SFI ID and Name"
        assert bucket.columns[0]["key"] == "sfi_id_and_name"
        assert bucket.columns[0]["description"] == "taken from check title"
        assert bucket.columns[1]["key"] == "compliance_status"

    def test_columns_none_when_not_specified(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text("---\nid: test\ndisplay_name: Test\ndisplay: table\n---\nBody")
        bucket = parse_agent_file(agent_file)
        assert bucket.columns is None

    def test_columns_description_defaults_to_name(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: table\n"
            "columns:\n"
            "  - name: Resource\n"
            "---\nBody"
        )
        bucket = parse_agent_file(agent_file)
        assert bucket.columns[0]["description"] == "Resource"

    def test_duplicate_column_key_raises(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: table\n"
            "columns:\n"
            "  - name: Foo Bar\n"
            "  - name: Foo-Bar\n"
            "---\nBody"
        )
        with pytest.raises(ValueError, match="duplicate column key"):
            parse_agent_file(agent_file)

    def test_column_missing_name_raises(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: table\n"
            "columns:\n"
            "  - description: no name here\n"
            "---\nBody"
        )
        with pytest.raises(ValueError, match="missing required 'name'"):
            parse_agent_file(agent_file)

    def test_columns_not_a_list_raises(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: table\ncolumns: not-a-list\n---\nBody"
        )
        with pytest.raises(ValueError, match="must be a list"):
            parse_agent_file(agent_file)

    def test_columns_with_summary_display_warns(self, tmp_path):
        agent_file = tmp_path / "test.md"
        agent_file.write_text(
            "---\nid: test\ndisplay_name: Test\ndisplay: summary\n"
            "columns:\n"
            "  - name: Resource\n"
            "---\nBody"
        )
        import warnings

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            bucket = parse_agent_file(agent_file)
            assert bucket.columns is not None
            assert len(w) == 1
            assert "columns only apply to table/list" in str(w[0].message)

    def test_sfi_infra_fixture_has_columns(self):
        """The sfi-infra.md fixture should parse with custom columns."""
        from pathlib import Path

        fixture = Path(__file__).parent / "agents" / "sfi-infra.md"
        bucket = parse_agent_file(fixture)
        assert bucket.columns is not None
        assert len(bucket.columns) == 3
        assert bucket.columns[0]["key"] == "sfi_id_and_name"
        assert bucket.columns[1]["key"] == "compliance_status"
        assert bucket.columns[2]["key"] == "applicable"
