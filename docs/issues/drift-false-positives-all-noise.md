# Bug: Infrastructure Drift False Positives When All Resources Are Noise

## Status: Fixed in v1.4.1 (PR #19)

## Description

When all resources in the What-If output were filtered as low-confidence noise (e.g., diagnostic settings, metadata changes), the Infrastructure Drift risk bucket incorrectly showed drift concerns instead of reporting "no drift."

## Expected Behavior

When all resources are flagged as low-confidence noise and excluded from analysis, all risk buckets should report "Low" risk with no concerns. The deployment should be marked as "SAFE."

## Actual Behavior

The Infrastructure Drift bucket showed drift concerns and the deployment was marked as "UNSAFE," even though there were no real changes to evaluate.

## Root Cause

**File:** `cli.py`

The risk assessment recalculation logic sent an empty What-If output (after filtering all resources) but included the full code diff to the LLM. The LLM interpreted this mismatch — seeing code changes but no What-If resources — as infrastructure drift rather than recognizing that all changes were filtered as noise.

## Fix

Added special case handling in the recalculation logic:
- Detects when all resources have been filtered (`num_remaining == 0`)
- Skips the unnecessary LLM recalculation
- Sets all risk buckets to "low" with empty concerns arrays
- Provides clear reasoning: "All detected changes were flagged as Azure What-If noise and excluded from analysis"

This also reduces unnecessary LLM API calls when all resources are noise.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/cli.py` | Added zero-resource shortcut in risk recalculation |
