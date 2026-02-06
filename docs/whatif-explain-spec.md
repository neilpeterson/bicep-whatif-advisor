# whatif-explain — Azure What-If Output Summarizer

## Overview

`whatif-explain` is a Python CLI tool that accepts Azure Bicep/ARM What-If output via stdin, sends it to an LLM for analysis, and renders a human-friendly summary table in the terminal.

```bash
az deployment group what-if -g my-rg -f main.bicep | whatif-explain
```

---

## Goals

- Provide instant, readable summaries of Azure What-If output
- Reduce cognitive load when reviewing infrastructure changes
- Support multiple LLM backends for flexibility
- Produce output suitable for terminals, pull requests, and CI pipelines

---

## Architecture

```
┌─────────────────────────────────┐
│  az deployment group what-if    │
│  (stdout: What-If text output)  │
└──────────────┬──────────────────┘
               │ pipe (stdin)
               ▼
┌─────────────────────────────────┐
│        whatif-explain            │
│                                 │
│  1. Read stdin                  │
│  2. Parse/validate input        │
│  3. Build prompt                │
│  4. Call LLM provider           │
│  5. Parse structured response   │
│  6. Render output               │
└─────────────────────────────────┘
```

---

## Project Structure

```
whatif-explain/
├── whatif_explain/
│   ├── __init__.py
│   ├── cli.py              # Entry point, argument parsing
│   ├── input.py            # Stdin reading and validation
│   ├── prompt.py           # Prompt template construction
│   ├── providers/
│   │   ├── __init__.py     # Provider registry and base class
│   │   ├── anthropic.py    # Claude API provider
│   │   ├── azure_openai.py # Azure OpenAI provider
│   │   └── ollama.py       # Local Ollama provider
│   └── render.py           # Output formatting (table, json, markdown)
├── tests/
│   ├── fixtures/           # Sample What-If outputs for testing
│   │   ├── create_only.txt
│   │   ├── mixed_changes.txt
│   │   ├── deletes.txt
│   │   └── no_changes.txt
│   ├── test_input.py
│   ├── test_prompt.py
│   ├── test_providers.py
│   └── test_render.py
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## CLI Interface

### Installation

```bash
pip install whatif-explain
```

### Usage

```bash
az deployment group what-if ... | whatif-explain [OPTIONS]
```

### Arguments & Flags

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--provider` | `-p` | `anthropic` | LLM provider: `anthropic`, `azure-openai`, `ollama` |
| `--model` | `-m` | Provider default | Override the model name (e.g., `claude-sonnet-4-20250514`) |
| `--format` | `-f` | `table` | Output format: `table`, `json`, `markdown` |
| `--verbose` | `-v` | `false` | Include property-level change details for modified resources |
| `--no-color` | | `false` | Disable colored output (also auto-detected if not a TTY) |
| `--version` | | | Print version and exit |
| `--help` | `-h` | | Print help and exit |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | If using `anthropic` provider | Anthropic API key |
| `AZURE_OPENAI_ENDPOINT` | If using `azure-openai` provider | Azure OpenAI endpoint URL |
| `AZURE_OPENAI_API_KEY` | If using `azure-openai` provider | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT` | If using `azure-openai` provider | Deployment name |
| `OLLAMA_HOST` | No | Ollama host (default: `http://localhost:11434`) |
| `WHATIF_PROVIDER` | No | Default provider (overridden by `--provider`) |
| `WHATIF_MODEL` | No | Default model (overridden by `--model`) |

---

## Modules

### `cli.py` — Entry Point

- Parse arguments using `click`
- Read stdin via `input.py`
- Validate that stdin is not empty; print helpful error if run without piped input
- Select provider based on `--provider` flag or `WHATIF_PROVIDER` env var
- Call provider, receive structured response
- Pass structured response to renderer
- Exit code: `0` on success, `1` on error, `2` on invalid input

### `input.py` — Input Handling

