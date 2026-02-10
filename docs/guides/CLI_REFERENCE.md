# bicep-whatif-advisor Reference Guide

This document provides comprehensive details, examples, and configuration options for `bicep-whatif-advisor`.

## Table of Contents

- [Standard vs CI Mode](#standard-vs-ci-mode)
- [CLI Reference](#cli-reference)
- [Environment Variables](#environment-variables)
- [Output Formats](#output-formats)
- [CI Mode Deep Dive](#ci-mode-deep-dive)
- [Risk Classification](#risk-classification)
- [PR Intent Analysis](#pr-intent-analysis)
- [Usage Examples](#usage-examples)
- [Provider Configuration](#provider-configuration)
- [CI/CD Integration Examples](#cicd-integration-examples)
- [Troubleshooting](#troubleshooting)

## Standard vs CI Mode

`bicep-whatif-advisor` operates in two distinct modes:

### Standard Mode (Default)

**Purpose:** Human-readable summary of infrastructure changes

**Usage:**
```bash
az deployment group what-if ... | bicep-whatif-advisor
```

**Features:**
- ✅ Summarizes What-If output in plain English
- ✅ Colored table or JSON/Markdown output
- ✅ No risk assessment
- ✅ Always exits with code 0 (success)
- ✅ No git context needed

**Best for:**
- Interactive terminal usage
- Quick understanding of what will change
- Documentation and reporting
- Local development

### CI Mode (--ci flag)

**Purpose:** Automated deployment safety gate for pipelines

**Usage:**
```bash
az deployment group what-if ... | bicep-whatif-advisor --ci --diff-ref origin/main
```

**Features:**
- ✅ Everything in Standard Mode, plus:
- ✅ Risk assessment for each resource (none/low/medium/high/critical)
- ✅ Git diff analysis to see code changes
- ✅ PR intent analysis to catch scope creep
- ✅ Overall safety verdict
- ✅ Configurable risk threshold
- ✅ Exit code 0 (safe) or 1 (unsafe) for deployment gates
- ✅ Optional PR comment posting

**Best for:**
- CI/CD pipelines
- Automated deployment gates
- Pull request reviews
- Team collaboration and safety

### Quick Comparison

| Feature | Standard Mode | CI Mode |
|---------|---------------|---------|
| Summary table | ✅ | ✅ |
| Risk assessment | ❌ | ✅ |
| Git diff analysis | ❌ | ✅ |
| PR intent validation | ❌ | ✅ |
| Deployment verdict | ❌ | ✅ |
| Blocks unsafe deploys | ❌ | ✅ |
| PR comments | ❌ | ✅ (optional) |
| Exit codes | Always 0 | 0 (safe) or 1 (unsafe) |
| Use case | Local dev | CI/CD |

## CLI Reference

### Basic Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--provider` | `-p` | `anthropic` | LLM provider: `anthropic`, `azure-openai`, `ollama` |
| `--model` | `-m` | Provider default | Override model name |
| `--format` | `-f` | `table` | Output format: `table`, `json`, `markdown` |
| `--verbose` | `-v` | _(disabled)_ | Include property-level change details for modified resources |
| `--no-color` | | _(disabled)_ | Disable colored output (useful for logs) |
| `--version` | | | Print version and exit |
| `--help` | `-h` | | Print help message |

### CI Mode Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--ci` | | _(disabled)_ | **Enable CI mode with risk assessment and deployment gate** |
| `--diff` | `-d` | Auto-detect | Path to git diff file (auto-runs `git diff` if not provided) |
| `--diff-ref` | | `HEAD~1` | Git reference to diff against (e.g., `origin/main`, `HEAD~3`) |
| `--risk-threshold` | | `high` | Fail deployment at this risk level or above: `low`, `medium`, `high`, `critical` |
| `--post-comment` | | _(disabled)_ | Post summary as PR comment (GitHub or Azure DevOps) |
| `--pr-url` | | Auto-detect | PR URL for posting comments (auto-detected from environment if not provided) |
| `--bicep-dir` | | `.` | Path to Bicep source files for additional context |
| `--pr-title` | | Auto-detect | Pull request title for intent analysis (auto-fetched in GitHub Actions) |
| `--pr-description` | | Auto-detect | Pull request description for intent analysis (auto-fetched in GitHub Actions) |
| `--no-block` | | _(disabled)_ | Don't fail pipeline even if deployment is unsafe - only report findings (CI mode only) |

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (or safe deployment in CI mode) |
| `1` | Error or unsafe deployment (in CI mode, risk threshold exceeded) |
| `2` | Invalid input (no piped input, empty stdin, malformed What-If output) |

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

## Output Formats

### Table Format (Default)

Colored, formatted table with action symbols:

```
╭──────┬───────────────────┬────────────┬────────┬─────────────────────────╮
│ #    │ Resource          │ Type       │ Action │ Summary                 │
├──────┼───────────────────┼────────────┼────────┼─────────────────────────┤
│ 1    │ myAppService      │ Web App    │ Create │ Creates new web app...  │
│ 2    │ myDatabase        │ SQL DB     │ Modify │ Updates SKU to S1...    │
│ 3    │ oldStorage        │ Storage    │ Delete │ Removes storage acct... │
╰──────┴───────────────────┴────────────┴────────┴─────────────────────────╯
```

Action symbols:
- ✅ Create
- ✏️ Modify
- ❌ Delete
- 🚀 Deploy
- ⚪ NoChange
- ⚫ Ignore

### JSON Format

Structured output for scripting:

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

### Markdown Format

Formatted for PR comments:

```markdown
| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | myAppService | Web App | Create | Creates new web app with B1 SKU |

**Summary:** This deployment creates 1 new resource
```

## CI Mode Deep Dive

CI mode (`--ci`) transforms `bicep-whatif-advisor` from a summary tool into an **automated deployment safety gate** for your CI/CD pipelines.

### How CI Mode Works

1. **Input Collection**
   - Reads Azure What-If output (infrastructure changes)
   - Fetches git diff to see code changes
   - Optionally loads Bicep source files for context
   - Captures PR title and description for intent analysis

2. **Risk Assessment**
   - Each resource change is assigned a risk level: `none`, `low`, `medium`, `high`, or `critical`
   - Risk is based on action type, resource type, and alignment with PR intent
   - Overall deployment risk is the highest individual resource risk

3. **Intent Analysis**
   - Compares infrastructure changes against stated PR intent
   - Flags changes not mentioned in PR description
   - Elevates risk for destructive changes not explicitly documented
   - Catches scope creep and unintended side effects

4. **Deployment Decision**
   - Compares overall risk against `--risk-threshold`
   - Exit code 0 = safe to deploy (proceed with deployment)
   - Exit code 1 = unsafe (block deployment)
   - Optionally posts detailed analysis to PR as comment

### CI Mode Output Example

```
╭──────┬──────────────────┬────────────────┬────────┬──────────┬────────────────────────────────╮
│ #    │ Resource         │ Type           │ Action │ Risk     │ Summary                        │
├──────┼──────────────────┼────────────────┼────────┼──────────┼────────────────────────────────┤
│ 1    │ myDatabase       │ SQL Database   │ Delete │ CRITICAL │ ⚠️ Deleting production        │
│      │                  │                │        │          │ database - data loss will      │
│      │                  │                │        │          │ occur! Not mentioned in PR.    │
├──────┼──────────────────┼────────────────┼────────┼──────────┼────────────────────────────────┤
│ 2    │ myStorage        │ Storage Acct   │ Modify │ MEDIUM   │ Changing access tier from      │
│      │                  │                │        │          │ Cool to Hot. Not mentioned     │
│      │                  │                │        │          │ in PR description.             │
╰──────┴──────────────────┴────────────────┴────────┴──────────┴────────────────────────────────╯

🔴 CRITICAL RISK DETECTED
Verdict: UNSAFE - Deployment blocked

Concerns:
• Database deletion 'myDatabase' will cause data loss
• Change not mentioned in PR: "Add logging configuration"

Recommendations:
• Update PR description to document database deletion and justification
• Ensure database backup exists before proceeding
• Consider if this change belongs in a separate PR
```

## Risk Classification

### Risk Levels

| Risk Level | Examples | Typical Actions |
|------------|----------|-----------------|
| **🔴 CRITICAL** | Database deletions, storage account deletions, key vault deletions, RBAC/identity deletions, disabling encryption, broad network security changes | **BLOCK** - Requires manual review |
| **🟠 HIGH** | Production resource deletions, firewall rule changes, authentication/authorization modifications, SKU downgrades on critical services | **BLOCK** (default threshold) |
| **🟡 MEDIUM** | Behavioral changes to existing resources, new public endpoints, policy modifications, scaling config changes | **WARN** - Proceed with caution |
| **🟢 LOW** | Adding new resources, adding tags, diagnostic/monitoring resources, cosmetic changes | **SAFE** - Proceed |
| **⚪ NONE** | NoChange, Ignore actions, no actual modifications | **SAFE** - Proceed |

### Risk Assessment Factors

The AI considers multiple factors when assigning risk:

1. **Action Type**
   - Delete operations are inherently higher risk
   - Creates are generally low risk
   - Modifies vary based on what's changing

2. **Resource Type**
   - Stateful resources (databases, storage) = higher risk
   - Security resources (firewalls, NSGs, identity) = higher risk
   - Compute resources (VMs, App Services) = medium risk
   - Metadata resources (tags, diagnostics) = lower risk

3. **PR Intent Alignment**
   - Changes matching PR description = lower risk
   - Unmentioned changes = elevated risk
   - Destructive changes not documented = significantly elevated

4. **Environment Context**
   - Production indicators in resource names = higher risk
   - Test/dev indicators = lower risk

## PR Intent Analysis

The PR intent analysis feature helps catch unintended changes, scope creep, and configuration mistakes by comparing infrastructure changes against the stated purpose of your pull request.

### How It Works

1. **Extract Intent**: Reads PR title and description to understand what the change is supposed to do
2. **Compare Changes**: Analyzes What-If output to see what will actually change
3. **Flag Mismatches**: Identifies changes that don't align with the stated intent
4. **Elevate Risk**: Increases risk level for unmentioned or unexpected changes

### Intent Mismatch Detection Rules

**Risk Elevation:**
- 🔴 **CRITICAL**: Destructive changes (Delete) not mentioned in PR
- 🟠 **HIGH**: Security/auth/network changes not mentioned in PR
- 🟡 **MEDIUM**: Resource modifications not aligned with PR intent
- 🟢 **LOW**: New resources not mentioned but contextually aligned

### Real-World Examples

#### Example 1: Caught Unintended Deletion

**PR Description:**
```
Title: Update API Management logging configuration
Description: Configuring diagnostic settings to send logs to Application Insights
```

**What-If Shows:**
- ✅ APIM diagnostic settings modified
- ⚠️ SQL Database 'prod-customer-db' deleted

**AI Analysis:**
```
🔴 CRITICAL RISK - Intent Mismatch Detected

The PR claims to only update logging configuration, but the deployment
will DELETE a production database. This is not mentioned anywhere in the
PR description.

Risk: CRITICAL (deployment blocked)
Recommendation: Update PR description to explain database deletion or
revert the unintended change.
```

#### Example 2: Scope Creep Detection

**PR Description:**
```
Title: Add environment tags to storage account
Description: Adding standard Environment and ManagedBy tags for compliance
```

**What-If Shows:**
- ✅ Tags added to storage account
- ⚠️ Storage account access tier changed from Cool to Hot

**AI Analysis:**
```
🟡 MEDIUM RISK - Potential Scope Creep

While tag additions match the PR intent, the access tier change is not
mentioned. This may be unintentional or forgotten documentation.

Risk: MEDIUM (proceed with caution)
Recommendation: Update PR description to document the access tier change
and its impact on costs.
```

#### Example 3: Security Change Not Documented

**PR Description:**
```
Title: Update APIM policy fragments
Description: Refactoring JWT parsing logic into reusable fragments
```

**What-If Shows:**
- ✅ APIM policy fragments created
- ⚠️ Network security group rules modified (port 443 opened to 0.0.0.0/0)

**AI Analysis:**
```
🔴 HIGH RISK - Security Change Not Documented

The PR describes policy refactoring but doesn't mention the NSG rule
change that opens port 443 to the internet. This could be a security
risk or configuration error.

Risk: HIGH (deployment blocked)
Recommendation: Document the network security change in the PR or
investigate if this is an unintended side effect.
```

### Best Practices for PR Descriptions

To get the most value from intent analysis:

1. **Write Descriptive PR Titles**
   - ❌ "Update Bicep files"
   - ✅ "Add Application Insights logging to API Management"

2. **Document All Significant Changes**
   ```markdown
   ## Changes
   - Configure APIM diagnostic settings for App Insights
   - Add JWT parsing policy fragment
   - Update global policy to validate Front Door headers
   ```

3. **Explain Destructive Operations**
   ```markdown
   ## ⚠️ Destructive Changes
   - Deleting test database 'dev-temp-db' (no longer needed)
   - Backup verified and saved to storage account
   ```

4. **Call Out Security/Network Changes**
   ```markdown
   ## Security Changes
   - Opening port 443 on NSG for Front Door integration
   - Restricting access to Front Door IP ranges only
   ```

## Usage Examples

### Standard Mode Examples

#### Basic Usage

```bash
# Default table format
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep | bicep-whatif-advisor
```

#### Different Output Formats

```bash
# JSON output for scripting
az deployment group what-if ... | bicep-whatif-advisor --format json

# Markdown output for documentation
az deployment group what-if ... | bicep-whatif-advisor --format markdown

# Pipe JSON to jq for filtering
az deployment group what-if ... | bicep-whatif-advisor -f json | jq '.resources[] | select(.action == "Delete")'
```

#### Verbose Mode

```bash
# Show property-level changes for modified resources
az deployment group what-if ... | bicep-whatif-advisor --verbose
```

#### Different Providers

```bash
# Use Azure OpenAI
az deployment group what-if ... | bicep-whatif-advisor --provider azure-openai

# Use local Ollama
az deployment group what-if ... | bicep-whatif-advisor --provider ollama --model llama3.1

# Use a different Claude model
az deployment group what-if ... | bicep-whatif-advisor --model claude-opus-4
```

### CI Mode Examples

#### Basic Deployment Gate

```bash
# Run What-If analysis
az deployment group what-if \
  --resource-group my-rg \
  --template-file main.bicep \
  --parameters params.json > whatif-output.txt

# Analyze with CI mode
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --risk-threshold high

# Exit code 0 = safe, exit code 1 = unsafe
if [ $? -eq 0 ]; then
  echo "✅ Safe to deploy - proceeding..."
  az deployment group create \
    --resource-group my-rg \
    --template-file main.bicep \
    --parameters params.json
else
  echo "❌ Deployment blocked due to high risk"
  exit 1
fi
```

#### With Bicep Source Context

```bash
# Include Bicep source files for better analysis
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --bicep-dir ./bicep \
  --format markdown
```

#### Custom Risk Thresholds

```bash
# Block on medium risk or higher (more strict)
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --risk-threshold medium

# Only block on critical risk (more permissive)
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --risk-threshold critical
```

#### Different Diff References

```bash
# Compare against main branch
cat whatif-output.txt | bicep-whatif-advisor --ci --diff-ref origin/main

# Compare against specific commit
cat whatif-output.txt | bicep-whatif-advisor --ci --diff-ref abc123

# Compare against previous commit
cat whatif-output.txt | bicep-whatif-advisor --ci --diff-ref HEAD~1

# Compare against tag
cat whatif-output.txt | bicep-whatif-advisor --ci --diff-ref v1.0.0
```

#### With PR Intent Analysis

```bash
# In GitHub Actions (PR metadata auto-detected)
cat whatif-output.txt | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --pr-title "${{ steps.pr-details.outputs.pr_title }}" \
  --pr-description "${{ steps.pr-details.outputs.pr_body }}"
```

## Provider Configuration

### Anthropic Claude

Fast, accurate, and easy to set up.

**Installation:**
```bash
pip install bicep-whatif-advisor[anthropic]
```

**Configuration:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

**Default model:** `claude-sonnet-4-20250514`

**Using different models:**
```bash
# Use Claude Opus (more capable, slower)
bicep-whatif-advisor --model claude-opus-4

# Use Claude Haiku (faster, less capable)
bicep-whatif-advisor --model claude-haiku-3-5
```

### Azure OpenAI

Use your own Azure OpenAI deployment.

**Installation:**
```bash
pip install bicep-whatif-advisor[azure]
```

**Configuration:**
```powershell
$env:AZURE_OPENAI_ENDPOINT = "https://your-resource.openai.azure.com/"
$env:AZURE_OPENAI_API_KEY = "your-api-key"
$env:AZURE_OPENAI_DEPLOYMENT = "your-deployment-name"
```

**Usage:**
```bash
bicep-whatif-advisor --provider azure-openai
```

### Ollama (Local)

Run LLMs locally without API calls.

**Installation:**
```bash
pip install bicep-whatif-advisor[ollama]
ollama pull llama3.1
```

**Start Ollama:**
```bash
ollama serve
```

**Usage:**
```bash
bicep-whatif-advisor --provider ollama --model llama3.1
```

**Using different models:**
```bash
# Use Mistral
ollama pull mistral
bicep-whatif-advisor --provider ollama --model mistral

# Use CodeLlama
ollama pull codellama
bicep-whatif-advisor --provider ollama --model codellama
```

## CI/CD Integration Examples

### GitHub Actions - Complete Workflow

```yaml
name: PR Review - Infrastructure Changes

on:
  pull_request:
    branches: [main]
    paths: ['infrastructure/**']

permissions:
  id-token: write
  contents: read
  pull-requests: write

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Needed for git diff

      - name: Azure Login
        uses: azure/login@v2
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install bicep-whatif-advisor
        run: pip install bicep-whatif-advisor[anthropic]

      - name: Get PR Details
        id: pr
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          echo "title=$(gh pr view ${{ github.event.pull_request.number }} --json title --jq '.title')" >> $GITHUB_OUTPUT
          echo "body<<EOF" >> $GITHUB_OUTPUT
          gh pr view ${{ github.event.pull_request.number }} --json body --jq '.body' >> $GITHUB_OUTPUT
          echo "EOF" >> $GITHUB_OUTPUT

      - name: Run What-If Analysis
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.RESOURCE_GROUP }} \
            --template-file infrastructure/main.bicep \
            --parameters infrastructure/params.json \
            --exclude-change-types NoChange Ignore \
            > whatif-output.txt

      - name: AI Safety Analysis
        id: analysis
        continue-on-error: true
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: |
          cat whatif-output.txt | bicep-whatif-advisor \
            --ci \
            --diff-ref origin/main \
            --bicep-dir infrastructure/ \
            --pr-title "${{ steps.pr.outputs.title }}" \
            --pr-description "${{ steps.pr.outputs.body }}" \
            --risk-threshold high \
            --format markdown > analysis.md

      - name: Post PR Comment
        if: always()
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          gh pr comment ${{ github.event.pull_request.number }} --body-file analysis.md

      - name: Check Safety Verdict
        if: steps.analysis.outcome == 'failure'
        run: |
          echo "::error::Deployment blocked due to high risk"
          exit 1
```

### Azure DevOps Pipeline

```yaml
trigger:
  branches:
    include: [main]
  paths:
    include: ['infrastructure/*']

pr:
  branches:
    include: [main]
  paths:
    include: ['infrastructure/*']

pool:
  vmImage: 'ubuntu-latest'

steps:
  - task: AzureCLI@2
    displayName: 'Run What-If Analysis'
    inputs:
      azureSubscription: 'My-Service-Connection'
      scriptType: 'bash'
      scriptLocation: 'inlineScript'
      inlineScript: |
        az deployment group what-if \
          --resource-group $(RESOURCE_GROUP) \
          --template-file infrastructure/main.bicep \
          --parameters infrastructure/params.json \
          > whatif-output.txt

  - task: UsePythonVersion@0
    inputs:
      versionSpec: '3.11'

  - script: |
      pip install bicep-whatif-advisor[anthropic]
    displayName: 'Install bicep-whatif-advisor'

  - script: |
      cat whatif-output.txt | bicep-whatif-advisor \
        --ci \
        --diff-ref origin/main \
        --bicep-dir infrastructure/ \
        --risk-threshold high \
        --format markdown \
        --post-comment
    displayName: 'AI Safety Analysis'
    env:
      ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
      SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### GitLab CI

```yaml
stages:
  - validate

infrastructure-review:
  stage: validate
  image: mcr.microsoft.com/azure-cli
  only:
    refs:
      - merge_requests
    changes:
      - infrastructure/**
  before_script:
    - az login --service-principal -u $AZURE_CLIENT_ID -p $AZURE_CLIENT_SECRET --tenant $AZURE_TENANT_ID
    - pip install bicep-whatif-advisor[anthropic]
  script:
    - |
      az deployment group what-if \
        --resource-group $RESOURCE_GROUP \
        --template-file infrastructure/main.bicep \
        --parameters infrastructure/params.json \
        > whatif-output.txt
    - |
      cat whatif-output.txt | bicep-whatif-advisor \
        --ci \
        --diff-ref origin/main \
        --bicep-dir infrastructure/ \
        --risk-threshold high
  variables:
    ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
```

### Jenkins Pipeline

```groovy
pipeline {
    agent any

    environment {
        ANTHROPIC_API_KEY = credentials('anthropic-api-key')
        AZURE_CREDENTIALS = credentials('azure-service-principal')
    }

    stages {
        stage('Infrastructure Review') {
            when {
                changeRequest()
                changeset "infrastructure/**"
            }
            steps {
                sh '''
                    az login --service-principal \
                      -u $AZURE_CLIENT_ID \
                      -p $AZURE_CLIENT_SECRET \
                      --tenant $AZURE_TENANT_ID

                    pip install bicep-whatif-advisor[anthropic]

                    az deployment group what-if \
                      --resource-group ${RESOURCE_GROUP} \
                      --template-file infrastructure/main.bicep \
                      --parameters infrastructure/params.json \
                      > whatif-output.txt

                    cat whatif-output.txt | bicep-whatif-advisor \
                      --ci \
                      --diff-ref origin/main \
                      --bicep-dir infrastructure/ \
                      --risk-threshold high
                '''
            }
        }
    }
}
```

## Troubleshooting

### "No input detected" or "stdin is empty" error

**Problem:** The tool isn't receiving piped input.

**Solution:** Make sure you're piping What-If output to the command:

```bash
# ❌ Wrong - no piped input
bicep-whatif-advisor

# ❌ Wrong - command substitution doesn't work
bicep-whatif-advisor $(az deployment group what-if ...)

# ✅ Correct - piped input
az deployment group what-if ... | bicep-whatif-advisor

# ✅ Correct - file input
az deployment group what-if ... > output.txt
cat output.txt | bicep-whatif-advisor
```

### "ANTHROPIC_API_KEY environment variable not set"

**Problem:** API key not configured.

**Solution:** Set your API key for the provider you're using:

```bash
# Anthropic
export ANTHROPIC_API_KEY="sk-ant-..."

# Azure OpenAI
export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"
export AZURE_OPENAI_API_KEY="your-key"
export AZURE_OPENAI_DEPLOYMENT="your-deployment-name"
```

**PowerShell:**
```powershell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

### "Cannot reach Ollama" or "Connection refused" error

**Problem:** Ollama server is not running or not accessible.

**Solutions:**

1. Start Ollama server:
   ```bash
   ollama serve
   ```

2. Check if Ollama is running:
   ```bash
   curl http://localhost:11434/api/version
   ```

3. If using a different host/port:
   ```bash
   export OLLAMA_HOST="http://your-host:11434"
   ```

4. Verify the model is installed:
   ```bash
   ollama list
   ollama pull llama3.1  # If not installed
   ```

### "Invalid What-If output" or "No resource changes detected"

**Problem:** The piped input doesn't contain valid Azure What-If output.

**Solutions:**

1. Verify What-If output contains resource changes:
   ```bash
   az deployment group what-if ... | tee output.txt
   cat output.txt  # Check if it contains "Resource changes:" section
   ```

2. Make sure you're not filtering out all changes:
   ```bash
   # ❌ This might produce no output
   az deployment group what-if --exclude-change-types NoChange Ignore Create Modify Delete

   # ✅ Better - only exclude noise
   az deployment group what-if --exclude-change-types NoChange Ignore
   ```

3. Check for Azure CLI errors in the output:
   ```bash
   az deployment group what-if ... 2>&1 | tee output.txt
   # If there are errors, fix them before piping to bicep-whatif-advisor
   ```

### "LLM returned invalid JSON" or "Failed to parse response"

**Problem:** The LLM response couldn't be parsed as JSON.

**Solutions:**

1. Try a more capable model:
   ```bash
   # If using Haiku, try Sonnet
   bicep-whatif-advisor --model claude-sonnet-4-20250514

   # If using Ollama with a small model, try a larger one
   ollama pull llama3.1:70b
   bicep-whatif-advisor --provider ollama --model llama3.1:70b
   ```

2. Check if What-If output is too large (>100k chars):
   ```bash
   az deployment group what-if ... | wc -c
   # If over 100,000, the output is truncated
   ```

3. Check for prompt injection or unusual characters in What-If output:
   ```bash
   az deployment group what-if ... > output.txt
   cat output.txt  # Look for any unusual content
   ```

### "Rate limit exceeded" or "429 Too Many Requests"

**Problem:** You've exceeded your API provider's rate limits.

**Solutions:**

1. **Anthropic:** Check your usage limits at https://console.anthropic.com/
   - Wait a few minutes and retry
   - Upgrade your plan if needed

2. **Azure OpenAI:** Check your deployment's quota
   - Increase TPM (tokens per minute) limit in Azure portal
   - Use a different deployment

3. **Ollama:** Should not have rate limits, but check system resources
   - Verify CPU/memory availability
   - Try a smaller model

### CI Mode: "git diff failed" or "unable to read diff"

**Problem:** Can't collect git diff for CI mode analysis.

**Solutions:**

1. Ensure you're in a git repository:
   ```bash
   git status  # Should not error
   ```

2. Make sure the diff reference exists:
   ```bash
   # Check if origin/main exists
   git branch -r | grep origin/main

   # If not, fetch first
   git fetch origin

   # Or use a different reference
   bicep-whatif-advisor --ci --diff-ref HEAD~1
   ```

3. In CI/CD, ensure you're fetching full history:
   ```yaml
   # GitHub Actions
   - uses: actions/checkout@v4
     with:
       fetch-depth: 0  # Important!

   # Azure DevOps
   - checkout: self
     fetchDepth: 0
   ```

### CI Mode: "Failed to post PR comment"

**Problem:** Unable to post comment to GitHub or Azure DevOps.

**Solutions:**

1. **GitHub:** Check token permissions
   ```yaml
   permissions:
     pull-requests: write  # Required!
     contents: read
   ```

2. **GitHub:** Verify environment variables
   ```bash
   echo $GITHUB_TOKEN
   echo $GITHUB_REPOSITORY
   echo $GITHUB_PR_NUMBER
   ```

3. **Azure DevOps:** Enable System.AccessToken
   ```yaml
   - script: ...
     env:
       SYSTEM_ACCESSTOKEN: $(System.AccessToken)
   ```

4. **Azure DevOps:** Grant build service permissions
   - Project Settings → Repositories → Security
   - Grant "Contribute to pull requests" to build service

### "Output is truncated" or "Response too long"

**Problem:** What-If output is extremely large (>100k characters).

**Solutions:**

1. Use `--exclude-change-types` to reduce noise:
   ```bash
   az deployment group what-if \
     --exclude-change-types NoChange Ignore
   ```

2. Deploy in smaller chunks:
   ```bash
   # Instead of deploying everything at once, break into modules
   az deployment group what-if --template-file network.bicep | bicep-whatif-advisor
   az deployment group what-if --template-file compute.bicep | bicep-whatif-advisor
   ```

3. The tool automatically truncates at 100k chars - this is by design to stay within LLM context limits

### "Permission denied" errors in CI/CD

**Problem:** Can't access files or run commands in pipeline.

**Solutions:**

1. Check file permissions:
   ```bash
   ls -la main.bicep
   chmod +r main.bicep  # If needed
   ```

2. Verify working directory:
   ```yaml
   - script: |
       pwd
       ls -la
       cat whatif-output.txt | bicep-whatif-advisor --ci
   ```

3. Check Python installation:
   ```bash
   python --version
   pip --version
   pip show bicep-whatif-advisor
   ```

### Performance issues or slow response times

**Problem:** Analysis takes too long.

**Solutions:**

1. Use a faster model:
   ```bash
   # Anthropic Haiku is fastest
   bicep-whatif-advisor --model claude-haiku-3-5

   # Ollama with smaller models
   bicep-whatif-advisor --provider ollama --model llama3.1:8b
   ```

2. Reduce What-If output size (see "Output is truncated" above)

3. Check your internet connection if using cloud providers

4. For Ollama, ensure adequate system resources:
   ```bash
   # Check system load
   top
   # Consider using GPU acceleration if available
   ```

### "Module not found" or import errors

**Problem:** Missing dependencies.

**Solutions:**

1. Install with the correct extras:
   ```bash
   # For Anthropic
   pip install bicep-whatif-advisor[anthropic]

   # For Azure OpenAI
   pip install bicep-whatif-advisor[azure]

   # For all providers
   pip install bicep-whatif-advisor[all]
   ```

2. Verify installation:
   ```bash
   pip show bicep-whatif-advisor
   pip list | grep -E "anthropic|openai|requests"
   ```

3. Upgrade pip and reinstall:
   ```bash
   pip install --upgrade pip
   pip install --upgrade bicep-whatif-advisor[all]
   ```

### Getting help

If you're still having issues:

1. Check the [GitHub Issues](https://github.com/your-repo/bicep-whatif-advisor/issues) for similar problems
2. Enable verbose output to see more details (if available in future versions)
3. Verify your What-If output is valid by checking it manually first
4. Try with a minimal Bicep template to isolate the issue
5. Open a new issue with:
   - Your command and flags
   - Error message (full stack trace if available)
   - What-If output (sanitized of sensitive data)
   - Provider and model being used
