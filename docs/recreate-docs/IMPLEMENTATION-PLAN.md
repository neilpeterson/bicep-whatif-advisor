# Implementation Plan: bicep-whatif-advisor Recreation

## Overview

This plan provides a step-by-step execution strategy for recreating the `bicep-whatif-advisor` project from scratch using AI agents. The implementation is divided into 6 phases, each building on the previous phase.

## Prerequisites

- Python 3.8+ environment
- Git repository initialized
- Access to Anthropic API (for testing)
- Azure CLI installed (for integration testing)
- Familiarity with Python packaging (setuptools)

## Development Phases

### Phase 1: Core Foundation (4-6 hours)

**Goal:** Create basic CLI structure, input handling, and provider system

**Components:**
- Project structure and packaging (pyproject.toml)
- CLI framework with Click
- Input validation (stdin reading, What-If detection)
- Provider base class and registry
- All three LLM providers (Anthropic, Azure OpenAI, Ollama)

**Deliverables:**
- [ ] `pyproject.toml` with dependencies
- [ ] `bicep_whatif_advisor/__init__.py` with version
- [ ] `bicep_whatif_advisor/cli.py` with basic command structure
- [ ] `bicep_whatif_advisor/input.py` with validation
- [ ] `bicep_whatif_advisor/providers/__init__.py` with base class
- [ ] `bicep_whatif_advisor/providers/anthropic.py`
- [ ] `bicep_whatif_advisor/providers/azure_openai.py`
- [ ] `bicep_whatif_advisor/providers/ollama.py`

**Validation:**
```bash
# Test CLI loads
python -m bicep_whatif_advisor.cli --help

# Test input validation
echo "test" | python -m bicep_whatif_advisor.cli
# Should error: Invalid input

# Test provider initialization
ANTHROPIC_API_KEY=test python -c "from bicep_whatif_advisor.providers import get_provider; get_provider('anthropic')"
```

**Exit Criteria:**
- ✅ CLI accepts --help and shows all options
- ✅ Input validation rejects invalid What-If output
- ✅ All three providers can be initialized
- ✅ Clear error messages for missing API keys

---

### Phase 2: Prompt Engineering and Output Rendering (3-5 hours)

**Goal:** Create prompt construction and output formatting

**Components:**
- System and user prompt builders
- JSON schema definitions
- Table rendering with Rich
- JSON output rendering
- Markdown rendering

**Deliverables:**
- [ ] `bicep_whatif_advisor/prompt.py` with build functions
- [ ] `bicep_whatif_advisor/render.py` with all formats
- [ ] Complete JSON schema in system prompt
- [ ] Rich table with 85% width, ROUNDED box style
- [ ] Action symbols (✅ ✏️ ❌ etc.)

**Validation:**
```bash
# Test with fixture
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --format table
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --format json
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --format markdown
```

**Exit Criteria:**
- ✅ Standard mode works end-to-end
- ✅ Table output is formatted correctly
- ✅ JSON output is valid and parsable
- ✅ Markdown output is properly formatted

---

### Phase 3: CI/CD Platform Detection (2-4 hours)

**Goal:** Auto-detect CI/CD platform and extract metadata

**Components:**
- PlatformContext dataclass
- Platform detection logic
- GitHub Actions metadata extraction
- Azure DevOps metadata extraction
- Git diff collection

**Deliverables:**
- [ ] `bicep_whatif_advisor/ci/__init__.py`
- [ ] `bicep_whatif_advisor/ci/platform.py` with detect_platform()
- [ ] `bicep_whatif_advisor/ci/diff.py` with get_diff()
- [ ] Smart defaults in cli.py main()

**Validation:**
```bash
# Test local detection
python -c "from bicep_whatif_advisor.ci.platform import detect_platform; print(detect_platform())"
# Should show: PlatformContext(platform='local', ...)

# Test in GitHub Actions (requires GitHub Actions environment)
# GITHUB_ACTIONS=true GITHUB_EVENT_PATH=... python -c "..."

# Test git diff
python -c "from bicep_whatif_advisor.ci.diff import get_diff; print(get_diff(None, 'HEAD~1'))"
```