- Read all of stdin as a string
- Detect if stdin is a TTY (no piped input) and print a usage hint
- Basic validation: check that the input looks like What-If output (contains known markers like `Resource changes:` or symbols like `+ Create`, `~ Modify`, `- Delete`)
- If input is empty or invalid, raise a clear error
- Truncation: if input exceeds a configurable max token estimate (default: 100,000 characters), truncate with a warning to stderr

### `prompt.py` — Prompt Construction

Build the LLM prompt from the What-If input. The prompt should request a structured JSON response.

#### System Prompt

```
You are an Azure infrastructure expert. You analyze Azure Resource Manager
What-If deployment output and produce concise, accurate summaries.

You must respond with ONLY valid JSON matching this schema, no other text:

{
  "resources": [
    {
      "resource_name": "string — the short resource name",
      "resource_type": "string — the Azure resource type, abbreviated for readability",
      "action": "string — one of: Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — 1-2 sentence plain English explanation of what this resource is and what the change does"
    }
  ],
  "overall_summary": "string — a brief overall summary of the deployment, including counts by action type and the overall intent"
}
```

#### User Prompt

```
Analyze the following Azure What-If output:

<whatif_output>
{stdin_content}
</whatif_output>
```

#### Verbose Mode Additions

When `--verbose` is set, add to the system prompt:

```
For resources with action "Modify", also include a "changes" field:
an array of strings describing each property-level change.
```

### `providers/` — LLM Providers

#### Base Provider Interface

```python
class Provider(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the LLM and return the raw response text."""
        pass
```

#### `anthropic.py`

- Uses the `anthropic` Python SDK
- Default model: `claude-sonnet-4-20250514`
- Requires `ANTHROPIC_API_KEY`
- Max tokens: 4096
- Temperature: 0

#### `azure_openai.py`

- Uses the `openai` Python SDK with Azure configuration
- Requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
- Temperature: 0

#### `ollama.py`

- Uses HTTP requests to Ollama's local API (`/api/generate`)
- Default model: `llama3.1`
- Default host: `http://localhost:11434`
- Temperature: 0

#### Error Handling (all providers)

- Missing API key → clear error message telling the user which env var to set
- Network error → retry once, then fail with message
- Rate limit → print message suggesting retry after delay
- Malformed response → attempt to extract JSON from response, fail with raw output if impossible

### `render.py` — Output Rendering

#### Table Format (default)

Use the `rich` library to render a colored table to the terminal.

- Columns: `#`, `Resource`, `Type`, `Action`, `Summary`
- Action column color-coded:
  - ✅ Create → green
  - ✏️ Modify → yellow
  - ❌ Delete → red
  - 🔄 Deploy → blue
  - ➖ NoChange → dim/grey
  - ⬜ Ignore → dim/grey
- Below the table, print the `overall_summary`
- If `--verbose` and changes are present, print a collapsible detail section per modified resource
- Respect `--no-color` flag and TTY detection

#### JSON Format

Print the raw JSON response from the LLM, pretty-printed with 2-space indent. This enables downstream tooling:

```bash
az deployment group what-if ... | whatif-explain --format json | jq '.resources[] | select(.action == "Delete")'
```

#### Markdown Format

Render a markdown table plus summary, suitable for pasting into PRs or docs:

```markdown
| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | ... | ... | ✅ Create | ... |

**Summary:** 3 creates, 0 modifies, 0 deletes. ...
```

---

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI argument parsing |
| `rich` | Terminal table rendering and color |
| `anthropic` | Anthropic Claude API SDK |
| `openai` | Azure OpenAI API SDK |
| `requests` | HTTP calls for Ollama provider |

All provider-specific dependencies should be optional extras:

```bash
pip install whatif-explain[anthropic]    # installs anthropic SDK
pip install whatif-explain[azure]        # installs openai SDK
pip install whatif-explain[ollama]       # installs requests (likely already present)
pip install whatif-explain[all]          # installs everything
```

