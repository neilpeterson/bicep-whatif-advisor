---
id: sfi-infra
display_name: Secure Infrastructure
default_threshold: high
display: table
enabled: False
icon: "🔒"
---

**Secure Azure Infrastructure Risk:**
Evaluate whether the deployment follows Azure security best practices for infrastructure hardening. Flag resources that are created or modified with insecure configurations.

## Checks

### Storage Account Public Network Access
All Azure Storage Accounts (`Microsoft.Storage/storageAccounts`) must have public network access disabled. The What-If output or Bicep source should show `publicNetworkAccess` set to `Disabled`. If a storage account is being created or modified without explicitly disabling public network access, flag it.

Indicators of a violation:
- `publicNetworkAccess` is set to `Enabled` or not present in the resource configuration
- Network rules default action is `Allow` instead of `Deny`
- No private endpoint or virtual network rules are configured alongside the storage account

Risk levels:
- high: A storage account is created or modified with public network access enabled or not explicitly disabled — this exposes the account to the public internet
- medium: Storage account has network rules but default action is `Allow`, or public access is disabled but no private endpoint exists in the deployment
- low: Storage account has public access disabled and private endpoints configured, but minor improvements could be made (e.g., adding IP allow-list restrictions)

### Key Vault Public Network Access
All Azure Key Vaults (`Microsoft.KeyVault/vaults`) must have public network access disabled. The What-If output or Bicep source should show `publicNetworkAccess` set to `Disabled` or network ACLs with `defaultAction` set to `Deny`. If a Key Vault is being created or modified without restricting public network access, flag it.

Indicators of a violation:
- `publicNetworkAccess` is set to `Enabled` or not present in the resource configuration
- `networkAcls.defaultAction` is set to `Allow` instead of `Deny`
- No private endpoint or virtual network rules are configured alongside the Key Vault

Risk levels:
- high: A Key Vault is created or modified with public network access enabled or not explicitly disabled — this exposes secrets, keys, and certificates to the public internet
- medium: Key Vault has network ACLs but default action is `Allow`, or public access is disabled but no private endpoint exists in the deployment
- low: Key Vault has public access disabled and private endpoints configured, but minor improvements could be made (e.g., tightening IP allow-list rules)
