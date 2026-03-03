# Bug: Only First Risk Concern Shown in Key Concerns Column

## Status: Fixed in v2.5.2 (PR #31)

## Description

The Key Concerns column in the risk assessment table only displayed the first concern from each bucket's `concerns` array. When multiple issues were detected (e.g., both a Key Vault modification and an NSG rule violation), only one would appear.

## Expected Behavior

All concerns for a risk bucket should be visible in the Key Concerns column of the risk assessment table.

## Actual Behavior

Only `concerns[0]` was displayed. Additional concerns were silently dropped from the table display, even though they were present in the LLM response.

## Root Cause

**Files:** `prompt.py`, `render.py`

The rendering code accessed only the first element of the `concerns` array:

```python
concern_text = bucket_data.get("concerns", ["None"])[0]
```

For risk buckets with multiple concerns, all but the first were invisible in the output.

## Fix

Added a `concern_summary` field to the per-bucket LLM prompt schema. The LLM now generates a 1-2 sentence natural language summary of **all** concerns for each bucket. The rendering code displays this `concern_summary` field instead of `concerns[0]`.

This approach is better than concatenating raw concerns because the LLM produces a readable, contextual summary.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Added `concern_summary` field to risk bucket schema |
| `bicep_whatif_advisor/render.py` | Display `concern_summary` instead of `concerns[0]` |
