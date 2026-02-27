# 00 - Project Overview and Architecture

## Purpose

The `bicep-whatif-advisor` is a Python CLI tool that analyzes Azure Bicep/ARM What-If deployment output using Large Language Models (LLMs) to provide human-friendly summaries and automated deployment safety reviews. It transforms verbose Azure deployment previews into actionable insights and can block unsafe deployments in CI/CD pipelines.

**Current Version:** 1.4.0

## Core Concept

The tool operates as a stdin/stdout filter that accepts Azure What-If output and returns structured analysis:

```bash
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor
```

Instead of parsing JSON or using Azure SDKs, the tool uses LLM reasoning to:
- Understand complex resource changes
- Identify risky operations
- Detect infrastructure drift
- Filter out deployment noise
- Validate alignment with developer intent

## Operating Modes

### 1. Standard Mode (Default)

**Use Case:** Interactive analysis for developers

**Input:** Azure What-If text output via stdin

**Output:** Human-readable summary of resource changes

**Flow:**
```
What-If Output → Validation → Pre-LLM Noise Filtering → LLM Analysis → Confidence Filtering → Formatted Display
```

**Exit Codes:**
- `0` - Success
- `1` - Error (invalid input, API failure, etc.)
- `130` - User interrupt (Ctrl+C)

### 2. CI Mode (`--ci` flag)

**Use Case:** Automated deployment gates in CI/CD pipelines

**Input:**
- Azure What-If output (stdin)
- Git diff (via `--diff` or `--diff-ref`)
- PR metadata (auto-detected or via flags)

**Output:**
- Risk assessment across two built-in buckets (extensible via custom agents)
- Pass/fail verdict
- Optional PR comments

**Flow:**
```
What-If Output + Git Diff + PR Context
  → Validation
  → LLM Risk Analysis
  → Risk Bucket Evaluation
  → Verdict
  → Optional Re-analysis (if noise filtered)
  → PR Comment Posting
  → Exit Code
```

**Exit Codes:**
- `0` - Safe deployment (or `--no-block` mode)
- `1` - Error (invalid input, API failure, etc.)
- `2` - Unsafe deployment (risk thresholds exceeded)
- `130` - User interrupt (Ctrl+C)

## Data Flow Architecture

```
┌─────────────────────┐
│   User / CI/CD      │
│   Pipeline          │
└──────────┬──────────┘
           │
           │ What-If output via stdin
           ▼
┌─────────────────────┐
│  Input Validation   │──── input.py
│  - TTY detection    │
│  - Marker check     │
│  - Truncation       │
└──────────┬──────────┘
           │
           │ Validated text
           ▼
┌─────────────────────┐
│  Pre-LLM Noise      │──── noise_filter.py
│  Filter             │──── data/builtin_noise_patterns.txt
│  - Built-in patterns│
│  - User patterns    │
│  - Strip noisy lines│
└──────────┬──────────┘
           │
           │ Cleaned text
           ▼
┌─────────────────────┐
│  Prompt Builder     │──── prompt.py
│  - System prompt    │
│  - User prompt      │
│  - Schema gen       │
└──────────┬──────────┘
           │
           │ System + user prompts
           ▼
┌─────────────────────┐
│  LLM Provider       │──── providers/
│  - Anthropic        │
│  - Azure OpenAI     │
│  - Ollama           │
└──────────┬──────────┘
           │
           │ Raw JSON response
           ▼
┌─────────────────────┐
│  Response Parser    │──── cli.py:extract_json()
│  - JSON extraction  │
│  - Error recovery   │
└──────────┬──────────┘
           │
           │ Structured data
           ▼
┌─────────────────────┐
│ Confidence Filter   │──── cli.py:filter_by_confidence()
│  - Split high/low   │
└──────────┬──────────┘
           │
           ├──────────────────────┐
           │                      │
           │ High confidence      │ Low confidence
           │                      │
           ▼                      ▼
    ┌──────────┐         ┌──────────────┐
    │ CI Mode? │         │ Re-analyze?  │
    └─────┬────┘         │ (if filtered)│
          │              └──────────────┘
          │ Yes                 │
          ▼                     │
    ┌─────────────────┐        │
    │ Risk Assessment │        │
    │  - Drift        │        │
    │  - Intent       │        │
    └────────┬────────┘        │
             │                 │
             ▼                 │
    ┌─────────────────┐        │
    │ Verdict Logic   │        │
    │  - Threshold    │        │
    │  - Exit code    │        │
    └────────┬────────┘        │
             │                 │
             ├─────────────────┘
             │
             ▼
    ┌─────────────────┐
    │ PR Comment      │──── ci/github.py, ci/azdevops.py
    │ (optional)      │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │ Output Renderer │──── render.py
    │  - Table        │
    │  - JSON         │
    │  - Markdown     │
    └────────┬────────┘
             │
             ▼
    ┌─────────────────┐
    │   Exit Code     │
    └─────────────────┘
```

