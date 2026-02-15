# Quick Start Guide

Get `bicep-whatif-advisor` running in 5 minutes.

## What is it?

`bicep-whatif-advisor` transforms Azure Bicep/ARM What-If output into AI-powered summaries. It works locally for readable deployment previews, or in CI/CD pipelines as an automated deployment safety gate.

## Installation

```bash
pip install bicep-whatif-advisor[anthropic]
```

**Need other providers?**
- Azure OpenAI: `pip install bicep-whatif-advisor[azure]`
- Ollama (local): `pip install bicep-whatif-advisor[ollama]`
- All providers: `pip install bicep-whatif-advisor[all]`

## Set API Key

**For Anthropic Claude (recommended):**

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="sk-ant-..."

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Get your API key from: https://console.anthropic.com/

**For other providers,** see [USER_GUIDE.md](./USER_GUIDE.md#environment-variables)

## Test with Sample Data

```bash
cat tests/fixtures/create_only.txt | bicep-whatif-advisor
```

You should see a colorful table with resource summaries:

```
╭──────┬────────────────┬─────────────────┬────────┬─────────────────────────────╮
│ #    │ Resource       │ Type            │ Action │ Summary                     │
├──────┼────────────────┼─────────────────┼────────┼─────────────────────────────┤
│ 1    │ appinsights    │ APIM Diagnostic │ Create │ Adds Application Insights   │
╰──────┴────────────────┴─────────────────┴────────┴─────────────────────────────╯
```

## Run with Real Azure What-If

```bash
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --exclude-change-types NoChange Ignore \
  | bicep-whatif-advisor
```

**That's it!** You're analyzing Azure deployments with AI.

## Next Steps

**For local development:**
- [USER_GUIDE.md](./USER_GUIDE.md) - Learn all features (output formats, noise filtering, providers)

**For CI/CD pipelines:**
- [CICD_INTEGRATION.md](./CICD_INTEGRATION.md) - Set up deployment gates in GitHub Actions, Azure DevOps, etc.

**Understand the AI:**
- [RISK_ASSESSMENT.md](./RISK_ASSESSMENT.md) - How the three-bucket risk model works

## Common Issues

**"No input detected"**
- Make sure you're piping What-If output: `az ... | bicep-whatif-advisor`

**"API key not set"**
- Set the environment variable for your provider (see above)

**"Cannot reach Ollama"**
- Start Ollama server: `ollama serve`

For more troubleshooting, see [USER_GUIDE.md - Troubleshooting](./USER_GUIDE.md#troubleshooting)
