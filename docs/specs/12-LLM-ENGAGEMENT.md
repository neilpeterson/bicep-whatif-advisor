# 12 - LLM Engagement Model

## Purpose

This spec describes exactly when, why, and how the tool calls an LLM. It covers the full lifecycle of each LLM interaction — what triggers the call, what inputs are sent, what response is expected, and how the response is processed. Anyone integrating, auditing, or extending this tool should read this spec to understand the LLM engagement model.

**Primary files:**
- `bicep_whatif_advisor/cli.py` — Orchestrates all LLM calls
- `bicep_whatif_advisor/prompt.py` — Constructs system and user prompts
- `bicep_whatif_advisor/providers/` — Executes the actual API calls

## How Many LLM Calls?

| Mode | Calls | Condition |
|------|-------|-----------|
| Standard | 1 | Always |
| CI (no noise filtered) | 1 | No low-confidence resources after filtering |
| CI (some noise filtered) | 2 | At least one resource demoted to low confidence, but not all |
| CI (all noise filtered) | 1 | Every resource demoted — risk set to low programmatically, no second call |

Custom agents (`--agents-dir`) do **not** add extra LLM calls. They are injected into the same prompt as additional risk bucket instructions, and the LLM evaluates all buckets in a single response.

## Call 1: Primary Analysis

### Trigger

Every invocation of the tool makes this call. It is the core analysis step.

### What Happens Before the Call

Before the LLM is engaged, the following pipeline runs:

1. **Input validation** (`input.py`): Reads stdin, checks for What-If markers, truncates at 100K characters.
2. **Pre-LLM noise filtering** (`noise_filter.py`): Strips known-noisy property lines and entire resource blocks from the What-If text using keyword, regex, and fuzzy pattern matching. This reduces token usage and prevents noise from influencing risk assessment.
3. **Git diff collection** (CI mode only, `ci/diff.py`): Runs `git diff` to capture code changes.
4. **Provider initialization** (`providers/__init__.py`): Instantiates the selected LLM provider (Anthropic, Azure OpenAI, or Ollama).

### Prompt Construction

The tool builds two prompts via `prompt.py`:

**System prompt** — defines the LLM's role, response schema, and evaluation criteria:

| Mode | Role | Schema Includes |
|------|------|-----------------|
| Standard | "Azure infrastructure expert" | `resources[]`, `overall_summary` |
| Standard + verbose | Same | Adds `changes[]` field for Modify actions |
| CI | "Azure infrastructure deployment safety reviewer" | `resources[]`, `overall_summary`, `risk_assessment{}`, `verdict{}` |

In CI mode, the system prompt dynamically includes:
- **Risk bucket instructions** for each enabled bucket (drift, intent, and any custom agents)
- **Risk assessment schema** with keys for each enabled bucket
- **Verdict schema** with `highest_risk_bucket` options matching enabled buckets
- **Custom agent instructions** from markdown file bodies, injected as additional risk bucket sections
- **Findings schema** for agents with `display: table` or `display: list` (includes custom column definitions)

**User prompt** — contains the actual data to analyze:

| Section | Tag | Included When |
|---------|-----|---------------|
| What-If output | `<whatif_output>` | Always (required) |
| Git diff | `<code_diff>` | CI mode with diff available |
| Bicep source | `<bicep_source>` | CI mode with `--bicep-dir` |
| PR metadata | `<pull_request_intent>` | CI mode with PR title/description |

Standard mode sends only the What-If output. CI mode wraps all sections in XML-style tags to provide clear boundaries for the LLM.

### The API Call

```
cli.py:584 → llm_provider.complete(system_prompt, user_prompt)
```

All providers use **temperature 0** for deterministic output. Each provider implements retry logic: 2 attempts with a 1-second delay between them for retryable errors (network/server). Rate limit errors fail immediately.

| Provider | API | Max Tokens | Timeout |
|----------|-----|------------|---------|
| Anthropic | `messages.create()` | 4096 | SDK default |
| Azure OpenAI | `chat.completions.create()` | Not specified | SDK default |
| Ollama | `POST /api/generate` | Not specified | 120 seconds |

### Response Processing

After the LLM responds, the following steps occur in sequence:

#### Step 1: JSON Extraction (`extract_json()`)

