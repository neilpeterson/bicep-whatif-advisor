# Bug: Default Risk Threshold Too Strict (Low)

## Status: Fixed in v3.6.2 (PR #47)

## Description

The default risk threshold was set to `low` (in v3.6.0), which was too strict — it flagged deployments as unsafe even when the LLM assessed low risk on a clean deployment. This made the tool impractical for real-world use as nearly every deployment would fail.

## Expected Behavior

Clean deployments with only minor or expected changes should pass the safety check with default settings. The default threshold should balance safety with usability.

## Actual Behavior

Any detected risk level (low, medium, or high) would flag the deployment as unsafe, because the threshold was set to `low`. Since the LLM almost always assigns at least "low" risk to any change, virtually all deployments failed.

## History

- **v1.0.0 – v3.5.5:** Default threshold was `high` (only high-risk items fail)
- **v3.6.0:** Changed to `low` (any risk level fails) — too strict
- **v3.6.2:** Changed to `medium` (medium and high fail, low passes) — balanced

## Root Cause

The v3.6.0 change (PR #45) set the default threshold from `high` to `low` to make the tool stricter by default. However, this was overcorrection — the LLM assigns "low" risk to most changes even when they are routine and expected, making the `low` threshold impractical.

## Fix

Changed the default threshold to `medium` for all buckets:
- `--drift-threshold` default: `low` → `medium`
- `--intent-threshold` default: `low` → `medium`
- `RiskBucket.default_threshold` dataclass default: `low` → `medium`

With `medium` as default:
- **Low risk** → SAFE (passes)
- **Medium risk** → UNSAFE (blocks)
- **High risk** → UNSAFE (blocks)

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/cli.py` | Updated default threshold CLI flags |
| `bicep_whatif_advisor/ci/buckets.py` | Updated RiskBucket dataclass default |
