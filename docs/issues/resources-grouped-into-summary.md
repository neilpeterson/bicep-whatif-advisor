# Bug: LLM Grouping Resources into Summary Row Instead of Individual Entries

## Status: Fixed in v3.7.2 (PR #50)

## Description

The "View changed resources" table in PR comments displayed a single summary row (e.g., "Berlin branch resources" / "Multiple (Storage Account, Key Vault, NSG Rule, Private Endpoints)") instead of listing each resource individually. In some cases, the LLM generated phantom resource entries when the What-If output showed no actual changes.

## Expected Behavior

Each resource from the What-If output should appear as its own row in the resources table. If the What-If output contains no resource changes, the resources list should be empty.

## Actual Behavior

The LLM collapsed multiple resources into a single summary row like:

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | Berlin branch resources | Multiple (Storage Account, Key Vault, NSG Rule, Private Endpoints) | Create | High | Creates new Berlin branch office infrastructure... |

In environments with no changes, the LLM still generated resource entries by inferring from `<bicep_source>` or `<code_diff>` context rather than strictly using the What-If output.

## Root Cause

**File:** `prompt.py`

The `resources` array schema in both standard and CI mode prompts lacked explicit instructions about:
1. Listing resources individually (not grouping/summarizing)
2. Only including resources from the What-If output (not inferring from Bicep source or code diff)
3. Returning an empty array when no changes exist

Without these constraints, the LLM used its discretion to group related resources and infer resource entries from supplementary context.

## Fix

Added explicit instructions before the `resources` schema in both standard and CI mode prompts:

```
IMPORTANT rules for the "resources" array:
- List ONLY resources that appear in the <whatif_output>. Do NOT infer or add resources from <bicep_source> or <code_diff>.
- Each resource must be its own entry. NEVER group multiple resources into a single summary row.
- If the What-If output contains no resource changes, return an empty array: "resources": [].
```

Also updated the `resource_name` and `resource_type` field descriptions to clarify they come "from the What-If output."

## Related Issues

This is a recurring pattern related to [resource-list-regression.md](resource-list-regression.md) (v3.5.5), where stale epilogue lines after noise filtering caused a similar symptom. The root cause here is different — the LLM groups/invents resources from supplementary context rather than being confused by count mismatches.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Added resource listing constraints to both standard and CI mode prompts |
