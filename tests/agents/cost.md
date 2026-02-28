---
id: cost
display_name: Cost Impact
default_threshold: high
display: summary
enabled: True
icon: "💰"
---

**Cost Impact Risk:**
Evaluate whether the deployment changes could cause a significant increase in Azure spending. Consider the resource types being created or modified and their typical cost drivers.

Key cost signals to look for:
- SKU or tier changes (e.g. Basic to Premium, Standard to HighPerformance)
- New stateful or always-on resources (VMs, databases, App Service plans, firewalls, gateways)
- Scaling changes (increased instance count, higher vCPU/memory, larger disk sizes)
- Region changes to more expensive regions
- Enabling premium features (availability zones, geo-replication, private endpoints)
- Storage capacity or throughput increases
- Switching from consumption/serverless to dedicated/provisioned pricing

Risk levels for cost:
- high: New high-cost resources (VMs, SQL databases, App Gateways, Firewall Premium), SKU upgrades to premium or enterprise tiers, enabling geo-replication or multi-region, large scaling operations (3x+ instance count)
- medium: Moderate SKU upgrades (Basic to Standard), adding new always-on resources at standard tiers, enabling features with incremental cost (private endpoints, diagnostic storage), scaling up by 1-2 instances
- low: New low-cost or free-tier resources (tags, NSG rules, role assignments), minor configuration changes with negligible cost impact, adding monitoring or logging resources
