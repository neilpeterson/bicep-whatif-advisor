# Risk Assessment Guide

Complete guide to understanding how `bicep-whatif-advisor` evaluates deployment safety and makes decisions.

## Table of Contents

- [Overview](#overview)
- [The Decision Flow](#the-decision-flow)
- [Three Risk Buckets](#three-risk-buckets)
- [Risk Levels](#risk-levels)
- [How Risk Levels Are Determined](#how-risk-levels-are-determined)
- [Thresholds and Control](#thresholds-and-control)
- [Exit Codes](#exit-codes)
- [Complete Example](#complete-example)
- [FAQ](#faq)

## Overview

When running in CI mode, `bicep-whatif-advisor` acts as a deployment safety gate by evaluating your infrastructure changes across three independent risk categories. Each category gets its own risk level, and you set thresholds to control when deployments should be blocked.

## The Decision Flow

```
Azure What-If Output + Code Diff
           ↓
    AI Analysis (LLM)
           ↓
   Three Risk Assessments
           ↓
    ┌──────────────┬──────────────┬──────────────┐
    │              │              │              │
    │   Drift      │   Intent     │  Operations  │
    │   Bucket     │   Bucket     │   Bucket     │
    │              │              │              │
    │  Risk: Low   │  Risk: Med   │  Risk: High  │
    │              │              │              │
    └──────────────┴──────────────┴──────────────┘
           ↓
    Compare to Thresholds
           ↓
    Deployment Verdict
           ↓
    Exit Code (0 or 1)
```

## Three Risk Buckets

Each deployment is evaluated independently across three categories:

### 1. Infrastructure Drift 🔄

**What it detects:** Changes appearing in What-If output that aren't in your code diff.

**Why it matters:** Indicates someone manually changed infrastructure in Azure (via Portal, CLI, etc.) and those changes will be overwritten by your deployment.

**Examples:**
- **High Risk:** Storage account was manually set to "private" but template will revert to "public"
- **Medium Risk:** Multiple resources have configuration drift
- **Low Risk:** Only tags or display names differ

**Common causes:**
- Manual fixes in production
- Emergency changes not committed to code
- Configuration drift over time

**Risk Level Criteria:**

```
HIGH:
- Critical resources drifting (security, identity, stateful resources)
- Broad scope drift (many resources)

MEDIUM:
- Multiple resources drifting
- Configuration drift on important resources

LOW:
- Minor drift (tags, display names only)
- Single resource drift on non-critical resources
```

### 2. PR Intent Alignment 🎯

**What it detects:** Misalignment between what the PR says it does and what it actually does.

**Why it matters:** Catches unintended side effects, scope creep, or changes that weren't discussed in the PR.

**Examples:**
- **High Risk:** PR says "add monitoring" but it's also deleting a database
- **Medium Risk:** PR says "update tags" but it's modifying network rules
- **Low Risk:** PR says "add App Service" and it adds related resources not mentioned

**Common causes:**
- Unintended side effects
- Forgotten about previous changes
- Template dependencies creating extra changes

**Note:** This bucket is only evaluated if PR title/description are available (auto-detected or manual).

**Risk Level Criteria:**

```
HIGH:
- Destructive changes (Delete) not mentioned in PR
- Security/authentication changes not mentioned
- Critical resources affected but not discussed

MEDIUM:
- Resource modifications not aligned with PR intent
- Unexpected resource types being changed
- Scope significantly different from description

LOW:
- New resources not mentioned but aligned with intent
- Minor scope differences
```

### 3. Risky Operations ⚠️

**What it detects:** Inherently dangerous Azure operations regardless of context.

**Why it matters:** Some operations are risky by nature (deletions, security changes) and deserve extra scrutiny.

**Examples:**
- **High Risk:** Deleting a database, removing RBAC roles, enabling public access on storage
- **Medium Risk:** Changing firewall rules, modifying encryption settings, new public endpoints
- **Low Risk:** Creating new resources, updating tags, adding monitoring

**Common causes:**
- Intentional but risky changes
- Refactoring infrastructure
- Security configuration updates

**Risk Level Criteria:**

```
HIGH:
- Deletion of stateful resources (databases, storage, key vaults)
- Deletion of identity/RBAC resources
- Network security changes opening broad access
- Encryption modifications
- SKU downgrades (data loss risk)

MEDIUM:
- Modifications changing resource behavior (policies, scaling)
- New public endpoints
- Firewall rule changes

LOW:
- Adding new resources
- Tag updates
- Diagnostic/monitoring resources
- Description modifications
```

## Risk Levels

Each bucket receives one of three risk levels:

| Level | Meaning | Symbol |
|-------|---------|--------|
| **Low** | Safe, routine change | 🟢 Green |
| **Medium** | Needs attention but not critical | 🟡 Yellow |
| **High** | Dangerous, requires review | 🔴 Red |

The AI evaluates each bucket independently and assigns a risk level based on the specific concerns found.

## How Risk Levels Are Determined

### The Mechanism

**Risk levels are determined by an AI (LLM) using structured guidelines.**

The tool sends the Azure What-If output, code diff, and PR metadata to a Large Language Model (Claude, Azure OpenAI, or Ollama) along with specific instructions for evaluating risk. The LLM analyzes the data and applies the guidelines to determine risk levels.

### The Process

```
Input:
  ├─ Azure What-If Output (infrastructure changes)
  ├─ Git Diff (code changes)
  └─ PR Metadata (title, description)
       ↓
Sent to LLM with Guidelines
       ↓
LLM Analyzes and Applies Rules
       ↓
Output:
  ├─ Drift: [low|medium|high]
  ├─ Intent: [low|medium|high]
  └─ Operations: [low|medium|high]
```

### How the LLM Makes Decisions

The LLM (Claude Sonnet 4.5 by default) uses its reasoning capabilities to:

1. **Parse the What-If output** - Understand what resources are changing and how
2. **Parse the code diff** - See what was actually modified in source code
3. **Compare the two** - Identify discrepancies (drift detection)
4. **Apply guidelines** - Use the criteria to classify risk level
5. **Consider context** - Factor in resource types, change types, and relationships
6. **Generate reasoning** - Explain why it chose each risk level

### Example LLM Reasoning Process

**Input:**
- What-If shows: Storage account `publicNetworkAccess: Disabled → Enabled`
- Code diff: No changes to storage account properties
- PR title: "Add Application Insights logging"

**LLM Reasoning (internal):**
1. Storage account is changing but not in diff → **Drift detected**
2. Property is `publicNetworkAccess` → **Security property**
3. Changing Disabled → Enabled → **Security downgrade**
4. Not mentioned in PR → **Intent misalignment**
5. Enabling public access → **Risky operation**

**LLM Output:**
```json
{
  "risk_assessment": {
    "drift": {
      "risk_level": "high",
      "concerns": [
        "Storage account publicNetworkAccess changing without code changes"
      ],
      "reasoning": "Critical security property drifting - was manually secured but template will revert"
    },
    "intent": {
      "risk_level": "high",
      "concerns": [
        "Storage security change not mentioned in PR about logging"
      ],
      "reasoning": "PR is about adding logging but a security regression is occurring"
    },
    "operations": {
      "risk_level": "high",
      "concerns": [
        "Enabling public network access on storage account"
      ],
      "reasoning": "Opening storage to public network increases attack surface"
    }
  }
}
```

### Why Use an LLM?

**Traditional Rule-Based Approach (What We DON'T Do):**

```python
# Hypothetical rule-based code
if action == "Delete" and resource_type == "Microsoft.Sql/servers":
    risk = "high"
elif action == "Modify" and property == "publicNetworkAccess":
    if old_value == "Disabled" and new_value == "Enabled":
        risk = "high"
# ... hundreds more rules needed ...
```

**Problems:**
- ❌ Can't handle nuance
- ❌ Requires rules for every scenario
- ❌ Can't understand context
- ❌ Brittle and hard to maintain

**LLM Approach (What We DO):**

**Benefits:**
- ✅ Understands context and nuance
- ✅ Applies reasoning to new scenarios
- ✅ Handles complex relationships
- ✅ Explains its decisions
- ✅ Adapts to different resource types

**Real-World Example of LLM Advantage:**

**Scenario:** PR adds an App Service that needs storage, so it also creates a storage account.

**Rule-based system might flag:**
- ❌ "Storage account not mentioned in PR title" → High risk

**LLM understands:**
- ✅ "App Service needs storage backend" → Low risk
- ✅ "Related resources for the stated intent" → Low risk
- ✅ "No drift, just architectural requirements" → Low risk

### Consistency & Reliability

**Question:** Is the LLM deterministic?

**Answer:** We use `temperature=0` to maximize consistency, but LLMs can still have slight variations.

**In practice:**
- Same input typically produces same risk levels
- Reasoning text may vary slightly in wording
- Risk level (low/medium/high) is very stable
- Borderline cases might occasionally flip between medium/high

**Mitigation:**
- Clear, specific guidelines reduce ambiguity
- Temperature=0 maximizes determinism
- Three-bucket system provides redundancy
- Your thresholds control the final decision

## Thresholds and Control

You set independent thresholds for each bucket to control when deployments are blocked:

```bash
bicep-whatif-advisor \
  --drift-threshold high \       # Block only on high drift
  --intent-threshold high \      # Block only on high misalignment
  --operations-threshold high    # Block only on high-risk operations
```

### How Thresholds Work

**Deployment is BLOCKED if ANY bucket exceeds its threshold:**

```
Drift: Medium     (threshold: high)   → ✅ Pass (below threshold)
Intent: Low       (threshold: high)   → ✅ Pass (below threshold)
Operations: High  (threshold: high)   → ❌ FAIL (meets threshold)

Result: Deployment BLOCKED (exit code 1)
```

### Threshold Strategies

**Conservative (Recommended for Production):**
```bash
--drift-threshold high \
--intent-threshold high \
--operations-threshold high
```
- Blocks only critical issues
- Allows routine changes
- Good for production

**Moderate (Staging/Pre-Production):**
```bash
--drift-threshold medium \
--intent-threshold high \
--operations-threshold medium
```
- More sensitive to drift
- Catches moderate operational risks
- Good for staging

**Strict (Development/Audit):**
```bash
--drift-threshold low \
--intent-threshold low \
--operations-threshold low
```
- Blocks on any risk
- Maximum safety
- Good for learning or high-security environments

## Exit Codes

The tool uses standard exit codes to communicate results:

| Code | Meaning | When it happens | What to do |
|------|---------|-----------------|------------|
| **0** | Success / Safe | All risk buckets below thresholds | Deploy safely ✅ |
| **1** | Unsafe / Blocked | One or more buckets exceed thresholds | Review PR comment, fix issues ⚠️ |
| **2** | Error / Invalid | Bad input or tool error | Check logs, fix command ❌ |

### How CI/CD Pipelines Use Exit Codes

**GitHub Actions:**

```yaml
- run: az deployment group what-if ... | bicep-whatif-advisor
  # Exit code 1 automatically fails the workflow
  # Blocks PR from being merged if branch protection enabled
```

- Exit 0 → Workflow succeeds → PR can merge
- Exit 1 → Workflow fails → PR blocked
- Exit 2 → Workflow fails → Check logs

**Azure DevOps:**

```yaml
- script: az deployment group what-if ... | bicep-whatif-advisor
  # Exit code 1 automatically fails the pipeline
  # Sets build status to failed
```

- Exit 0 → Build succeeds → Can proceed
- Exit 1 → Build fails → Deployment blocked
- Exit 2 → Build fails → Check logs

## Complete Example

Let's walk through a complete scenario:

### The Setup

You have a PR titled "Add Application Insights monitoring" with this workflow:

```yaml
- env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor \
      --drift-threshold high \
      --intent-threshold high \
      --operations-threshold high
```

### What Happens

1. **Azure What-If runs:** Shows changes to deploy
2. **AI analyzes changes:** Evaluates three risk buckets
3. **Drift check:** Compares What-If to git diff
   - Finds: Storage account `publicNetworkAccess` changing Disabled → Enabled
   - But: No code changes to this property
   - **Result: High drift risk** ⚠️
4. **Intent check:** Compares changes to PR title
   - PR says: "Add Application Insights"
   - What-If shows: Adding App Insights + Changing storage security
   - **Result: High intent misalignment** ⚠️
5. **Operations check:** Evaluates operation risk
   - Enabling public network access is dangerous
   - **Result: High operations risk** ⚠️

### The Verdict

```
Risk Assessment:
  Drift: High       (threshold: high)   → ❌ FAIL
  Intent: High      (threshold: high)   → ❌ FAIL
  Operations: High  (threshold: high)   → ❌ FAIL

Verdict: UNSAFE
Exit Code: 1
```

### PR Comment Posted

```markdown
## What-If Deployment Review

### Risk Assessment

| Risk Bucket | Risk Level | Key Concerns |
|-------------|------------|--------------|
| Infrastructure Drift | High | Storage account publicNetworkAccess changed manually |
| PR Intent Alignment | High | PR is about monitoring, not security changes |
| Risky Operations | High | Enabling public network access on storage |

### Verdict: ❌ UNSAFE

**Reasoning:** Storage account was manually secured (publicNetworkAccess: Disabled)
outside of this PR, but the Bicep template will revert it to an insecure state
(Enabled). This security regression is unrelated to the PR's stated monitoring
purpose and appears to be unintentional.
```

### What You Should Do

1. **Review the drift:** Check why storage account was manually changed
2. **Update Bicep code:** Add `publicNetworkAccess: 'Disabled'` to template
3. **Update PR:** Explain the security fix
4. **Re-run workflow:** Will now pass with code matching infrastructure

## FAQ

### Q: What if I disagree with the risk assessment?

**A:** You can:
1. Adjust thresholds to be more lenient
2. Review the PR comment reasoning and address the concerns
3. Use `--ci` flag locally to test before pushing
4. Manually override by adjusting your workflow (not recommended)

### Q: Can I see what caused each risk level?

**A:** Yes! The PR comment includes:
- Key concerns for each bucket
- Specific resources flagged
- Reasoning for the verdict
- Recommendations

### Q: Does it block safe changes?

**A:** With default thresholds (all "high"), it only blocks critical issues:
- Security regressions
- Unintended deletions
- Major drift
- Complete misalignment with PR intent

Routine changes like adding resources, updating tags, or modifying configurations typically get low/medium risk and pass.

### Q: What if there's no PR description?

**A:** The Intent bucket is skipped. Risk assessment continues with just:
- Drift detection
- Operations risk

This is fine - you can still catch drift and risky operations.

### Q: Can I test locally?

**A:** Yes! Use `--ci` flag manually:

```bash
az deployment group what-if ... | bicep-whatif-advisor \
  --ci \
  --diff-ref origin/main \
  --pr-title "My test PR"
```

This lets you see the risk assessment before pushing.

### Q: Can I customize the risk guidelines?

**A:** You cannot customize the guidelines directly, but you can:

1. **Adjust thresholds** to change sensitivity
2. **Choose different models** with different characteristics
3. **Provide context** via PR descriptions

### Q: What if the LLM makes a mistake?

**A:** If you disagree with a risk level:
1. Check the PR comment for reasoning
2. Review if the concern is valid
3. Check if thresholds are appropriate
4. Update PR description to provide context
5. Fix the actual issue if it's a real problem

The LLM reasoning is transparent - you can always see why it made each decision.

## Summary

**Simple mental model:**

1. **Three checks** (drift, intent, operations)
2. **Each gets a risk level** (low, medium, high)
3. **You set thresholds** for each check
4. **Deployment blocked** if ANY check exceeds its threshold
5. **Exit code 0** = safe, **1** = blocked, **2** = error
6. **PR comment** explains everything

**Default behavior (recommended):**
- Thresholds all set to "high"
- Only critical issues block deployments
- Routine changes pass through
- You get detailed PR comments either way

**Key insight:** The three-bucket system catches different types of problems:
- **Drift** → "Does code match reality?"
- **Intent** → "Does this match what the PR claims?"
- **Operations** → "Is this operation inherently risky?"

All three checks together provide comprehensive deployment safety, powered by AI reasoning that understands context and nuance! 🛡️🤖

## Additional Resources

- [Getting Started Guide](./GETTING_STARTED.md) - Installation and basic usage
- [CI/CD Integration Guide](./CICD_INTEGRATION.md) - Set up deployment gates
- [CLI Reference](./CLI_REFERENCE.md) - Complete command reference
