# Bug: Drift Detection Confused by --bicep-dir Source Context

## Status: Fixed in v3.5.3 (PR #42)

## Description

When `--bicep-dir` was used to pass full Bicep source files to the LLM alongside the code diff, drift detection produced false negatives. Resources that were manually changed in the Azure portal (actual drift) were not flagged because the LLM saw the resource defined in the Bicep source and concluded the change was intentional.

## Expected Behavior

A Key Vault with `publicNetworkAccess` manually changed to "Enabled" in the Azure portal should be flagged as infrastructure drift when the Bicep source has it set to "Disabled" — even though the Bicep source is visible to the LLM.

## Actual Behavior

The LLM saw `publicNetworkAccess: 'Disabled'` in the `<bicep_source>` section and concluded "this is intentional, not drift," even though the PR's `<code_diff>` didn't touch that resource at all. The What-If output showed the property being set back to "Disabled" (reverting the manual change), but the LLM interpreted this as an intended configuration.

## Root Cause

**File:** `prompt.py` (drift bucket instructions)

The drift detection prompt did not clearly distinguish between the two input sources:
- `<code_diff>` — only the lines changed in the current PR (the source of truth for drift detection)
- `<bicep_source>` — the full Bicep codebase (supplementary context only)

The LLM treated both inputs equally, using the full Bicep source to "explain away" drift by finding the property definition in the codebase.

## Fix

Updated the drift prompt to explicitly distinguish the two inputs:
- `<code_diff>` = only the lines changed in **this PR** — use for drift detection
- `<bicep_source>` = the full Bicep codebase — context only, **not** for drift analysis

The key instruction: if What-If shows a Modify on a resource that the code diff didn't touch, that's drift regardless of what the full Bicep source says.

This is a follow-up to v3.5.2 which improved the drift prompt's detection logic but didn't account for the `--bicep-dir` interaction.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Clarified drift prompt to distinguish code_diff from bicep_source |