Core dependencies (always installed): `click`, `rich`

---

## Configuration File (Optional, v1.1)

Support an optional `.whatif-explain.yaml` in the user's home directory or current directory for defaults:

```yaml
provider: anthropic
model: claude-sonnet-4-20250514
format: table
verbose: false
```

CLI flags always override config file values. Not required for v1.0.

---

## Example Outputs

### Table (default)

```
╭───┬──────────────────────────┬────────────────────┬───────────┬───────────────────────────────────────────────╮
│ # │ Resource                 │ Type               │ Action    │ Summary                                       │
├───┼──────────────────────────┼────────────────────┼───────────┼───────────────────────────────────────────────┤
│ 1 │ applicationinsights      │ APIM Diagnostic    │ ✅ Create │ Configures App Insights logging with custom   │
│   │                          │                    │           │ JWT headers and 100% sampling.                │
│ 2 │ policy                   │ APIM Global Policy │ ✅ Create │ Global inbound policy validating Front Door   │
│   │                          │                    │           │ header and including JWT parsing fragment.     │
│ 3 │ sce-jwt-parsing-and-     │ APIM Policy        │ ✅ Create │ Reusable fragment that parses Bearer tokens   │
│   │ logging                  │ Fragment           │           │ and extracts claims into logging headers.      │
╰───┴──────────────────────────┴────────────────────┴───────────┴───────────────────────────────────────────────╯
Summary: 3 creates, 0 modifies, 0 deletes. Sets up a JWT claim extraction and
Application Insights logging pipeline, secured behind Azure Front Door.
```

### JSON

```json
{
  "resources": [
    {
      "resource_name": "applicationinsights",
      "resource_type": "APIM Diagnostic",
      "action": "Create",
      "summary": "Configures App Insights logging with custom JWT headers and 100% sampling."
    }
  ],
  "overall_summary": "3 creates, 0 modifies, 0 deletes. ..."
}
```

### Markdown

```markdown
| # | Resource | Type | Action | Summary |
|---|----------|------|--------|---------|
| 1 | applicationinsights | APIM Diagnostic | ✅ Create | Configures App Insights logging... |

**Summary:** 3 creates, 0 modifies, 0 deletes. ...
```

---

## Error Scenarios

| Scenario | Behavior |
|----------|----------|
| No piped input (TTY detected) | Print usage hint to stderr, exit 2 |
| Empty stdin | Print "No What-If output received" to stderr, exit 2 |
| Input doesn't look like What-If output | Print warning to stderr, attempt anyway |
| Missing API key | Print "Set ANTHROPIC_API_KEY environment variable" to stderr, exit 1 |
| LLM returns non-JSON | Attempt to extract JSON from response; if impossible, print raw response to stderr, exit 1 |
| LLM returns JSON missing required fields | Fill in defaults ("Unknown") for missing fields, print warning to stderr |
| Network timeout | Retry once, then print error to stderr, exit 1 |

---

## Testing Strategy

### Unit Tests

- `test_input.py` — validate input detection (valid What-If, empty, garbage, TTY)
- `test_prompt.py` — verify prompt construction with and without `--verbose`
- `test_render.py` — verify table, JSON, and markdown output from known structured input
- `test_providers.py` — mock API calls, verify request construction and error handling

### Integration Tests

- Use fixture files in `tests/fixtures/` containing real What-If output samples
- Pipe fixtures through the full CLI with a mocked provider to verify end-to-end flow

### Test Fixtures Needed

- `create_only.txt` — only `+ Create` resources
- `mixed_changes.txt` — creates, modifies, and deletes
- `deletes.txt` — only deletes (test risk highlighting in v2)
- `no_changes.txt` — all resources are NoChange
- `large_output.txt` — 50+ resources to test truncation

---

## CI/CD Deployment Gate

### Overview

