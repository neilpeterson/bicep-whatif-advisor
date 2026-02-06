# Implementation Guide: whatif-explain

This document provides step-by-step instructions for installing, using, and integrating the `whatif-explain` tool.

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager
- Azure CLI installed and configured
- An LLM provider account (Anthropic, Azure OpenAI, or Ollama)

### Install from Source

```bash
cd whatif-explain

# Install with Anthropic support
pip install -e .[anthropic]

# Or install all providers
pip install -e .[all]

# Or install for development (includes test dependencies)
pip install -e .[all,dev]
```

### Install from PyPI (when published)

```bash
pip install whatif-explain[anthropic]
```

## Quick Start

### 1. Set Up API Credentials

**For Anthropic Claude (recommended):**

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

Get your API key from: https://console.anthropic.com/

**For Azure OpenAI:**

```bash
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-api-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
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
cat tests/fixtures/create_only.txt | whatif-explain

# You should see a colorful table with resource summaries
```

### 3. Use with Real Azure What-If Output

```bash
# Run Azure What-If and pipe to whatif-explain
az deployment group what-if \
  --resource-group my-rg \
  --template-file ./bicep-sample/main.bicep \
  --parameters ./bicep-sample/tme-lab.bicepparam \
  --exclude-change-types NoChange Ignore | whatif-explain
```

## Command-Line Usage

### Basic Usage

```bash
# Default: table format with Anthropic
az deployment group what-if ... | whatif-explain

# JSON format (for scripting)
az deployment group what-if ... | whatif-explain --format json

# Markdown format (for documentation)
az deployment group what-if ... | whatif-explain --format markdown

# With verbose property-level details
az deployment group what-if ... | whatif-explain --verbose
```

### Different Providers

```bash
# Use Azure OpenAI
az deployment group what-if ... | whatif-explain --provider azure-openai

# Use local Ollama
az deployment group what-if ... | whatif-explain --provider ollama

# Override model
az deployment group what-if ... | whatif-explain --model claude-opus-4-20250101
```

### Scripting with JSON Output

```bash
# Save to file
az deployment group what-if ... | whatif-explain --format json > analysis.json

# Filter with jq
az deployment group what-if ... | whatif-explain -f json | \
  jq '.resources[] | select(.action == "Delete")'

# Count creates
az deployment group what-if ... | whatif-explain -f json | \
  jq '[.resources[] | select(.action == "Create")] | length'
```

## CI/CD Pipeline Integration

### GitHub Actions

**File: `.github/workflows/deploy.yml`**

```yaml
name: Infrastructure Deployment

on:
  pull_request:
    paths:
      - 'infra/**'

jobs:
  whatif-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Install whatif-explain
        run: pip install whatif-explain[anthropic]

      - name: Run What-If
        run: |
          az deployment group what-if \
            --resource-group my-rg \
            --template-file infra/main.bicep \
            --parameters infra/parameters.json \
            --exclude-change-types NoChange Ignore \
            > whatif-output.txt

      - name: AI Review & Gate
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          cat whatif-output.txt | whatif-explain \
            --ci \
            --diff-ref origin/main \
            --risk-threshold high \
            --post-comment
```

**Setup:**

1. Add `ANTHROPIC_API_KEY` to repository secrets
2. Add `AZURE_CREDENTIALS` to repository secrets
3. Commit the workflow file
4. Create a PR to test

### Azure DevOps

**File: `azure-pipelines.yml`**

```yaml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - infra/*

pool:
  vmImage: ubuntu-latest

stages:
  - stage: Review
    jobs:
      - job: WhatIfReview
        steps:
          - checkout: self
            fetchDepth: 0

          - task: AzureCLI@2
            displayName: 'What-If'
            inputs:
              azureSubscription: 'my-service-connection'
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: |
                az deployment group what-if \
                  --resource-group my-rg \
                  --template-file infra/main.bicep \
                  --parameters infra/parameters.json \
                  --exclude-change-types NoChange Ignore \
                  > $(Build.ArtifactStagingDirectory)/whatif.txt

          - task: Bash@3
            displayName: 'Install Tool'
            inputs:
              targetType: inline
              script: pip install whatif-explain[anthropic]

          - task: Bash@3
            displayName: 'AI Review'
            env:
              ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
              SYSTEM_ACCESSTOKEN: $(System.AccessToken)
            inputs:
              targetType: inline
              script: |
                cat $(Build.ArtifactStagingDirectory)/whatif.txt | whatif-explain \
                  --ci \
                  --risk-threshold high \
                  --post-comment
```

