---
id: sfi-infra
display_name: Secure Infrastructure
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
---

**Secure Azure Infrastructure Risk:**
Evaluate whether the deployment follows Azure security best practices for infrastructure hardening. Flag resources that are created or modified with insecure configurations. For the output, return a table with the following columns:

- SFI ID and Name - this is taken from the title of each check below
- Compliance Status - compliant or non-compliant
- Applicable - true / false if the specific check applies to the deployment (e.g., if there are no SQL databases, then the SQL DB check would be not applicable)

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
PaaS resources (Storage Accounts, SQL Databases, Cosmos DB, Key Vaults) must have private endpoints configured or be associated with a network security perimeter. Check for one of the following in the What-If output or Bicep source:

- Presence of a private endpoint resource linked to the PaaS resource.
- Assoication with a network security perimeter.

If a PaaS resource is being created or modified without private endpoints or network security perimeter association, flag it.

### [SFI-ID4.3.3] Service Bus - Safe Secrets Standard
Disable local authentication for Azure Service Bus. The What-If output or Bicep source should show `disableLocalAuth` set to `true`. If a Service Bus namespace is being created or modified without disabling local authentication, flag it.

### [SFI-ID4.2.1] Storage Accounts - Safe Secrets Standard
Azure Storaeg Accounts must have the `allowSharedKeyAccess` property set to `false`. The What-If output or Bicep source should show `allowSharedKeyAccess` set to `false`. If a Storage Account is being created or modified with `allowSharedKeyAccess` set to `true`, flag it.