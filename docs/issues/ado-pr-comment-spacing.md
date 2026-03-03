# Bug: Azure DevOps PR Comment Spacing Issues

## Status: Fixed in v2.5.3 (PR #32) and v2.1.0 (PR #26)

## Description

Collapsible sections in Azure DevOps PR comments appeared too close together or had inconsistent spacing. This occurred in two separate areas of the rendering code.

## Issue 1: Spacing between resource table and noise section (v2.1.0)

### Problem

On GitHub, blank lines between `</details>` and the next `<details>` block provide sufficient visual spacing. On Azure DevOps, the markdown renderer collapses these blank lines, causing sections to run together.

### Fix

Added conditional `<br>` tags between collapsible sections, only on non-GitHub platforms. GitHub's renderer handles spacing with blank lines alone.

**Fixed in:** v2.1.0 (PR #26)

## Issue 2: Spacing for noise and raw What-If sections (v2.5.3)

### Problem

The same spacing issue affected the low-confidence noise section and raw What-If output section added later. These sections used the same collapsible `<details>` pattern but didn't inherit the platform-conditional `<br>` fix from v2.1.0.

### Fix

Applied the same conditional `<br>` formatting pattern to the noise and raw What-If collapsible sections.

**Fixed in:** v2.5.3 (PR #32)

## Files Changed

| File | Change |
|------|--------|
| `bicep_whatif_advisor/render.py` | Added platform-conditional `<br>` tags between collapsible sections |