**Setup:**

1. Add `ANTHROPIC_API_KEY` as pipeline variable (secret)
2. Create Azure service connection
3. Enable "Allow scripts to access OAuth token" in pipeline settings
4. Commit the pipeline file

## Testing the Implementation

### Run Test Fixtures

```bash
cd whatif-explain

# Test with create-only fixture
cat tests/fixtures/create_only.txt | python -m whatif_explain.cli

# Test with mixed changes
cat tests/fixtures/mixed_changes.txt | whatif-explain --verbose

# Test CI mode (requires git repo)
cat tests/fixtures/deletes.txt | whatif-explain \
  --ci \
  --diff tests/fixtures/diffs/risky_delete.diff \
  --risk-threshold high
```

### Expected Output

You should see:
1. ✅ Colored table with resource names and summaries
2. Clear action symbols (✅ Create, ✏️ Modify, ❌ Delete)
3. Overall summary at the bottom
4. In CI mode: risk assessment and verdict

### Test All Output Formats

```bash
# Table (default)
cat tests/fixtures/create_only.txt | whatif-explain

# JSON
cat tests/fixtures/create_only.txt | whatif-explain --format json

# Markdown
cat tests/fixtures/create_only.txt | whatif-explain --format markdown
```

## Troubleshooting

### Command not found: whatif-explain

```bash
# Make sure it's installed
pip install -e .

# Or run directly
python -m whatif_explain.cli --help
```

### No input detected

You must pipe What-If output to the command:

```bash
# ❌ Wrong
whatif-explain

# ✅ Correct
cat file.txt | whatif-explain
```

### API Key errors

```bash
# Verify environment variable is set
echo $ANTHROPIC_API_KEY

# Set it if missing
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Module import errors

```bash
# Install with provider extras
pip install -e .[anthropic]

# Check installation
pip show whatif-explain
```

## Advanced Usage

### Custom Risk Thresholds

```bash
# Very strict - block on any risk
whatif-explain --ci --risk-threshold low

# Recommended for production
whatif-explain --ci --risk-threshold high

# Only block critical risks
whatif-explain --ci --risk-threshold critical
```

### Multiple Resource Groups

```bash
# Review each scope separately
for rg in rg-app rg-data rg-network; do
  echo "Reviewing $rg..."
  az deployment group what-if -g $rg -f main.bicep | whatif-explain
done
```

### Save Analysis Results

```bash
# Save JSON for later processing
az deployment group what-if ... | \
  whatif-explain --format json | \
  tee analysis.json

# Generate markdown report
az deployment group what-if ... | \
  whatif-explain --format markdown > DEPLOYMENT_PLAN.md
```

## Development

### Run Tests (when implemented)

```bash
cd whatif-explain

# Install dev dependencies
pip install -e .[all,dev]

# Run all tests
pytest

# Run specific test file
pytest tests/test_input.py -v

# Run with coverage
pytest --cov=whatif_explain --cov-report=html
```

### Code Quality

```bash
# Format code
ruff format .

# Lint code
ruff check .

# Type checking (if mypy is installed)
mypy whatif_explain/
```

## Next Steps

1. **Try with Real Deployments:** Use with your actual Bicep templates
2. **Integrate into CI/CD:** Add to your GitHub Actions or Azure DevOps pipelines
3. **Customize Risk Thresholds:** Adjust based on your team's risk tolerance
4. **Review PR Comments:** Check the AI-generated summaries and recommendations
5. **Iterate:** Refine your Bicep templates based on insights

## Support

- **Documentation:** See [README.md](../README.md) and [PIPELINE.md](PIPELINE.md)
- **Issues:** Report bugs or request features at your repository issues page
- **Examples:** Check `tests/fixtures/` for sample What-If outputs

## License

MIT License - See [LICENSE](../LICENSE)
