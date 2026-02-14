# Feature Specification: Project Overview

## Project Summary

`bicep-whatif-advisor` is an AI-powered deployment safety gate for Azure Bicep/ARM templates. It analyzes Azure What-If deployment output using LLMs to provide:

1. **Human-readable summaries** for interactive use
2. **Automated safety reviews** for CI/CD pipelines

## Core Value Proposition

**Problem:** Azure What-If output is verbose, difficult to parse, and doesn't detect:
- Infrastructure drift (out-of-band changes)
- Misalignment between PR intent and actual changes
- Risky operations that need human review

**Solution:** LLM-powered analysis that:
- Summarizes changes in plain English
- Compares What-If output to code diffs to detect drift
- Validates changes match PR descriptions
- Flags dangerous operations (deletions, security changes, downgrades)
- Automatically blocks unsafe deployments in CI/CD

## Operating Modes

### Standard Mode (Interactive)

**Input:** Azure What-If output via stdin
**Output:** Formatted table/JSON/markdown summary
**Exit Code:** 0 (success) or 1 (error)

```bash
az deployment group what-if -f main.bicep -g my-rg | bicep-whatif-advisor
```

### CI Mode (Deployment Gate)

**Input:** What-If output + git diff + PR metadata
**Output:** Risk assessment + safety verdict
**Exit Code:** 0 (safe), 1 (unsafe), 2 (error)

Auto-detects GitHub Actions or Azure DevOps and:
1. Extracts PR metadata from environment
2. Collects git diff automatically
3. Analyzes across three risk buckets
4. Posts formatted comment to PR
5. Blocks deployment if thresholds exceeded

```bash
az deployment group what-if ... | bicep-whatif-advisor
# Zero configuration - auto-detects everything!
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                          │
│                     (click-based argument parsing)               │
└────────────────────────────┬────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Input Handler  │  │ Platform       │  │ Provider       │
│                │  │ Detection      │  │ System         │
│ - Validate     │  │                │  │                │
│ - Truncate     │  │ - GitHub       │  │ - Anthropic    │
│ - Detect TTY   │  │ - Azure DevOps │  │ - Azure OpenAI │
└────────┬───────┘  │ - Local        │  │ - Ollama       │
         │          └────────┬───────┘  └────────┬───────┘
         │                   │                   │
         └───────────────────┼───────────────────┘
                             │
                             ▼
                  ┌──────────────────┐
                  │ Prompt Builder   │
                  │                  │
                  │ - System prompt  │
                  │ - User prompt    │
                  │ - CI context     │
                  └─────────┬────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │   LLM Provider   │
                  │   (API call)     │
                  └─────────┬────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Response Parser  │
                  │                  │
                  │ - Extract JSON   │
                  │ - Validate       │
                  └─────────┬────────┘
                            │
         ┌──────────────────┼──────────────────┐
         │                  │                  │
         ▼                  ▼                  ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────┐
│ Noise Filter   │  │ Risk Evaluator │  │ Output         │
│                │  │                │  │ Renderer       │
│ - LLM scoring  │  │ - 3 buckets    │  │                │
│ - Pattern      │  │ - Thresholds   │  │ - Table        │
│   matching     │  │ - Verdict      │  │ - JSON         │
└────────┬───────┘  └────────┬───────┘  │ - Markdown     │
         │                   │          └────────┬───────┘
         └───────────────────┼──────────────────┘
                             │
                ┌────────────┼────────────┐
                │            │            │
                ▼            ▼            ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Console  │  │ PR       │  │ Exit     │
        │ Output   │  │ Comment  │  │ Code     │
        └──────────┘  └──────────┘  └──────────┘
```

## Key Features

### 1. Zero-Config CI/CD Integration

- Auto-detects GitHub Actions and Azure DevOps
- Extracts PR metadata from environment files
- Sets appropriate diff references automatically
- Auto-enables PR comments when auth tokens present

### 2. Three-Bucket Risk Assessment

Independent evaluation across:

1. **Infrastructure Drift** - Changes not in code diff
2. **PR Intent Alignment** - Changes not mentioned in PR
3. **Risky Operations** - Inherently dangerous changes

Each bucket has configurable threshold (low/medium/high).

### 3. LLM-Based Noise Filtering

Azure What-If has many false positives (metadata changes, computed properties). The tool uses:

1. **LLM confidence scoring** - Analyzes each resource for likelihood of being noise
2. **Pattern matching** - User-defined noise patterns with fuzzy matching
3. **Re-analysis** - If noise filtered in CI mode, re-prompts LLM for accurate risk assessment

### 4. Pluggable Provider System

Abstract provider interface supports:
- Anthropic Claude (default)
- Azure OpenAI
- Ollama (local/free)

Easy to add new providers.

### 5. Rich Output Formats

- **Table** - Colored terminal output with rounded borders
- **JSON** - Machine-readable for piping to other tools
- **Markdown** - Formatted for PR comments

## Technology Stack

- **Language:** Python 3.8+
- **CLI Framework:** Click
- **Terminal UI:** Rich
- **HTTP:** requests
- **LLM SDKs:** anthropic, openai (optional extras)
- **Testing:** pytest, pytest-mock

## Package Structure

```
bicep-whatif-advisor/
├── bicep_whatif_advisor/
│   ├── __init__.py              # Version constant
│   ├── cli.py                   # Entry point, orchestration
│   ├── input.py                 # Stdin validation
│   ├── prompt.py                # Prompt construction
│   ├── render.py                # Output formatting
│   ├── noise_filter.py          # Confidence + pattern filtering
│   ├── providers/
│   │   ├── __init__.py          # Provider base class + registry
│   │   ├── anthropic.py         # Anthropic Claude
│   │   ├── azure_openai.py      # Azure OpenAI
│   │   └── ollama.py            # Ollama local
│   └── ci/
│       ├── __init__.py
│       ├── platform.py          # Platform detection
│       ├── diff.py              # Git diff collection
│       ├── risk_buckets.py      # Risk evaluation
│       ├── github.py            # GitHub PR comments
│       └── azdevops.py          # Azure DevOps PR comments
├── tests/
│   ├── test_*.py                # Unit tests
│   └── fixtures/                # Sample What-If outputs
├── pyproject.toml               # Package configuration
└── README.md                    # User documentation
```

## Dependencies

**Core:**
- click >= 8.0.0
- rich >= 13.0.0
- requests >= 2.31.0

**Optional (extras):**
- anthropic >= 0.40.0
- openai >= 1.0.0

**Development:**
- pytest >= 7.0.0
- pytest-mock >= 3.10.0

## Installation

```bash
# Core only
pip install bicep-whatif-advisor

# With Anthropic (recommended)
pip install bicep-whatif-advisor[anthropic]

# All providers
pip install bicep-whatif-advisor[all]

# Development
pip install bicep-whatif-advisor[all,dev]
```

## Success Criteria

A successful recreation should:

1. ✅ Accept What-If output via stdin
2. ✅ Support three LLM providers
3. ✅ Auto-detect GitHub Actions and Azure DevOps
4. ✅ Extract PR metadata from environment
5. ✅ Evaluate three risk buckets independently
6. ✅ Filter Azure noise using LLM + patterns
7. ✅ Render table/JSON/markdown output
8. ✅ Post PR comments automatically
9. ✅ Exit with correct codes (0/1/2)
10. ✅ Have comprehensive test coverage
