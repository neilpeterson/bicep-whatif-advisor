# whatif-explain

> Azure What-If deployment analyzer using LLMs for human-friendly summaries and safety reviews

`whatif-explain` is a Python CLI tool that accepts Azure Bicep/ARM What-If output via stdin, sends it to an LLM for analysis, and renders a human-friendly summary table in the terminal. In CI mode, it acts as an automated deployment gate with risk assessment and PR comments.

## Features

- 📊 **Human-Friendly Summaries** - Colored tables with plain English explanations of infrastructure changes
- 🔒 **Deployment Safety Gates** - Automated risk assessment for CI/CD pipelines
- 🤖 **Multiple LLM Providers** - Anthropic Claude, Azure OpenAI, or local Ollama
- 📝 **Multiple Output Formats** - Table, JSON, or Markdown
- 🚦 **PR Integration** - Post summaries directly to GitHub or Azure DevOps pull requests
- ⚡ **Fast & Lightweight** - Minimal dependencies, works anywhere Python runs

## Quick Start

### Installation

```bash
# Install with Anthropic Claude support (recommended)
pip install whatif-explain[anthropic]

# Or with Azure OpenAI
pip install whatif-explain[azure]

# Or with local Ollama
pip install whatif-explain[ollama]

# Or install all providers
pip install whatif-explain[all]
```

### Basic Usage

```powershell
# Set your API key
$env:ANTHROPIC_API_KEY = "your-api-key"

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

## CLI Reference

### Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--provider` | `-p` | `anthropic` | LLM provider: `anthropic`, `azure-openai`, `ollama` |
| `--model` | `-m` | Provider default | Override model name |
| `--format` | `-f` | `table` | Output format: `table`, `json`, `markdown` |
| `--verbose` | `-v` | | Include property-level change details |
| `--no-color` | | | Disable colored output |
| `--version` | | | Print version and exit |
| `--help` | `-h` | | Print help |

### CI Mode Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--ci` | | | Enable CI mode with risk assessment |
| `--diff` | `-d` | Auto-detect | Path to diff file or auto-run `git diff` |
| `--diff-ref` | | `HEAD~1` | Git ref to diff against |
| `--risk-threshold` | | `high` | Fail at: `low`, `medium`, `high`, `critical` |
| `--post-comment` | | | Post summary as PR comment |
| `--pr-url` | | Auto-detect | PR URL for comments |
| `--bicep-dir` | | `.` | Path to Bicep source files |

## Environment Variables

### Provider Credentials

**Anthropic:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

**Azure OpenAI:**
```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-key"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
```

**Ollama:**
```powershell
$env:OLLAMA_HOST = "http://localhost:11434"  # Optional, this is the default
```

### Optional Overrides

```powershell
$env:WHATIF_PROVIDER = "anthropic"  # Override default provider
$env:WHATIF_MODEL = "claude-sonnet-4-20250514"  # Override default model
```

## Usage Examples

### Different Output Formats

```bash
# Table (default, colored)
az deployment group what-if ... | whatif-explain

# JSON (for scripting)
az deployment group what-if ... | whatif-explain --format json

# Markdown (for documentation)
az deployment group what-if ... | whatif-explain --format markdown

# Pipe JSON to jq for filtering
az deployment group what-if ... | whatif-explain -f json | jq '.resources[] | select(.action == "Delete")'
```

### Verbose Mode

```bash
# Show property-level changes for modified resources
az deployment group what-if ... | whatif-explain --verbose
```

### Different Providers

```bash
# Use Azure OpenAI
az deployment group what-if ... | whatif-explain --provider azure-openai

# Use local Ollama
az deployment group what-if ... | whatif-explain --provider ollama --model llama3.1

# Use a different Claude model
az deployment group what-if ... | whatif-explain --model claude-opus-4
```

### CI Mode (Deployment Gate)

```powershell
# Run as deployment gate in CI pipeline
az deployment group what-if ... > whatif-output.txt

cat whatif-output.txt | whatif-explain `
  --ci `
  --diff-ref origin/main `
  --risk-threshold high `
  --post-comment `
  --format markdown

# Exit code 0 = safe to deploy
# Exit code 1 = unsafe, block deployment
if ($LASTEXITCODE -eq 0) {
  az deployment group create --template-file main.bicep
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or safe in CI mode) |
| `1` | Error or unsafe deployment (in CI mode) |
| `2` | Invalid input (no piped input, empty stdin) |

## Providers

### Azure OpenAI

Use your own Azure OpenAI deployment.

```powershell
pip install whatif-explain[azure]
$env:AZURE_OPENAI_ENDPOINT = "https://..."
$env:AZURE_OPENAI_API_KEY = "..."
$env:AZURE_OPENAI_DEPLOYMENT = "..."
```

### Anthropic Claude

Fast, accurate, and easy to set up.

```powershell
pip install whatif-explain[anthropic]
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Default model: `claude-sonnet-4-20250514`

### Ollama (Local)

Run LLMs locally without API calls.

```bash
pip install whatif-explain[ollama]
ollama pull llama3.1
ollama serve
```

Default model: `llama3.1`

## CI/CD Integration

See [PIPELINE.md](docs/PIPELINE.md) for complete CI/CD integration guides for:
- GitHub Actions
- Azure DevOps Pipelines

## Troubleshooting

### "No input detected" error

Make sure you're piping What-If output to the command:

```bash
# ❌ Wrong - no piped input
whatif-explain

# ✅ Correct - piped input
az deployment group what-if ... | whatif-explain
```

### "ANTHROPIC_API_KEY environment variable not set"

Set your API key:

```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### "Cannot reach Ollama" error

Make sure Ollama is running:

```bash
ollama serve
```

### LLM returns invalid JSON

The tool attempts to extract JSON from malformed responses. If this fails consistently:
- Try a different model with `--model`
- Check if your What-If output is extremely large (truncated to 100k chars)
- Use a more capable model (e.g., Claude Opus)

## Contributing

Issues and pull requests are welcome! Please see the repository for contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## Links

- Anthropic API: https://console.anthropic.com/
- Azure OpenAI: https://azure.microsoft.com/products/ai-services/openai-service
- Ollama: https://ollama.com/
