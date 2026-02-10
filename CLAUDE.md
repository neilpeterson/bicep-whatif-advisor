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
bicep-bicep-whatif-advisor/       # Root directory
├── bicep_whatif_advisor/         # Main Python package
│   ├── __init__.py
│   ├── cli.py              # Entry point using click
│   ├── input.py            # Stdin reading and validation
│   ├── prompt.py           # Prompt template construction (standard + CI mode)
│   ├── render.py           # Output formatting (table, json, markdown)
│   ├── providers/          # LLM provider implementations
│   │   ├── __init__.py     # Provider base class and registry
│   │   ├── anthropic.py    # Anthropic Claude provider
│   │   ├── azure_openai.py # Azure OpenAI provider
│   │   └── ollama.py       # Ollama provider
│   └── ci/                 # CI/CD deployment gate features
│       ├── __init__.py
│       ├── diff.py         # Git diff collection
│       ├── verdict.py      # Safety verdict evaluation
│       ├── github.py       # GitHub PR comments
│       └── azdevops.py     # Azure DevOps PR comments
├── tests/
│   └── fixtures/           # Sample What-If outputs
├── bicep-sample/           # Example Bicep template for testing
├── docs/                   # Documentation
│   ├── specs/              # Technical specifications
│   │   ├── SPECIFICATION.md
│   │   └── PLATFORM_AUTO_DETECTION_PLAN.md
│   └── guides/             # User guides
│       ├── GETTING_STARTED.md
│       ├── CICD_INTEGRATION.md
│       ├── RISK_ASSESSMENT.md
│       └── CLI_REFERENCE.md
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
  --intent-threshold high \
  --operations-threshold high

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
2. **CI Mode (`--ci` flag):** Also accepts git diff, evaluates deployment safety across three risk buckets, sets pass/fail exit codes, optionally posts PR comments

### Risk Bucket System (CI Mode)

CI mode evaluates three independent risk categories:

1. **Infrastructure Drift**: Compares What-If output to code diff to detect changes not in the PR (out-of-band modifications)
2. **PR Intent Alignment**: Compares What-If output to PR title/description to catch unintended changes (optional - skipped if no PR metadata)
3. **Risky Operations**: Evaluates inherent risk of Azure operations (deletions, security changes, etc.)

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

Three-bucket risk assessment:

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
    },
    "operations": {
      "risk_level": "low|medium|high",
      "concerns": ["..."],
      "reasoning": "..."
    }
  },
  "verdict": {
    "safe": true|false,
    "highest_risk_bucket": "drift|intent|operations|none",
    "overall_risk_level": "low|medium|high",
    "reasoning": "..."
  }
}
```

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

**Risky Operations Bucket:**
- **High:** Deletion of stateful resources (databases, storage, key vaults), RBAC deletions, broad network security changes, encryption changes, SKU downgrades
- **Medium:** Behavioral changes to existing resources, new public endpoints, firewall changes, policy modifications
- **Low:** New resources, tags, monitoring resources, cosmetic changes

## Documentation Structure

Documentation is organized into two directories:

**`/docs/specs/`** - Technical specifications and feature plans
- `SPECIFICATION.md` - Complete technical design and architecture
- `PLATFORM_AUTO_DETECTION_PLAN.md` - CI/CD auto-detection implementation

**`/docs/guides/`** - User-facing guides
- `GETTING_STARTED.md` - Installation and basic usage
- `CICD_INTEGRATION.md` - CI/CD pipeline setup (GitHub Actions, Azure DevOps, etc.)
- `RISK_ASSESSMENT.md` - How risk evaluation works
- `CLI_REFERENCE.md` - Complete command reference

The main `README.md` provides a concise overview with links to all documentation.

## Sample Bicep Template

The `bicep-sample/` directory contains a working Azure API Management configuration example:

**Test What-If output:**
```bash
# Generic command (replace <resource-group> with your Azure resource group)
az deployment group what-if \
  --template-file ./bicep-sample/main.bicep \
  --parameters ./bicep-sample/tme-lab.bicepparam \
  -g <resource-group> \
  --exclude-change-types NoChange Ignore

# Example from original development environment:
az deployment group what-if --template-file ./bicep-sample/main.bicep --parameters ./bicep-sample/tme-lab.bicepparam -g rg-api-gateway-tme-two --exclude-change-types NoChange Ignore
```

This Bicep template:
- Creates APIM policy fragments for JWT parsing and logging
- Configures Application Insights diagnostics
- Sets up Front Door ID validation
- Uses `loadTextContent()` to inject XML policy files

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
3. Return structured safety verdict with three-bucket risk assessment
4. Post formatted markdown comments to GitHub/Azure DevOps PRs
5. Exit with code 0 (safe) or 1 (unsafe) based on three independent thresholds:
   - `--drift-threshold` (default: high)
   - `--intent-threshold` (default: high)
   - `--operations-threshold` (default: high)

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
  --operations-threshold high \
  --pr-title "Add monitoring resources" \
  --pr-description "This PR adds Application Insights diagnostics" \
  --post-comment
```

**Optional CI flags:**
- `--no-block`: Report findings without failing pipeline (exit code 0 even if unsafe)

## Testing Strategy

Required test fixtures in `tests/fixtures/`:
- `create_only.txt` — Only create operations
- `mixed_changes.txt` — Creates, modifies, and deletes
- `deletes.txt` — Only deletion operations
- `no_changes.txt` — All NoChange resources
- `large_output.txt` — 50+ resources for truncation testing

Mock LLM providers in tests to avoid API calls during unit testing.

## Future Improvements / Backlog

### Priority: High - Simplify GitHub Actions Integration

**Problem:** Current GitHub Actions workflows are too complex with too much manual logic:
- Manual PR details fetching using `gh pr view`
- Complex error handling and file management
- Manual PR comment posting
- Excessive debugging code
- Users need to understand workflow YAML internals

**Goal:** Make workflows as simple as possible - ideally 6 lines of logic:

```yaml
- name: Run What-If and AI Review
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor --ci --post-comment
```

**Implementation Tasks:**

1. **Auto-detect GitHub Actions Environment**
   - Detect `GITHUB_ACTIONS=true` environment variable
   - Auto-extract PR details from `GITHUB_EVENT_PATH` JSON file
   - Auto-set diff reference to PR base branch
   - File: `cli.py`

2. **Auto-fetch PR Metadata**
   - Read PR number, title, description from `GITHUB_EVENT_PATH`
   - No need for `--pr-title` or `--pr-description` flags
   - File: `ci/github.py`

3. **Simplify PR Comment Posting**
   - Use `GITHUB_TOKEN`, `GITHUB_REPOSITORY` automatically
   - No manual `gh` CLI commands needed
   - Better error messages if token missing
   - File: `ci/github.py`

4. **Smart Defaults**
   - Default thresholds to `high` (already done)
   - Auto-detect repository context
   - Auto-enable `--post-comment` if `GITHUB_TOKEN` exists

5. **Better Error Handling**
   - Clear, actionable error messages
   - Suggest fixes for common issues (missing API key, etc.)
   - No need for workflow-level debugging

6. **Update Documentation**
   - Show simplified workflow examples in `PIPELINE.md`
   - Update `GITHUB_ACTIONS_SETUP.md` with 6-line workflow
   - Add troubleshooting guide

**Benefits:**
- Easier onboarding for new users
- Less copy-paste errors
- Workflows focus on Azure deployment, not tool orchestration
- Reduced maintenance burden

**Estimated Effort:** 4-6 hours implementation + testing
