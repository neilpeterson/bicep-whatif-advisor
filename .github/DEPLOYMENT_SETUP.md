# GitHub Actions Deployment Setup

This guide explains how to configure GitHub Actions to deploy the Bicep template to Azure.

## Prerequisites

- Azure subscription
- GitHub repository with this code
- Resource group already created in Azure
- Existing APIM instance and Application Insights logger (as required by the Bicep template)

## Setup Instructions

This workflow uses **OIDC (OpenID Connect)** authentication - a passwordless, secure method that works with GitHub-hosted runners. This is similar to Azure DevOps service connections.

### Benefits of OIDC
- ✅ No passwords or secrets stored
- ✅ Uses federated identity (like ADO service connections)
- ✅ Works with GitHub-hosted runners
- ✅ Automatically rotates credentials

## OIDC Authentication Setup

### Step 1: Create Azure AD Application

```powershell
# Create the Azure AD application
$APP_NAME = "github-actions-bicep-deploy"
$APP_ID = az ad app create --display-name "github-actions-bicep-deploy" --query appId -o tsv

# Create service principal
az ad sp create --id $APP_ID

# Get tenant and subscription IDs
$TENANT_ID = az account show --query tenantId -o tsv
$SUBSCRIPTION_ID = az account show --query id -o tsv
$SP_OBJECT_ID = az ad sp show --id $APP_ID --query id -o tsv

Write-Host "Client ID (AZURE_CLIENT_ID): $APP_ID"
Write-Host "Tenant ID (AZURE_TENANT_ID): $TENANT_ID"
Write-Host "Subscription ID (AZURE_SUBSCRIPTION_ID): $SUBSCRIPTION_ID"
```

### Step 2: Configure Federated Credentials

Federated credentials allow GitHub Actions to authenticate to Azure without storing passwords. You'll create one or both depending on your workflow needs:

- **Main Branch Credential (Required)**: Allows workflows to deploy when running on the main branch (e.g., after PR merge)
- **Pull Request Credential (Optional)**: Allows workflows to run What-If analysis on PRs for preview and validation

```powershell
# Replace with your GitHub username/organization and repository name
$GITHUB_ORG = "your-github-username"
$REPO_NAME = "bicep-whatif-explain"

# Main Branch Credential (REQUIRED)
# Used by: deploy-bicep.yml workflow when triggered on push to main
# Purpose: Authenticate for actual deployments after code is merged
$federatedCredMain = @{
  name = "github-main-branch"
  issuer = "https://token.actions.githubusercontent.com"
  subject = "repo:$GITHUB_ORG/$REPO_NAME:ref:refs/heads/main"
  audiences = @("api://AzureADTokenExchange")
} | ConvertTo-Json -Compress

az ad app federated-credential create `
  --id $APP_ID `
  --parameters $federatedCredMain

# Pull Request Credential (OPTIONAL)
# Used by: Future What-If preview workflows triggered on pull_request events
# Purpose: Run What-If analysis and post summaries to PRs before merging
# Recommended: Add now even if not using yet - easier than adding later
$federatedCredPR = @{
  name = "github-pull-requests"
  issuer = "https://token.actions.githubusercontent.com"
  subject = "repo:$GITHUB_ORG/$REPO_NAME:pull_request"
  audiences = @("api://AzureADTokenExchange")
} | ConvertTo-Json -Compress

az ad app federated-credential create `
  --id $APP_ID `
  --parameters $federatedCredPR
```

### Step 3: Assign Azure Permissions

```powershell
# Get your resource group name
$RESOURCE_GROUP = "rg-apim-nepeters-vs"

# Assign Contributor role to the service principal on the resource group
az role assignment create `
  --assignee $APP_ID `
  --role Contributor `
  --scope /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RESOURCE_GROUP
```

### Step 4: Configure GitHub Secrets and Variables

In your GitHub repository, go to **Settings → Secrets and variables → Actions**:

**Secrets** (Settings → Secrets and variables → Actions → Secrets):
- `AZURE_CLIENT_ID`: The application (client) ID from step 1
- `AZURE_TENANT_ID`: Your Azure tenant ID
- `AZURE_SUBSCRIPTION_ID`: Your Azure subscription ID

**Variables** (Settings → Secrets and variables → Actions → Variables):
- `AZURE_RESOURCE_GROUP`: Your target resource group name (e.g., `rg-api-gateway-tme-two`)

## Testing the Deployment

### Manual Trigger

1. Go to **Actions** tab in GitHub
2. Select "Deploy Bicep Template" workflow
3. Click "Run workflow"
4. Select branch and run

### Automatic Trigger

Push changes to the `bicep-sample/` directory on the main branch:

```powershell
git add bicep-sample/
git commit -m "Update Bicep template"
git push origin main
```

## Troubleshooting

### Error: "The client does not have authorization"

- Verify the app registration has Contributor role on the resource group
- Check that the resource group name in GitHub variables matches exactly
- Ensure the federated credential subject matches your repository

### Error: "Resource not found" for APIM or App Insights

- Ensure the APIM instance and Application Insights logger exist
- Verify the names in `bicep-sample/tme-lab.bicepparam` match your Azure resources

### OIDC Error: "No matching federated identity record found"

- Verify federated credentials subject matches: `repo:ORG/REPO:ref:refs/heads/main`
- Ensure the `id-token: write` permission is set in the workflow

### Storage Account Name Conflict

- Storage account names must be globally unique
- Update `storageAccountName` in `bicep-sample/tme-lab.bicepparam` if needed

## Next Steps

Once basic deployment is working, you can:
- Add What-If analysis step before deployment
- Integrate `whatif-explain` for LLM-powered change summaries
- Add approval gates for production deployments
- Configure branch protection rules