In CI mode, `whatif-explain` acts as an automated deployment gate. It sends both the **What-If output** and the **source code diff** to the LLM, which assesses whether the deployment is safe to proceed. The tool then sets a pass/fail exit code and posts a summary to the PR.

```
┌──────────────────┐     ┌──────────────────┐
│  Git Diff         │     │  What-If Output   │
│  (code changes)   │     │  (infra changes)  │
└────────┬─────────┘     └────────┬──────────┘
         │                        │
         └──────────┬─────────────┘
                    ▼
         ┌─────────────────────┐
         │   whatif-explain     │
         │   --ci               │
         │                     │
         │  LLM evaluates:     │
         │  • Do infra changes │
         │    match code intent?│
         │  • Any risky deletes?│
         │  • Any drift?       │
         │  • Safety verdict   │
         └──────────┬──────────┘
                    │
              ┌─────┴──────┐
              ▼            ▼
         Exit 0        Exit 1
         (safe)        (unsafe)
              │            │
              ▼            ▼
         Deploy        Block + PR Comment
```

### Additional CLI Flags for CI Mode

| Flag | Short | Default | Description |
|------|-------|---------|-------------|
| `--ci` | | `false` | Enable CI mode: structured verdict, exit codes, and optional PR comment |
| `--diff` | `-d` | Auto-detected | Path to a diff file, or `-` to read a second stdin. If not provided, attempts `git diff HEAD~1` |
| `--diff-ref` | | `HEAD~1` | Git ref to diff against (e.g., `main`, `origin/main`, a commit SHA) |
| `--risk-threshold` | | `high` | Fail pipeline at this risk level or above: `low`, `medium`, `high`, `critical` |
| `--post-comment` | | `false` | Post the summary as a PR comment (requires `--pr-url` or auto-detection) |
| `--pr-url` | | Auto-detected | PR URL for posting comments. Auto-detected from `GITHUB_*` or `BUILD_*` env vars |
| `--bicep-dir` | | `.` | Path to Bicep source files (included as context for the LLM) |

### CI Prompt Design

In CI mode, the prompt is extended to include the code diff and request a safety verdict.

#### System Prompt (CI Extension)

```
You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes

Evaluate the deployment for safety and correctness.

Respond with ONLY valid JSON matching this schema:

{
  "resources": [
    {
      "resource_name": "string",
      "resource_type": "string",
      "action": "string — Create, Modify, Delete, Deploy, NoChange, Ignore",
      "summary": "string — what this change does",
      "risk_level": "string — none, low, medium, high, critical",
      "risk_reason": "string or null — why this is risky, if applicable"
    }
  ],
  "overall_summary": "string",
  "verdict": {
    "safe": true/false,
    "risk_level": "string — none, low, medium, high, critical (highest individual risk)",
    "reasoning": "string — 2-3 sentence explanation of the verdict",
    "concerns": ["string — list of specific concerns, if any"],
    "recommendations": ["string — list of recommendations, if any"]
  }
}
```

#### Risk Classification Guidelines (included in prompt)

```
Apply these risk classifications:

- critical: Deletion of stateful resources (databases, storage accounts, key vaults),
  deletion of identity/RBAC resources, changes to network security rules that open
  broad access, modifications to encryption settings
- high: Deletion of any production resource, modifications to authentication/authorization
  config, changes to firewall rules, SKU downgrades on critical services
- medium: Modifications to existing resources that change behavior (policy changes,
  scaling config, diagnostic settings), new public endpoints
- low: Adding new resources, adding tags, adding diagnostic/monitoring resources,
  modifying descriptions or display names
- none: NoChange, Ignore, cosmetic-only changes
```

#### User Prompt (CI Mode)

```
Review this Azure deployment for safety.

<whatif_output>
{whatif_content}
</whatif_output>

<code_diff>
{git_diff_content}
</code_diff>

<bicep_source>
{bicep_file_contents — optional, included if --bicep-dir provided}
</bicep_source>
```

### Exit Codes (CI Mode)

