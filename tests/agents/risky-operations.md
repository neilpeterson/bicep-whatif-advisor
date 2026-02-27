---
id: operations
display_name: Risky Operations
default_threshold: high
display: table
enabled: false
---
**Risky Operations Risk:**
Evaluate the inherent risk of the operations being performed,
regardless of drift or intent.

Risk levels for operations:
- high: Deletion of stateful resources (databases, storage accounts,
  key vaults), deletion of identity/RBAC resources, network security
  changes that open broad access, encryption setting modifications,
  SKU downgrades that could cause data loss
- medium: Modifications to existing resources that change behavior
  (policy changes, scaling configuration), new public endpoints,
  firewall rule changes, significant configuration updates
- low: Adding new resources, modifying tags, adding
  diagnostic/monitoring resources, modifying display
  names/descriptions