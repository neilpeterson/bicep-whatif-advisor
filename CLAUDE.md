# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains the `bicep-whatif-advisor` Python CLI tool that analyzes Azure Bicep/ARM What-If deployment output using LLMs to provide human-friendly summaries and automated deployment safety reviews.

**Current State:** ✅ Fully implemented and ready to use. The Python package is at the root level.

## Core Concept

The tool accepts Azure What-If output via stdin, sends it to an LLM (Anthropic Claude, Azure OpenAI, or Ollama), and outputs a structured summary:

```bash
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor
```

## Project Structure

The implementation follows this structure:

```
bicep-whatif-advisor/             # Root directory
├── bicep_whatif_advisor/         # Main Python package
│   ├── __init__.py
│   ├── cli.py              # Entry point using click
│   ├── input.py            # Stdin reading and validation
│   ├── prompt.py           # Prompt template construction (standard + CI mode)
│   ├── render.py           # Output formatting (table, json, markdown)
│   ├── noise_filter.py     # Pre-LLM property-line noise filtering
│   ├── data/
│   │   └── builtin_noise_patterns.txt  # Bundled known-noisy Azure property keywords
│   ├── providers/          # LLM provider implementations
│   │   ├── __init__.py     # Provider base class and registry
│   │   ├── anthropic.py    # Anthropic Claude provider
│   │   ├── azure_openai.py # Azure OpenAI provider
│   │   └── ollama.py       # Ollama provider
│   └── ci/                 # CI/CD deployment gate features
│       ├── __init__.py
│       ├── buckets.py      # Risk bucket registry and definitions
│       ├── platform.py     # CI/CD platform auto-detection
│       ├── risk_buckets.py # Risk evaluation and threshold logic
│       ├── diff.py         # Git diff collection
│       ├── verdict.py      # Safety verdict evaluation
│       ├── github.py       # GitHub PR comments
│       └── azdevops.py     # Azure DevOps PR comments
├── tests/
│   ├── conftest.py         # Shared fixtures, MockProvider, sample responses
│   ├── fixtures/           # Sample What-If outputs
│   ├── sample-bicep-deployment/  # Example Bicep template for testing
│   ├── test_input.py       # Input validation tests
│   ├── test_noise_filter.py # Noise filtering tests
│   ├── test_buckets.py     # Risk bucket registry tests
│   ├── test_risk_buckets.py # Risk evaluation tests
│   ├── test_prompt.py      # Prompt construction tests
│   ├── test_render.py      # Output rendering tests
│   ├── test_platform.py    # Platform detection tests
│   ├── test_diff.py        # Git diff tests
│   ├── test_providers.py   # Provider system tests
│   ├── test_github.py      # GitHub PR comment tests
│   ├── test_azdevops.py    # Azure DevOps PR comment tests
│   ├── test_cli.py         # CLI entry point tests
│   └── test_integration.py # End-to-end pipeline tests
├── .github/workflows/
│   ├── test.yml            # CI test suite (Python 3.9/3.11/3.13)
│   ├── publish-pypi.yml    # PyPI publishing on release
│   └── bicep-sample-pipeline.yml  # Sample Bicep deployment pipeline
├── docs/                   # Documentation
│   ├── specs/              # Technical specifications (00-12)
│   │   ├── 00-OVERVIEW.md
│   │   ├── 01-CLI-INTERFACE.md
│   │   ├── 02-INPUT-VALIDATION.md
│   │   ├── 03-PROVIDER-SYSTEM.md
│   │   ├── 04-PROMPT-ENGINEERING.md
│   │   ├── 05-OUTPUT-RENDERING.md
│   │   ├── 06-NOISE-FILTERING.md
│   │   ├── 07-PLATFORM-DETECTION.md
│   │   ├── 08-RISK-ASSESSMENT.md
│   │   ├── 09-PR-INTEGRATION.md
│   │   ├── 10-GIT-DIFF.md
│   │   ├── 11-TESTING-STRATEGY.md
│   │   └── 12-BACKLOG.md
│   └── guides/             # User guides
│       ├── QUICKSTART.md
│       ├── USER_GUIDE.md
│       ├── CICD_INTEGRATION.md
│       └── RISK_ASSESSMENT.md
├── pyproject.toml          # Package configuration
├── README.md               # User documentation
└── LICENSE                 # MIT license
```