**Exit Criteria:**
- ✅ Detects local vs GitHub vs Azure DevOps correctly
- ✅ Extracts PR metadata in GitHub Actions
- ✅ Collects git diff successfully
- ✅ Smart defaults apply in CI environments

---

### Phase 4: Risk Assessment System (3-5 hours)

**Goal:** Implement three-bucket risk evaluation and verdict logic

**Components:**
- Risk bucket evaluation
- Threshold comparison
- Verdict determination
- CI mode prompt updates

**Deliverables:**
- [ ] `bicep_whatif_advisor/ci/risk_buckets.py` with evaluate_risk_buckets()
- [ ] Updated prompt.py for CI mode
- [ ] Updated cli.py for CI mode flow
- [ ] Risk assessment display in render.py

**Validation:**
```bash
# Test CI mode with different thresholds
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor \
  --ci \
  --drift-threshold high \
  --intent-threshold high \
  --operations-threshold high

# Should exit with code based on risk levels
echo $?
```

**Exit Criteria:**
- ✅ CI mode prompts include diff and PR context
- ✅ LLM returns risk_assessment and verdict
- ✅ evaluate_risk_buckets() correctly compares thresholds
- ✅ Exit codes are correct (0=safe, 1=unsafe)
- ✅ Intent bucket skipped when no PR metadata

---

### Phase 5: Noise Filtering and PR Comments (3-5 hours)

**Goal:** Implement confidence scoring, pattern matching, and PR comment posting

**Components:**
- Confidence filtering
- Pattern-based noise filtering
- Re-analysis after filtering
- GitHub PR comment posting
- Azure DevOps PR comment posting

**Deliverables:**
- [ ] `bicep_whatif_advisor/noise_filter.py` with all functions
- [ ] `bicep_whatif_advisor/ci/github.py` with post_github_comment()
- [ ] `bicep_whatif_advisor/ci/azdevops.py` with post_azdevops_comment()
- [ ] filter_by_confidence() in cli.py
- [ ] Re-analysis logic in cli.py

**Validation:**
```bash
# Test noise filtering
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor \
  --noise-file tests/noise_patterns.txt \
  --noise-threshold 80

# Test PR comment posting (requires GitHub token)
cat tests/fixtures/create_only.txt | bicep-whatif-advisor \
  --ci \
  --post-comment \
  --pr-url "https://github.com/owner/repo/pull/123"
```

**Exit Criteria:**
- ✅ Confidence filtering works correctly
- ✅ Pattern matching filters summaries
- ✅ Re-analysis triggered in CI mode after filtering
- ✅ GitHub PR comments post successfully
- ✅ Azure DevOps PR comments post successfully
- ✅ Low-confidence resources shown in separate section

---

### Phase 6: Testing and Documentation (4-6 hours)

**Goal:** Comprehensive test coverage and user documentation

**Components:**
- Unit tests for all modules
- Integration tests
- Test fixtures
- User documentation
- CI/CD workflow examples

**Deliverables:**
- [ ] `tests/test_input.py`
- [ ] `tests/test_prompt.py`
- [ ] `tests/test_render.py`
- [ ] `tests/test_platform.py`
- [ ] `tests/test_risk_buckets.py`
- [ ] `tests/test_noise_filter.py`
- [ ] `tests/test_cli.py` (integration)
- [ ] `tests/fixtures/` directory with 5 fixtures
- [ ] `README.md` with usage examples
- [ ] `docs/guides/GETTING_STARTED.md`
- [ ] `docs/guides/CICD_INTEGRATION.md`

**Validation:**
```bash
# Run all tests
pytest -v

# Check coverage
pytest --cov=bicep_whatif_advisor --cov-report=html

# Test package installation
pip install -e .
bicep-whatif-advisor --version
```

**Exit Criteria:**
- ✅ All tests passing
- ✅ Test coverage > 80%
- ✅ Documentation complete
- ✅ Package installs correctly
- ✅ CLI works from installed package

