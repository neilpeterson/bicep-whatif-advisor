# Platform Auto-Detection Implementation Plan

## Goal
Simplify GitHub Actions and Azure DevOps pipeline integration by auto-detecting platform context and eliminating manual logic from workflow YAML files.

## Target User Experience

### GitHub Actions (Before: 170 lines → After: 6 lines)
```yaml
- name: Run What-If and AI Review
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor
```

### Azure DevOps (Before: ~100 lines → After: 6 lines)
```yaml
- script: |
    az deployment group what-if ... | bicep-whatif-advisor
  env:
    ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
    SYSTEM_ACCESSTOKEN: $(System.AccessToken)
  displayName: 'Run What-If and AI Review'
```

## Implementation Phases

### ✅ Phase 0: Planning & Setup
- [x] Create feature branch: `feature/unified-platform-detection`
- [x] Create plan document
- [x] Review existing code structure

### ✅ Phase 1: Platform Detection Module (30 min)
**Status:** Complete

**Tasks:**
- [x] Create `bicep_whatif_advisor/ci/platform.py`
- [x] Implement `PlatformContext` dataclass
- [x] Implement `detect_platform()` function
- [x] Implement `_detect_github()` function
- [x] Implement `_detect_azuredevops()` function
- [x] Add basic verification tests for platform detection

**Deliverables:**
- ✅ New module: `bicep_whatif_advisor/ci/platform.py`
- ✅ Auto-detects GitHub Actions environment
- ✅ Auto-detects Azure DevOps environment
- ✅ Extracts PR metadata from both platforms
- ✅ Returns unified `PlatformContext` object

**Notes:**
- All three platform types (local, github, azuredevops) working correctly
- GitHub Actions reads PR metadata from GITHUB_EVENT_PATH JSON file
- Azure DevOps reads PR ID and branches from environment variables
- Diff reference auto-generated from base branch (e.g., origin/main)

### ✅ Phase 2: CLI Integration (45 min)
**Status:** Complete

**Tasks:**
- [x] Import platform detection in `cli.py`
- [x] Auto-enable CI mode in pipeline environments
- [x] Auto-set diff reference from base branch
- [x] Auto-populate PR title/description
- [x] Auto-enable PR comments when token available
- [x] Add informative stderr messages for auto-detection
- [x] Ensure backward compatibility (manual flags still work)

**Deliverables:**
- ✅ Updated `bicep_whatif_advisor/cli.py`
- ✅ Automatic smart defaults in pipeline environments
- ✅ Helpful auto-detection messages in stderr (with emoji indicators)
- ✅ No breaking changes for existing users
- ✅ Removed old `_auto_detect_pr_metadata()` function (replaced by platform module)

**Notes:**
- Platform detection runs immediately after reading stdin
- Auto-detection only applies when platform != "local"
- Manual CLI flags always override auto-detected values (backward compatible)
- Helpful stderr messages show what was auto-detected:
  - 🤖 CI mode enabled
  - 📊 Diff reference detected
  - 📝 PR title detected
  - 📄 PR description detected
  - 💬 PR comments enabled

### ⏳ Phase 3: Azure DevOps PR Metadata (Optional - 1 hour)
**Status:** Not Started

**Tasks:**
- [ ] Research Azure DevOps REST API for PR metadata
- [ ] Implement `_fetch_ado_pr_metadata()` function
- [ ] Add API call when `SYSTEM_ACCESSTOKEN` available
- [ ] Add graceful fallback if API call fails
- [ ] Document limitations in PIPELINE.md

**Deliverables:**
- Optional: Fetch PR title/description from Azure DevOps API
- Falls back to manual `--pr-title`/`--pr-description` if unavailable

**Decision Point:** Implement if ADO users need automatic PR metadata. Otherwise, manual flags are acceptable.

### ⏳ Phase 4: Documentation Updates (30 min)
**Status:** Not Started

**Tasks:**
- [ ] Update `docs/PIPELINE.md` with simplified examples
- [ ] Add troubleshooting guide for common issues
- [ ] Document auto-detection behavior
- [ ] Document environment variables for both platforms
- [ ] Update README.md with new simplified examples
- [ ] Add "Migration Guide" for existing users

**Deliverables:**
- Updated documentation showing 6-line workflows
- Clear troubleshooting steps
- Migration guide from old to new approach

