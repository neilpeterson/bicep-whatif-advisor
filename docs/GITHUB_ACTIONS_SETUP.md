# GitHub Actions Setup Guide

Quick start guide for integrating `whatif-explain` with GitHub Actions to automatically review Bicep deployments on pull requests.

## Overview

This setup enables:
- ✅ **Automatic PR reviews** with AI-powered safety analysis
- ✅ **Deployment blocking** for high-risk changes
- ✅ **Zero manual logic** - just pipe What-If output to `whatif-explain`
- ✅ **PR comments** posted automatically with risk assessment

## Prerequisites

Before starting, ensure you have:

1. **Azure Setup:**
   - Azure subscription with Contributor access
   - Resource group created (e.g., `rg-my-app-prod`)
   - Azure CLI installed locally

2. **Anthropic API:**
   - API key from https://console.anthropic.com/
   - Free tier available for testing

3. **GitHub Repository:**
   - Admin access to configure secrets
   - Bicep templates in your repo

## Quick Start (5 Minutes)

### Step 1: Create Azure App Registration

Run these commands to create an app registration for GitHub Actions:

```bash
# Create app registration
APP_ID=$(az ad app create --display-name "github-actions-whatif-explain" --query appId -o tsv)

# Create service principal
az ad sp create --id $APP_ID

# Get your Azure IDs
TENANT_ID=$(az account show --query tenantId -o tsv)
SUBSCRIPTION_ID=$(az account show --query id -o tsv)

# Display values
echo "AZURE_CLIENT_ID: $APP_ID"
echo "AZURE_TENANT_ID: $TENANT_ID"
echo "AZURE_SUBSCRIPTION_ID: $SUBSCRIPTION_ID"
```

**Save these three values** - you'll add them to GitHub in the next step.

### Step 2: Configure GitHub Secrets

1. Go to your repository → **Settings → Secrets and variables → Actions**

2. Click **New repository secret** and add:

   | Secret Name | Value | Description |
   |-------------|-------|-------------|
   | `AZURE_CLIENT_ID` | From Step 1 | App registration ID |
   | `AZURE_TENANT_ID` | From Step 1 | Azure AD tenant ID |
   | `AZURE_SUBSCRIPTION_ID` | From Step 1 | Azure subscription ID |
   | `ANTHROPIC_API_KEY` | From Anthropic console | API key for AI analysis |

3. Click **Variables** tab → **New repository variable**:

   | Variable Name | Value | Description |
   |---------------|-------|-------------|
   | `AZURE_RESOURCE_GROUP` | Your RG name | Target resource group |

### Step 3: Create Federated Credential

This enables passwordless authentication from GitHub to Azure.

**Using Azure Portal (Recommended):**

1. Go to **Azure Portal → Azure AD → App registrations**
2. Find **github-actions-whatif-explain**
3. Click **Certificates & secrets → Federated credentials → Add credential**
4. Fill in:
   - **Federated credential scenario:** GitHub Actions deploying Azure resources
   - **Organization:** Your GitHub username/org
   - **Repository:** Your repo name (e.g., `bicep-whatif-explain`)
   - **Entity type:** Pull Request
   - **Name:** `github-pr-access`
5. Click **Add**

**Using Azure CLI:**

```bash
# Replace with your GitHub username and repo name
GITHUB_ORG="your-username"
REPO_NAME="your-repo"

# Create federated credential for pull requests
az ad app federated-credential create --id $APP_ID --parameters '{
  "name": "github-pr-access",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:'"$GITHUB_ORG"'/'"$REPO_NAME"':pull_request",
  "audiences": ["api://AzureADTokenExchange"]
}'
```

### Step 4: Assign Azure Permissions

Grant the app permission to run What-If analysis:

```bash
# Replace with your resource group name
RESOURCE_GROUP="rg-my-app-prod"

# Assign Contributor role
az role assignment create \
  --assignee $APP_ID \
  --role Contributor \
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
```

### Step 5: Create Workflow File

Create `.github/workflows/pr-review-bicep.yml`:

```yaml
name: PR Review - Bicep What-If Analysis

on:
  pull_request:
    branches: [main]
    paths:
      - 'bicep/**'  # Adjust to your Bicep directory

permissions:
  id-token: write
  contents: read
  pull-requests: write

env:
  BICEP_TEMPLATE: bicep/main.bicep
  BICEP_PARAMS: bicep/main.bicepparam

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

      - run: pip install whatif-explain[anthropic]

      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --template-file ${{ env.BICEP_TEMPLATE }} \
            --parameters ${{ env.BICEP_PARAMS }} \
            --exclude-change-types NoChange Ignore \
            | whatif-explain
```

