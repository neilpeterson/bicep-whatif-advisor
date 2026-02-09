# CI/CD Integration Guide

Complete guide for integrating `bicep-whatif-advisor` as an automated deployment gate in CI/CD pipelines.

## Table of Contents

- [Overview](#overview)
- [GitHub Actions](#github-actions)
- [Azure DevOps](#azure-devops)
- [Other CI Platforms](#other-ci-platforms)
- [Risk Assessment System](#risk-assessment-system)
- [Configuration Options](#configuration-options)
- [Troubleshooting](#troubleshooting)

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

## GitHub Actions

### Prerequisites

Before starting, ensure you have:

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

By default, deployments are blocked only on **high** risk. Adjust by adding flags:

```yaml
# More strict - block on medium risk
| bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Very strict - block on any risk
| bicep-whatif-advisor \
  --drift-threshold low \
  --intent-threshold low \
  --operations-threshold low
```

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

## Azure DevOps

### Minimal Setup (Recommended)

Complete PR review pipeline:

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
  BICEP_TEMPLATE: bicep/main.bicep
  BICEP_PARAMS: bicep/main.bicepparam

stages:
  - stage: WhatIfReview
    displayName: 'What-If Review'
    jobs:
      - job: Review
        displayName: 'AI Safety Review'
        steps:
          - checkout: self
            fetchDepth: 0

          - task: AzureCLI@2
            displayName: 'What-If Analysis & AI Review'
            inputs:
              azureSubscription: 'my-service-connection'
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

**Auto-detection includes:**
- CI mode enabled
- PR ID from `SYSTEM_PULLREQUEST_PULLREQUESTID`
- Diff reference from `SYSTEM_PULLREQUEST_TARGETBRANCH`
- PR comments posted when `SYSTEM_ACCESSTOKEN` available

### Required Variables

Add these in **Pipelines → Library → Variable groups:**

| Variable | Type | Description |
|----------|------|-------------|
| `ANTHROPIC_API_KEY` | Secret | From https://console.anthropic.com/ |
| `RESOURCE_GROUP` | Plain | Your Azure resource group name |

**Important:** Set `SYSTEM_ACCESSTOKEN` in pipeline YAML as shown above to enable PR comments.

### Azure DevOps Configuration Options

#### Adjust Risk Thresholds

```yaml
| bicep-whatif-advisor \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium
```

#### Manual PR Title/Description (Optional)

If you want intent analysis in Azure DevOps:

```yaml
| bicep-whatif-advisor \
  --pr-title "$(System.PullRequest.Title)" \
  --pr-description "$(System.PullRequest.Description)"
```

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

## Risk Assessment System

### Three Independent Risk Buckets

Each deployment is evaluated across three risk categories:

1. **Infrastructure Drift**
   - Detects changes in What-If output not present in code diff
   - Catches out-of-band modifications (manual portal changes)
   - **High risk:** Security settings, stateful resources
   - **Medium risk:** Multiple resources drifting
   - **Low risk:** Tags, display names

2. **PR Intent Alignment**
   - Compares What-If changes to PR title/description
   - Catches unintended side effects
   - **High risk:** Destructive changes not mentioned
   - **Medium risk:** Changes misaligned with PR purpose
   - **Low risk:** Minor scope differences

3. **Risky Operations**
   - Evaluates inherent danger of Azure operations
   - Independent of code/PR context
   - **High risk:** Deletions, security changes, public access
   - **Medium risk:** Behavioral changes, new endpoints
   - **Low risk:** New resources, monitoring, tags

### Risk Thresholds

Each bucket has an independent threshold (low, medium, high):

```bash
# Example: Strict on drift, lenient on operations
--drift-threshold low \
--intent-threshold high \
--operations-threshold high
```

**Deployment fails if ANY bucket exceeds its threshold.**

See [Risk Assessment Guide](./RISK_ASSESSMENT.md) for detailed explanation.

## Configuration Options

### Multi-Environment Setup

Use different thresholds per environment:

**Development:**
```yaml
| bicep-whatif-advisor \
  --drift-threshold low \      # Catch all drift
  --intent-threshold medium \
  --operations-threshold medium
```

**Production:**
```yaml
| bicep-whatif-advisor \
  --drift-threshold high \     # Only block critical drift
  --intent-threshold high \
  --operations-threshold high
```

### Specify Bicep Source Directory

Include Bicep source files for better analysis:

```bash
| bicep-whatif-advisor --bicep-dir bicep/modules/
```

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

### Azure DevOps: Build service permissions

**Cause:** Build service doesn't have permission to comment on PRs

**Fix:**
1. Project Settings → Repositories → Security
2. Grant "Contribute to pull requests" to build service

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

## Additional Resources

- [Getting Started Guide](./GETTING_STARTED.md) - Installation and basic usage
- [Risk Assessment Guide](./RISK_ASSESSMENT.md) - Understanding risk evaluation
- [CLI Reference](./CLI_REFERENCE.md) - Complete command reference
- [Azure OIDC Authentication](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect) - GitHub Actions Azure auth
