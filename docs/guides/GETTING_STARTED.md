# Getting Started with bicep-whatif-advisor

Complete installation and usage guide for `bicep-whatif-advisor`.

## Table of Contents

- [What is bicep-whatif-advisor?](#what-is-bicep-whatif-advisor)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Basic Usage](#basic-usage)
- [Output Formats](#output-formats)
- [Operating Modes](#operating-modes)
- [Environment Variables](#environment-variables)
- [Next Steps](#next-steps)

## What is bicep-whatif-advisor?

`bicep-whatif-advisor` is a Python CLI tool that transforms Azure Bicep/ARM What-If output into human-friendly summaries using AI. It operates in two modes:

1. **Standard Mode**: Provides readable summaries for local development
2. **CI Mode**: Acts as an automated deployment safety gate with risk assessment

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Azure CLI installed and configured
- An LLM provider account (Anthropic, Azure OpenAI, or Ollama)

### Install from PyPI

```bash
# Install with Anthropic Claude support (recommended)
pip install bicep-whatif-advisor[anthropic]

# Or with Azure OpenAI
pip install bicep-whatif-advisor[azure]

# Or with all providers
pip install bicep-whatif-advisor[all]
```

### Install from Source

```bash
cd bicep-whatif-advisor

# Install with Anthropic support
pip install -e .[anthropic]

# Or install all providers
pip install -e .[all]

# Or install for development (includes test dependencies)
pip install -e .[all,dev]
```

## Quick Start

### 1. Set Up API Credentials

**For Anthropic Claude (recommended):**

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Get your API key from: https://console.anthropic.com/

**For Azure OpenAI:**

```bash
# Linux/macOS
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"

# Windows PowerShell
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-api-key"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
```

**For Ollama (local):**

```bash
# Install and start Ollama
ollama pull llama3.1
ollama serve

# Optional: set custom host
export OLLAMA_HOST="http://localhost:11434"
```

### 2. Test with Sample Data

```bash
# Test with a fixture file
cat tests/fixtures/create_only.txt | bicep-whatif-advisor

# You should see a colorful table with resource summaries
```

### 3. Use with Real Azure What-If Output

```bash
# Run Azure What-If and pipe to bicep-whatif-advisor
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --parameters params.json \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor
```

## Basic Usage

### Default Output (Table Format)

```bash
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  | bicep-whatif-advisor
```

**Example Output:**

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

### Different Output Formats

```bash
# JSON format (for scripting)
az deployment group what-if ... | bicep-whatif-advisor --format json

# Markdown format (for documentation)
az deployment group what-if ... | bicep-whatif-advisor --format markdown

# With verbose property-level details
az deployment group what-if ... | bicep-whatif-advisor --verbose
```

### Using Different Providers

```bash
# Use Azure OpenAI
az deployment group what-if ... | bicep-whatif-advisor --provider azure-openai

# Use local Ollama
az deployment group what-if ... | bicep-whatif-advisor --provider ollama

# Override model
az deployment group what-if ... | bicep-whatif-advisor --model claude-opus-4-20250101
```

## Output Formats

### Table (Default)

Colored, formatted table with action symbols:

- ✅ Create
- ✏️ Modify
- ❌ Delete
- 🚀 Deploy
- ⚪ NoChange
- ⚫ Ignore

### JSON

Structured output for scripting and automation:

```json
{
  "resources": [
    {
      "resource_name": "myAppService",
      "resource_type": "Web App",
      "action": "Create",
      "summary": "Creates new web app with B1 SKU"
    }
  ],
  "overall_summary": "This deployment creates 1 new resource"
}
```

**Use cases:**

```bash
# Filter resources by action
az deployment group what-if ... | bicep-whatif-advisor -f json | jq '.resources[] | select(.action == "Delete")'

# Count creates
az deployment group what-if ... | bicep-whatif-advisor -f json | jq '[.resources[] | select(.action == "Create")] | length'

# Save to file
az deployment group what-if ... | bicep-whatif-advisor -f json > analysis.json
```

### Markdown

Formatted for PR comments and documentation:

```markdown
| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | myAppService | Web App | Create | Creates new web app with B1 SKU |

**Summary:** This deployment creates 1 new resource
```

## Operating Modes

### Standard Mode (Default)

For local development and interactive usage.

**Features:**
- Plain English summaries
- Colored output
- Multiple formats (table/JSON/markdown)
- No risk assessment
- Always exits with code 0

**Use Cases:**
- Local development
- Understanding changes before deployment
- Documentation

### CI Mode (Auto-Detected in Pipelines)

For CI/CD pipelines. Automatically enabled when running in GitHub Actions or Azure DevOps.

**Features:**
- Everything in Standard Mode, plus:
- Three-bucket risk assessment (drift, intent, operations)
- Git diff analysis
- PR intent validation
- Deployment verdicts with configurable thresholds
- Exit code 0 (safe) or 1 (unsafe)
- Automatic PR comment posting

**Use Cases:**
- CI/CD deployment gates
- Automated safety reviews
- Pull request reviews

**Example:**

```bash
# In GitHub Actions or Azure DevOps, just pipe the output:
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor

# Everything auto-detects:
# ✅ CI mode enabled
# ✅ PR metadata extracted
# ✅ Diff reference set
# ✅ PR comments posted
# ✅ Deployment blocked if high risk
```

See [CI/CD Integration Guide](./CICD_INTEGRATION.md) for detailed setup.

## Environment Variables

### Provider Credentials

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | For Anthropic provider | Anthropic API key |
| `AZURE_OPENAI_ENDPOINT` | For Azure OpenAI provider | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | For Azure OpenAI provider | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | For Azure OpenAI provider | Deployment name |
| `OLLAMA_HOST` | Optional | Ollama host (default: `http://localhost:11434`) |

### Optional Overrides

| Variable | Description |
|----------|-------------|
| `WHATIF_PROVIDER` | Default provider (overridden by `--provider` flag) |
| `WHATIF_MODEL` | Default model (overridden by `--model` flag) |

## Next Steps

1. **Learn CI/CD Integration**: See [CI/CD Integration Guide](./CICD_INTEGRATION.md)
2. **Understand Risk Assessment**: See [Risk Assessment Guide](./RISK_ASSESSMENT.md)
3. **Explore CLI Options**: See [CLI Reference](./CLI_REFERENCE.md)

## Troubleshooting

### "No input detected" error

Make sure you're piping What-If output to the command:

```bash
# ❌ Wrong - no piped input
bicep-whatif-advisor

# ✅ Correct - piped input
az deployment group what-if ... | bicep-whatif-advisor
```

### "API key not set" error

Set the appropriate environment variable for your provider:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "Cannot reach Ollama" error

Start the Ollama server:

```bash
ollama serve
```

For more troubleshooting, see [CLI Reference - Troubleshooting](./CLI_REFERENCE.md#troubleshooting).

## Support

- **Documentation**: See other guides in `/docs/guides/`
- **Issues**: Report bugs at the repository issues page
- **Examples**: Check `tests/fixtures/` for sample What-If outputs

## License

MIT License - See [LICENSE](../../LICENSE)
