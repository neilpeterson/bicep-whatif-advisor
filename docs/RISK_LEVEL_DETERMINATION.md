# How Risk Levels Are Determined

This document explains the actual mechanism used to determine risk levels for each category in `whatif-explain`.

## The Short Answer

**Risk levels are determined by an AI (LLM) using structured guidelines.**

The tool sends the Azure What-If output, code diff, and PR metadata to a Large Language Model (Claude, Azure OpenAI, or Ollama) along with specific instructions for evaluating risk. The LLM analyzes the data and applies the guidelines to determine risk levels.

## The Process

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

## The Guidelines (From prompt.py)

These are the exact instructions sent to the LLM for determining risk levels:

### Infrastructure Drift Bucket

**Objective:** Compare What-If output to code diff. Find resources changing that aren't in the diff.

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

**Examples of LLM Application:**

| Scenario | Risk Level | Why |
|----------|------------|-----|
| Storage account `publicNetworkAccess` changes Disabled → Enabled, but not in code | **High** | Security setting drifting |
| 5 resources have tag differences | **Medium** | Multiple resources, but only tags |
| One App Service has a `displayName` difference | **Low** | Single non-critical property |
| Key Vault access policy changed manually | **High** | Security/identity resource |
| 10 resources across multiple types drifting | **High** | Broad scope |

### Risky Operations Bucket

**Objective:** Evaluate inherent danger of Azure operations, regardless of whether they're intentional.

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

**Examples of LLM Application:**

| Scenario | Risk Level | Why |
|----------|------------|-----|
| Deleting a SQL Database | **High** | Stateful resource deletion |
| Removing RBAC role assignment | **High** | Identity/security deletion |
| Changing storage from private to public | **High** | Broad network access |
| Adding firewall rule to allow specific IP | **Medium** | Firewall change (limited scope) |
| Creating new App Service | **Low** | Adding resource |
| Updating resource tags | **Low** | Non-functional change |
| Modifying autoscale settings | **Medium** | Behavior change |

### PR Intent Alignment Bucket

**Objective:** Compare What-If changes to PR title/description. Flag misalignment or unmentioned changes.

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
- Minor scope differences (e.g., PR says "add API" and also adds related resources)
```

**Examples of LLM Application:**

| PR Says | What-If Shows | Risk Level | Why |
|---------|---------------|------------|-----|
| "Add monitoring" | Creates App Insights + Deletes storage | **High** | Deletion not mentioned |
| "Update API policies" | Modifies API + Changes network rules | **High** | Security change not mentioned |
| "Add App Service" | Creates App Service + App Plan + Storage | **Low** | Related resources, aligned |
| "Fix typo in tags" | Deletes Key Vault | **High** | Destructive, completely unrelated |
| "Update configuration" | Modifies 15 different resources | **Medium** | Much broader scope than stated |
| "Add logging" | Creates App Insights only | **Low** | Exactly as described |

## How the LLM Makes Decisions

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

## Why Use an LLM?

### Traditional Rule-Based Approach (What We DON'T Do)

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

### LLM Approach (What We DO)

```python
# Simplified actual code
response = llm.complete(
    system_prompt=guidelines,
    user_prompt=f"{whatif_output}\n{code_diff}\n{pr_metadata}"
)
```

**Benefits:**
- ✅ Understands context and nuance
- ✅ Applies reasoning to new scenarios
- ✅ Handles complex relationships
- ✅ Explains its decisions
- ✅ Adapts to different resource types

### Real-World Example of LLM Advantage

**Scenario:** PR adds an App Service that needs storage, so it also creates a storage account.

**Rule-based system might flag:**
- ❌ "Storage account not mentioned in PR title" → High risk

**LLM understands:**
- ✅ "App Service needs storage backend" → Low risk
- ✅ "Related resources for the stated intent" → Low risk
- ✅ "No drift, just architectural requirements" → Low risk

## Model Selection

Different models have different strengths:

| Model | Strength | Best For |
|-------|----------|----------|
| **Claude Sonnet 4.5** | Reasoning & context | Production (default) |
| **Claude Haiku** | Speed | High-volume pipelines |
| **Azure OpenAI GPT-4** | Enterprise integration | Azure-only environments |
| **Ollama (local)** | Privacy | Sensitive environments |

All models receive the same guidelines and produce comparable results.

## Consistency & Reliability

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

## Customization

You **cannot** customize the risk level guidelines directly, but you **can**:

1. **Adjust thresholds** to change sensitivity
   ```bash
   # More strict drift detection
   --drift-threshold medium  # blocks medium and high
   ```

2. **Choose models** with different characteristics
   ```bash
   --provider azure-openai --model gpt-4
   ```

3. **Provide context** via PR descriptions
   ```bash
   --pr-description "This change intentionally opens storage for public CDN use"
   ```

## Debugging Risk Decisions

If you disagree with a risk level, check the PR comment for:

1. **Concerns list** - What specific issues were found
2. **Reasoning** - Why the LLM chose that level
3. **Resource details** - Which resources triggered the risk

Then:
- Review if the concern is valid
- Check if thresholds are appropriate
- Update PR description to provide context
- Fix the actual issue if it's a real problem

## Summary

**How it works:**
1. Guidelines sent to LLM (from `prompt.py`)
2. LLM analyzes What-If + Diff + PR metadata
3. LLM applies guidelines using reasoning
4. Risk levels determined: low, medium, or high
5. Explanation provided in response

**Key insight:** It's not hardcoded rules - it's AI reasoning applied to structured guidelines. This provides flexibility, context-awareness, and adaptability while maintaining consistency through clear criteria.

The LLM acts as an expert reviewer applying the guidelines to each unique deployment scenario! 🤖
