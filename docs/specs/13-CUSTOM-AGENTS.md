# 13 — Custom Risk Assessment Agents

## Overview

Extends the CI mode risk assessment system with pluggable, markdown-based
custom agents. Teams define new risk dimensions (compliance, cost review,
naming conventions, etc.) as markdown files that plug into the existing
pipeline — no code changes required.

Custom agents are **additive** to the two built-in buckets (drift,
intent). They use the same evaluation pipeline: each agent
produces a `risk_level` (low/medium/high) with independent threshold
control.

## Agent File Format

Each agent is a `.md` file with YAML frontmatter for metadata and a
markdown body containing LLM instructions:

```markdown
---
id: compliance
display_name: Compliance Review
default_threshold: high
---

**Compliance Risk:**
Evaluate whether the deployment changes comply with organizational
policies including encryption requirements, network isolation,
and data residency.

Risk levels for compliance:
- high: Changes to encryption settings, public network access enabled,
  data residency violations, removal of compliance tags
- medium: Policy assignment changes, diagnostic settings modifications,
  new resource types not in approved list
- low: Tag changes for compliance metadata, monitoring additions,
  minor configuration updates within policy bounds
```

### Frontmatter Fields

| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| `id` | Yes | — | Unique identifier (alphanumeric, hyphens, underscores). Must not collide with built-in IDs (`drift`, `intent`, `operations`). |
| `display_name` | Yes | — | User-facing name shown in tables and PR comments. |
| `default_threshold` | No | `high` | Default threshold if no `--agent-threshold` override. Must be `low`, `medium`, or `high`. |
| `optional` | No | `false` | If `true`, agent can be conditionally skipped. |

### Markdown Body

The markdown body becomes the `prompt_instructions` for the risk bucket.
It is embedded directly into the LLM system prompt alongside the built-in
bucket instructions. Write it as clear instructions for the LLM, including
explicit risk level criteria (high/medium/low).

## CLI Interface

### New Flags

```
--agents-dir PATH       Path to directory of custom agent .md files
                        (CI mode only)

--agent-threshold ID=LEVEL
                        Set threshold for a custom agent
                        (e.g., --agent-threshold compliance=high).
                        Repeatable. Overrides default_threshold from
                        the agent file.

--skip-agent ID         Skip a custom agent by ID
                        (e.g., --skip-agent compliance). Repeatable.
                        CI mode only.
```

### Usage Examples

```bash
# Basic usage with custom agents
cat whatif.txt | bicep-whatif-advisor --ci \
  --agents-dir ./my-agents/ \
  --agent-threshold compliance=medium

# Skip a custom agent
cat whatif.txt | bicep-whatif-advisor --ci \
  --agents-dir ./my-agents/ \
  --skip-agent cost-review

# Multiple thresholds
cat whatif.txt | bicep-whatif-advisor --ci \
  --agents-dir ./my-agents/ \
  --agent-threshold compliance=medium \
  --agent-threshold cost-review=low \
  --drift-threshold high
```

## Architecture

### Data Flow

1. **CLI startup**: `--agents-dir`, `--agent-threshold`, `--skip-agent`
   parsed
2. **Agent loading**: `load_agents_from_directory()` parses `.md` files
   into `RiskBucket` instances
3. **Agent registration**: `register_agents()` adds them to global
   `RISK_BUCKETS` dict, returns list of custom agent IDs
4. **Bucket filtering**: `get_enabled_buckets()` appends custom agent
   IDs (minus skipped) after built-in buckets
5. **Prompt building**: `_build_ci_system_prompt()` iterates all enabled
   buckets — custom agents included automatically via `RISK_BUCKETS`
   lookup
6. **LLM call**: System prompt includes instructions for all enabled
   buckets; JSON schema includes `risk_assessment` entries for each
7. **Risk evaluation**: `evaluate_risk_buckets()` checks each bucket
   against its threshold (built-in or custom)
8. **Rendering**: Table/markdown renderers iterate enabled buckets and
   look up display names from `RISK_BUCKETS` — works for custom agents
   without changes

### Key Design Insight

The prompt builder (`prompt.py`) and renderers (`render.py`) require
**zero changes**. They already iterate `enabled_buckets` dynamically and
look up bucket metadata from the `RISK_BUCKETS` dict. Registering custom
agents in that dict makes them work end-to-end automatically.

### LLM Response Schema

Custom agents use the same per-bucket schema as built-in buckets:

```json
{
  "risk_assessment": {
    "compliance": {
      "risk_level": "low|medium|high",
      "concerns": ["array of specific concerns"],
      "concern_summary": "1-2 sentence summary",
      "reasoning": "explanation of risk assessment"
    }
  }
}
```

## Implementation

### New Module: `bicep_whatif_advisor/ci/agents.py`

| Function | Description |
|----------|-------------|
| `_parse_frontmatter(content)` | Splits YAML frontmatter from body using `yaml.safe_load()` |
| `parse_agent_file(file_path)` | Parses one `.md` file into a `RiskBucket` with validation |
| `load_agents_from_directory(agents_dir)` | Globs `*.md` files alphabetically, returns (successes, errors) |
| `register_agents(agents)` | Adds to `RISK_BUCKETS` dict, checks for collisions, returns IDs |
| `get_custom_agent_ids()` | Returns IDs of registered custom agents |

### Modified: `bicep_whatif_advisor/ci/buckets.py`

- Add `default_threshold: str = "high"` and `custom: bool = False` to
  `RiskBucket` dataclass (backwards-compatible defaults)
- Extend `get_enabled_buckets()` with `custom_agent_ids` and
  `skip_agents` parameters

### Modified: `bicep_whatif_advisor/ci/risk_buckets.py`

- Add `custom_thresholds: Dict[str, str] = None` parameter to
  `evaluate_risk_buckets()`
- Merge custom thresholds into threshold map; fall back to bucket's
  `default_threshold` for agents without explicit threshold

### Modified: `bicep_whatif_advisor/cli.py`

- Three new click options: `--agents-dir`, `--agent-threshold`,
  `--skip-agent`
- Agent loading/registration after CI mode detection
- Threshold parsing and forwarding to `evaluate_risk_buckets()`

### Modified: `pyproject.toml`

- Add `pyyaml>=6.0` to core dependencies

### Unchanged (zero modifications needed)

- `bicep_whatif_advisor/prompt.py` — already dynamic
- `bicep_whatif_advisor/render.py` — already dynamic
- `bicep_whatif_advisor/ci/verdict.py` — already dynamic

## Constraints and Validation

- Custom agent IDs must not collide with built-in IDs
- Custom agent IDs must contain only alphanumeric chars, hyphens,
  underscores
- At least one bucket (built-in or custom) must be enabled in CI mode
- Invalid agent files produce warnings but don't block execution
  (partial loading)
- `--agents-dir` without `--ci` emits a warning and is ignored

## Testing

### New Test Files

- `tests/test_agents.py` — Unit tests for parsing, loading, registration
- `tests/test_agents_integration.py` — End-to-end CLI tests with custom
  agents

### Extended Test Files

- `tests/test_buckets.py` — Tests for new `get_enabled_buckets()` params
- `tests/test_risk_buckets.py` — Tests for `custom_thresholds` and
  `default_threshold` fallback

### Test Isolation

Tests that register custom agents use an `autouse` fixture that saves and
restores `RISK_BUCKETS` state to prevent test pollution.

## Dependency

- `pyyaml>=6.0` — Reliable YAML frontmatter parsing. Lightweight with
  no transitive dependencies.