## Development Commands

**Install dependencies:**
```bash
pip install -e .                    # Core dependencies only
pip install -e .[anthropic]         # With Anthropic SDK (recommended)
pip install -e .[all]               # All provider dependencies
pip install -e .[all,dev]           # With dev/test dependencies
```

**Version updates for releases:**
```bash
# CRITICAL: Version must be updated in TWO places for PyPI releases:
# 1. bicep_whatif_advisor/__init__.py
__version__ = "X.Y.Z"

# 2. pyproject.toml (this is what the build system uses!)
[project]
version = "X.Y.Z"

# Then commit, tag, and create release:
git add bicep_whatif_advisor/__init__.py pyproject.toml
git commit -m "Bump version to X.Y.Z"
git push origin main
git tag -a vX.Y.Z -m "Release vX.Y.Z: Description"
git push origin vX.Y.Z
gh release create vX.Y.Z --title "vX.Y.Z - Title" --notes "Release notes"
```

**Run tests:**
```bash
pytest                              # Run all tests
pytest tests/test_input.py          # Run specific test file
pytest -v                           # Verbose output
pytest -k "test_name"               # Run specific test
```

**Testing with fixtures:**
```bash
cat tests/fixtures/create_only.txt | bicep-whatif-advisor

# Test CI mode:
cat tests/fixtures/create_only.txt | bicep-whatif-advisor \
  --ci \
  --drift-threshold high \
  --intent-threshold high

# Or run directly via Python module:
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli
```

**Linting and formatting:**
```bash
ruff check .                        # Lint code
ruff format .                       # Format code
```

## Architecture Notes

### Two Operating Modes

1. **Interactive Mode (default):** Reads What-If output from stdin, sends to LLM, displays formatted table/JSON/markdown
2. **CI Mode (`--ci` flag):** Also accepts git diff, evaluates deployment safety across risk buckets, sets pass/fail exit codes, optionally posts PR comments

### Risk Bucket System (CI Mode)

CI mode evaluates independent risk categories:

1. **Infrastructure Drift** (built-in): Compares What-If output to code diff to detect changes not in the PR (out-of-band modifications)
2. **PR Intent Alignment** (built-in): Compares What-If output to PR title/description to catch unintended changes (optional - skipped if no PR metadata)
3. **Custom Agents** (user-created via `--agents-dir`): Additional risk dimensions defined as markdown files with YAML frontmatter

Each bucket has an independent configurable threshold (low, medium, high). Deployment fails if ANY bucket exceeds its threshold.

### LLM Provider Interface

All providers implement a common interface:

```python
class Provider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the LLM and return raw response text."""
        pass
```

Default models:
- Anthropic: `claude-sonnet-4-20250514`
- Azure OpenAI: Deployment-dependent
- Ollama: `llama3.1`

All providers use temperature 0 for deterministic output.

### Structured Response Format

**Standard Mode:**

```json
{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "Create|Modify|Delete|Deploy|NoChange|Ignore",
      "summary": "string"
    }
  ],
  "overall_summary": "string"
}
```

**CI Mode:**

Per-resource fields include `risk_level` (low|medium|high) and `risk_reason`.

Multi-bucket risk assessment:

```json
{
  "resources": [...],
  "overall_summary": "string",
  "risk_assessment": {
    "drift": {
      "risk_level": "low|medium|high",
      "concerns": ["..."],
      "reasoning": "..."
    },
    "intent": {
      "risk_level": "low|medium|high",
      "concerns": ["..."],
      "reasoning": "..."
    }
  },
  "verdict": {
    "safe": true|false,
    "highest_risk_bucket": "drift|intent|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "..."
  }
}
```

Custom agents added via `--agents-dir` will also appear as keys in `risk_assessment`.

**Note:** The `intent` bucket is only included if PR title/description are provided via `--pr-title` or `--pr-description` flags.

### Risk Classification (CI Mode)