### ⏳ Phase 5: Testing (1 hour)
**Status:** Not Started

**Tasks:**
- [ ] Test GitHub Actions workflow in this repo
- [ ] Test Azure DevOps pipeline (if available)
- [ ] Test local execution (ensure no regression)
- [ ] Test with manual flags (backward compatibility)
- [ ] Test error cases (missing tokens, invalid metadata)
- [ ] Add integration tests if needed

**Deliverables:**
- Verified GitHub Actions workflow
- Verified Azure DevOps pipeline (if available)
- Verified local execution still works
- Verified backward compatibility

## Environment Variables Reference

### GitHub Actions
| Variable | Purpose | Auto-detected |
|----------|---------|---------------|
| `GITHUB_ACTIONS` | Platform detection | ✅ Yes |
| `GITHUB_EVENT_PATH` | PR metadata JSON | ✅ Yes |
| `GITHUB_BASE_REF` | Base branch for diff | ✅ Yes |
| `GITHUB_HEAD_REF` | Source branch | ✅ Yes |
| `GITHUB_REPOSITORY` | Repo name (owner/repo) | ✅ Yes |
| `GITHUB_TOKEN` | PR comment auth | ✅ Yes |

### Azure DevOps
| Variable | Purpose | Auto-detected |
|----------|---------|---------------|
| `TF_BUILD` or `AGENT_ID` | Platform detection | ✅ Yes |
| `SYSTEM_PULLREQUEST_PULLREQUESTID` | PR number | ✅ Yes |
| `SYSTEM_PULLREQUEST_TARGETBRANCH` | Base branch for diff | ✅ Yes |
| `SYSTEM_PULLREQUEST_SOURCEBRANCH` | Source branch | ✅ Yes |
| `BUILD_REPOSITORY_NAME` | Repo name | ✅ Yes |
| `SYSTEM_ACCESSTOKEN` | PR comment auth | ✅ Yes |
| PR Title/Description | PR metadata | ⚠️ Phase 3 |

## Success Criteria

- [ ] GitHub Actions workflows reduced from ~170 lines to ~6 lines
- [ ] Azure DevOps pipelines reduced from ~100 lines to ~6 lines
- [ ] No breaking changes for existing users
- [ ] Auto-detection works correctly for both platforms
- [ ] Helpful error messages when auto-detection fails
- [ ] Documentation updated with new simplified examples
- [ ] All tests pass

## Notes

- **Backward Compatibility:** All existing flags (`--ci`, `--diff-ref`, `--pr-title`, etc.) will continue to work. Auto-detection only fills in missing values.
- **Local Execution:** Tool detects "local" platform and behaves as before (no auto-enabling of CI mode).
- **Error Handling:** If auto-detection fails, tool falls back to defaults or manual flags with helpful error messages.

## Timeline

- Phase 1: 30 minutes (Platform detection module)
- Phase 2: 45 minutes (CLI integration)
- Phase 3: 1 hour (Optional - ADO PR metadata)
- Phase 4: 30 minutes (Documentation)
- Phase 5: 1 hour (Testing)

**Total:** ~3.5 hours (or ~2.5 hours without Phase 3)

## Current Status

**Completed Phases:** Phase 0, Phase 1, Phase 2
**Active Phase:** Phase 3 (Optional) - Azure DevOps PR Metadata
**Started:** 2026-02-08
**Branch:** `feature/unified-platform-detection`

### Summary of Completed Work

**Phase 1 - Platform Detection Module:**
- Created `bicep_whatif_advisor/ci/platform.py` with unified platform detection
- Supports GitHub Actions, Azure DevOps, and local environments
- Auto-extracts PR metadata, branch info, and generates diff references

**Phase 2 - CLI Integration:**
- Integrated platform detection into `cli.py`
- Auto-enables CI mode in pipeline environments
- Auto-populates all relevant flags from environment
- Added helpful emoji-based status messages to stderr
- Maintained full backward compatibility with manual flags

### Next Steps

**Recommended:** Skip Phase 3 (Azure DevOps PR metadata via API) for now since:
- ADO users can manually provide `--pr-title` and `--pr-description` flags
- API call adds complexity and potential auth issues
- Most critical features already working (PR comments, diff detection, CI mode)

**Proceed to:** Phase 4 (Documentation) and Phase 5 (Testing) to finalize the feature.
