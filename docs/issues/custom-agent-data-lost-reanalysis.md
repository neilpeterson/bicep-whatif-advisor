# Bug: Custom Agent Data Lost During Noise Re-Analysis

## Status: Fixed in v3.1.0 (PR #34)

## Description

When noise re-analysis triggered in CI mode (second LLM call after filtering low-confidence resources), custom agent risk assessment data from the initial LLM response was lost. The re-analysis response overwrote the full `risk_assessment` dict instead of merging bucket data.

## Expected Behavior

After noise re-analysis, custom agent risk assessment data should be preserved from the initial response. Only the built-in buckets (drift, intent) should be updated with recalculated values.

## Actual Behavior

The re-analysis response replaced the entire `risk_assessment` dict. Since the re-analysis prompt didn't include custom agent instructions, the custom agent buckets were completely absent from the final output.

## Root Cause

**File:** `cli.py`

The re-analysis merge logic did:

```python
data["risk_assessment"] = reanalysis_data["risk_assessment"]
```

This replaced the entire dict instead of merging per-bucket. Custom agent data from the initial call was overwritten with an empty or missing entry.

## Fix

Changed to per-bucket merge that preserves custom agent data:

```python
for bucket_id, bucket_data in reanalysis_data.get("risk_assessment", {}).items():
    data["risk_assessment"][bucket_id] = bucket_data
```

Also added a backfill step that ensures custom agents always appear in the risk assessment output, defaulting to "low" risk if the LLM omitted them from its response.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/cli.py` | Changed risk_assessment merge to per-bucket; added backfill for custom agents |
