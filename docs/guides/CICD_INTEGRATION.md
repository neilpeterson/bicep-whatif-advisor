# CI/CD Integration Guide

Complete guide for integrating `bicep-whatif-advisor` as an automated deployment gate in CI/CD pipelines.

**Prerequisites:** Familiarity with basic tool usage. See [QUICKSTART.md](./QUICKSTART.md) or [USER_GUIDE.md](./USER_GUIDE.md) first.

---

## Table of Contents

- [Overview](#overview)
- [GitHub Actions](#github-actions)
- [Azure DevOps](#azure-devops)
- [Other CI Platforms](#other-ci-platforms)
- [Advanced Features](#advanced-features)
- [Troubleshooting](#troubleshooting)

---

## Overview

`bicep-whatif-advisor` provides **platform auto-detection** for seamless CI/CD integration:

- ✅ **Automatic CI mode** - Detects GitHub Actions or Azure DevOps and enables safety gates
- ✅ **Zero configuration** - Extracts PR metadata from environment automatically
- ✅ **Automatic PR comments** - Posts detailed analysis without manual commands
- ✅ **Exit code gating** - Blocks unsafe deployments automatically (exit code 1)

### What Gets Auto-Detected

**GitHub Actions:**
- CI mode automatically enabled
- PR title and description from event file
- Git diff reference from PR base branch
- PR comments posted when `GITHUB_TOKEN` available

**Azure DevOps:**
- CI mode automatically enabled
- PR ID from environment variables
- Git diff reference from target branch
- PR comments posted when `SYSTEM_ACCESSTOKEN` available

### How Risk Assessment Works

The tool evaluates **three independent risk buckets**:

1. **Infrastructure Drift** - Changes in What-If not present in code diff
2. **PR Intent Alignment** - Changes not aligned with PR description
3. **Risky Operations** - Inherently dangerous operations (deletions, security changes)

Each bucket gets a risk level (low/medium/high) and has an independent configurable threshold. Deployment is blocked if **ANY** bucket exceeds its threshold.

**For detailed explanation,** see [RISK_ASSESSMENT.md](./RISK_ASSESSMENT.md)

**For all configuration options,** see [USER_GUIDE.md - CLI Flags Reference](./USER_GUIDE.md#cli-flags-reference)

---

## GitHub Actions

### Prerequisites

1. **Azure Setup:**
   - Azure subscription with Contributor access
   - Resource group created
   - Azure CLI installed locally

2. **Anthropic API:**
   - API key from https://console.anthropic.com/
   - Free tier available for testing

3. **GitHub Repository:**
   - Admin access to configure secrets
   - Bicep templates in your repo

### Step 1: Create Azure App Registration

Run these commands to create an app registration for GitHub Actions:

```bash
# Create app registration
APP_ID=$(az ad app create --display-name "github-actions-bicep-whatif-advisor" --query appId -o tsv)

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
2. Find **github-actions-bicep-whatif-advisor**
3. Click **Certificates & secrets → Federated credentials → Add credential**
4. Fill in:
   - **Federated credential scenario:** GitHub Actions deploying Azure resources
   - **Organization:** Your GitHub username/org
   - **Repository:** Your repo name
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

      - run: pip install bicep-whatif-advisor[anthropic]

      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.AZURE_RESOURCE_GROUP }} \
            --template-file ${{ env.BICEP_TEMPLATE }} \
            --parameters ${{ env.BICEP_PARAMS }} \
            --exclude-change-types NoChange Ignore \
            | bicep-whatif-advisor
```

**That's it!** The tool automatically:
- ✅ Detects GitHub Actions environment
- ✅ Extracts PR title and description
- ✅ Sets git diff reference to PR base branch
- ✅ Posts detailed PR comment
- ✅ Blocks deployment if high risk detected

### GitHub Actions Configuration Options

#### Adjust Risk Thresholds

```yaml
# More strict - block on medium risk in all buckets
| bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Custom per-bucket - strict on drift, lenient on operations
| bicep-whatif-advisor \
  --drift-threshold low \
  --intent-threshold medium \
  --operations-threshold high
```

**For all threshold options,** see [USER_GUIDE.md - CI Mode Flags](./USER_GUIDE.md#ci-mode-flags)

#### Skip Specific Risk Buckets

```yaml
# Skip infrastructure drift assessment (useful when state differs from code)
| bicep-whatif-advisor --skip-drift

# Skip PR intent alignment (useful for automated maintenance PRs)
| bicep-whatif-advisor --skip-intent

# Skip risky operations (focus only on drift and intent)
| bicep-whatif-advisor --skip-operations

# Combine skip flags - only evaluate operations bucket
| bicep-whatif-advisor \
  --skip-drift \
  --skip-intent
```

**Use cases:**
- `--skip-drift` - Infrastructure state managed outside of code (manual changes expected)
- `--skip-intent` - Automated dependency updates, bot PRs, or when PR descriptions are minimal
- `--skip-operations` - Focus assessment on drift and intent, allowing any Azure operations

**Note:** At least one risk bucket must remain enabled.

#### Use Different Providers

**Azure OpenAI:**
```yaml
- run: pip install bicep-whatif-advisor[azure]

- env:
    AZURE_OPENAI_API_KEY: ${{ secrets.AZURE_OPENAI_KEY }}
    AZURE_OPENAI_ENDPOINT: ${{ vars.AZURE_OPENAI_ENDPOINT }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor --provider azure-openai
```

**Ollama (self-hosted):**
```yaml
- run: pip install bicep-whatif-advisor[ollama]

- env:
    OLLAMA_HOST: http://localhost:11434
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor --provider ollama
```

---

## Azure DevOps

### Prerequisites

1. **Azure Setup:**
   - Azure subscription with access to resource groups
   - Azure service connection configured in Azure DevOps
   - Resource group created

2. **Anthropic API:**
   - API key from https://console.anthropic.com/
   - Free tier available for testing

3. **Azure DevOps Repository:**
   - Admin access to configure permissions and variables
   - Bicep templates in your repo

### Step 1: Configure Build Service Permissions

**⚠️ CRITICAL:** The build service must have permission to post PR comments. Without this, you'll get a `403 Forbidden` error when the tool tries to post comments.

1. Go to your Azure DevOps project
2. **Project Settings** (gear icon, bottom left) → **Repositories**
3. Select your repository (or click **Security** tab)
4. Search for: **`{ProjectName} Build Service ({OrgName})`**
   - Example: `MyProject Build Service (myorg)`
   - If not found, click **Add** → search for "build service" → add it
5. Set **"Contribute to pull requests"** permission to **Allow** ✓
6. Click **Save changes**

**Alternative:** Disable job authorization scope restrictions:
- **Project Settings** → **Pipelines** → **Settings**
- Turn **OFF**: _"Limit job authorization scope to current project for non-release pipelines"_

### Step 2: Create Variable Group

1. Go to **Pipelines → Library → Variable groups**
2. Click **+ Variable group**
3. Name: `bicep-whatif-advisor-config` (or your preferred name)
4. Add variables:

   | Variable | Type | Value | Description |
   |----------|------|-------|-------------|
   | `ANTHROPIC_API_KEY` | Secret (lock icon) | Your API key | From Anthropic console |
   | `RESOURCE_GROUP` | Plain | Your RG name | Target resource group |

5. Click **Save**

### Step 3: Create Pipeline File

Create `azure-pipelines.yml` in your repository:

```yaml
trigger:
  branches:
    include:
      - main
  paths:
    include:
      - bicep/*

pr:
  branches:
    include:
      - main
  paths:
    include:
      - bicep/*

pool:
  vmImage: ubuntu-latest

variables:
  - group: bicep-whatif-advisor-config  # Link your variable group
  - name: BICEP_TEMPLATE
    value: bicep/main.bicep
  - name: BICEP_PARAMS
    value: bicep/main.bicepparam

stages:
  - stage: WhatIfReview
    displayName: 'What-If Review'
    condition: eq(variables['Build.Reason'], 'PullRequest')
    jobs:
      - job: Review
        displayName: 'AI Safety Review'
        steps:
          - checkout: self
            fetchDepth: 0

          - task: AzureCLI@2
            displayName: 'What-If Analysis & AI Review'
            inputs:
              azureSubscription: 'my-service-connection'  # Your Azure service connection
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: |
                pip install bicep-whatif-advisor[anthropic]

                az deployment group what-if \
                  --resource-group $(RESOURCE_GROUP) \
                  --template-file $(BICEP_TEMPLATE) \
                  --parameters $(BICEP_PARAMS) \
                  --exclude-change-types NoChange Ignore \
                  | bicep-whatif-advisor
            env:
              ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
              SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

**That's it!** The tool automatically:
- ✅ Detects Azure DevOps environment
- ✅ Extracts PR ID and metadata
- ✅ Fetches PR title and description via REST API
- ✅ Sets git diff reference to PR target branch
- ✅ Posts detailed PR comment
- ✅ Blocks deployment if high risk detected

**Auto-detection includes:**
- CI mode enabled
- PR ID from `SYSTEM_PULLREQUEST_PULLREQUESTID`
- PR title/description via Azure DevOps REST API (requires `SYSTEM_ACCESSTOKEN`)
- Diff reference from `SYSTEM_PULLREQUEST_TARGETBRANCH`
- PR comments posted when `SYSTEM_ACCESSTOKEN` available

### Azure DevOps Configuration Options

#### Adjust Risk Thresholds

```yaml
| bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium
```

#### Skip Specific Risk Buckets

```yaml
# Skip infrastructure drift assessment
| bicep-whatif-advisor --skip-drift

# Skip PR intent alignment
| bicep-whatif-advisor --skip-intent

# Combine skip flags
| bicep-whatif-advisor --skip-drift --skip-operations
```

See [GitHub Actions - Skip Specific Risk Buckets](#skip-specific-risk-buckets) for detailed use cases.

#### PR Metadata Auto-Fetch

**Azure DevOps automatically fetches PR title and description** via the Azure DevOps REST API when `SYSTEM_ACCESSTOKEN` is available (automatically provided in Azure Pipelines).

You'll see output like:
```
✅ Fetched PR title from Azure DevOps API: Add monitoring resources
✅ Fetched PR description from Azure DevOps API (3 lines)
```

**Manual Override (Optional):** If you want to override the auto-fetched metadata:

```yaml
| bicep-whatif-advisor \
  --pr-title "Custom title" \
  --pr-description "Custom description"
```

---

## Other CI Platforms

For platforms without built-in auto-detection (GitLab, Jenkins, etc.), manually enable CI mode:

### GitLab CI

```yaml
bicep_review:
  stage: review
  script:
    - pip install bicep-whatif-advisor[anthropic]
    - |
      az deployment group what-if ... | bicep-whatif-advisor \
        --ci \
        --diff-ref origin/$CI_MERGE_REQUEST_TARGET_BRANCH_NAME \
        --pr-title "$CI_MERGE_REQUEST_TITLE" \
        --pr-description "$CI_MERGE_REQUEST_DESCRIPTION"
  only:
    - merge_requests
  variables:
    ANTHROPIC_API_KEY: $ANTHROPIC_API_KEY
```

### Jenkins

```groovy
stage('What-If Review') {
  steps {
    sh '''
      pip install bicep-whatif-advisor[anthropic]
      az deployment group what-if ... | bicep-whatif-advisor \
        --ci \
        --diff-ref origin/${CHANGE_TARGET} \
        --pr-title "${CHANGE_TITLE}"
    '''
  }
  environment {
    ANTHROPIC_API_KEY = credentials('anthropic-api-key')
  }
}
```

---

## Advanced Features

### Multi-Environment Labeling (`--comment-title`)

When running the tool against multiple environments in the same pipeline (dev, staging, production), use `--comment-title` to distinguish PR comments:

**Problem:** Multiple comments titled "What-If Deployment Review" are hard to differentiate.

**Solution:** Customize the title for each environment:

```bash
# Development environment
az deployment group what-if ... | bicep-whatif-advisor \
  --comment-title "Dev Environment"

# Production environment
az deployment group what-if ... | bicep-whatif-advisor \
  --comment-title "Production"

# Non-blocking analysis (automatically appends "non-blocking" to title)
az deployment group what-if ... | bicep-whatif-advisor \
  --comment-title "Deployment Analysis Production" \
  --no-block
# Title becomes: "Deployment Analysis Production (non-blocking)"
```

**GitHub Actions Example:**
```yaml
jobs:
  review-dev:
    runs-on: ubuntu-latest
    steps:
      - name: Dev What-If Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.DEV_RESOURCE_GROUP }} \
            --template-file main.bicep \
            --exclude-change-types NoChange Ignore \
            | bicep-whatif-advisor --comment-title "Dev Environment"

  review-prod:
    runs-on: ubuntu-latest
    steps:
      - name: Production What-If Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group ${{ vars.PROD_RESOURCE_GROUP }} \
            --template-file main.bicep \
            --exclude-change-types NoChange Ignore \
            | bicep-whatif-advisor --comment-title "Production"
```

**Result:** PR will show clearly labeled comments:
- **Dev Environment**
- **Production**
- **Deployment Analysis Production (non-blocking)** - when using `--no-block`

### Non-Blocking Mode (`--no-block`)

By default, CI mode blocks deployment if risk thresholds are exceeded (exit code 1). Use `--no-block` to report findings without failing the pipeline:

**Use cases:**
- **Informational reviews** - Get risk analysis without blocking deployment
- **Gradual rollout** - Collect data before enforcing strict gates
- **Soft gates** - Let teams review warnings but don't stop deployments
- **Multi-environment** - Block production but allow dev/staging

**Example:**
```bash
# Report findings but don't fail pipeline
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --no-block \
  --post-comment \
  --comment-title "Deployment Analysis Production"

# Exit code: Always 0, even if unsafe
# PR comment title: "Deployment Analysis Production (non-blocking)"
```

**Output:**
```
⚠️  Warning: Failed risk buckets: operations (pipeline not blocked due to --no-block)
ℹ️  CI mode: Reporting findings only (--no-block enabled)
```

**Note:** When `--no-block` is used, "(non-blocking)" is automatically appended to the PR comment title, making it immediately clear that the review is informational only.

**GitHub Actions example:**
```yaml
- name: AI Review (Non-blocking for Dev)
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if \
      --resource-group ${{ vars.DEV_RESOURCE_GROUP }} \
      --template-file main.bicep \
      | bicep-whatif-advisor --no-block
```

---

## Troubleshooting

### GitHub Actions: No PR comment posted

**Cause:** Missing `pull-requests: write` permission

**Fix:**
```yaml
permissions:
  pull-requests: write
```

### GitHub Actions: Login failed

**Cause:** Federated credential not configured correctly

**Fix:**
1. Verify federated credential exists: `az ad app federated-credential list --id $APP_ID`
2. Check subject matches: `repo:YOUR-ORG/YOUR-REPO:pull_request`
3. Ensure credential is for **Pull Request** entity type

### Azure DevOps: No PR comment posted

**Cause:** Missing `SYSTEM_ACCESSTOKEN` environment variable

**Fix:**
```yaml
env:
  SYSTEM_ACCESSTOKEN: $(System.AccessToken)
```

### Azure DevOps: 403 Forbidden when posting PR comments

**Cause:** Build service doesn't have "Contribute to pull requests" permission

**Fix:** See [Azure DevOps - Step 1: Configure Build Service Permissions](#step-1-configure-build-service-permissions) for detailed instructions

**Quick fix:**
1. **Project Settings** → **Repositories** → **Security**
2. Find: `{ProjectName} Build Service ({OrgName})`
3. Set **"Contribute to pull requests"** to **Allow** ✓

### "CI mode not detected"

**Cause:** Running outside GitHub Actions or Azure DevOps

**Fix:** Manually enable CI mode:
```bash
| bicep-whatif-advisor --ci
```

### High risk detected unexpectedly

**Cause:** Infrastructure drift (deployed resources don't match code)

**Fix:**
1. Check drift explanation in PR comment
2. Update code to match infrastructure, OR
3. Deploy from main branch to sync infrastructure

**For more troubleshooting,** see [USER_GUIDE.md - Troubleshooting](./USER_GUIDE.md#troubleshooting)

---

## Example PR Comment

When a PR is created, you'll see:

```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | Low | All changes present in code |
| PR Intent Alignment | Low | Changes match PR description |
| Risky Operations | Medium | Creates new public endpoint |

### Resource Changes

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | app-service | Microsoft.Web/sites | Create | Medium | New App Service with public endpoint |
| 2 | app-plan | Microsoft.Web/serverfarms | Create | Low | Consumption plan for App Service |

**Summary:** This deployment creates new App Service resources as described in PR.

### Verdict: ✅ SAFE

**Overall Risk Level:** Medium
**Highest Risk Bucket:** Operations
**Reasoning:** New public endpoint is documented in PR and includes planned firewall rules.

---
*Generated by bicep-whatif-advisor*
```

---

## Additional Resources

- [Quick Start Guide](./QUICKSTART.md) - 5-minute getting started
- [User Guide](./USER_GUIDE.md) - Complete feature reference
- [Risk Assessment Guide](./RISK_ASSESSMENT.md) - Understanding risk evaluation
- [Azure OIDC Authentication](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect) - GitHub Actions Azure auth