**Infrastructure Drift Bucket:**
- **High:** Critical resources drifting (security, identity, stateful), broad scope drift
- **Medium:** Multiple resources drifting, important resource configuration drift
- **Low:** Minor drift (tags, display names), single non-critical resource drift

**PR Intent Alignment Bucket:**
- **High:** Destructive changes not mentioned in PR, security/auth changes not mentioned
- **Medium:** Modifications not aligned with PR intent, unexpected resource types
- **Low:** New resources not mentioned but aligned with intent, minor scope differences

## Documentation Structure

Documentation is organized into two directories:

**`/docs/specs/`** - Technical specifications (numbered 00-12 for reading order)
- `00-OVERVIEW.md` - Project architecture, data flow, design principles
- `01-CLI-INTERFACE.md` - CLI flags, orchestration, and smart defaults
- `02-INPUT-VALIDATION.md` - Stdin processing and validation
- `03-PROVIDER-SYSTEM.md` - LLM provider abstraction (Anthropic, Azure OpenAI, Ollama)
- `04-PROMPT-ENGINEERING.md` - System/user prompts and dynamic schema generation
- `05-OUTPUT-RENDERING.md` - Table/JSON/Markdown formatting
- `06-NOISE-FILTERING.md` - Confidence scoring and pattern matching
- `07-PLATFORM-DETECTION.md` - GitHub Actions & Azure DevOps auto-detection
- `08-RISK-ASSESSMENT.md` - Multi-bucket risk model and threshold logic
- `09-PR-INTEGRATION.md` - GitHub & Azure DevOps PR comment posting
- `10-GIT-DIFF.md` - Git diff collection for drift detection
- `11-TESTING-STRATEGY.md` - Test architecture and fixtures
- `12-BACKLOG.md` - Feature backlog and future enhancements

**`/docs/guides/`** - User-facing guides (clear progression for new users)
- `QUICKSTART.md` - 5-minute getting started guide
- `USER_GUIDE.md` - Complete feature reference and all CLI flags
- `CICD_INTEGRATION.md` - CI/CD pipeline setup (GitHub Actions, Azure DevOps, etc.)
- `RISK_ASSESSMENT.md` - Deep dive into AI risk evaluation

The main `README.md` provides a concise overview with links to all documentation.

## Sample Bicep Template

The `tests/sample-bicep-deployment/` directory contains a working Azure deployment example:

**Test What-If output:**
```bash
# Generic command (replace <resource-group> with your Azure resource group)
az deployment group what-if \
  --template-file ./tests/sample-bicep-deployment/main.bicep \
  --parameters ./tests/sample-bicep-deployment/pre-production.bicepparam \
  -g <resource-group> \
  --exclude-change-types NoChange Ignore
```

This directory contains sample Bicep templates and parameter files for testing the tool.

## Key Implementation Requirements

### Input Validation
- Detect TTY (no piped input) and show usage hint
- Validate input contains What-If markers (`Resource changes:`, `+ Create`, etc.)
- Truncate inputs exceeding 100,000 characters with warning

### Error Handling
- Missing API keys → Clear message with env var name
- Network errors → Retry once, then fail
- Malformed LLM response → Attempt JSON extraction, fail gracefully
- Exit codes: 0 (success), 1 (error), 2 (invalid input/unsafe in CI mode)

### Output Formats
- **table:** Rich library colored table with action symbols (✅ Create, ✏️ Modify, ❌ Delete)
  - Tables render at 85% of terminal width for improved readability
  - Uses `box.ROUNDED` style with horizontal lines between rows
- **json:** Raw structured response for piping to jq
- **markdown:** Table format for PR comments

### Dependencies
- Core: `click`, `rich`
- Optional extras: `anthropic`, `openai`, `requests`

## CI/CD Integration

When implementing CI mode (`--ci` flag):

1. Accept both What-If output and git diff as input
2. Include source code context in prompt
3. Return structured safety verdict with multi-bucket risk assessment
4. Post formatted markdown comments to GitHub/Azure DevOps PRs
5. Exit with code 0 (safe) or 1 (unsafe) based on independent thresholds:
   - `--drift-threshold` (default: high)
   - `--intent-threshold` (default: high)
   - `--agent-threshold <agent_id>=<level>` (for custom agents)

