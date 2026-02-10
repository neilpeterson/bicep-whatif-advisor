# bicep-whatif-advisor

`bicep-whatif-advisor` is an AI-powered deployment safety gate for Azure Bicep and ARM templates. It automatically integrates into your CI/CD pipeline (GitHub Actions or Azure DevOps) to analyze Azure What-If output using LLMs (Anthropic Claude, Azure OpenAI, or Ollama), providing intelligent risk assessment before deployments reach production. The tool detects infrastructure drift by comparing What-If results against your code changes, validates that deployment changes align with PR intent, and flags inherently risky operations like deletions, security changes, and SKU downgrades. With zero-configuration platform auto-detection and automatic PR comments, it blocks unsafe deployments through configurable three-bucket risk thresholds—giving teams confidence that infrastructure changes match their intentions.

> **Note:** The tool also includes a CLI for local What-If analysis and human-readable deployment summaries.

## How It Works

When integrated into your CI/CD pipeline, `bicep-whatif-advisor` automatically detects the platform (GitHub Actions or Azure DevOps) and performs comprehensive deployment analysis with zero configuration required. Simply pipe Azure What-If output to the tool and it handles the rest.

**The tool will:**
1. Extract PR metadata (title, description, number) from the CI environment
2. Collect your code diff to understand what changes are in the PR
3. Send What-If output and diff to the LLM for analysis
4. Evaluate risk across three independent categories
5. Post a detailed assessment as a PR comment
6. Exit with code 0 (safe) or 1 (unsafe) to block/allow deployment

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

## Quick Start

**GitHub Actions:**
```yaml
- name: Deployment Safety Gate
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    pip install bicep-whatif-advisor[anthropic]
    az deployment group what-if \
      --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
      --template-file main.bicep \
      --exclude-change-types NoChange Ignore \
      | bicep-whatif-advisor
```

**Azure DevOps:**
```yaml
- script: |
    pip install bicep-whatif-advisor[anthropic]
    az deployment group what-if \
      --resource-group $(RESOURCE_GROUP) \
      --template-file main.bicep \
      --exclude-change-types NoChange Ignore \
      | bicep-whatif-advisor
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

The tool automatically detects your CI platform, extracts PR metadata, analyzes code diffs, evaluates risk, posts PR comments, and blocks unsafe deployments (exit code 1) based on configurable thresholds.

## Configuration Options

### Output Formats
```bash
# JSON for additional processing
bicep-whatif-advisor --format json

# Markdown (default for PR comments)
bicep-whatif-advisor --format markdown
```

### Risk Thresholds

Control deployment sensitivity by adjusting thresholds for each risk bucket independently:

```bash
# Stricter gates (block on medium or high risk)
bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Strictest gates (block on any risk)
bicep-whatif-advisor \
  --drift-threshold low \
  --intent-threshold low \
  --operations-threshold low
```

**Available thresholds:** `low`, `medium`, `high` (default: `high` for all buckets)

**Threshold meanings:**
- `low` - Block if ANY risk detected in this category
- `medium` - Block if medium or high risk detected
- `high` - Only block on high risk (most permissive)

### Alternative LLM Providers

By default, the tool uses Anthropic Claude. You can also use Azure OpenAI or local Ollama:

```bash
# Azure OpenAI
pip install bicep-whatif-advisor[azure]
export AZURE_OPENAI_ENDPOINT="https://..."
export AZURE_OPENAI_API_KEY="..."
export AZURE_OPENAI_DEPLOYMENT="gpt-4"
bicep-whatif-advisor --provider azure-openai

# Local Ollama (free, runs on your infrastructure)
pip install bicep-whatif-advisor[ollama]
bicep-whatif-advisor --provider ollama --model llama3.1
```

### Multi-Environment Pipelines
```bash
# Distinguish environments in PR comments
bicep-whatif-advisor --comment-title "Production"
bicep-whatif-advisor --comment-title "Dev Environment"

# Non-blocking mode automatically labels the comment
bicep-whatif-advisor --comment-title "Production" --no-block
# Title becomes: "Production (non-blocking)"
```

## Complete Setup Guide

The tool works with any CI/CD platform that can run Azure CLI and Python. For complete setup instructions including:

- Azure authentication configuration (service principals, managed identities)
- Repository permissions and access tokens
- Multi-environment pipeline patterns
- Advanced configuration options
- Troubleshooting common issues

See the **[CI/CD Integration Guide](docs/guides/CICD_INTEGRATION.md)** for platform-specific examples including GitHub Actions, Azure DevOps, GitLab CI, and Jenkins.

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
