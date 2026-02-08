# whatif-explain

> Azure What-If deployment analyzer using LLMs for human-friendly summaries and safety reviews

`whatif-explain` is a Python CLI tool that accepts Azure Bicep/ARM What-If output via stdin, sends it to an LLM for analysis, and renders a human-friendly summary. In CI mode, it acts as an automated deployment safety gate with risk assessment and PR comments.

## Features

- **Human-Friendly Summaries** - Colored tables with plain English explanations of infrastructure changes
- **Deployment Safety Gates** - Three independent risk assessments with configurable thresholds:
  - Infrastructure Drift Detection - Identifies changes not present in your code (out-of-band modifications)
  - PR Intent Analysis - Compares actual changes against PR description to catch unintended modifications
  - Risky Operations Detection - Flags dangerous operations (deletions, security changes, public endpoints)
- **Multiple LLM Providers** - Anthropic Claude, Azure OpenAI, or local Ollama
- **Multiple Output Formats** - Table, JSON, or Markdown
- **PR Integration** - Post summaries directly to GitHub or Azure DevOps pull requests
- **Fast & Lightweight** - Minimal dependencies, works anywhere Python runs

## Quick Start

### Installation

```bash
# Install with Anthropic Claude support (recommended)
pip install whatif-explain[anthropic]

# Or with Azure OpenAI
pip install whatif-explain[azure]

# Or with all providers
pip install whatif-explain[all]
```

### Set Your API Key

```powershell
# Anthropic (recommended)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Or Azure OpenAI
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-key"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
```

### Basic Usage

```powershell
# Pipe What-If output to whatif-explain
az deployment group what-if `
  --resource-group my-rg `
  --template-file main.bicep `
  --parameters params.json | whatif-explain
```

### Example Output

```
╭──────┬───────────────────────────┬──────────────────────┬────────┬─────────────────────────────────────╮
│ #    │ Resource                  │ Type                 │ Action │ Summary                             │
├──────┼───────────────────────────┼──────────────────────┼────────┼─────────────────────────────────────┤
│ 1    │ applicationinsights       │ APIM Diagnostic      │ Create │ Configures App Insights logging     │
│      │                           │                      │        │ with custom JWT headers and 100%    │
│      │                           │                      │        │ sampling.                           │
├──────┼───────────────────────────┼──────────────────────┼────────┼─────────────────────────────────────┤
│ 2    │ policy                    │ APIM Global Policy   │ Modify │ Updates global inbound policy to    │
│      │                           │                      │        │ validate Front Door header and      │
│      │                           │                      │        │ include JWT parsing fragment.       │
├──────┼───────────────────────────┼──────────────────────┼────────┼─────────────────────────────────────┤
│ 3    │ sce-jwt-parsing-logging   │ APIM Policy Fragment │ Create │ Reusable fragment that parses       │
│      │                           │                      │        │ Bearer tokens and extracts claims   │
│      │                           │                      │        │ into logging headers.               │
╰──────┴───────────────────────────┴──────────────────────┴────────┴─────────────────────────────────────╯

Summary: This deployment creates JWT authentication policies, updates diagnostic
logging, and enhances API security with Front Door validation.
```

## Two Operating Modes

### Standard Mode (Default)

For local development and interactive usage. Provides human-readable summaries without risk assessment.

```bash
az deployment group what-if ... | whatif-explain
```

**Features:** Plain English summaries, colored output, multiple formats (table/JSON/markdown)

### CI Mode (--ci)

For CI/CD pipelines. Acts as an automated deployment safety gate with three-bucket risk assessment.

```bash
# Run What-If and save output
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep > whatif-output.txt

# Analyze with CI mode (three independent risk thresholds)
cat whatif-output.txt | whatif-explain \
  --ci \
  --diff-ref origin/main \
  --drift-threshold high \
  --intent-threshold high \
  --operations-threshold high

# Use exit code to gate deployment
if [ $? -eq 0 ]; then
  az deployment group create --resource-group my-rg --template-file main.bicep
else
  echo "❌ Deployment blocked - check which risk bucket failed"
  exit 1
fi
```

**Features:** Everything in Standard Mode, plus:
- **Three-bucket risk assessment** (drift, intent alignment, risky operations)
- Git diff analysis to detect infrastructure drift
- PR intent validation (compares changes to PR description)
- Independent thresholds for each risk category
- Deployment verdicts with configurable sensitivity
- Exit code 0 (safe) or 1 (unsafe)
- Optional PR comment posting

**Risk Buckets:**
- 🔄 **Infrastructure Drift** - Detects changes not in your code diff (out-of-band modifications)
- 🎯 **PR Intent Alignment** - Ensures changes match PR description (optional)
- ⚠️ **Risky Operations** - Identifies dangerous Azure operations (deletions, security changes)

**Risk Levels per Bucket:** Low, Medium, High (deployment fails if ANY bucket exceeds its threshold)

## Common Options

```bash
# Use different output format
whatif-explain --format json
whatif-explain --format markdown

# Use different provider
whatif-explain --provider azure-openai
whatif-explain --provider ollama

# Show property-level details
whatif-explain --verbose

# CI mode with custom thresholds (three independent buckets)
whatif-explain --ci \
  --drift-threshold low \
  --intent-threshold medium \
  --operations-threshold high
```

## Environment Variables

### Provider Credentials

**Anthropic:**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**Azure OpenAI:**
```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

**Ollama:**
```bash
export OLLAMA_HOST="http://localhost:11434"  # Optional
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or safe deployment in CI mode) |
| `1` | Error or unsafe deployment (risk threshold exceeded) |
| `2` | Invalid input (no piped input or malformed What-If output) |

## CI/CD Integration

### GitHub Actions

```yaml
- name: AI Safety Analysis
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... > whatif-output.txt
    cat whatif-output.txt | whatif-explain \
      --ci \
      --diff-ref origin/main \
      --drift-threshold high \
      --intent-threshold high \
      --operations-threshold high \
      --post-comment \
      --format markdown
```

### Azure DevOps

```yaml
- script: |
    az deployment group what-if ... > whatif-output.txt
    cat whatif-output.txt | whatif-explain \
      --ci \
      --diff-ref origin/main \
      --drift-threshold high \
      --intent-threshold high \
      --operations-threshold high
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

See [PIPELINE.md](docs/PIPELINE.md) for complete CI/CD integration guides and [REFERENCE.md](docs/REFERENCE.md) for detailed configuration options and examples.

## Documentation

- **[REFERENCE.md](docs/REFERENCE.md)** - Complete CLI reference, examples, and configuration options
- **[PIPELINE.md](docs/PIPELINE.md)** - CI/CD integration guides for GitHub Actions, Azure DevOps, GitLab, and Jenkins
- **[IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)** - Step-by-step installation and usage walkthrough

## Contributing

Issues and pull requests are welcome! Please see the repository for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- Anthropic API: https://console.anthropic.com/
- Azure OpenAI: https://azure.microsoft.com/products/ai-services/openai-service
- Ollama: https://ollama.com/
