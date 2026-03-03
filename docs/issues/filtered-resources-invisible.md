# Bug: Pre-Filtered Resources Not Visible in Noise Section

## Status: Fixed in v3.5.1 (PR #40)

## Description

Pre-LLM resource block filtering (introduced in v3.5.0) removed matching blocks before the LLM saw them, which meant they had no entries to display in the "Potential Azure What-If Noise" section. Filtered resources simply vanished from all output with no trace.

## Expected Behavior

Resources removed by pre-LLM noise filtering should still appear in the "Potential Azure What-If Noise" section so users can see what was filtered and why.

## Actual Behavior

Resources matched by `resource:` noise patterns were completely invisible in the output — they were removed before the LLM could classify them, and no synthetic entries were created to track them.

## Root Cause

**File:** `noise_filter.py`, `cli.py`

`filter_whatif_text()` removed resource blocks but did not return metadata about what was removed. The CLI had no information to create noise section entries for pre-filtered resources.

## Fix

- `filter_whatif_text()` now returns a 4-tuple including metadata about each removed block (resource_type, resource_name, operation)
- The CLI injects synthetic low-confidence entries from this metadata so pre-filtered resources appear in the noise section with the reason "Matched resource noise pattern (pre-LLM filtered)"

### API Change

```python
# Before (3.5.0)
text, lines_removed, blocks_removed = filter_whatif_text(content, patterns)

# After (3.5.1)
text, lines_removed, blocks_removed, removed_resources = filter_whatif_text(content, patterns)
```

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/noise_filter.py` | Return removed resource metadata in 4-tuple |
| `bicep_whatif_advisor/cli.py` | Inject synthetic noise entries for pre-filtered resources |
