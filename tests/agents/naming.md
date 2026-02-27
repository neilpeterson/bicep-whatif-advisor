---
id: naming
display_name: Naming Convention
default_threshold: medium
---

**Naming Convention Risk:**
Evaluate whether resource names in the What-If output follow the Azure Cloud Adoption Framework (CAF) naming conventions defined at https://learn.microsoft.com/en-us/azure/cloud-adoption-framework/ready/azure-best-practices/resource-naming.

The expected naming pattern is:

    <resource-type-prefix>-<workload/app>-<environment>-<region (optional)>-<instance (optional)>

Common resource type abbreviations:

| Resource Type | Prefix | Example |
|---|---|---|
| Resource group | `rg` | `rg-webapp-prod` |
| Virtual machine | `vm` | `vm-sql-prod-001` |
| Storage account | `st` (no hyphens) | `stnavigatordata001` |
| Key vault | `kv` | `kv-app-prod-001` |
| Virtual network | `vnet` | `vnet-prod-westus-001` |
| Subnet | `snet` | `snet-prod-westus-001` |
| Network security group | `nsg` | `nsg-weballow-001` |
| Public IP address | `pip` | `pip-app-prod-westus-001` |
| App Service / Web app | `app` | `app-navigator-prod-001` |
| Function app | `func` | `func-navigator-prod-001` |
| SQL database | `sqldb` | `sqldb-users-prod` |
| Cosmos DB | `cosmos` | `cosmos-navigator-prod` |
| Container registry | `cr` (no hyphens) | `crnavigatorprod001` |
| Load balancer | `lbe` / `lbi` | `lbe-app-prod-001` |
| Managed identity | `id` | `id-app-prod-eastus2-001` |

Resources like storage accounts and container registries do not allow hyphens, so their names concatenate components without delimiters.

Risk levels for naming:
- high: Resources with no recognizable CAF prefix, completely non-standard names that ignore the convention entirely, or names that would make the resource type unidentifiable
- medium: Correct prefix but missing key components (environment, workload), inconsistent delimiter usage, or mixed naming patterns across resources in the same deployment
- low: Minor deviations such as non-standard abbreviations for environment or region, missing optional instance numbers, or slight ordering differences
