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
---

**Secure Azure Infrastructure Risk:**
Evaluate whether the deployment follows Azure security best practices for infrastructure hardening. Flag resources that are created or modified with insecure configurations.

You MUST return exactly 7 findings rows — one for each check listed below. Never skip, combine, or omit checks. If a check does not apply to this deployment (e.g., no SQL databases exist), still include the row with Applicable set to "false" and Compliance Status set to "not-applicable".

Return a table with the following columns:

- **SFI ID and Name** — copy the `[SFI-XXXX]` ID and name exactly from each check heading below
- **Compliance Status** — "compliant", "non-compliant", or "not-applicable"
- **Applicable** — "true" if the resource type exists in the deployment, "false" otherwise

## Checks

### [SFI-ID4.2.2] SQL DB - Safe Secrets Standard
- **Resource type:** `Microsoft.Sql/servers`
- **Compliance condition:** `administratorType` must be set to `ActiveDirectory`
- **Non-compliant if:** A SQL logical server is created or modified without Entra ID authorization

### [SFI-ID4.2.3] Cosmos DB - Safe Secrets Standard
- **Resource type:** `Microsoft.DocumentDB/databaseAccounts`
- **Compliance condition:** `administratorType` must be set to `ActiveDirectory`
- **Non-compliant if:** A Cosmos DB account is created or modified without Entra ID authorization

### [SFI-ID4.3.2] Event Hub - Safe Secrets Standard
- **Resource type:** `Microsoft.EventHub/namespaces`
- **Compliance condition:** `disableLocalAuth` must be set to `true`
- **Non-compliant if:** An Event Hub namespace is created or modified without disabling local authentication

### [SFI-NS2.1] IP Allocations with Service Tags
- **Resource type:** `Microsoft.Network/publicIPAddresses`
- **Compliance condition:** `serviceTag` must be set to a valid Azure service tag (e.g., `AzureCloud`, `AzureFrontDoor.Backend`)
- **Non-compliant if:** A public IP address is created or modified without an associated service tag

### [SFI-NS2.2.1] Secure PaaS Resources
- **Resource type:** `Microsoft.Storage/storageAccounts`, `Microsoft.Sql/servers`, `Microsoft.DocumentDB/databaseAccounts`, `Microsoft.KeyVault/vaults`
- **Compliance condition:** At least one of the following must be true: (1) a `Microsoft.Network/privateEndpoints` resource references the PaaS resource, (2) the resource is associated with a `Microsoft.Network/networkSecurityPerimeters` resource, or (3) `publicNetworkAccess` is set to `Disabled`
- **Non-compliant if:** None of the above conditions are met (e.g., `publicNetworkAccess` is `Enabled` or defaulted with no private endpoint)

### [SFI-ID4.3.3] Service Bus - Safe Secrets Standard
- **Resource type:** `Microsoft.ServiceBus/namespaces`
- **Compliance condition:** `disableLocalAuth` must be set to `true`
- **Non-compliant if:** A Service Bus namespace is created or modified without disabling local authentication

### [SFI-ID4.2.1] Storage Accounts - Safe Secrets Standard
- **Resource type:** `Microsoft.Storage/storageAccounts`
- **Compliance condition:** `allowSharedKeyAccess` must be set to `false`
- **Non-compliant if:** A Storage Account is created or modified with `allowSharedKeyAccess` set to `true` or left at the default

---

**Reminder:** The findings array MUST contain exactly 7 rows — one per check above. Do not skip or combine checks.
