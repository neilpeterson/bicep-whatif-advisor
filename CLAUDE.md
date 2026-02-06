# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This repository contains the `whatif-explain` Python CLI tool that analyzes Azure Bicep/ARM What-If deployment output using LLMs to provide human-friendly summaries and automated deployment safety reviews.

**Current State:** ✅ Fully implemented and ready to use. The Python package is at the root level.

## Core Concept

The tool accepts Azure What-If output via stdin, sends it to an LLM (Anthropic Claude, Azure OpenAI, or Ollama), and outputs a structured summary:

```bash
az deployment group what-if -g my-rg -f main.bicep | whatif-explain
```

## Project Structure

The implementation follows this structure:

```
bicep-whatif-explain/       # Root directory
├── whatif_explain/         # Main Python package
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
│   ├── PIPELINE.md         # CI/CD integration guide
│   ├── IMPLEMENTATION_GUIDE.md # Installation and usage walkthrough
│   └── whatif-explain-spec.md  # Original specification
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
cat tests/fixtures/create_only.txt | whatif-explain
# Or run directly via Python module:
cat tests/fixtures/create_only.txt | python -m whatif_explain.cli
```

**Linting and formatting:**
```bash
ruff check .                        # Lint code
ruff format .                       # Format code
```

## Architecture Notes

### Two Operating Modes

1. **Interactive Mode (default):** Reads What-If output from stdin, sends to LLM, displays formatted table/JSON/markdown
2. **CI Mode (`--ci` flag):** Also accepts git diff, evaluates deployment safety, sets pass/fail exit codes, optionally posts PR comments

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

The LLM returns JSON with this schema:

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

In CI mode, additional fields are included:
- `risk_level`: "none|low|medium|high|critical"
- `risk_reason`: Explanation of risk
- `verdict`: Object with safety assessment

### Risk Classification (CI Mode)

- **critical:** Deletion of stateful resources (databases, storage, key vaults), identity/RBAC deletions, broad network security changes
- **high:** Production resource deletions, auth/authz modifications, firewall changes, SKU downgrades
- **medium:** Behavioral changes to existing resources, new public endpoints
- **low:** New resources, tags, monitoring resources, cosmetic changes
- **none:** NoChange, Ignore actions

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
3. Return structured safety verdict with risk assessment
4. Post formatted markdown comments to GitHub/Azure DevOps PRs
5. Exit with code 0 (safe) or 1 (unsafe) based on `--risk-threshold`

**Environment variables for PR comments:**
- GitHub: `GITHUB_TOKEN`, `GITHUB_REPOSITORY`, `GITHUB_PR_NUMBER`
- Azure DevOps: `SYSTEM_ACCESSTOKEN`, `SYSTEM_PULLREQUEST_PULLREQUESTID`

## Testing Strategy

Required test fixtures in `tests/fixtures/`:
- `create_only.txt` — Only create operations
- `mixed_changes.txt` — Creates, modifies, and deletes
- `deletes.txt` — Only deletion operations
- `no_changes.txt` — All NoChange resources
- `large_output.txt` — 50+ resources for truncation testing

Mock LLM providers in tests to avoid API calls during unit testing.
