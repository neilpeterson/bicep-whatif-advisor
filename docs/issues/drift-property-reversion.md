# Bug: Drift Detection Missing Property Reversion Scenarios

## Status: Fixed in v3.5.2 (PR #41)

## Description

Infrastructure drift detection failed to identify the most common type of drift: property reversion. When a resource was manually changed in the Azure portal and the deployment would revert it back to the code-defined state, the LLM did not flag it as drift.

## Expected Behavior

If a Key Vault had `publicNetworkAccess` manually changed to "Enabled" in the portal, and the What-If output shows it being set back to "Disabled" (matching the code), this should be flagged as infrastructure drift — someone changed the resource outside of the PR process.

## Actual Behavior

The LLM concluded "no drift" because the What-If output and the code agreed on the final state. The drift prompt focused on "changes in What-If that aren't in the code diff," which missed reversion scenarios where the What-If change is actually *restoring* the code-defined value.

## Root Cause

**File:** `prompt.py` (drift bucket instructions)

The drift detection prompt instructed the LLM to look for "changes in What-If that aren't in the code diff." This framing missed the key signal: if What-If shows a Modify on a resource that the code diff didn't touch, that's drift regardless of whether the values match.

The prompt didn't account for the scenario where:
1. Code defines `publicNetworkAccess: 'Disabled'`
2. Someone manually sets it to `'Enabled'` in the portal
3. What-If shows it being set back to `'Disabled'`
4. The code diff doesn't touch this resource at all

## Fix

Rewrote the drift prompt with step-by-step detection logic:
- If What-If shows a Modify on a resource the code diff didn't touch, that's drift
- Added `publicNetworkAccess`, firewall rules, and RBAC settings as high-risk drift examples
- Explicit instruction to flag property reversion as drift

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Rewrote drift detection prompt with step-by-step logic |
