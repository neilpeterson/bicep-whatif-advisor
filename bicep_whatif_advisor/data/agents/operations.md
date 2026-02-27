---
id: operations
display_name: Risky Operations
description: Evaluates inherent risk of Azure operations (deletions, security changes, etc.)
default_threshold: high
display: table
icon: "\u26A0\uFE0F"
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
