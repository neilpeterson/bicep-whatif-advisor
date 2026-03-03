# Bug: Custom Agents Flagging Issues Outside Their Defined Scope

## Status: Fixed in v3.2.0 (PR #34)

## Description

Custom agents evaluated issues beyond their defined scope. An agent designed to check specific security properties (e.g., Storage Account `allowSharedKeyAccess` and Key Vault `publicNetworkAccess`) would also flag unrelated security concerns like NSG rules allowing traffic from `*`.

## Expected Behavior

A custom agent should only evaluate the specific checks defined in its markdown file. If the agent defines 3 checks, only those 3 checks should be evaluated, and the agent should not flag issues outside its instructions.

## Actual Behavior

The LLM used its general Azure security knowledge to flag additional issues beyond the agent's defined scope. For example, an agent checking only Storage Account and Key Vault settings would also report on network security group configurations, missing diagnostics, etc.

## Root Cause

**File:** `prompt.py`

The agent's body content was embedded in the system prompt without explicit scoping constraints. The LLM treated the agent instructions as minimum coverage rather than exclusive scope, using its general knowledge to flag additional concerns.

## Fix

Added constraining instructions to the prompt for custom agents:

```
IMPORTANT: For the "{bucket_id}" bucket, ONLY evaluate the specific checks described above.
Do NOT flag issues outside the scope of these instructions, even if they are legitimate
security or operational concerns. If no resources match the defined checks, return
risk_level "low" with an empty concerns array.
```

This makes agents predictable and scoped — only what you define is what gets evaluated.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Added scope constraint to custom agent prompt sections |