| Code | Meaning |
|------|---------|
| `0` | Safe — highest risk level is below `--risk-threshold` |
| `1` | Unsafe — risk level meets or exceeds `--risk-threshold` |
| `2` | Error — invalid input, API failure, or malformed response |

### PR Comment Format

When `--post-comment` is set, the tool posts a markdown comment to the PR:

```markdown
## 🔍 What-If Deployment Review

| # | Resource | Type | Action | Risk | Summary |
|---|----------|------|--------|------|---------|
| 1 | applicationinsights | APIM Diagnostic | ✅ Create | 🟢 Low | Configures App Insights logging... |
| 2 | my-database | SQL Database | ❌ Delete | 🔴 Critical | Deletes production database... |

### Verdict: ❌ UNSAFE

**Risk Level:** Critical
**Reasoning:** The deployment deletes a SQL database which is a stateful
resource that cannot be easily recovered.

**Concerns:**
- Deletion of `my-database` will result in permanent data loss
- No backup or soft-delete configuration detected

**Recommendations:**
- Verify this deletion is intentional
- Ensure a recent backup exists before proceeding
- Consider enabling soft-delete on the database first

---
<details>
<summary>📄 Code Changes</summary>

- Removed `database.bicep` module reference from `main.bicep`
- Modified `parameters.json` to remove database connection string

</details>

*Generated by [whatif-explain](https://github.com/yourorg/whatif-explain)*
```

### PR Comment Posting

#### GitHub Actions

Uses the GitHub API via `GITHUB_TOKEN` (automatically available in Actions):

```python
# Auto-detect from environment
github_token = os.environ.get("GITHUB_TOKEN")
repo = os.environ.get("GITHUB_REPOSITORY")       # e.g., "myorg/myrepo"
pr_number = os.environ.get("GITHUB_PR_NUMBER")    # parsed from GITHUB_REF

# POST /repos/{owner}/{repo}/issues/{pr_number}/comments
```

#### Azure DevOps

Uses the Azure DevOps REST API via `SYSTEM_ACCESSTOKEN`:

```python
# Auto-detect from environment
token = os.environ.get("SYSTEM_ACCESSTOKEN")
collection_uri = os.environ.get("SYSTEM_COLLECTIONURI")
project = os.environ.get("SYSTEM_TEAMPROJECT")
pr_id = os.environ.get("SYSTEM_PULLREQUEST_PULLREQUESTID")
repo_id = os.environ.get("BUILD_REPOSITORY_ID")

# POST {collection_uri}{project}/_apis/git/repositories/{repo_id}/pullRequests/{pr_id}/threads
```

### GitHub Actions Example

```yaml
name: Infrastructure Deployment

on:
  pull_request:
    paths:
      - 'infra/**'

jobs:
  whatif:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # needed for git diff

      - name: Azure Login
        uses: azure/login@v2
        with:
          creds: ${{ secrets.AZURE_CREDENTIALS }}

      - name: Install whatif-explain
        run: pip install whatif-explain[anthropic]

      - name: Run What-If and Review
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          az deployment group what-if \
            --resource-group my-rg \
            --template-file infra/main.bicep \
            --parameters infra/parameters.json \
            --exclude-change-types NoChange Ignore \
            > whatif-output.txt

          cat whatif-output.txt | whatif-explain \
            --ci \
            --diff-ref origin/main \
            --bicep-dir infra/ \
            --risk-threshold high \
            --post-comment \
            --format markdown

      - name: Deploy (only if safe)
        if: success()
        run: |
          az deployment group create \
            --resource-group my-rg \
            --template-file infra/main.bicep \
            --parameters infra/parameters.json
```

### Azure DevOps Pipeline Example

