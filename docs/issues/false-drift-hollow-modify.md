# Bug: False Drift Alerts from Hollow Noise-Filtered Modify Blocks

## Status: Fixed in v3.5.4 (PR #43)

## Description

When the noise filter removed all property-change lines from a Modify block, the resource header and attribute lines still remained in the text sent to the LLM. The LLM interpreted these "hollow" resources as real modifications, causing false **High risk / UNSAFE** verdicts on no-op deployments where all changes were noise.

## Expected Behavior

When all property-change lines in a Modify block are known noise (e.g., etag, provisioningState), the entire block should be suppressed from LLM analysis. The deployment should receive a "SAFE" verdict if no real changes exist.

## Actual Behavior

On a clean deployment where all detected changes were Azure What-If noise (e.g., 10 Modify blocks with only etag/provisioningState changes), the tool reported **High risk / UNSAFE** because the LLM saw 10 resource headers and inferred they were being modified.

## Root Cause

**File:** `noise_filter.py`

Phase 2 property filtering stripped individual property-change lines matching noise patterns but left the surrounding resource block structure intact:

```
~ Microsoft.KeyVault/vaults/myKeyVault [2023-07-01]
    id: "/subscriptions/.../myKeyVault"
    name: "myKeyVault"
    type: "Microsoft.KeyVault/vaults"
    location: "eastus"
    # (all property lines removed by noise filter)
```

The LLM saw these hollow blocks and treated them as real Modify operations, triggering drift concerns.

## Fix

Phase 2 property filtering now suppresses the entire Modify block when **all** its property-change lines match noise patterns. The suppressed blocks appear in the "Potential Azure What-If Noise" section but never reach the LLM. Create/Delete blocks are exempt since those operations are inherently significant regardless of listed properties.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/noise_filter.py` | Suppress entire Modify block when all property lines are noise |
