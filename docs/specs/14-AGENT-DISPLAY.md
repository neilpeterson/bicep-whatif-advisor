# Spec 14: Per-Agent Collapsible Detail Sections in PR Comments

## Context

Custom agents are implemented and working — they appear as rows in the risk assessment table in PR comments. However, their results are disconnected: the summary/reasoning don't reference specific resources, and there's no way to expand an agent's findings for details.

This spec adds a `display` field to agent frontmatter that controls how each agent's detailed findings render in a collapsible `<details>` section in the PR comment. Built-in buckets (drift, intent) remain first-class — table rows only, no collapsibles.

## Design

- All buckets (built-in + custom) stay in the unified risk assessment table
- Each custom agent gets a collapsible `<details>` section after the resource/noise sections
- The `display` frontmatter field controls what renders inside each collapsible
- An `icon` frontmatter field sets the emoji in the collapsible header

### Display Modes

| Mode | Schema | Renders As |
|------|--------|------------|
| `summary` (default) | Existing `reasoning` field only | Text paragraph |
| `table` | `findings` array added to schema | Resource / Issue / Recommendation table |
| `list` | `findings` array added to schema | Bullet list with recommendations |

### Findings Schema (for `table` and `list` modes)

```json
"findings": [
  {
    "resource": "storageaccount1",
    "issue": "No CAF prefix, missing environment",
    "recommendation": "Use st<workload><env> (e.g. stnavigatorprod001)"
  }
]
```

Fixed schema — agent prompt instructions guide the LLM on what to populate. Falls back to `reasoning` text when `findings` is empty.

## PR Comment Layout

```
| Risk Assessment        | Risk Level | Key Concerns        |  <- all buckets
|------------------------|------------|---------------------|
| Infrastructure Drift   | High       | ...                 |
| PR Intent Alignment    | High       | ...                 |
| Cost Impact            | Low        | None                |
| Naming Convention      | Medium     | Storage account...  |

**Summary:** ...

<details>View changed resources (3 High Confidence)</details>
<details>Potential Azure What-If Noise (7 Low Confidence)</details>

<details>Cost Impact Details</details>              <- display: summary
  Minor configuration changes with negligible cost impact...

<details>Naming Convention Details</details>        <- display: table
  | Resource | Issue | Recommendation |
  | storageaccount1 | No CAF prefix... | st<workload><env> |

<details>Raw What-If Output</details>

### Verdict: UNSAFE
```

## Files to Modify

### 1. `bicep_whatif_advisor/ci/buckets.py` — Add fields to RiskBucket

Add two fields with defaults (backwards-compatible):

```python
display: str = "summary"   # "summary", "table", or "list"
icon: str = ""             # emoji for collapsible header
```

### 2. `bicep_whatif_advisor/ci/agents.py` — Parse new frontmatter fields

- Add `_VALID_DISPLAY_MODES = {"summary", "table", "list"}` constant
- In `parse_agent_file()`: parse and validate `display` (default: `"summary"`) and `icon` (default: `""`)
- Pass both to `RiskBucket` constructor

### 3. `bicep_whatif_advisor/prompt.py` — Add findings to LLM schema

In `_build_ci_system_prompt()` (~line 130-139):
- For custom agents with `display` in `("table", "list")`: append `"findings"` array to the bucket's JSON schema
- Add LLM instructions after bucket prompt explaining the findings fields
- Built-in buckets and `summary` display agents: unchanged (no findings)

### 4. `bicep_whatif_advisor/render.py` — Render agent collapsible sections

Add `_render_agent_detail_sections(data, platform)` helper:
- Iterates `_enabled_buckets`, skips non-custom buckets
- For `summary`: renders `reasoning` text
- For `table`: renders findings as `| Resource | Issue | Recommendation |` table
- For `list`: renders findings as bullet list with recommendations
- Falls back to `reasoning` when `findings` is empty
- Handles ADO `<br>` spacing

Insert call in `render_markdown()` between the noise section (line 476) and raw What-If section (line 478).

### 5. Update agent files — Add display/icon to existing agents

`tests/agents/naming.md`:
```yaml
display: table
icon: "📛"
```

`tests/agents/cost.md`:
```yaml
display: summary
icon: "💰"
```

### 6. Tests

**`tests/test_agents.py`** — Add to `TestParseAgentFile`:
- `test_display_field_defaults_to_summary`
- `test_display_field_table` / `test_display_field_list`
- `test_invalid_display_raises`
- `test_icon_field` / `test_icon_default_empty`

**`tests/test_prompt.py`** — Add:
- `test_custom_agent_table_display_has_findings_in_schema`
- `test_builtin_bucket_no_findings_in_schema`
- `test_summary_display_no_findings_in_schema`

**`tests/test_render.py`** — Add:
- `test_custom_agent_summary_collapsible`
- `test_custom_agent_table_collapsible`
- `test_custom_agent_list_collapsible`
- `test_builtin_buckets_no_collapsible`
- `test_table_display_empty_findings_falls_back_to_reasoning`

**`tests/test_agents_integration.py`** — Add:
- `test_agent_table_display_findings_in_markdown_output`

## Files NOT Modified

- **cli.py** — findings flow through existing data dict, no changes needed
- **risk_buckets.py** — findings are display-only, don't affect threshold evaluation
- **verdict.py** — unchanged

## Implementation Order

1. `buckets.py` — add `display` and `icon` fields
2. `agents.py` — parse/validate new frontmatter fields
3. `prompt.py` — conditional `findings` in schema
4. `render.py` — new helper + integrate into `render_markdown()`
5. Update `tests/agents/naming.md` and `tests/agents/cost.md`
6. `tests/test_agents.py` — frontmatter field tests
7. `tests/test_prompt.py` — schema generation tests
8. `tests/test_render.py` — collapsible rendering tests
9. `tests/test_agents_integration.py` — end-to-end test

## Verification

1. `pytest` — all existing 343+ tests still pass
2. New tests pass for all three display modes
3. `ruff check . && ruff format .` — lint clean
4. Manual test: `cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --ci --agents-dir ./tests/agents/ --format markdown` — verify collapsible sections appear with correct display modes
