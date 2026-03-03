# Bug: Verdict Display Ignoring Threshold Evaluation

## Status: Fixed in v3.6.1 (PR #46)

## Description

The rendered output and PR comments displayed the LLM's raw verdict instead of the tool's threshold evaluation result. This caused the verdict to show "SAFE" even when a risk level exceeded the configured threshold.

## Expected Behavior

When a risk bucket's level exceeds its configured threshold (e.g., medium risk with a low threshold), the verdict should display "UNSAFE" and the pipeline should fail.

## Actual Behavior

The verdict displayed the LLM's assessment ("SAFE") rather than the tool's threshold comparison result, leading to misleading output. The exit code was correct (the pipeline would fail), but the displayed verdict contradicted the exit code.

## Root Cause

**File:** `cli.py`

The threshold evaluation logic ran **after** rendering, so the displayed verdict was the LLM's raw `verdict.safe` field rather than the computed result from `evaluate_risk_buckets()`. The LLM might assess "low" risk and say "safe", but if the threshold was set to flag anything above "none", the tool should override the verdict display.

## Fix

The threshold evaluation now runs **before** rendering. The `verdict.safe` and related fields in the data dict are updated to reflect whether any risk levels exceeded their configured thresholds before the data is passed to the rendering functions.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/cli.py` | Moved threshold evaluation before rendering |
| `bicep_whatif_advisor/ci/verdict.py` | Updated verdict evaluation logic |
