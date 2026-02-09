# bicep-whatif-advisor

> Azure What-If deployment analyzer using LLMs for human-friendly summaries and safety reviews

`bicep-whatif-advisor` is a Python CLI tool that accepts Azure Bicep/ARM What-If output via stdin, sends it to an LLM for analysis, and renders a human-friendly summary. In CI mode, it acts as an automated deployment safety gate with risk assessment and PR comments.

## Features

- **Platform Auto-Detection** - Automatically detects GitHub Actions or Azure DevOps and enables full CI/CD integration (zero configuration required)
- **Human-Friendly Summaries** - Colored tables with plain English explanations of infrastructure changes
- **Deployment Safety Gates** - Three independent risk assessments with configurable thresholds:
  - Infrastructure Drift Detection - Identifies changes not present in your code (out-of-band modifications)
  - PR Intent Analysis - Compares actual changes against PR description to catch unintended modifications
  - Risky Operations Detection - Flags dangerous operations (deletions, security changes, public endpoints)
- **Automatic PR Comments** - Posts detailed analysis to pull requests without manual configuration
- **Multiple LLM Providers** - Anthropic Claude, Azure OpenAI, or local Ollama
- **Multiple Output Formats** - Table, JSON, or Markdown
- **Fast & Lightweight** - Minimal dependencies, works anywhere Python runs

## Quick Start

### Installation

```bash
# Install with Anthropic Claude support (recommended)
pip install bicep-whatif-advisor[anthropic]

# Or with Azure OpenAI
pip install bicep-whatif-advisor[azure]

# Or with all providers
pip install bicep-whatif-advisor[all]
```

### Set Your API Key

```bash
# Anthropic (recommended)
export ANTHROPIC_API_KEY="sk-ant-..."

# Or Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

### Basic Usage

```bash
# Pipe What-If output to bicep-whatif-advisor
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --parameters params.json \
  | bicep-whatif-advisor
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
╰──────┴───────────────────────────┴──────────────────────┴────────┴─────────────────────────────────────╯

Summary: This deployment creates JWT authentication policies and updates diagnostic logging.
```

## Two Operating Modes

### Standard Mode (Default)

For local development and interactive usage. Provides human-readable summaries without risk assessment.

```bash
az deployment group what-if ... | bicep-whatif-advisor
```

**Features:** Plain English summaries, colored output, multiple formats (table/JSON/markdown)

### CI Mode (Auto-Detected)

For CI/CD pipelines. Automatically detects GitHub Actions or Azure DevOps environment and enables full safety gate analysis.

```bash
# Simple - just pipe What-If output
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor

# Exit code 0 = safe, 1 = unsafe (deployment blocked)
```

**Features:** Everything in Standard Mode, plus:
- ✅ **Platform Auto-Detection** - Automatically enables CI mode in GitHub Actions/Azure DevOps
- ✅ **Git Diff Analysis** - Compares infrastructure changes to code changes to detect drift
- ✅ **PR Intent Validation** - Auto-extracts PR title/description and validates changes match intent
- ✅ **Three-Bucket Risk Assessment** - Independent evaluation of drift, intent alignment, and risky operations
- ✅ **Configurable Thresholds** - Set sensitivity per risk category (low, medium, high)
- ✅ **Deployment Gating** - Exit code 0 (safe) or 1 (unsafe) blocks deployments automatically
- ✅ **Automatic PR Comments** - Posts detailed analysis when auth token available

**Risk Buckets:**
- 🔄 **Infrastructure Drift** - Detects changes not in your code diff (out-of-band modifications)
- 🎯 **PR Intent Alignment** - Ensures changes match PR description (optional)
- ⚠️ **Risky Operations** - Identifies dangerous Azure operations (deletions, security changes)

**Risk Levels per Bucket:** Low, Medium, High (deployment fails if ANY bucket exceeds its threshold)

## Documentation

### User Guides

- **[Getting Started](docs/guides/GETTING_STARTED.md)** - Complete installation and usage guide
- **[CI/CD Integration](docs/guides/CICD_INTEGRATION.md)** - Set up deployment gates in GitHub Actions, Azure DevOps, GitLab, Jenkins
- **[Risk Assessment](docs/guides/RISK_ASSESSMENT.md)** - Understand how risk evaluation works
- **[CLI Reference](docs/guides/CLI_REFERENCE.md)** - Complete command reference with examples

### Technical Specifications

- **[Project Specification](docs/specs/SPECIFICATION.md)** - Technical design and architecture
- **[Platform Auto-Detection Plan](docs/specs/PLATFORM_AUTO_DETECTION_PLAN.md)** - Implementation details for CI/CD auto-detection

## Common Usage

### Different Output Formats

```bash
# JSON format for scripting
bicep-whatif-advisor --format json

# Markdown format for documentation
bicep-whatif-advisor --format markdown

# Show property-level details
bicep-whatif-advisor --verbose
```

### Different LLM Providers

```bash
# Use Azure OpenAI
bicep-whatif-advisor --provider azure-openai

# Use local Ollama
bicep-whatif-advisor --provider ollama
```

### Adjust Risk Thresholds (CI Mode)

```bash
# More strict (block on medium or high risk)
bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Very strict (block on any risk)
bicep-whatif-advisor \
  --drift-threshold low \
  --intent-threshold low \
  --operations-threshold low
```

**Note:** CI mode is automatically enabled when running in GitHub Actions or Azure DevOps. Manual `--ci` flag only needed for local testing or other CI platforms.

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or safe deployment in CI mode) |
| `1` | Error or unsafe deployment (risk threshold exceeded) |
| `2` | Invalid input (no piped input or malformed What-If output) |

## CI/CD Integration Examples

### GitHub Actions

Complete workflow in ~50 lines:

```yaml
name: PR Review - Bicep What-If

on:
  pull_request:
    branches: [main]

permissions:
  id-token: write
  contents: read
  pull-requests: write

jobs:
  whatif-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - run: pip install bicep-whatif-advisor[anthropic]

      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --template-file bicep/main.bicep \
            --exclude-change-types NoChange Ignore \
            | bicep-whatif-advisor
```

**That's it!** Auto-detects everything: CI mode, PR metadata, diff reference, and posts comments.

### Azure DevOps

```yaml
- script: |
    az deployment group what-if \
      --resource-group $(RESOURCE_GROUP) \
      --template-file bicep/main.bicep \
      --exclude-change-types NoChange Ignore \
      | bicep-whatif-advisor
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

**Auto-detects:** CI mode, PR ID, target branch, posts comments when token available.

See **[CI/CD Integration Guide](docs/guides/CICD_INTEGRATION.md)** for complete setup instructions.

## Support & Contributing

- **Documentation**: See [docs/guides/](docs/guides/) for comprehensive guides
- **Issues**: Report bugs or request features at the repository issues page
- **Contributing**: Issues and pull requests are welcome!

## Links

- Anthropic API: https://console.anthropic.com/
- Azure OpenAI: https://azure.microsoft.com/products/ai-services/openai-service
- Ollama: https://ollama.com/

## License

MIT License - see [LICENSE](LICENSE) for details.
