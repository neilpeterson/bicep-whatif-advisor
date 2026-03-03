# Drift Detection Bypassed by Noise Filtering

**Status:** Open
**Severity:** High
**Related issues:** drift-false-positives-all-noise, false-drift-hollow-modify, risk-not-recalculated-after-filter

## Problem

Pre-LLM noise filtering and drift detection are in conflict. When a `resource:` noise pattern (e.g., `resource: Microsoft.Storage/storageAccounts/blobServices:Modify`) matches a resource block, the entire block is removed from the What-If text before the LLM sees it. The LLM cannot detect drift on resources it never receives.

When ALL resources are filtered as noise, the code at `cli.py` lines 667-700 hardcodes all risk buckets (including drift) to "low" and the verdict to "safe" — completely hiding real drift.

### Reproduction

1. Have a storage account with manual portal changes (e.g., public access enabled, relaxed network ACLs)
2. Deploy with a noise file containing `resource: Microsoft.Storage/storageAccounts/blobServices:Modify`
3. The What-If shows the storage account being modified (drift — deployment will revert manual changes)
4. The noise filter removes the storage account block pre-LLM
5. The LLM never sees the storage account, cannot detect drift
6. All resources are now filtered → drift hardcoded to "low" → verdict "SAFE"

### Root Cause

This is a fundamental architectural conflict, not a simple bug. The noise filter and drift detection share the same What-If input, but:
- **Noise filtering** wants to REMOVE known false-positive properties before the LLM sees them
- **Drift detection** needs to SEE all What-If changes to compare them against the code diff

Fixes for one side keep breaking the other (see Related Issues cycle).

### Data Flow (Current — Broken)

```
Raw What-If Input
    ↓
Phase 1: Remove entire blocks matching resource: patterns (pre-LLM)
Phase 2: Remove property lines matching keyword/regex patterns (pre-LLM)
    ↓
Filtered What-If → LLM (drift info permanently lost)
    ↓
Post-LLM: confidence filtering
    ↓
If num_remaining == 0 → HARDCODE all buckets to "low" (including drift)
```

## Solution: Include Unfiltered What-If for Drift Analysis

Include BOTH filtered and unfiltered What-If content in the CI mode prompt when drift is enabled. The LLM uses `<whatif_output>` (filtered) for resource summaries and other buckets, and `<whatif_output_unfiltered>` (original) for drift detection only.

The unfiltered content is only sent when all three conditions are met:
1. CI mode is active
2. Drift bucket is enabled
3. Filtering actually changed the What-If content

Zero extra tokens in all other cases.

### Data Flow (Fixed)

```
Raw What-If Input
    ↓
    ├── original_whatif_content (preserved — already exists at cli.py line 545)
    ↓
Phase 1+2: Noise filtering (pre-LLM)
    ↓
    ├── <whatif_output> = filtered content → for resource summaries, intent, custom agents
    ├── <whatif_output_unfiltered> = original content → for drift detection ONLY
    ↓
LLM receives BOTH → evaluates drift on unfiltered, everything else on filtered
    ↓
Post-LLM: confidence filtering
    ↓
If num_remaining == 0:
    ├── Drift: PRESERVE LLM's assessment (it used unfiltered content)
    ├── Other buckets: set to "low" (no resources to evaluate)
    └── Verdict: recalculated considering preserved drift level
```

## Implementation

### 1. `bicep_whatif_advisor/prompt.py` — Add unfiltered What-If to user prompt

- Add `whatif_content_unfiltered: str = None` parameter to `build_user_prompt()`
- In CI mode branch, insert `<whatif_output_unfiltered>` tag between `<whatif_output>` and `<code_diff>` when the parameter is not None
- Update `_build_ci_system_prompt()` intro text to mention the optional unfiltered input

### 2. `bicep_whatif_advisor/ci/buckets.py` — Update drift prompt instructions

- Add paragraph to drift bucket `prompt_instructions` (before "Risk levels for drift:") telling the LLM to use `<whatif_output_unfiltered>` for drift analysis when available
- Other bucket instructions are unchanged — they continue referencing `<whatif_output>`

### 3. `bicep_whatif_advisor/cli.py` — Thread unfiltered content and fix "all filtered" path

**3a. Compute `whatif_content_unfiltered` (after line ~562):**
- Set `whatif_content_unfiltered = original_whatif_content` only when CI mode + drift enabled + filtering changed content
- `original_whatif_content` already exists at line 545

**3b. Pass to initial LLM call (line ~575):**
- Add `whatif_content_unfiltered=whatif_content_unfiltered` to `build_user_prompt()` call

**3c. Fix "all filtered" shortcut (lines 667-700):**
- When `num_remaining == 0` and drift was enabled with unfiltered content:
  - **Preserve** the LLM's original drift assessment (it used `<whatif_output_unfiltered>`)
  - Set non-drift buckets to "low" as before
  - Recalculate verdict considering preserved drift level
- When drift was NOT enabled or no unfiltered content: existing behavior (all "low")

**3d. Fix re-analysis path (line ~714):**
- Pass `whatif_content_unfiltered` to the re-analysis `build_user_prompt()` call

### 4. Tests

- `test_prompt.py`: Verify `<whatif_output_unfiltered>` appears/absent based on parameter
- `test_prompt.py`: Verify drift instructions reference `whatif_output_unfiltered`
- `test_cli.py`: All-filtered with drift enabled preserves LLM's drift assessment
- `test_cli.py`: All-filtered with drift skipped still sets all to "low"
- `test_cli.py`: Non-drift buckets still set to "low" when all filtered
- `test_cli.py`: Re-analysis passes unfiltered content
- `test_integration.py`: End-to-end all-filtered-with-drift scenario
- `test_integration.py`: Regression guard — all-filtered, drift is low, verdict is safe

## Verification

```bash
pytest tests/test_prompt.py tests/test_cli.py tests/test_integration.py -v
pytest  # Full suite — ensure no regressions
ruff check . && ruff format .
```

## Why This Breaks the Fix Cycle

Previous fixes addressed symptoms by choosing between false positives and false negatives on the same data path. This solution breaks the cycle by giving drift detection its own independent data path (`<whatif_output_unfiltered>`) that noise filtering cannot interfere with. The two systems no longer compete for the same input.