```yaml
trigger:
  paths:
    include:
      - infra/*

pool:
  vmImage: ubuntu-latest

stages:
  - stage: WhatIf
    jobs:
      - job: Review
        steps:
          - checkout: self
            fetchDepth: 0

          - task: AzureCLI@2
            displayName: 'Run What-If'
            inputs:
              azureSubscription: 'my-service-connection'
              scriptType: bash
              scriptLocation: inlineScript
              inlineScript: |
                az deployment group what-if \
                  --resource-group my-rg \
                  --template-file infra/main.bicep \
                  --parameters infra/parameters.json \
                  --exclude-change-types NoChange Ignore \
                  > $(Build.ArtifactStagingDirectory)/whatif-output.txt

          - task: Bash@3
            displayName: 'AI Review'
            env:
              ANTHROPIC_API_KEY: $(ANTHROPIC_API_KEY)
              SYSTEM_ACCESSTOKEN: $(System.AccessToken)
            inputs:
              targetType: inline
              script: |
                pip install whatif-explain[anthropic]

                cat $(Build.ArtifactStagingDirectory)/whatif-output.txt | whatif-explain \
                  --ci \
                  --diff-ref origin/main \
                  --bicep-dir infra/ \
                  --risk-threshold high \
                  --post-comment \
                  --format markdown

  - stage: Deploy
    dependsOn: WhatIf
    condition: succeeded()
    jobs:
      - deployment: DeployInfra
        environment: production
        strategy:
          runOnce:
            deploy:
              steps:
                - task: AzureCLI@2
                  inputs:
                    azureSubscription: 'my-service-connection'
                    scriptType: bash
                    scriptLocation: inlineScript
                    inlineScript: |
                      az deployment group create \
                        --resource-group my-rg \
                        --template-file infra/main.bicep \
                        --parameters infra/parameters.json
```

### Updated Project Structure

```
whatif-explain/
├── whatif_explain/
│   ├── __init__.py
│   ├── cli.py              # Entry point, argument parsing
│   ├── input.py            # Stdin reading and validation
│   ├── prompt.py           # Prompt template construction (standard + CI)
│   ├── providers/
│   │   ├── __init__.py     # Provider registry and base class
│   │   ├── anthropic.py    # Claude API provider
│   │   ├── azure_openai.py # Azure OpenAI provider
│   │   └── ollama.py       # Local Ollama provider
│   ├── ci/
│   │   ├── __init__.py
│   │   ├── diff.py         # Git diff collection and parsing
│   │   ├── verdict.py      # Safety verdict evaluation and threshold comparison
│   │   ├── github.py       # GitHub PR comment posting
│   │   └── azdevops.py     # Azure DevOps PR comment posting
│   └── render.py           # Output formatting (table, json, markdown)
├── tests/
│   ├── fixtures/
│   │   ├── create_only.txt
│   │   ├── mixed_changes.txt
│   │   ├── deletes.txt
│   │   ├── no_changes.txt
│   │   └── diffs/
│   │       ├── safe_change.diff
│   │       └── risky_delete.diff
│   ├── test_input.py
│   ├── test_prompt.py
│   ├── test_providers.py
│   ├── test_render.py
│   ├── test_verdict.py
│   └── test_ci_comments.py
├── pyproject.toml
├── README.md
└── LICENSE
```

---

## v2 Roadmap

These features are out of scope for v1 but should be considered in the design:

| Feature | Description |
|---------|-------------|
| Cost estimation | Flag resources that may incur new costs and estimate monthly impact using Azure pricing data |
| Config file | `.whatif-explain.yaml` for persisted defaults |
| Caching | Cache identical What-If outputs to avoid redundant API calls during iterative development |
| Streaming | Stream LLM response to terminal for faster perceived performance |
| GitHub Action wrapper | Published GitHub Action (`uses: yourorg/whatif-explain-action@v1`) that wraps installation and execution |
| Policy rules | User-defined rules file (e.g., "always fail if Key Vault is deleted") that supplement the LLM verdict with deterministic checks |
| Multi-deployment support | Review multiple What-If outputs in a single run (e.g., multi-resource-group deployments) |
| Historical tracking | Store verdicts over time to track deployment risk trends |