# User Guide

Complete guide to using `bicep-whatif-advisor` for local development and understanding all features.

**New to the tool?** Start with [QUICKSTART.md](./QUICKSTART.md) for a 5-minute introduction.

---

## Table of Contents

- [Installation](#installation)
- [Basic Usage](#basic-usage)
- [Output Formats](#output-formats)
- [Noise Filtering](#noise-filtering)
- [Operating Modes](#operating-modes)
- [CLI Flags Reference](#cli-flags-reference)
- [Environment Variables](#environment-variables)
- [Common Patterns](#common-patterns)
- [Troubleshooting](#troubleshooting)

---

## Installation

### From PyPI (Recommended)

**For most users** - Install the published package:

```bash
# With Anthropic Claude support (recommended)
pip install bicep-whatif-advisor[anthropic]

# With Azure OpenAI
pip install bicep-whatif-advisor[azure]

# With all providers
pip install bicep-whatif-advisor[all]
```

### From Source (Contributors)

**For contributors and developers** - Install from source to modify the code:

```bash
# Clone the repository
git clone https://github.com/neilpeterson/bicep-whatif-advisor.git
cd bicep-whatif-advisor

# Install with Anthropic support
pip install -e .[anthropic]

# Or install for development (includes test dependencies)
pip install -e .[all,dev]
```

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Azure CLI installed and configured
- An LLM provider account (Anthropic, Azure OpenAI, or Ollama)

---

## Basic Usage

### Default Output (Table Format)

```bash
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor
```

**Example Output:**

```
╭──────┬────────────────┬─────────────────┬────────┬─────────────────────────────╮
│ #    │ Resource       │ Type            │ Action │ Summary                     │
├──────┼────────────────┼─────────────────┼────────┼─────────────────────────────┤
│ 1    │ appinsights    │ APIM Diagnostic │ Create │ Adds Application Insights   │
│      │                │                 │        │ logging with 100% sampling  │
╰──────┴────────────────┴─────────────────┴────────┴─────────────────────────────╯

Summary: This deployment creates diagnostic logging configuration.
```

### Different Providers

```bash
# Use Azure OpenAI
az deployment group what-if ... | bicep-whatif-advisor --provider azure-openai

# Use local Ollama
az deployment group what-if ... | bicep-whatif-advisor --provider ollama

# Override model
az deployment group what-if ... | bicep-whatif-advisor --model claude-opus-4-20250514
```

### Verbose Output

```bash
# Show property-level details for Modify actions
az deployment group what-if ... | bicep-whatif-advisor --verbose
```

---

## Output Formats

### Table (Default)

Colored, formatted table with action symbols:

- ✅ Create
- ✏️ Modify
- ❌ Delete
- 🚀 Deploy
- ⚪ NoChange
- ⚫ Ignore

```bash
az deployment group what-if ... | bicep-whatif-advisor
```

### JSON

Structured output for scripting and automation:

```bash
az deployment group what-if ... | bicep-whatif-advisor --format json
```

**Example:**

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

```bash
az deployment group what-if ... | bicep-whatif-advisor --format markdown
```

**Example:**

```markdown
| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | myAppService | Web App | Create | Creates new web app with B1 SKU |

**Summary:** This deployment creates 1 new resource
```

---

## Noise Filtering

Azure What-If output often includes "noise" — spurious property changes like `etag`, `provisioningState`, and IPv6 flags that don't represent real infrastructure changes. Left unfiltered, these can cause false positives in CI mode.

The tool uses a two-layer approach: pre-LLM property filtering (removes noise before the LLM ever sees it) and post-LLM confidence scoring (the LLM flags remaining uncertain changes).

### Built-in Patterns (Always On)

A curated set of known-noisy Azure property names is bundled with the tool and applied automatically to every run. These are matched against property-change lines in the raw What-If text **before** sending to the LLM:

| Pattern | Catches |
|---------|---------|
| `etag` | ETag header changes on any resource |
| `provisioningState` | ARM state transitions (not real changes) |
| `resourceGuid` | GUID regeneration on networking resources |
| `ipv6AddressSpace`, `disableIpv6`, `enableIPv6Addressing` | Spurious IPv6 flags |
| `logAnalyticsDestinationType` | Diagnostics setting noise |
| `hidden-link:`, `hidden-title` | Azure-managed hidden tags |
| `inboundNatRules`, `effectiveRouteTable`, ... | Computed networking fields |

To disable built-ins (e.g., if you care about IPv6 changes in your environment):

```bash
az deployment group what-if ... | bicep-whatif-advisor --no-builtin-patterns
```

### Custom Patterns File (Optional, Additive)

Add your own property-path patterns to suppress project-specific noise. The file is additive — your patterns combine with the built-ins.

```bash
# Create a patterns file (one keyword per line, # for comments)
cat > noise-patterns.txt <<EOF
# Custom noise for our environment
creationTime
lastModifiedTime

# Use regex: prefix for advanced matching
regex: properties\.metadata\..*Version

# Use fuzzy: prefix for legacy summary-text matching
fuzzy: Changes to internal routing table
EOF

# Use with the tool
az deployment group what-if ... | bicep-whatif-advisor \
  --noise-file noise-patterns.txt
```

**Pattern types:**

| Prefix | Match Strategy |
|--------|---------------|
| *(none)* | Case-insensitive substring — keyword appears anywhere in the property-change line |
| `regex:` | Python `re.search()`, case-insensitive |
| `fuzzy:` | Legacy fuzzy similarity (SequenceMatcher) — `--noise-threshold` applies |

### Automatic Confidence Scoring (Always On)

After filtering, the LLM assigns a confidence level to each remaining resource change:

- **High** - Real, meaningful changes (resource creation/deletion, security changes)
- **Medium** - Potentially real but uncertain (retention policies, dynamic references)
- **Low** - Likely noise the LLM identified on its own (computed properties not caught by patterns)

Low-confidence resources are automatically:
- ✅ Excluded from risk analysis (in CI mode)
- ✅ Displayed separately in a "Potential Noise" section
- ✅ Still visible for verification

**Example Output:**

```
╭──────┬────────────────┬─────────────────┬────────┬─────────────────────────╮
│ #    │ Resource       │ Type            │ Action │ Summary                 │
├──────┼────────────────┼─────────────────┼────────┼─────────────────────────┤
│ 1    │ myApp          │ Web App         │ Create │ Creates new web app     │
╰──────┴────────────────┴─────────────────┴────────┴─────────────────────────╯

⚠️  Potential Azure What-If Noise (Low Confidence)
╭──────┬────────────────┬─────────────────┬────────┬─────────────────────────╮
│ 1    │ mySubnet       │ VNET            │ Modify │ IPv6 flag change        │
╰──────┴────────────────┴─────────────────┴────────┴─────────────────────────╯
```

---

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

**Example:**

```bash
az deployment group what-if ... | bicep-whatif-advisor
```

### CI Mode

For CI/CD pipelines. Automatically enabled when running in GitHub Actions or Azure DevOps.

**Features:**
- Everything in Standard Mode, plus:
- Three-bucket risk assessment (drift, intent, operations)
- Git diff analysis
- PR intent validation
- Deployment verdicts with configurable thresholds
- Exit codes: 0 (safe), 1 (unsafe), 2 (input error), 130 (interrupted)
- Automatic PR comment posting

**Use Cases:**
- CI/CD deployment gates
- Automated safety reviews
- Pull request reviews

**Example:**

```bash
# Auto-detected in GitHub Actions or Azure DevOps
az deployment group what-if ... | bicep-whatif-advisor

# Manual CI mode
az deployment group what-if ... | bicep-whatif-advisor --ci --diff-ref origin/main
```

**For CI/CD setup,** see [CICD_INTEGRATION.md](./CICD_INTEGRATION.md)

**For risk assessment details,** see [RISK_ASSESSMENT.md](./RISK_ASSESSMENT.md)

---

## CLI Flags Reference

### Core Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--version` | Show version and exit | - |
| `--help` | Show help message | - |
| `--verbose`, `-v` | Show property-level changes for Modify actions | `false` |
| `--no-color` | Disable colored output | `false` |

### Provider Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--provider` | LLM provider: `anthropic`, `azure-openai`, `ollama` | `anthropic` |
| `--model` | Override default model for the provider | Provider-specific |

**Default models:**
- Anthropic: `claude-sonnet-4-20250514`
- Azure OpenAI: Deployment-dependent
- Ollama: `llama3.1`

### Output Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--format`, `-f` | Output format: `table`, `json`, `markdown` | `table` |

### CI Mode Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--ci` | Enable CI mode (auto-detected in GitHub Actions/Azure DevOps) | `false` |
| `--diff` | Path to git diff file | - |
| `--diff-ref` | Git reference for diff (e.g., `origin/main`, `HEAD~1`) | `HEAD~1` |
| `--pr-title` | PR title for intent validation (auto-detected in pipelines) | - |
| `--pr-description` | PR description for intent validation (auto-detected) | - |
| `--pr-url` | PR URL for comment posting (auto-detected) | - |
| `--drift-threshold` | Drift bucket threshold: `low`, `medium`, `high` | `high` |
| `--intent-threshold` | Intent bucket threshold: `low`, `medium`, `high` | `high` |
| `--operations-threshold` | Operations bucket threshold: `low`, `medium`, `high` | `high` |
| `--skip-drift` | Skip infrastructure drift risk assessment | `false` |
| `--skip-intent` | Skip PR intent alignment risk assessment | `false` |
| `--skip-operations` | Skip risky operations risk assessment | `false` |
| `--post-comment` | Post analysis as PR comment (auto-enabled if token exists) | `false` |
| `--comment-title` | Custom title for PR comment | `What-If Deployment Review` |
| `--no-block` | Report findings without failing pipeline (exit code 0) | `false` |

### Noise Filtering Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--noise-file` | Path to additional noise patterns file (additive with built-ins) | - |
| `--noise-threshold` | Similarity threshold % for `fuzzy:` prefix patterns only (0-100) | `80` |
| `--no-builtin-patterns` | Disable the bundled Azure What-If noise patterns | `false` |

### Output Control Flags

| Flag | Description | Default |
|------|-------------|---------|
| `--include-whatif` | Include raw What-If output in markdown/PR comment as collapsible section | `false` |

---

## Environment Variables

### Provider Credentials

| Variable | Required For | Description |
|----------|--------------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic provider | Anthropic API key from https://console.anthropic.com/ |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI provider | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI provider | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | Azure OpenAI provider | Deployment name |
| `OLLAMA_HOST` | Ollama provider (optional) | Ollama host (default: `http://localhost:11434`) |

### CI/CD Platform Variables

| Variable | Platform | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | GitHub Actions | Required for posting PR comments |
| `GITHUB_REPOSITORY` | GitHub Actions | Auto-set by GitHub Actions |
| `GITHUB_EVENT_PATH` | GitHub Actions | Auto-set by GitHub Actions |
| `SYSTEM_ACCESSTOKEN` | Azure DevOps | Required for posting PR comments |
| `SYSTEM_COLLECTIONURI` | Azure DevOps | Auto-set by Azure DevOps |
| `SYSTEM_TEAMPROJECT` | Azure DevOps | Auto-set by Azure DevOps |
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | Azure DevOps | Auto-set by Azure DevOps |
| `BUILD_REPOSITORY_ID` | Azure DevOps | Auto-set by Azure DevOps |

### Optional Overrides

| Variable | Description |
|----------|-------------|
| `WHATIF_PROVIDER` | Default provider (overridden by `--provider` flag) |
| `WHATIF_MODEL` | Default model (overridden by `--model` flag) |

---

## Common Patterns

### Local Development

```bash
# Quick analysis with default settings
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor

# Verbose output for detailed changes
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor --verbose

# JSON output for scripting
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor -f json

# Filter out known noise patterns
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor \
  --noise-file ./noise-patterns.txt
```

### Testing Before CI/CD

```bash
# Simulate CI mode locally
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --pr-title "Add monitoring resources" \
  --pr-description "This PR adds Application Insights"

# Test with strict thresholds
az deployment group what-if -g my-rg -f main.bicep | bicep-whatif-advisor \
  --ci \
  --drift-threshold low \
  --intent-threshold low \
  --operations-threshold low
```

### Skipping Risk Buckets

```bash
# Skip infrastructure drift assessment (useful when state differs from code)
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --skip-drift

# Skip PR intent alignment (useful for automated maintenance PRs)
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --skip-intent

# Skip risky operations assessment (focus only on drift and intent)
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --skip-operations

# Combine skip flags (only evaluate drift bucket)
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --skip-intent \
  --skip-operations \
  --pr-title "Update configuration"
```

**Note:** At least one risk bucket must remain enabled in CI mode.

### Different Providers

```bash
# Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://my-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="gpt-4"
az deployment group what-if ... | bicep-whatif-advisor --provider azure-openai

# Local Ollama (free)
ollama pull llama3.1
ollama serve
az deployment group what-if ... | bicep-whatif-advisor --provider ollama
```

---

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
# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="gpt-4"
```

### "Cannot reach Ollama" error

Start the Ollama server:

```bash
ollama serve
```

Or set a custom host:

```bash
export OLLAMA_HOST="http://localhost:11434"
```

### "Input too large" warning

The tool truncates inputs exceeding 100,000 characters. Solutions:

1. Use `--exclude-change-types NoChange Ignore` with Azure What-If
2. Filter noise with `--noise-file` to reduce resource count
3. Deploy in smaller batches

### Rate limiting errors

If you hit provider rate limits:

1. **Anthropic:** Upgrade API tier or wait for rate limit reset
2. **Azure OpenAI:** Increase TPM quota or use different deployment
3. **Ollama:** No rate limits (runs locally)

The tool automatically retries once on network errors.

### Unexpected risk assessment

If CI mode produces unexpected results:

1. Check the PR comment for detailed reasoning
2. Review the three risk buckets independently
3. Adjust thresholds if needed (`--drift-threshold`, `--intent-threshold`, `--operations-threshold`)
4. Provide more context in PR description for intent validation
5. See [RISK_ASSESSMENT.md](./RISK_ASSESSMENT.md) for how risk evaluation works

### CI mode not auto-detecting

If running in GitHub Actions or Azure DevOps but CI mode doesn't activate:

1. Ensure running in a PR context (not main/master branch)
2. Check that platform environment variables are set
3. Manually enable with `--ci` flag if needed

### Exit codes

| Code | Meaning | Resolution |
|------|---------|------------|
| 0 | Success/Safe | Deployment can proceed |
| 1 | Unsafe/Error | Review PR comment, fix issues, or adjust thresholds |
| 2 | Input error | Check command syntax and input |
| 130 | Interrupted | User pressed Ctrl+C |

---

## Next Steps

- **Set up CI/CD:** [CICD_INTEGRATION.md](./CICD_INTEGRATION.md)
- **Understand risk model:** [RISK_ASSESSMENT.md](./RISK_ASSESSMENT.md)
- **Quick reference:** [QUICKSTART.md](./QUICKSTART.md)

## Support

- **Documentation:** See other guides in `/docs/guides/`
- **Issues:** Report bugs at the repository issues page
- **Examples:** Check `tests/fixtures/` for sample What-If outputs

## License

MIT License - See [LICENSE](../../LICENSE)
