---
id: sfi-infra
display_name: SFI Secure Infrastructure
default_threshold: high
display: table
enabled: true
icon: "🔒"
columns:
  - name: SFI ID and Name
    description: taken from the title of each check
  - name: Compliance Status
    description: compliant or non-compliant
  - name: Applicable
    description: true / false if the specific check applies
  - name: Description
    description: Describe the SFI item and all violations found for the PR
---

**Secure Azure Infrastructure Risk:**
Evaluate whether the deployment follows Azure security best practices for infrastructure hardening. Flag resources that are created or modified with insecure configurations. For the output, return a table with the following columns. Return all checks regardless of compliance status, but indicate whether each check is applicable to the deployment.

- SFI ID and Name - this is taken from the title of each check below
- Compliance Status - compliant or non-compliant
- Applicable - true / false if the specific check applies to the deployment (e.g., if there are no SQL databases, then the SQL DB check would be not applicable)
- Description - Describe the SFI item and all violations found for the PR

## Checks

### [SFI-ID4.2.2] SQL DB - Safe Secrets Standard
Azure SQL servers must use Entra ID authorization. The What-If output or Bicep source should show `administratorType` set to `ActiveDirectory`. If a SQL logical server is being created or modified without using Entra ID authorization, flag it.

### [SFI-ID4.2.3] Cosmos DB - Safe Secrets Standard
Azure Cosmos DB instances must use Entra ID authorization. The What-If output or Bicep source should show `administratorType` set to `ActiveDirectory`. If a Cosmos DB account is being created or modified without using Entra ID authorization, flag it.

### [SFI-ID4.3.2] Event Hub - Safe Secrets Standard
Disable local authentication for Azure Event Hubs. The What-If output or Bicep source should show `disableLocalAuth` set to `true`. If an Event Hub namespace is being created or modified without disabling local authentication, flag it.

### [SFI-NS2.1] IP Allocations with Service Tags
Public IP addresses must have an associated service tag. The What-If output or Bicep source should show `serviceTag` set to a valid Azure service tag (e.g., `AzureCloud`, `AzureFrontDoor.Backend`, etc.) for any public IP address resource. If a public IP address is being created or modified without an associated service tag, flag it.

### [SFI-NS2.2.1] Secure PaaS Resources
PaaS resources (Storage Accounts, SQL Databases, Cosmos DB, Key Vaults) must have private endpoints configured or be associated with a network security perimeter. A resource is **compliant** if at least one of the following is true in the What-If output or Bicep source:

1. A `Microsoft.Network/privateEndpoints` resource exists with a `privateLinkServiceConnections` entry whose `groupIds` and `privateLinkServiceId` reference the PaaS resource.
2. The PaaS resource is associated with a `Microsoft.Network/networkSecurityPerimeters` resource.
3. The PaaS resource has `publicNetworkAccess` set to `'Disabled'`.

A resource is **non-compliant** if none of the above conditions are met — for example, the resource is deployed with `publicNetworkAccess` set to `'Enabled'` (or left at the default) and no private endpoint or network security perimeter association exists.

Multiple resources may be non-compliant, return all of them for the PR description.

#### Bicep Examples

**PASS — Private endpoint configured for a Storage Account:**

```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'mystorageaccount'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    publicNetworkAccess: 'Disabled'
  }
}

resource privateEndpoint 'Microsoft.Network/privateEndpoints@2023-11-01' = {
  name: 'pe-storage'
  location: location
  properties: {
    subnet: { id: subnetId }
    privateLinkServiceConnections: [
      {
        name: 'plsc-storage'
        properties: {
          privateLinkServiceId: storageAccount.id
          groupIds: [ 'blob' ]
        }
      }
    ]
  }
}
```

**PASS — Public network access disabled (Key Vault):**

```bicep
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: 'mykeyvault'
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: tenant().tenantId
    publicNetworkAccess: 'Disabled'
  }
}
```

**FAIL — Storage Account with no private endpoint and public access enabled:**

```bicep
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: 'mystorageaccount'
  location: location
  kind: 'StorageV2'
  sku: { name: 'Standard_LRS' }
  properties: {
    publicNetworkAccess: 'Enabled'    // ← non-compliant: public access with no private endpoint
  }
}
```

**FAIL — SQL Database with default public access and no private endpoint:**

```bicep
resource sqlServer 'Microsoft.Sql/servers@2023-08-01-preview' = {
  name: 'mysqlserver'
  location: location
  properties: {
    administratorLogin: 'adminUser'
    // publicNetworkAccess defaults to 'Enabled' — non-compliant without a private endpoint
  }
}
```

**FAIL — Cosmos DB with public access enabled and no private endpoint:**

```bicep
resource cosmosDb 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' = {
  name: 'mycosmosdb'
  location: location
  properties: {
    databaseAccountOfferType: 'Standard'
    publicNetworkAccess: 'Enabled'    // ← non-compliant: no private endpoint or NSP
    locations: [ { locationName: location, failoverPriority: 0 } ]
  }
}
```

### [SFI-ID4.3.3] Service Bus - Safe Secrets Standard
Disable local authentication for Azure Service Bus. The What-If output or Bicep source should show `disableLocalAuth` set to `true`. If a Service Bus namespace is being created or modified without disabling local authentication, flag it.

### [SFI-ID4.2.1] Storage Accounts - Safe Secrets Standard
Azure Storaeg Accounts must have the `allowSharedKeyAccess` property set to `false`. The What-If output or Bicep source should show `allowSharedKeyAccess` set to `false`. If a Storage Account is being created or modified with `allowSharedKeyAccess` set to `true`, flag it.