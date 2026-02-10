# bicep-whatif-advisor

`bicep-whatif-advisor` is a Python CLI tool that transforms Azure's technical What-If deployment output into plain English summaries. It pipes What-If results to an LLM (Anthropic Claude, Azure OpenAI, or Ollama) which analyzes each resource change and explains what's actually happening in human-readable terms. In CI/CD pipelines, it automatically detects your platform (GitHub Actions or Azure DevOps), analyzes your code diff alongside the What-If output to detect drift and unintended changes, evaluates deployment risk across three independent categories, and posts detailed safety assessments as PR comments—blocking unsafe deployments before they reach production.

## Quick Start

```bash
# Install with Anthropic Claude support
pip install bicep-whatif-advisor[anthropic]

# Set your API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Run analysis
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  | bicep-whatif-advisor
```

## CLI Mode (Local Development)

For interactive usage and local development. Provides human-readable summaries of infrastructure changes.

**Usage:**
```bash
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
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
├──────┼───────────────────────────┼──────────────────────┼────────┼─────────────────────────────────────┤
│ 3    │ storageAccount            │ Storage Account      │ Delete │ Removes storage account including   │
│      │                           │                      │        │ all blobs, tables, and queues.      │
╰──────┴───────────────────────────┴──────────────────────┴────────┴─────────────────────────────────────╯

Overall: This deployment updates API Management policies and diagnostics, but also deletes a storage
account. Verify that the storage account deletion is intentional.
```

**Features:**
- Plain English explanations of each resource change
- Colored output with action symbols (Create, Modify, Delete)
- Overall deployment summary
- Multiple output formats: `--format json|markdown|table`
- Multiple LLM providers: `--provider anthropic|azure-openai|ollama`

## CI Mode (Automated Deployment Gates)

For CI/CD pipelines. Automatically detects GitHub Actions or Azure DevOps and enables deployment safety gates with risk assessment.

**Usage:**
```bash
# Automatically detects CI environment - zero config needed
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor

# Exit code: 0 = safe | 1 = unsafe (blocks deployment)
```

**Example Output:**
```
╭──────┬────────────────┬─────────────────┬────────┬──────┬────────────────────────────────────────╮
│ #    │ Resource       │ Type            │ Action │ Risk │ Summary                                │
├──────┼────────────────┼─────────────────┼────────┼──────┼────────────────────────────────────────┤
│ 1    │ appinsights    │ APIM Diagnostic │ Create │ Low  │ Adds Application Insights logging      │
├──────┼────────────────┼─────────────────┼────────┼──────┼────────────────────────────────────────┤
│ 2    │ sqlDatabase    │ SQL Database    │ Modify │ Med  │ Changes SKU from Standard to Basic     │
├──────┼────────────────┼─────────────────┼────────┼──────┼────────────────────────────────────────┤
│ 3    │ roleAssignment │ Role Assignment │ Delete │ High │ Removes Contributor access from        │
│      │                │                 │        │      │ managed identity                       │
╰──────┴────────────────┴─────────────────┴────────┴──────┴────────────────────────────────────────╯

Risk Assessment:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Infrastructure Drift: LOW
   All changes match code diff

PR Intent Alignment: MEDIUM
   PR mentions adding logging, but also includes database SKU change not described

Risky Operations: HIGH
   Deletes RBAC role assignment (Contributor)
   Downgrades database SKU (may cause data loss)

Verdict: UNSAFE - Deployment blocked
Reason: Risky operations exceed threshold (high). Address role deletion and SKU downgrade.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

**Features:**
- **Platform Auto-Detection** - Automatically enables CI mode in GitHub Actions/Azure DevOps
- **Three-Bucket Risk Assessment** - Independent evaluation across:
  - **Infrastructure Drift** - Detects changes not in your code (out-of-band modifications)
  - **PR Intent Alignment** - Ensures changes match PR description
  - **Risky Operations** - Flags dangerous operations (deletions, security changes, downgrades)
- **Configurable Thresholds** - Set sensitivity per bucket: `--drift-threshold`, `--intent-threshold`, `--operations-threshold`
- **Automatic PR Comments** - Posts detailed analysis (zero config when using platform tokens)
- **Deployment Gating** - Exit codes block unsafe deployments automatically

## Additional Options

### Output Formats
```bash
# JSON for scripting
bicep-whatif-advisor --format json

# Markdown for documentation
bicep-whatif-advisor --format markdown
```

### LLM Providers
```bash
# Azure OpenAI
pip install bicep-whatif-advisor[azure]
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="gpt-4"
bicep-whatif-advisor --provider azure-openai

# Local Ollama
bicep-whatif-advisor --provider ollama --model llama3.1
```

### Adjust Risk Thresholds (CI Mode)
```bash
# Stricter gates (block on medium or high)
bicep-whatif-advisor \
  --drift-threshold medium \
  --operations-threshold medium
```

**Available thresholds:** `low`, `medium`, `high` (defaults to `high`)

### Multi-Environment Pipelines
```bash
# Distinguish environments in PR comments
bicep-whatif-advisor --comment-title "Production"
bicep-whatif-advisor --comment-title "Dev Environment"

# Non-blocking mode automatically labels the comment
bicep-whatif-advisor --comment-title "Production" --no-block
# Title becomes: "Production (non-blocking)"
```

## CI/CD Integration

### GitHub Actions
```yaml
- name: Deployment Safety Gate
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if \
      --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
      --template-file main.bicep \
      --exclude-change-types NoChange Ignore \
      | bicep-whatif-advisor
```

### Azure DevOps
```yaml
- script: |
    az deployment group what-if \
      --resource-group $(RESOURCE_GROUP) \
      --template-file main.bicep \
      --exclude-change-types NoChange Ignore \
      | bicep-whatif-advisor
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

**Auto-detects:** CI environment, PR metadata, diff analysis, and automatically posts PR comments.

See **[CI/CD Integration Guide](docs/guides/CICD_INTEGRATION.md)** for complete setup instructions including Azure authentication.

## Documentation

**User Guides:**
- [Getting Started](docs/guides/GETTING_STARTED.md) - Complete installation and usage guide
- [CI/CD Integration](docs/guides/CICD_INTEGRATION.md) - Pipeline setup for GitHub Actions, Azure DevOps, GitLab, Jenkins
- [Risk Assessment](docs/guides/RISK_ASSESSMENT.md) - How risk evaluation works
- [CLI Reference](docs/guides/CLI_REFERENCE.md) - Complete command reference

**Technical Specifications:**
- [Project Specification](docs/specs/SPECIFICATION.md) - Technical design and architecture
- [Platform Auto-Detection](docs/specs/PLATFORM_AUTO_DETECTION_PLAN.md) - CI/CD auto-detection implementation

## Support

- **Issues**: Report bugs or request features via repository issues
- **Contributing**: Pull requests welcome!
- **License**: MIT - see [LICENSE](LICENSE) for details
