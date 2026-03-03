# Bug: Custom Agent Returning Incomplete Findings

## Status: Fixed in v3.7.1 (PR #48)

## Description

Custom agents with `display: table` that define multiple checks (e.g., 7 security compliance checks) only returned a subset of findings. For example, an agent designed to evaluate 7 SFI security checks and return all of them regardless of compliance status would only return 1 non-compliant finding instead of the expected 3.

## Expected Behavior

All checks defined in the agent should appear in the `findings` array, with compliance status and applicability for each, as specified by the agent's instructions ("Return all checks regardless of compliance status").

## Actual Behavior

Only 1 of 3 non-compliant checks appeared in the findings output. Compliant checks and some non-compliant checks were silently omitted.

## Root Cause

### Issue 1 (Primary): Conflicting prompt instructions

**File:** `prompt.py:200-203`

The system-generated findings instruction appended to every custom agent prompt said:

```
Include one finding per affected resource. If no issues found, return an empty array.
```

This conflicted with the agent's own body instructions which said "Return all checks regardless of compliance status." The LLM resolved the conflict by following the system instruction, only including findings for "affected" resources and skipping compliant checks entirely. The "per affected resource" phrasing was also resource-centric rather than check-centric, causing the LLM to collapse or skip check-oriented findings.

### Issue 2 (Contributing): Insufficient max output tokens

**File:** `providers/anthropic.py:60`

The Anthropic provider was capped at `max_tokens=4096`. With complex agent responses containing multiple risk buckets (drift, intent, custom agent), a full resources array, and 7+ findings rows, the JSON response could be truncated mid-stream, losing findings from the end of the output.

The Azure OpenAI provider (`providers/azure_openai.py`) had no explicit `max_tokens` set, relying on model defaults which vary by deployment.

## Fix

### Fix 1: Defer to agent instructions for findings format

Changed the system-generated instruction from prescriptive "one finding per affected resource" to:

```
Include ALL checks or items described in the agent instructions, not just failing ones.
```

This allows the agent's own body content to control the output structure.

### Fix 2: Increase max output tokens

- Anthropic: `max_tokens` increased from 4096 to 16384
- Azure OpenAI: Added explicit `max_tokens=16384` (previously unset)

The LLM only generates tokens needed, so the higher cap has no cost impact on shorter responses — it simply prevents truncation on complex outputs.

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/prompt.py` | Updated findings instruction to defer to agent body |
| `bicep_whatif_advisor/providers/anthropic.py` | max_tokens 4096 → 16384 |
| `bicep_whatif_advisor/providers/azure_openai.py` | Added explicit max_tokens=16384 |