The tool attempts to parse the response as JSON. If that fails, it searches for the first balanced `{...}` block in the response text. This handles cases where the LLM wraps JSON in markdown code fences or adds preamble text.

If no valid JSON is found, the tool exits with code 1.

#### Step 2: Field Validation

Missing required fields are handled gracefully:
- Missing `resources` → defaults to empty array (with warning)
- Missing `overall_summary` → defaults to "No summary provided." (with warning)
- Missing `confidence_level` on a resource → defaults to `"medium"`
- Missing `confidence_reason` on a resource → defaults to placeholder text

#### Step 3: Post-LLM Resource Noise Reclassification

If `resource:` noise patterns are configured, the tool scans the LLM's resource list and demotes matching resources to `confidence_level: "low"`. This catches resources the LLM rated as medium/high confidence but that match known noise patterns by resource type.

#### Step 4: Pre-Filtered Resource Injection

Resources that were completely removed during pre-LLM noise filtering (entire resource blocks stripped) are injected back as synthetic low-confidence entries. This ensures they appear in the "Potential Noise" display section even though the LLM never saw them.

#### Step 5: Confidence Splitting (`filter_by_confidence()`)

All resources are split into two groups:
- **High confidence** (medium + high `confidence_level`): Used for analysis, risk assessment, and verdict
- **Low confidence** (low `confidence_level`): Displayed separately as "Potential Noise"

This split preserves the original `risk_assessment` and `verdict` from the LLM in the high-confidence data.

## Call 2: Risk Recalculation (CI Mode Only)

### Trigger

This call is made only when **all three** conditions are true:
1. Running in CI mode (`--ci`)
2. At least one resource was demoted to low confidence (noise filtering removed resources)
3. At least one resource remains at high confidence (not all filtered)

### Why a Second Call?

The first LLM call generated its `risk_assessment` and `verdict` based on **all** resources, including ones later identified as noise. If noise-filtered resources were driving the risk assessment (e.g., a drifting resource that turns out to be Azure noise), the risk levels would be inaccurate. The second call re-evaluates risk using only the high-confidence resources.

### What's Different

The second call uses the **same prompt structure** as the first but is constructed with:
- The same `enabled_buckets`, `pr_title`, `pr_description`, and `verbose` settings
- The same What-If content, diff, and Bicep source
- The same system prompt (rebuilt with identical parameters)

The key difference is conceptual: the What-If content was already noise-filtered before Call 1, and the resource list from Call 1 has now been confidence-split. The second call re-prompts the LLM to produce a fresh `risk_assessment` based on the cleaned input.

```
cli.py:728 → llm_provider.complete(filtered_system_prompt, filtered_user_prompt)
```

### Response Merging

The second call's response is merged into the existing high-confidence data:
- `risk_assessment` buckets from the second call **update** (not replace) the existing assessment. Buckets the LLM omitted in re-analysis keep their original values.
- `verdict` from the second call **replaces** the original verdict.

If the second call fails to return valid JSON, the tool logs a warning and falls back to the original risk assessment from Call 1.

### Special Case: All Resources Filtered

When noise filtering removes **every** resource, no second LLM call is made. Instead, the tool programmatically sets:
- All enabled risk buckets to `risk_level: "low"` with empty concerns
- Verdict to `safe: true` with reasoning explaining that all changes were identified as noise

This avoids wasting an LLM call when there's nothing meaningful to evaluate.

## Post-LLM Processing (Both Calls)

After all LLM calls complete, the following steps apply to the final high-confidence data:

### Bucket Backfill

The LLM may omit custom agent buckets from `risk_assessment` even when the schema requests them. The tool backfills any missing bucket with a default low-risk entry:

```python
{
    "risk_level": "low",
    "concerns": [],
    "concern_summary": "None",
    "reasoning": "No assessment returned by LLM"
}
```

### Threshold Evaluation

In CI mode, the tool's own threshold logic (`ci/risk_buckets.py`) evaluates the final `risk_assessment` against configured thresholds — it does **not** trust the LLM's `verdict.safe` field. The LLM's verdict reasoning is preserved, but `safe`, `verdict_status`, `highest_risk_bucket`, and `overall_risk_level` are all recomputed by the tool.

This means the LLM determines **risk levels**, but the tool determines the **pass/fail decision**.

### Exit Code Decision