## Package Structure

```
bicep_whatif_advisor/
├── __init__.py              # Version: 1.4.0
├── cli.py                   # Main orchestration (634 lines)
│                            # - Click CLI setup
│                            # - Smart defaults
│                            # - Confidence filtering
│                            # - CI mode logic
│                            # - Exit code handling
├── input.py                 # Input validation (66 lines)
│                            # - Stdin reading
│                            # - TTY detection
│                            # - Marker validation
├── prompt.py                # Prompt engineering (315 lines)
│                            # - System prompt builder
│                            # - User prompt builder
│                            # - Dynamic schema generation
├── render.py                # Output formatting (486 lines)
│                            # - Table (Rich library)
│                            # - JSON (two-tier)
│                            # - Markdown (PR comments)
├── noise_filter.py          # Pre-LLM noise filtering
│                            # - filter_whatif_text() strips noisy property lines
│                            # - Keyword / regex / fuzzy pattern types
│                            # - load_builtin_patterns() + load_user_patterns()
├── data/
│   └── builtin_noise_patterns.txt  # Bundled known-noisy Azure property keywords
├── providers/               # LLM provider implementations
│   ├── __init__.py          # Abstract base class + factory
│   ├── anthropic.py         # Claude via Anthropic API
│   ├── azure_openai.py      # GPT via Azure OpenAI
│   └── ollama.py            # Local LLMs via Ollama
└── ci/                      # CI/CD features
    ├── __init__.py
    ├── platform.py          # Platform auto-detection (172 lines)
    ├── diff.py              # Git diff collection (69 lines)
    ├── risk_buckets.py      # Risk bucket evaluation (97 lines)
    ├── verdict.py           # Exit code constants (4 lines)
    ├── github.py            # GitHub PR comments (85 lines)
    └── azdevops.py          # Azure DevOps PR comments (93 lines)
```

## Module Responsibilities

