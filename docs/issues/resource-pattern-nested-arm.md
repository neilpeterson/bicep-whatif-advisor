# Bug: Resource Noise Patterns Not Matching Nested ARM Child Resources

## Status: Fixed in v2.4.0 (PR #29)

## Description

`resource:` noise filter patterns failed to match nested ARM child resource types. Azure What-If output includes resource names interleaved between type segments, causing direct substring matching to fail.

## Expected Behavior

A pattern like `resource: storageAccounts/blobServices:Modify` should match What-If entries for `Microsoft.Storage/storageAccounts/myaccount/blobServices/default`.

## Actual Behavior

The pattern did not match because `storageAccounts/blobServices` is not a direct substring of the full What-If path `Microsoft.Storage/storageAccounts/myaccount/blobServices/default` (the resource name `myaccount` is interleaved).

## Root Cause

**File:** `noise_filter.py`

Azure What-If output interleaves resource names between ARM type segments:

```
Microsoft.Storage/storageAccounts/myaccount/blobServices/default
                                  ^^^^^^^^^             ^^^^^^^
                                  resource name segments
```

The noise pattern matcher performed a simple substring check against the full What-If path, which failed because the ARM type path (without names) doesn't appear as a contiguous substring.

## Fix

Added `_extract_arm_type()` function that strips resource name segments from full What-If paths to derive the ARM resource type. The pattern matcher now checks against both the full path **and** the extracted ARM type, so patterns work correctly for all nesting levels.

Example:
```
Full path:     Microsoft.Storage/storageAccounts/myaccount/blobServices/default
Extracted type: Microsoft.Storage/storageAccounts/blobServices
Pattern:        storageAccounts/blobServices → MATCH
```

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/noise_filter.py` | Added ARM type extraction and dual-path matching |