---

## Task Dependencies

```
Phase 1 (Core)
    ↓
Phase 2 (Prompts & Rendering)
    ↓
Phase 3 (Platform Detection)
    ↓
Phase 4 (Risk Assessment)
    ↓
Phase 5 (Noise & PR Comments)
    ↓
Phase 6 (Testing & Docs)
```

**Note:** Phases must be completed in order. Each phase depends on deliverables from previous phases.

## Estimated Total Effort

- **Phase 1:** 4-6 hours
- **Phase 2:** 3-5 hours
- **Phase 3:** 2-4 hours
- **Phase 4:** 3-5 hours
- **Phase 5:** 3-5 hours
- **Phase 6:** 4-6 hours

**Total:** 19-31 hours (2-4 days for single agent)

## Critical Implementation Notes

### 1. Re-analysis After Noise Filtering

**CRITICAL:** In CI mode, if noise filtering removes resources, the LLM's risk_assessment is stale (it was generated before filtering). The implementation MUST:

1. Filter resources by confidence
2. Check if any low-confidence resources exist
3. If yes, re-construct What-If output from high-confidence resources only
4. Re-prompt LLM with filtered What-If output
5. Extract fresh risk_assessment and verdict
6. Use fresh verdict for deployment decision

See `cli.py` lines 413-478 for implementation.

### 2. Intent Bucket Optional

The intent bucket should ONLY be evaluated if PR title or description is provided. If neither is available:

- Do not include intent bucket in risk_assessment
- Threshold checking should skip intent bucket
- Display should indicate "Intent: Skipped (no PR metadata)"

See `ci/risk_buckets.py` for implementation.

### 3. Smart Defaults

When platform is detected (not local), apply these defaults:

- Auto-enable `--ci` mode
- Auto-set diff reference to `origin/{base_branch}`
- Auto-populate `--pr-title` and `--pr-description`
- Auto-enable `--post-comment` if auth token present

See `cli.py` lines 290-326 for implementation.

### 4. Error Handling

All errors should:
- Write to stderr (not stdout)
- Include actionable guidance
- Use appropriate exit codes
- Be user-friendly (no stack traces for expected errors)

### 5. Security

- Prevent path traversal in `_load_bicep_files()`
- Skip symbolic links
- Limit file size/count
- Sanitize user input in prompts
- Never log API keys

## Success Metrics

Upon completion, the recreated project should:

1. ✅ Pass all tests with >80% coverage
2. ✅ Work in both standard and CI modes
3. ✅ Auto-detect GitHub Actions and Azure DevOps
4. ✅ Support all three LLM providers
5. ✅ Filter Azure What-If noise effectively
6. ✅ Post PR comments automatically
7. ✅ Exit with correct codes for deployment gating
8. ✅ Match the functionality of the original implementation

## Troubleshooting

### Common Issues

**1. LLM returns invalid JSON**
- Check prompt includes complete JSON schema
- Ensure examples show exact format
- Use temperature 0 for deterministic output
- Implement robust JSON extraction with balanced brace matching

**2. Platform detection fails**
- Verify environment variables are set correctly
- Check GITHUB_EVENT_PATH file exists and is valid JSON
- Test with actual CI/CD environment (not simulated)

**3. Noise filtering too aggressive**
- Lower noise threshold (default: 80%)
- Review noise patterns file
- Check LLM confidence scoring consistency

**4. PR comments fail to post**
- Verify auth tokens are set
- Check token has correct permissions
- Validate PR number/URL format
- Test API calls manually with curl

## Next Steps After Recreation

Once the core project is recreated:

1. Add support for additional CI/CD platforms (GitLab, Jenkins)
2. Implement Azure DevOps API call to fetch PR metadata
3. Add `--show-all-confidence` flag for debugging
4. Create VS Code extension for local development
5. Add telemetry for usage analytics
6. Optimize prompt sizes to reduce API costs
7. Add caching layer for repeated analyses
