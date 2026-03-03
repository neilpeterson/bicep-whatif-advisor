# Bug: Resource Noise Patterns Failing on LLM-Shortened Types

## Status: Fixed in v2.5.1 (PR #30)

## Description

`resource:` noise patterns failed to match when the LLM returned shortened resource types (e.g., `Network/privateEndpoints` instead of `Microsoft.Network/privateEndpoints`). This caused patterns written with full ARM types to silently fail, leaving matched resources at whatever confidence the LLM assigned.

## Expected Behavior

A pattern like `resource: Microsoft.Network/privateEndpoints:Modify` should match LLM output that uses `Network/privateEndpoints` as the resource type.

## Actual Behavior

The pattern did not match because the post-LLM matcher performed a direct substring check. Since `Microsoft.Network/privateEndpoints` is not a substring of `Network/privateEndpoints`, the pattern silently failed.

## Root Cause

**File:** `noise_filter.py`

In v2.5.0, `resource:` patterns moved from pre-LLM block removal to post-LLM confidence demotion. The post-LLM matcher operates on LLM-generated `resource_type` fields, which consistently omit the `Microsoft.` namespace prefix. The original pre-LLM matcher worked against raw What-If text which always includes the full ARM type path.

The substring check was unidirectional — it only checked if the pattern was contained in the type string, not the reverse.

## Fix

Added **bidirectional substring matching** in `_matches_resource_pattern_post_llm`: the function now checks both `pattern in type` and `type in pattern`. This handles cases where the LLM shortens the type by stripping the `Microsoft.` prefix.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/noise_filter.py` | Added bidirectional substring matching for post-LLM resource patterns |
