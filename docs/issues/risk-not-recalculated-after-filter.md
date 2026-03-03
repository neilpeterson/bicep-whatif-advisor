# Bug: Risk Assessment Not Recalculating After Noise Filtering

## Status: Fixed in v1.4.0 (PR #15)

## Description

In CI mode, when resources were filtered as noise after the initial LLM analysis, the risk assessment was not recalculated based on the remaining high-confidence resources. The verdict was based on the original full set of resources, including noisy ones.

## Expected Behavior

After noise filtering removes low-confidence resources, the risk assessment should be recalculated using only the remaining high-confidence resources. A deployment with only noisy changes should be assessed as low risk.

## Actual Behavior

The risk assessment and verdict reflected the original LLM analysis that included all resources, even those subsequently filtered as noise. This led to elevated risk levels caused by noise rather than real changes.

## Root Cause

**File:** `cli.py`

The CI mode pipeline performed noise filtering after the LLM call but did not trigger a second LLM call to recalculate risk based on the filtered resource set. The risk_assessment and verdict from the initial call were used as-is.

## Fix

Added a re-analysis step in CI mode: after filtering low-confidence resources, a second LLM call is made with only the high-confidence What-If content to produce an updated risk assessment and verdict. The resource list from the first call is preserved; only the risk_assessment and verdict are replaced.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/cli.py` | Added post-filter risk recalculation with second LLM call |