**That's it!** The tool automatically:
- ✅ Detects GitHub Actions environment
- ✅ Extracts PR title and description
- ✅ Sets git diff reference to PR base branch
- ✅ Posts detailed PR comment
- ✅ Blocks deployment if high risk detected

## What Happens on Pull Requests

When you create a PR that modifies Bicep files:

1. **Workflow runs automatically**
2. **Azure What-If** analyzes deployment changes
3. **AI analysis** evaluates three risk areas:
   - **Infrastructure Drift:** Changes not in code
   - **PR Intent Alignment:** Changes match PR description
   - **Risky Operations:** Deletions, security changes
4. **PR comment posted** with detailed risk assessment
5. **Workflow passes/fails** based on risk level

### Example PR Comment

```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | Low | All changes present in code |
| PR Intent Alignment | Low | Changes match PR description |
| Risky Operations | Medium | Creates new public endpoint |

### Resource Changes

| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | app-service | Microsoft.Web/sites | Create | New App Service with basic SKU |
| 2 | app-plan | Microsoft.Web/serverfarms | Create | Consumption plan for App Service |

**Summary:** This deployment creates new App Service resources as described in PR.

### Verdict: ✅ SAFE

**Overall Risk Level:** Medium
**Reasoning:** All changes are intentional and documented in PR. New public endpoint requires firewall rules (already planned).
```

## Configuration Options

### Adjust Risk Thresholds

By default, deployments are blocked only on **high** risk. You can adjust thresholds:

```bash
# More strict (block on medium or high risk)
| whatif-explain \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Very strict (block on any risk)
| whatif-explain \
  --drift-threshold low \
  --intent-threshold low \
  --operations-threshold low
```

### Specify Bicep Source Directory

If your Bicep files are in a subdirectory, include them for better analysis:

```bash
| whatif-explain --bicep-dir bicep/modules/
```

### Use Different LLM Provider

**Azure OpenAI:**
```bash
pip install whatif-explain[azure]

# Set environment variables
AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_KEY }}
AZURE_OPENAI_ENDPOINT: ${{ vars.AZURE_OPENAI_ENDPOINT }}

# Run with provider flag
| whatif-explain --provider azure-openai
```

**Local Ollama:**
```bash
pip install whatif-explain[ollama]

| whatif-explain --provider ollama --model llama3.1
```

## Troubleshooting

### Workflow fails: "Login failed"

**Cause:** Federated credential not configured correctly

**Fix:**
1. Verify federated credential exists: `az ad app federated-credential list --id $APP_ID`
2. Check subject matches: `repo:YOUR-ORG/YOUR-REPO:pull_request`
3. Ensure credential is for **Pull Request** entity type

### No PR comment posted

**Cause:** Missing `GITHUB_TOKEN` or `pull-requests: write` permission

**Fix:**
```yaml
permissions:
  pull-requests: write  # Required
```

### "requests package not installed"

**Cause:** Installed without dependencies

**Fix:**
```bash
# Install with provider dependencies
pip install whatif-explain[anthropic]  # Includes requests
```

### High risk detected but looks safe

**Cause:** Drift between code and deployed infrastructure

**Fix:**
1. Review the drift detection explanation in PR comment
2. Update Bicep code to match deployed state, OR
3. Deploy from main branch first to sync infrastructure

## Advanced Setup

### Run on Multiple Environments

Create separate workflows for dev/staging/prod:

```yaml
# .github/workflows/pr-review-dev.yml
env:
  BICEP_PARAMS: bicep/dev.bicepparam

# .github/workflows/pr-review-prod.yml
env:
  BICEP_PARAMS: bicep/prod.bicepparam
```

Use different risk thresholds per environment:
- **Dev:** `--drift-threshold low` (catch all drift)
- **Prod:** `--drift-threshold high` (only block critical drift)

### Add Manual Approval Gate

Require approval before merging high-risk PRs:

1. Go to **Settings → Branches → Branch protection rules**
2. Require status check: `whatif-review`
3. Require review from code owners for high-risk changes

### Integrate with Azure DevOps

See [PIPELINE.md](./PIPELINE.md) for Azure DevOps setup (also supports auto-detection).

## What's Next

Once your workflow is running:

1. **Test it:** Create a test PR modifying your Bicep files
2. **Review the comment:** See the AI analysis in action
3. **Adjust thresholds:** Fine-tune based on your risk tolerance
4. **Enable branch protection:** Require PR review workflow to pass

## Additional Resources

- [Azure OIDC Authentication](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Workflow Comparison](./WORKFLOW_COMPARISON.md) - See before/after examples
- [Platform Auto-Detection](./PLATFORM_AUTO_DETECTION_PLAN.md) - How auto-detection works
- [Main Documentation](../README.md) - Full feature reference
