# Known Issues and Bug Fixes

This directory documents bugs that were discovered and fixed across releases. Each file describes the problem, root cause, and fix for a specific issue.

## Issue Index

### Custom Agent Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [Agent Incomplete Findings](agent-incomplete-findings.md) | v3.7.1 | Custom agent returning subset of findings due to conflicting prompt instructions and token limit |
| [Agent Scope Creep](custom-agent-scope-creep.md) | v3.2.0 | Custom agents flagging issues outside their defined scope |
| [Agent Data Lost on Re-Analysis](custom-agent-data-lost-reanalysis.md) | v3.1.0 | Custom agent risk data overwritten during noise re-analysis merge |

### Drift Detection Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [Drift with --bicep-dir](drift-bicep-dir-confusion.md) | v3.5.3 | LLM confused bicep source context with code diff for drift detection |
| [Drift Property Reversion](drift-property-reversion.md) | v3.5.2 | Drift detection missing property reversion (most common drift type) |
| [Drift False Positives (All Noise)](drift-false-positives-all-noise.md) | v1.4.1 | False drift alerts when all resources were filtered as noise |

### Noise Filtering Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [Resource List Regression](resource-list-regression.md) | v3.5.5 | Resource table showing summary row instead of individual resources after filtering |
| [False Drift from Hollow Modify](false-drift-hollow-modify.md) | v3.5.4 | Noise-filtered Modify blocks with no remaining properties still sent to LLM |
| [Filtered Resources Invisible](filtered-resources-invisible.md) | v3.5.1 | Pre-LLM filtered resources vanished from all output |
| [Risk Not Recalculated](risk-not-recalculated-after-filter.md) | v1.4.0 | Risk assessment not updated after noise filtering |

### Resource Pattern Matching Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [Shortened Type Matching](resource-pattern-shortened-types.md) | v2.5.1 | Resource patterns failed when LLM omitted `Microsoft.` prefix |
| [Nested ARM Type Matching](resource-pattern-nested-arm.md) | v2.4.0 | Resource patterns failed on child resources with interleaved names |

### Verdict and Threshold Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [Verdict Ignoring Thresholds](verdict-ignoring-thresholds.md) | v3.6.1 | Displayed verdict used LLM's raw assessment instead of threshold evaluation |
| [Default Threshold Too Strict](default-threshold-too-strict.md) | v3.6.2 | Default `low` threshold made nearly all deployments fail |

### Rendering Issues

| Issue | Fixed In | Description |
|-------|----------|-------------|
| [ADO PR Comment Spacing](ado-pr-comment-spacing.md) | v2.5.3, v2.1.0 | Collapsible sections in Azure DevOps PR comments lacked spacing |
| [Single Concern Display](single-concern-display.md) | v2.5.2 | Only first concern shown in Key Concerns column |
