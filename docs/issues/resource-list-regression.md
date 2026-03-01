# Bug: Changed Resources Table Shows Summary Row Instead of Individual Resources

## Status: Fixed

## Description

In CI mode PR comments, the "View changed resources" collapsible section displays a single summary row (e.g., "10 resources / Various / Modify / High") instead of listing each resource individually with its own name, type, action, and risk level.

## Expected Behavior (v3.2.0)

Each changed resource should appear as its own row in the table:

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | myKeyVault | Microsoft.KeyVault/vaults | Modify | Low | Name updated |
| 2 | myAppInsights | Microsoft.Insights/components | Modify | Low | Tags changed |
| ... | ... | ... | ... | ... | ... |

## Actual Behavior (v3.5.4)

A single aggregated row appears instead:

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | 10 resources | Various | Modify | High | What-If shows 10 resources being modified... |

## Regression Window

- **Last known good:** v3.2.0
- **First known broken:** v3.5.0 (commit `96b0315` — pre-LLM resource block filtering)
- **Worsened in:** v3.5.4 (commit `8c68b5d` — hollow Modify block suppression)

## Reproduction

Run the tool in CI mode against a deployment with multiple resource changes where most resources have only noisy property changes (e.g., etag, provisioningState). The more resources that get noise-filtered, the more likely the LLM produces a summary row.

## Root Cause

### Issue 1 (Primary): Stale epilogue after noise filtering

**File:** `noise_filter.py:494`

When `filter_whatif_text()` removes resource blocks (Phase 1 resource patterns and hollow Modify suppression), it strips the blocks from the output but **preserves the epilogue line verbatim**:

```
Resource changes: 1 to create, 9 to modify.
```

After filtering removes 9 of 10 blocks, the LLM receives What-If text that contains only 1 resource block but the epilogue still claims 10 changes. The LLM tries to reconcile this mismatch by producing a single summary row for the "missing" resources (e.g., "10 resources / Various / Modify").

When ALL blocks are removed, the LLM receives just the preamble + epilogue with zero resource blocks, guaranteeing a summary-style response.

**How it worked in v3.2.0:** Pre-LLM resource block removal didn't exist. All blocks were sent to the LLM, so the epilogue always matched the content. The LLM saw each resource and produced individual rows.

### Issue 2 (Secondary): Lossy reconstruction in re-analysis path

**File:** `cli.py:695-710`

When re-analysis triggers (low-confidence resources detected in CI mode), the code reconstructs fake What-If content from the first LLM call's summaries instead of using the already-filtered `whatif_content` variable:

```python
filtered_whatif_lines = ["Resource changes:"]
for resource in high_confidence_data.get("resources", []):
    action_symbol = {...}.get(resource.get("action", "").lower(), "~")
    filtered_whatif_lines.append(f"{action_symbol} {resource['resource_name']}")
    filtered_whatif_lines.append(f"  Summary: {resource['summary']}")
```

This produces entries like:
```
~ storageAccount1
  Summary: Modifies storage configuration
```

This doesn't match real What-If format (missing API version, indentation, property details), which may further confuse the LLM.

Note: The re-analysis path only merges `risk_assessment` and `verdict` (lines 743-748), not `resources`, so this primarily affects risk assessment accuracy rather than the displayed resource list. However, if Issue 1 caused the initial LLM call to return a summary row, the re-analysis inherits that broken data.

## Commits Involved

| Commit | Version | Change | Impact |
|--------|---------|--------|--------|
| `96b0315` | v3.5.0 | Pre-LLM resource block filtering | Introduced block removal without epilogue update |
| `8c68b5d` | v3.5.4 | Hollow Modify block suppression | More blocks removed, worsening the epilogue mismatch |

## Proposed Fix

### Fix 1 (Critical): Update or strip the epilogue after filtering

In `noise_filter.py`, after resource blocks are removed, either:
- **Option A:** Remove the epilogue line entirely from filtered output
- **Option B:** Rewrite the epilogue to reflect actual remaining block counts

Option A is simpler and sufficient — the LLM doesn't need the epilogue to analyze individual resources.

### Fix 2 (Improvement): Use real What-If content in re-analysis

In `cli.py:695-710`, replace the fake What-If reconstruction with the already-filtered `whatif_content` variable, which is real What-If format with noise already removed.