| Verdict Status | Exit Code | Meaning |
|---------------|-----------|---------|
| `safe` | 0 | No buckets exceeded thresholds |
| `review` | 0 | Only `review_only` agents flagged concerns |
| `unsafe` | 2 | At least one blocking bucket exceeded its threshold |
| (with `--no-block`) | 0 | Always 0, regardless of verdict |

## Data Flow Summary

```
┌──────────────────────────────────────────────────────────────────┐
│                        INPUT PIPELINE                            │
├──────────────────────────────────────────────────────────────────┤
│  stdin → validate → pre-LLM noise filter → cleaned What-If text  │
│  git diff → diff content (CI only)                               │
│  PR metadata → title + description (CI only)                     │
│  agent .md files → additional risk bucket instructions (CI only) │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                     LLM CALL 1 (always)                          │
├──────────────────────────────────────────────────────────────────┤
│  System prompt: role + schema + bucket instructions + confidence │
│  User prompt:   What-If + diff + Bicep + PR intent               │
│                                                                  │
│  → LLM returns JSON with resources, risk_assessment, verdict     │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                    RESPONSE PROCESSING                           │
├──────────────────────────────────────────────────────────────────┤
│  1. Extract JSON from response                                   │
│  2. Validate/default missing fields                              │
│  3. Post-LLM noise reclassification (resource: patterns)         │
│  4. Inject pre-filtered resource blocks as low-confidence        │
│  5. Split into high-confidence vs low-confidence                 │
└────────────────────────────┬─────────────────────────────────────┘
                             │
                    ┌────────┴────────┐
                    │  CI mode AND    │
                    │  noise filtered │
                    │  (not all)?     │
                    └───┬─────────┬───┘
                    Yes │         │ No
                        ▼         │
┌───────────────────────────┐     │
│   LLM CALL 2 (optional)   │     │
├───────────────────────────┤     │
│  Same prompt structure    │     │
│  Re-evaluates risk with   │     │
│  high-confidence resources│     │
│                           │     │
│  → Merges risk_assessment │     │
│  → Replaces verdict       │     │
└─────────────┬─────────────┘     │
              │                   │
              ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    POST-LLM PROCESSING                           │
├──────────────────────────────────────────────────────────────────┤
│  1. Backfill missing risk buckets                                │
│  2. Threshold evaluation (tool overrides LLM verdict)            │
│  3. Compute final verdict_status: safe / review / unsafe         │
│  4. Render output (table / JSON / markdown)                      │
│  5. Post PR comment (optional, CI mode)                          │
│  6. Exit with code 0, 1, or 2                                    │ 
└──────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### Why Temperature 0?

All providers use `temperature=0` to produce deterministic output. In a CI/CD gate, the same input should produce the same verdict. Non-determinism in risk assessment would erode trust in the tool.

### Why Not One Call Per Bucket?

Custom agents are evaluated in the same LLM call as built-in buckets rather than making separate calls per agent. This keeps latency constant regardless of agent count and allows the LLM to reason about cross-cutting concerns.

Trade-off: A single call with many agents produces a larger prompt and response, which could increase token costs and risk hitting output token limits.

### Why Recompute the Verdict?

The LLM produces a `verdict.safe` field, but the tool ignores it and recomputes the verdict using its own threshold logic. This separation ensures:
- Thresholds are applied deterministically (not subject to LLM interpretation)
- Users can tune thresholds without changing LLM behavior
- The tool never blocks a deployment based solely on LLM judgment

### Why Two Calls Instead of Re-prompting With Filtered Resources?

The second call exists because the LLM's risk assessment from Call 1 was based on all resources, including ones later classified as noise. Rather than asking the LLM to "ignore these resources," the tool re-sends the full prompt context and lets the LLM produce a clean assessment. This avoids complex instructions about which resources to skip and produces more reliable results.

## Related Specs

- [03-PROVIDER-SYSTEM.md](03-PROVIDER-SYSTEM.md) — Provider interface, retry logic, API parameters
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) — Prompt construction details, schema definitions
- [06-NOISE-FILTERING.md](06-NOISE-FILTERING.md) — Pre-LLM and post-LLM noise filtering
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) — Threshold evaluation and verdict logic
- [13-CUSTOM-AGENTS.md](13-CUSTOM-AGENTS.md) — How agent markdown files become risk buckets
