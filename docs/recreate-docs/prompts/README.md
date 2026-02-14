# bicep-whatif-advisor Implementation Prompts

This directory contains comprehensive implementation prompts for recreating the bicep-whatif-advisor project from scratch. Each phase builds on the previous one, following a logical development progression.

## Implementation Phases

### Phase 1: Core Foundation
**File:** `PHASE-1-CORE.md`

**Objective:** Build the core CLI framework, input validation, and LLM provider system.

**Deliverables:**
- Project structure and packaging (`pyproject.toml`)
- Input validation module (`input.py`)
- Provider system with three backends (`providers/`)
- Basic CLI framework (`cli.py`)

**Duration:** 2-3 hours

---

### Phase 2: Prompt Engineering and Output Rendering
**File:** `PHASE-2-RENDERING.md`

**Objective:** Implement LLM prompt construction, API communication, and multi-format output rendering.

**Deliverables:**
- Prompt construction module (`prompt.py`)
- JSON response parsing (`extract_json()`)
- Output rendering (`render.py`)
  - Rich table with 85% width, ROUNDED box
  - JSON output
  - Markdown for PR comments
- End-to-end standard mode workflow

**Duration:** 3-4 hours

---

### Phase 3: CI/CD Platform Detection
**File:** `PHASE-3-CI-MODE.md`

**Objective:** Implement automatic CI/CD platform detection and git diff collection.

**Deliverables:**
- Platform detection module (`ci/platform.py`)
- Git diff collection (`ci/diff.py`)
- GitHub Actions detection with event file parsing
- Azure DevOps detection
- Smart defaults based on environment
- CLI integration with `--ci` flag

**Duration:** 2-3 hours

---

### Phase 4: Risk Assessment System
**File:** `PHASE-4-RISK.md`

**Objective:** Implement the three-bucket risk assessment system with independent threshold evaluation.

**Deliverables:**
- Risk evaluation module (`ci/risk_buckets.py`, `ci/verdict.py`)
- Three-bucket evaluation logic (drift, intent, operations)
- Independent threshold comparison
- CI mode prompts with risk assessment schema
- Exit code handling (0 = safe, 1 = unsafe)
- Risk bucket display in rendering

**Duration:** 3-4 hours

---

### Phase 5: Noise Filtering and PR Comments
**File:** `PHASE-5-NOISE.md`

**Objective:** Implement two-phase noise filtering and PR comment posting.

**Deliverables:**
- Noise filtering module (`noise_filter.py`)
  - LLM confidence scoring
  - Pattern-based fuzzy matching
- Confidence filtering (`filter_by_confidence()`)
- Re-analysis workflow for CI mode
- GitHub PR comment posting (`ci/github.py`)
- Azure DevOps PR comment posting (`ci/azdevops.py`)
- CLI integration with `--noise-filter` and `--post-comment`

**Duration:** 3-4 hours

---

### Phase 6: Testing and Documentation
**File:** `PHASE-6-TESTING.md`

**Objective:** Create comprehensive test suite and user-facing documentation.

**Deliverables:**
- Test fixtures (create_only, mixed_changes, deletes, no_changes, large_output)
- Unit tests for all modules
- Integration tests (end-to-end workflows)
- pytest configuration
- 80%+ code coverage
- README.md
- User guides (Getting Started, CI/CD Integration, Risk Assessment, CLI Reference)

**Duration:** 4-6 hours

---

## Total Estimated Time

**17-24 hours** for complete implementation (all 6 phases)

## Usage Instructions

### For AI Agents

1. **Sequential Implementation:** Start with Phase 1 and proceed through Phase 6 in order
2. **Validation:** Complete the validation checklist at the end of each phase before proceeding
3. **Context:** Each prompt references relevant specification files in `../specifications/`
4. **Testing:** Test each phase thoroughly before moving to the next

### For Human Developers

1. Each phase is self-contained with clear objectives and tasks
2. Code examples and snippets are provided throughout
3. Validation checklists ensure completeness
4. Can be implemented by multiple developers in parallel (after Phase 1)

## Dependency Graph

```
Phase 1 (Core Foundation)
    ↓
Phase 2 (Rendering) ← Must complete Phase 1
    ↓
Phase 3 (Platform Detection) ← Must complete Phases 1-2
    ↓
Phase 4 (Risk Assessment) ← Must complete Phases 1-3
    ↓
Phase 5 (Noise Filtering) ← Must complete Phases 1-4
    ↓
Phase 6 (Testing) ← Must complete Phases 1-5
```

## Key Implementation Notes

### Critical Requirements

1. **Phase 1:** Provider system must handle missing SDKs gracefully
2. **Phase 2:** Confidence scoring is included from the start (critical for Phase 5)
3. **Phase 3:** Platform detection must never fail (always return valid context)
4. **Phase 4:** Risk buckets are independent - no cascading dependencies
5. **Phase 5:** Re-analysis in CI mode is critical for clean risk assessment
6. **Phase 6:** All tests must use mocked LLM providers (no real API calls)

### Common Pitfalls to Avoid

1. **Don't skip confidence fields in Phase 2** - they're needed for Phase 5 filtering
2. **Don't couple risk buckets in Phase 4** - they must be independently configurable
3. **Don't forget re-analysis in Phase 5** - filtering requires clean risk assessment
4. **Don't require real API keys in tests** - use mocked providers

### Code Quality Standards

- Type hints for all function signatures
- Clear docstrings following Google/NumPy style
- PEP 8 compliance
- Defensive coding (validate inputs, handle errors gracefully)
- Single-purpose functions
- No external API calls in tests

## Reference Documentation

### Specification Files (in `../specifications/`)

- `00-OVERVIEW.md` - Project architecture and design
- `01-CLI-INPUT.md` - CLI and input handling
- `02-PROVIDER-SYSTEM.md` - LLM provider architecture
- `03-PROMPT-ENGINEERING.md` - Prompt construction
- `04-OUTPUT-RENDERING.md` - Output formatting
- `05-PLATFORM-DETECTION.md` - CI/CD platform detection
- `06-RISK-ASSESSMENT.md` - Three-bucket risk system
- `07-PR-COMMENTS.md` - PR comment posting
- `08-NOISE-FILTERING.md` - Noise filtering system
- `09-TESTING.md` - Testing strategy

### Example Outputs

See existing implementation in the main project directory for reference:
- `/bicep_whatif_advisor/` - Working implementation
- `/tests/` - Test examples
- `/docs/` - Documentation examples

## Support

For questions or issues during implementation:

1. Refer to the specification files for detailed requirements
2. Check the existing implementation for reference
3. Consult the validation checklists in each phase prompt
4. Review the Notes section at the end of each prompt

## License

MIT License - See main project LICENSE file