### Core Pipeline
- **cli.py**: Orchestrates entire flow, CLI argument parsing, mode switching
- **input.py**: Validates stdin before processing
- **prompt.py**: Constructs LLM prompts based on mode and configuration
- **providers/**: Abstracts LLM API differences, handles retries
- **render.py**: Formats output for different audiences (terminal, scripts, PRs)

### CI/CD Features
- **noise_filter.py**: Pre-LLM property-line filtering removes deterministic noise (etag, provisioningState, IPv6 flags) before LLM analysis; LLM confidence scoring handles remaining ambiguous noise
- **ci/platform.py**: Auto-detects GitHub Actions / Azure DevOps context
- **ci/diff.py**: Collects git changes for drift detection
- **ci/risk_buckets.py**: Evaluates independent risk dimensions (drift, intent, plus custom agents)
- **ci/github.py**: Posts analysis as GitHub PR comments
- **ci/azdevops.py**: Posts analysis as Azure DevOps PR comments

## Design Principles

### 1. LLM-First Architecture

Instead of parsing Azure's JSON output with brittle regex, the tool leverages LLM reasoning to:
- Understand resource relationships
- Infer change impact
- Recognize patterns humans would flag
- Adapt to new Azure resource types without code changes

**Trade-off:** Requires LLM API access, adds latency vs. local parsing

### 2. Provider Abstraction

All LLM providers implement a common `Provider` interface:
```python
class Provider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        pass
```

This enables:
- Easy provider switching (Anthropic → Azure OpenAI → Ollama)
- Consistent behavior across providers
- Local development without API costs (Ollama)

### 3. Confidence-Based Filtering

Azure What-If output contains significant noise (spurious changes, cosmetic updates). The tool:
1. Asks LLM to assign confidence levels to each resource change
2. Filters low-confidence changes into separate "Potential Noise" section
3. Optionally re-analyzes with high-confidence subset for cleaner results

**Key Insight:** Pattern matching alone misses context; LLM can judge "is this likely noise?"

### 4. Multi-Bucket Risk Model

CI mode evaluates deployments across **two built-in dimensions** (drift, intent), each with its own threshold. Additional dimensions can be added via custom agents using `--agents-dir`:

| Bucket              | Question                                          | Threshold Flag           |
|---------------------|---------------------------------------------------|--------------------------|
| **Drift**           | Does What-If differ from code changes?            | `--drift-threshold`      |
| **Intent**          | Does What-If align with PR description?           | `--intent-threshold`     |

**Why separate buckets?**
- **Separation of concerns:** Infrastructure drift ≠ intent misalignment
- **Independent tuning:** Teams can be strict on drift but lenient on intent
- **Clear reasoning:** "Deployment blocked due to high drift risk" vs. vague "unsafe"
- **Extensibility:** Custom agents via `--agents-dir` add new risk dimensions without modifying core code

Deployment is **blocked if ANY bucket exceeds its threshold** (AND logic), ensuring comprehensive safety.

### 5. Platform Auto-Detection

In CI environments, the tool auto-detects:
- GitHub Actions (via `GITHUB_EVENT_PATH` JSON file)
- Azure DevOps (via pipeline environment variables)
- PR metadata (number, title, description, base branch)

**User benefit:** No manual flag configuration in pipelines

### 6. Graceful Degradation

The tool handles partial failures elegantly:
- Can't fetch git diff → Warns but proceeds (skips drift analysis)
- No PR metadata → Skips intent bucket evaluation
- Low-confidence filtering removes all resources → Optionally re-analyzes with unfiltered data
- LLM response malformed → Attempts JSON extraction before failing

**Philosophy:** Provide useful output even when ideal conditions aren't met

## Exit Code Contract

The tool uses distinct exit codes for automation:

| Code | Meaning                          | Standard Mode | CI Mode        |
|------|----------------------------------|---------------|----------------|
| `0`  | Success (or safe deployment)     | ✅            | ✅ (or --no-block) |
| `1`  | Error (input/API/system failure) | ✅            | ✅             |
| `2`  | Unsafe deployment                | ❌            | ✅             |
| `130`| User interrupt (Ctrl+C)          | ✅            | ✅             |

**CI/CD Usage:**
```yaml
- run: |
    az deployment group what-if ... | bicep-whatif-advisor --ci
    if [ $? -eq 2 ]; then
      echo "Deployment blocked due to safety concerns"
      exit 1
    fi
```

## Configuration Points

### LLM Provider Selection

```bash
# Auto-detected from environment variables:
ANTHROPIC_API_KEY=...        # → Anthropic provider
AZURE_OPENAI_ENDPOINT=...    # → Azure OpenAI provider
# (Ollama assumed if both missing)
```

### CI Mode Activation

```bash
# Explicit:
bicep-whatif-advisor --ci

# Auto-detected (planned):
# - GITHUB_ACTIONS=true → Auto-enable CI mode
# - SYSTEM_TEAMFOUNDATIONCOLLECTIONURI=... → Auto-enable CI mode
```

### Risk Thresholds

```bash
bicep-whatif-advisor --ci \
  --drift-threshold high \        # Require high drift risk to block
  --intent-threshold medium       # Block on medium intent misalignment
```

Valid values: `low`, `medium`, `high` (default: `high` for all)

### Output Format

```bash
bicep-whatif-advisor --format table    # Default: colored terminal output
bicep-whatif-advisor --format json     # For scripting (jq, etc.)
bicep-whatif-advisor --format markdown # For PR comments
```

### Noise Filtering

```bash
# Built-in patterns auto-loaded on every run (no flags required)
bicep-whatif-advisor

# Add custom project-specific patterns (additive with built-ins)
bicep-whatif-advisor --noise-file patterns.txt

# Disable built-ins (use only custom patterns)
bicep-whatif-advisor --no-builtin-patterns --noise-file patterns.txt

# Adjust fuzzy: prefix pattern threshold (default 80)
bicep-whatif-advisor --noise-file patterns.txt --noise-threshold 90
```

## Integration Points

### Inputs
- **stdin**: Azure What-If output (required)
- **git diff**: Code changes for drift detection (CI mode)
- **Environment**: API keys, CI platform metadata
- **Files**: Bicep source files (optional), noise pattern files (optional)

### Outputs
- **stdout**: Formatted analysis (table/JSON/markdown)
- **stderr**: Error messages, warnings
- **Exit code**: Success/failure/unsafe status
- **PR comments**: GitHub/Azure DevOps REST APIs (CI mode)

### External Services
- **LLM APIs**: Anthropic Claude, Azure OpenAI, Ollama
- **Git**: Diff collection via `git diff` command
- **GitHub API**: PR comment posting (REST API)
- **Azure DevOps API**: PR comment posting (REST API v7.0)

## Error Handling Strategy

### Validation Errors (Exit Code 1)
- No stdin input (TTY detected)
- Invalid What-If format (no recognized markers)
- Input truncated (exceeds 100K chars)

### API Errors (Exit Code 1)
- Missing API keys → Clear message with env var name
- Network failures → Retry once, then fail with error
- Rate limiting → Exponential backoff (Anthropic provider)

### LLM Response Errors (Exit Code 1)
- Malformed JSON → Attempt extraction from text
- Missing required fields → Fail with clear error
- Invalid confidence levels → Normalize or fail

### Deployment Safety (Exit Code 2, CI Mode Only)
- Risk threshold exceeded in any bucket
- Clear message indicating which bucket(s) failed

### User Interrupts (Exit Code 130)
- Ctrl+C during LLM API call
- Clean shutdown, no partial state

## Performance Characteristics

- **Latency**: 2-10 seconds (depends on LLM API)
- **Input size**: Up to 100,000 characters (enforced truncation)
- **Resource count**: Tested with 50+ resources
- **Network retries**: 1 retry on failure (Anthropic: exponential backoff)
- **Timeout**: 120 seconds for Ollama requests

## Next Steps

For detailed implementation of each module, see:
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - CLI orchestration and flags
- [02-INPUT-VALIDATION.md](02-INPUT-VALIDATION.md) - Stdin processing
- [03-PROVIDER-SYSTEM.md](03-PROVIDER-SYSTEM.md) - LLM provider abstraction
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - Prompt construction
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - Output formatting
- [06-NOISE-FILTERING.md](06-NOISE-FILTERING.md) - Confidence-based filtering
- [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) - CI/CD auto-detection
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) - Risk bucket model
- [09-PR-INTEGRATION.md](09-PR-INTEGRATION.md) - GitHub/Azure DevOps comments
- [10-GIT-DIFF.md](10-GIT-DIFF.md) - Git diff collection
- [11-TESTING-STRATEGY.md](11-TESTING-STRATEGY.md) - Test architecture