**Environment variables for PR comments:**
- GitHub: `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_PR_NUMBER`
- Azure DevOps: `SYSTEM_ACCESSTOKEN`, `SYSTEM_PULLREQUEST_PULLREQUESTID`

**Sample CI command:**
```bash
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --drift-threshold high \
  --intent-threshold high \
  --pr-title "Add monitoring resources" \
  --pr-description "This PR adds Application Insights diagnostics" \
  --post-comment
```

**Optional CI flags:**
- `--no-block`: Report findings without failing pipeline (exit code 0 even if unsafe)
- `--skip-drift`: Skip infrastructure drift risk assessment (CI mode only)
- `--skip-intent`: Skip PR intent alignment risk assessment (CI mode only)
- `--skip-agent <id>`: Skip a custom agent by ID (repeatable, CI mode only)

**Noise filtering flags (all modes):**
- `--noise-file`: Path to additional patterns file (additive with built-ins)
- `--noise-threshold`: Similarity % for `fuzzy:` prefix patterns only (default: 80)
- `--no-builtin-patterns`: Disable bundled Azure What-If noise patterns

**Output control flags:**
- `--include-whatif`: Include raw What-If output in markdown/PR comment as collapsible section

**Note:** At least one risk bucket must remain enabled when using skip flags.

**Skip flag examples:**
```bash
# Skip drift assessment (useful when infrastructure state differs from code)
cat whatif-output.txt | bicep-whatif-advisor --ci --skip-drift

# Skip intent assessment (useful for automated maintenance PRs)
cat whatif-output.txt | bicep-whatif-advisor --ci --skip-intent

# Skip a custom agent
cat whatif-output.txt | bicep-whatif-advisor --ci --skip-agent compliance
```

## Testing

**Test suite:** 230 tests (221 unit + 9 integration), ~82% coverage, runs in ~1.5s.

**Run tests:**
```bash
pytest                              # Run all tests
pytest -m unit                      # Unit tests only
pytest -m integration               # Integration tests only
pytest --cov=bicep_whatif_advisor    # With coverage report
```

**CI workflow:** `.github/workflows/test.yml` runs tests on Python 3.9, 3.11, and 3.13 with lint/format checks.

**Test fixtures in `tests/fixtures/`:**
- `create_only.txt` — Only create operations
- `mixed_changes.txt` — Creates, modifies, and deletes
- `deletes.txt` — Only deletion operations
- `no_changes.txt` — All NoChange resources
- `large_output.txt` — 50+ resources for truncation testing
- `noisy_changes.txt` — Real changes mixed with known-noisy properties (etag, provisioningState, IPv6)

All tests use `MockProvider` from `conftest.py` — no real API calls during testing.

## Future Improvements / Backlog

**Note:** Platform auto-detection for GitHub Actions and Azure DevOps is ✅ **COMPLETED**. The tool now automatically detects CI environments, extracts PR metadata, and posts comments with minimal configuration.

### Potential Future Enhancements

1. **Additional CI/CD Platforms**
   - Add native auto-detection for GitLab CI, Jenkins, CircleCI
   - Currently supported via manual `--ci` flag

2. **Test Coverage** ✅ **COMPLETED**
   - 230 tests (221 unit + 9 integration), ~82% coverage
   - CI workflow on Python 3.9/3.11/3.13

3. **Enhanced Noise Filtering** (pre-LLM property filtering ✅ implemented)
   - Configurable confidence thresholds (currently hardcoded)
   - Block-level suppression: omit entire Modify blocks when all properties are filtered
   - Resource-type-scoped patterns (`[Microsoft.Network/virtualNetworks]` sections)
   - Pattern suggestion tooling based on low-confidence LLM output

4. **Performance Optimizations**
   - Parallel LLM requests for large What-If outputs
   - Caching of LLM responses for identical inputs
   - Streaming output for better UX

5. **Additional Output Formats**
   - HTML report generation
   - SARIF format for security scanners
   - Excel/CSV exports
