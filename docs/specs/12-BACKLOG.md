# 12 - Feature Backlog

A prioritized list of potential features and improvements. Each entry captures the problem, goals, and enough context to implement independently.

---

## F-01: PR Intent Alignment — Non-Deterministic Risk Classification

**Status:** Open
**Area:** Prompt Engineering / CI Mode
**Related spec:** 04-PROMPT-ENGINEERING.md, 08-RISK-ASSESSMENT.md

### Problem

When the PR Intent Alignment bucket is evaluated, the LLM sometimes classifies the same input as Medium on one run and High on another. This causes identical deployments (e.g., the same Bicep changes deployed to pre-production and production in the same pipeline) to receive different verdicts — one SAFE, one UNSAFE.

The root cause is that the LLM is making a subjective judgment call near a classification boundary. In the observed case, both environments had a vague PR title/description ("Bicep Updates") with no meaningful detail. The LLM correctly identified the vagueness but inconsistently rated it Medium vs High.

### Secondary Design Issue

The PR Intent Alignment bucket is designed to detect *mismatches* between described intent and actual changes. However, the LLM is also penalizing for *poor PR description quality* — which is a different concern. A vague description doesn't mean the changes are misaligned; it means there's not enough context to evaluate alignment. These two cases should be handled differently.

### Goals

1. Make intent alignment risk classification deterministic and consistent across identical inputs.
2. Distinguish between two scenarios:
   - **Intent mismatch:** The PR description says one thing but the What-If output shows something different. This is a genuine risk concern.
   - **Insufficient description:** The PR description is too vague to evaluate alignment. This should default to a predictable, consistent rating (likely Medium), not be treated as a High risk.
3. Consider a pre-check on description quality before invoking the LLM — if the description is below a meaningful threshold (e.g., too short, just repeats the PR title, generic placeholder text), skip intent alignment entirely or treat it equivalently to no PR metadata being provided (which already omits the bucket).

### Possible Approaches

- **Prompt clarification (low effort):** Add explicit instruction to the LLM: "If the PR description is too vague to evaluate intent alignment, rate this as **medium**. Reserve **high** only for clear mismatches between stated intent and actual changes."
- **Description quality pre-check (more robust):** Before invoking intent alignment, evaluate the description against simple heuristics (length, similarity to title, known placeholder phrases). If it fails the quality check, omit the intent bucket or set it to a fixed medium with a note.
- **Threshold guidance in prompt:** Provide concrete examples of High vs Medium in the system prompt so the LLM has less room for subjective interpretation.

---

## F-02: Additional CI/CD Platform Support

**Status:** Open
**Area:** Platform Detection
**Related spec:** 07-PLATFORM-DETECTION.md

### Problem

Auto-detection is currently implemented for GitHub Actions and Azure DevOps. Users on GitLab CI, Jenkins, or CircleCI must use the manual `--ci` flag and supply all metadata themselves.

### Goals

- Auto-detect GitLab CI environment variables (`CI_MERGE_REQUEST_IID`, `CI_PROJECT_PATH`, etc.)
- Post PR comments to GitLab merge requests
- Investigate Jenkins and CircleCI detection feasibility

---

## F-03: Test Coverage

**Status:** ✅ Completed
**Area:** Testing
**Related spec:** 11-TESTING-STRATEGY.md

### Resolution

Implemented 223 tests (214 unit + 9 integration) with ~82% overall coverage. CI workflow runs on Python 3.9, 3.11, and 3.13. All modules covered including noise filtering recalculation flow, CI mode verdict logic, and end-to-end fixture-based integration tests.

---

## F-04: Configurable Noise Filtering Thresholds

**Status:** Open
**Area:** Noise Filtering
**Related spec:** 06-NOISE-FILTERING.md

### Problem

Confidence thresholds for noise filtering are currently hardcoded. Users with different deployment patterns may need to tune sensitivity.

### Goals

- Expose confidence threshold as a CLI flag (e.g., `--confidence-threshold 0.7`)
- Allow users to add custom noise patterns via config file or CLI flag

---

## F-05: Streaming Output

**Status:** Open
**Area:** UX / Provider System
**Related spec:** 03-PROVIDER-SYSTEM.md

### Problem

For large What-If outputs the tool is silent until the LLM finishes, which can feel slow. Users have no feedback that it's working.

### Goals

- Stream LLM output tokens to the terminal in interactive mode
- Show a progress indicator (spinner or live output) while waiting for LLM response

---

## F-06: HTML / SARIF Report Output

**Status:** Open
**Area:** Output Rendering
**Related spec:** 05-OUTPUT-RENDERING.md

### Problem

Current output formats are table, JSON, and markdown. Teams that want a standalone report or integration with security scanners have no option.

### Goals

- `--format html`: Self-contained HTML report with color-coded risk assessment
- `--format sarif`: SARIF output for ingestion by GitHub Advanced Security or Azure DevOps security scanners

---

## F-07: Refactor Operations Bucket to Bundled Agent

**Status:** Open
**Area:** Architecture / CI Mode
**Related spec:** 08-RISK-ASSESSMENT.md, 14-AGENT-DISPLAY.md

### Problem

The three built-in risk buckets (drift, intent, operations) are hardcoded in `buckets.py`. However, the operations bucket has no special context dependencies — it only evaluates the What-If output for risky Azure operations. This makes it functionally identical to a custom agent, yet it cannot benefit from agent features like `display: table` for per-resource findings, custom icons, or user customization of its prompt instructions.

Drift and intent have genuine reasons to remain built-in: drift requires the code diff, and intent requires PR metadata and is conditionally enabled. Operations has neither constraint.

### Goals

1. Convert the operations bucket from a hardcoded built-in to a bundled agent that ships with the package (e.g., in `bicep_whatif_advisor/data/agents/operations.md`).
2. Load the bundled agent automatically — users get the same out-of-the-box behavior without needing an `--agents-dir`.
3. Allow users to override the bundled operations agent by placing their own `operations.md` in their `--agents-dir`.
4. Migrate CLI flags:
   - `--skip-operations` → `--skip-agent operations` (or keep as an alias for backwards compatibility)
   - `--operations-threshold` → `--agent-threshold operations=<level>` (or keep as an alias)
5. Give the operations agent `display: table` so its findings render as a per-resource table in PR comments.

### Design Considerations

- **Bundled agent loading order:** Bundled agents should load first, then user agents from `--agents-dir`. If a user agent has the same ID as a bundled agent, the user version wins (override pattern).
- **Backwards compatibility:** Existing pipelines using `--skip-operations` and `--operations-threshold` should continue to work. Either keep the flags as aliases or provide a deprecation path.
- **Built-in asymmetry:** After this change, only drift and intent remain as true built-ins. This is acceptable since both have real context dependencies that justify special handling.
- **BUILTIN_BUCKET_IDS:** The `operations` ID would need to be removed from this frozenset so it no longer blocks agent registration with that ID.
