---
name: new-feature
description: Complete workflow for adding a new feature including code implementation and documentation updates
---

# New Feature Workflow

Comprehensive workflow for adding new features to bicep-whatif-advisor. Handles code implementation, testing, and automatic documentation synchronization.

**Use this skill when:**
- Adding a new CLI flag or option
- Adding a new provider (LLM service)
- Adding a new output format
- Adding a new CI/CD platform
- Adding a new risk assessment bucket
- Adding any new functionality to the tool

## Workflow

### Phase 1: Planning and Design

#### 1. Understand the Feature Request

Ask the user to clarify:
- What is the feature?
- How should it work?
- What are the inputs/outputs?
- Are there any configuration options?
- Should it be optional or always-on?

#### 2. Identify Implementation Areas

Determine which parts of the codebase need changes:

| Feature Type | Files to Modify | New Files Needed |
|--------------|----------------|------------------|
| **New CLI Flag** | `cli.py` | None |
| **New Provider** | `providers/__init__.py` | `providers/new_provider.py` |
| **New Output Format** | `render.py` | None |
| **New Risk Bucket** | `ci/risk_buckets.py`, `prompt.py` | None |
| **New CI Platform** | `ci/platform.py` | `ci/new_platform.py` |
| **New Filtering Method** | `noise_filter.py` | None |

#### 3. Check Dependencies

Determine if new dependencies are needed:
- Python packages (add to `pyproject.toml`)
- Environment variables
- External services or APIs

### Phase 2: Code Implementation

#### 1. Write the Code

Follow these patterns based on feature type:

**A. New CLI Flag:**
```python
# In bicep_whatif_advisor/cli.py

@click.option(
    "--new-flag",
    type=str,  # or bool, int, Path, etc.
    default=None,
    help="Description of what this flag does"
)
def main(new_flag, ...):
    # Add handling logic
    if new_flag:
        # Process the flag
        pass
```

**B. New Provider:**
```python
# Create bicep_whatif_advisor/providers/new_provider.py

from . import Provider

class NewProvider(Provider):
    """Description of the provider."""

    def __init__(self, model: str = "default-model"):
        self.model = model
        # Initialize API client

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the LLM and return response."""
        # Implementation
        pass
```

Then update `providers/__init__.py`:
```python
from .new_provider import NewProvider

def get_provider(name: str, model: Optional[str] = None) -> Provider:
    if name == "new-provider":
        return NewProvider(model=model or "default-model")
    # ... existing providers
```

**C. New Output Format:**
```python
# In bicep_whatif_advisor/render.py

def render_new_format(data: dict, verbose: bool = False) -> str:
    """Render in new format.

    Args:
        data: Parsed response from LLM
        verbose: Include detailed information

    Returns:
        Formatted output string
    """
    # Implementation
    pass
```

Then update `cli.py`:
```python
@click.option("--format", type=click.Choice(["table", "json", "markdown", "new-format"]))
def main(format, ...):
    if format == "new-format":
        output = render_new_format(response_data, verbose)
```

**D. New Risk Bucket:**
```python
# In bicep_whatif_advisor/prompt.py
# Add bucket to schema in build_system_prompt()

# In bicep_whatif_advisor/ci/risk_buckets.py
def evaluate_risk_buckets(
    data: dict,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str,
    new_bucket_threshold: str,  # Add new parameter
) -> tuple[bool, list[str], dict]:
    # Add evaluation logic for new bucket
    pass
```

Then update `cli.py` to add the threshold flag.

#### 2. Update Dependencies

If new dependencies are needed:

```toml
# In pyproject.toml

[project.optional-dependencies]
new-provider = ["new-sdk>=1.0.0"]
all = [
    "anthropic>=0.40.0",
    "openai>=1.0.0",
    "new-sdk>=1.0.0",  # Add here
]
```

#### 3. Add Error Handling

Ensure proper error handling:
```python
try:
    # Feature implementation
    result = process_new_feature()
except SpecificError as e:
    click.echo(f"Error: {e}", err=True)
    click.echo("Suggestion: How to fix this", err=True)
    sys.exit(1)
```

### Phase 3: Testing

#### 1. Manual Testing

Test the feature works:
```bash
# Test with fixture
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli --new-flag

# Test with real Azure What-If
az deployment group what-if ... | bicep-whatif-advisor --new-flag
```

#### 2. Test Edge Cases

- Invalid inputs
- Missing required configuration
- Empty responses
- Error conditions

#### 3. Add Test Fixtures (if needed)

If new fixture files are needed:
```bash
# Create new fixture in tests/fixtures/
# Document what it's for in 11-TESTING-STRATEGY.md
```

### Phase 4: Documentation Updates

**CRITICAL:** Update all relevant documentation to reflect the new feature.

#### A. Identify Documentation to Update

Use this mapping:

**Code File → Technical Spec:**
- `cli.py` → `01-CLI-INTERFACE.md`
- `input.py` → `02-INPUT-VALIDATION.md`
- `providers/*.py` → `03-PROVIDER-SYSTEM.md`
- `prompt.py` → `04-PROMPT-ENGINEERING.md`
- `render.py` → `05-OUTPUT-RENDERING.md`
- `noise_filter.py` → `06-NOISE-FILTERING.md`
- `ci/platform.py` → `07-PLATFORM-DETECTION.md`
- `ci/risk_buckets.py` → `08-RISK-ASSESSMENT.md`
- `ci/github.py`, `ci/azdevops.py` → `09-PR-INTEGRATION.md`
- `ci/diff.py` → `10-GIT-DIFF.md`
- `pyproject.toml` → `00-OVERVIEW.md`

**Feature Type → User Guides:**
- New CLI flag → `USER_GUIDE.md` (CLI Flags Reference)
- New provider → `USER_GUIDE.md` (Providers), `QUICKSTART.md` (Installation)
- New output format → `USER_GUIDE.md` (Output Formats)
- CI/CD feature → `CICD_INTEGRATION.md`
- Risk assessment change → `RISK_ASSESSMENT.md`
- Installation change → `QUICKSTART.md`, `USER_GUIDE.md`

**Always Check:**
- `CLAUDE.md` - Architecture, commands, requirements
- `README.md` - Quick examples, feature list
- `00-OVERVIEW.md` - Data flow, architecture

#### B. Update Technical Specs

For each affected spec (docs/specs/00-11):

**Update these sections:**

1. **Implementation Section:**
   - Add new function/class/module
   - Include file path and line numbers
   - Add function signatures
   - Describe behavior

2. **Data Structures Section (if applicable):**
   - Add new schemas or formats
   - Show JSON/dict structure
   - Explain each field

3. **Integration Points Section (if applicable):**
   - Describe how it connects to other modules
   - Show call flow
   - Document dependencies

4. **Configuration Section (if applicable):**
   - Add new CLI flags
   - Add new environment variables
   - Show default values

5. **Examples Section:**
   - Add code examples
   - Show usage patterns
   - Include error handling

**Example Update:**
```markdown
## Implementation

### File: bicep_whatif_advisor/cli.py

**New CLI Flag: --new-flag**
- **Lines:** 123-127
- **Type:** `str`
- **Default:** `None`
- **Purpose:** Enables new feature X

**Function: main()**
- **Lines:** 200-250
- Added handling for --new-flag (lines 230-235)
- Calls `process_new_feature()` when enabled
- Integrates with render module (line 245)

### File: bicep_whatif_advisor/new_module.py

**New Module Created**
- **Purpose:** Implements feature X
- **Exports:** `process_new_feature()`

**Function: process_new_feature()**
```python
def process_new_feature(config: dict) -> dict:
    """Process the new feature.

    Args:
        config: Configuration dictionary

    Returns:
        Processed result dictionary
    """
```

**Integration:**
- Called from cli.py main() (line 230)
- Uses providers module for LLM calls (line 50)
- Returns data to render module (line 80)
```

#### C. Update User Guides

**1. QUICKSTART.md** - Only if installation changes:
```markdown
# Installation

## Prerequisites
- New requirement (if applicable)

## Install from PyPI

```bash
# With new provider
pip install bicep-whatif-advisor[new-provider]
```

## Set API Key

```bash
export NEW_PROVIDER_API_KEY="..."
```
```

**2. USER_GUIDE.md** - Always update for new features:

**Add to appropriate table:**
```markdown
## CLI Flags Reference

### Core Flags (or appropriate section)

| Flag | Description | Default |
|------|-------------|---------|
| `--new-flag` | Description of new flag | `default-value` |
```

**Add to Environment Variables (if applicable):**
```markdown
| Variable | Required For | Description |
|----------|--------------|-------------|
| `NEW_PROVIDER_API_KEY` | New provider | API key from service |
```

**Add to Common Patterns:**
```markdown
## Common Patterns

### Using New Feature

```bash
# Basic usage
az deployment group what-if ... | bicep-whatif-advisor --new-flag

# With options
bicep-whatif-advisor --new-flag value --other-options
```
```

**Add to Troubleshooting (if needed):**
```markdown
### "New feature error" message

**Cause:** Missing configuration

**Fix:**
```bash
export REQUIRED_VAR="value"
```
```

**3. CICD_INTEGRATION.md** - For CI/CD features:

Add examples to platform sections:
```markdown
### GitHub Actions Configuration Options

#### Use New Feature

```yaml
- env:
    NEW_VAR: ${{ secrets.NEW_VAR }}
  run: |
    az deployment group what-if ... | bicep-whatif-advisor --new-flag
```
```

**4. RISK_ASSESSMENT.md** - For risk assessment changes:

Update affected sections:
- Three Risk Buckets section
- How Risk Levels Are Determined section
- Examples section

#### D. Update Project Files

**1. CLAUDE.md:**

Update these sections as needed:

```markdown
## Project Structure
- Add new files to tree

## Development Commands
- Add new commands if applicable

## Architecture Notes
- Describe new patterns or integrations

### LLM Provider Interface
- Add new providers to list
- Update default models

### Structured Response Format
- Add new fields to schema examples

## Documentation Structure
- Note new sections if added
```

**2. README.md:**

Update these sections:

```markdown
## How It Works
- Update if workflow changes

## Quick Start
- Update if basic usage changes

## Configuration Options
- Add new options with examples

### Alternative LLM Providers
- Add new provider section

## Documentation
- Add new guides if created
```

#### E. Verify Documentation

**1. Check Consistency:**
```bash
# Version numbers
grep "version" bicep_whatif_advisor/__init__.py pyproject.toml

# CLI flags in code vs docs
grep -E "@click\.(option|argument)" bicep_whatif_advisor/cli.py
# Compare with USER_GUIDE.md

# Environment variables in code vs docs
grep -r "os\.environ\|os\.getenv" bicep_whatif_advisor/
# Compare with USER_GUIDE.md
```

**2. Test Examples:**
- Run all example commands from updated guides
- Verify they work as documented
- Test with fixtures where applicable

**3. Validate Links:**
```bash
# Check all markdown links
grep -r "\[.*\](.*\.md)" docs/
# Verify all referenced files exist
```

### Phase 5: Commit and Document

#### 1. Review Changes

```bash
git status
git diff
```

#### 2. Stage Files

```bash
git add bicep_whatif_advisor/
git add docs/
git add pyproject.toml  # if changed
git add CLAUDE.md  # if changed
git add README.md  # if changed
```

#### 3. Create Comprehensive Commit

```bash
git commit -m "Add [feature name]

Brief description of what the feature does.

## Implementation

- File: bicep_whatif_advisor/[file].py
  - Added: [functions/classes]
  - Modified: [existing code]

- Dependencies: [if added]

## Documentation Updates

**Technical Specs:**
- Updated [XX-SPEC-NAME.md]
  - Added implementation details
  - Added examples

**User Guides:**
- Updated [GUIDE-NAME.md]
  - Added CLI flag documentation
  - Added usage examples
  - Added troubleshooting

**Project Files:**
- Updated CLAUDE.md
  - [what changed]
- Updated README.md
  - [what changed]

## Testing

- [x] Manual testing with fixtures
- [x] Edge cases handled
- [x] Example commands tested
- [x] Documentation verified

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

### Phase 6: Final Checklist

Use this checklist before finishing:

```markdown
## New Feature Checklist

### Code Implementation
- [ ] Feature implemented in appropriate module
- [ ] Error handling added
- [ ] Integration with existing modules works
- [ ] Dependencies added to pyproject.toml (if needed)
- [ ] Environment variables documented
- [ ] Follows existing code patterns

### Testing
- [ ] Manual testing completed
- [ ] Tested with fixtures
- [ ] Tested with real Azure What-If output
- [ ] Edge cases handled
- [ ] Error messages are clear and helpful

### Technical Specs Updated
- [ ] Primary spec file updated
- [ ] Secondary spec files updated (if applicable)
- [ ] Implementation section complete
- [ ] Data structures documented (if applicable)
- [ ] Integration points documented
- [ ] Configuration documented
- [ ] Examples added
- [ ] File paths and line numbers accurate

### User Guides Updated
- [ ] QUICKSTART.md (if installation changed)
- [ ] USER_GUIDE.md
  - [ ] CLI Flags Reference table
  - [ ] Environment Variables table (if applicable)
  - [ ] Common Patterns section
  - [ ] Troubleshooting section
- [ ] CICD_INTEGRATION.md (if CI/CD feature)
  - [ ] GitHub Actions examples
  - [ ] Azure DevOps examples
- [ ] RISK_ASSESSMENT.md (if risk feature)

### Project Files Updated
- [ ] CLAUDE.md
  - [ ] Project Structure (if files added)
  - [ ] Development Commands (if commands added)
  - [ ] Architecture Notes (if patterns changed)
  - [ ] Documentation Structure (if docs added)
- [ ] README.md
  - [ ] How It Works (if workflow changed)
  - [ ] Quick Start (if usage changed)
  - [ ] Configuration Options (if options added)

### Verification
- [ ] Version numbers consistent across files
- [ ] All markdown links valid
- [ ] CLI flags match between code and docs
- [ ] Environment variables match between code and docs
- [ ] Example commands tested and work
- [ ] Cross-references updated
- [ ] No broken links in documentation

### Commit
- [ ] All changes staged
- [ ] Comprehensive commit message written
- [ ] Co-author credit included
```

## Common Feature Examples

### Example 1: New CLI Flag (--bicep-dir)

**User Request:** "Add a flag to specify Bicep source directory for better analysis"

**Implementation:**
1. Add flag to cli.py:
```python
@click.option("--bicep-dir", type=click.Path(exists=True))
def main(bicep_dir, ...):
    if bicep_dir:
        # Read Bicep files and include in prompt
        bicep_source = read_bicep_files(bicep_dir)
        system_prompt = build_system_prompt(bicep_source=bicep_source)
```

2. Update prompt.py to accept bicep_source parameter

3. Update docs:
   - 01-CLI-INTERFACE.md (implementation)
   - 04-PROMPT-ENGINEERING.md (how source is used)
   - USER_GUIDE.md (CLI flags table + example)
   - CICD_INTEGRATION.md (workflow examples)

### Example 2: New Provider (Gemini)

**User Request:** "Add support for Google Gemini"

**Implementation:**
1. Create providers/gemini.py:
```python
class GeminiProvider(Provider):
    def __init__(self, model: str = "gemini-pro"):
        import google.generativeai as genai
        genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
        self.model = genai.GenerativeModel(model)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self.model.generate_content(f"{system_prompt}\n\n{user_prompt}")
        return response.text
```

2. Update providers/__init__.py

3. Update pyproject.toml:
```toml
[project.optional-dependencies]
gemini = ["google-generativeai>=0.3.0"]
all = [..., "google-generativeai>=0.3.0"]
```

4. Update docs:
   - 03-PROVIDER-SYSTEM.md (implementation details)
   - USER_GUIDE.md (installation, env var, examples)
   - QUICKSTART.md (installation option)
   - CLAUDE.md (provider list)
   - README.md (provider examples)

### Example 3: New Risk Bucket (Compliance)

**User Request:** "Add compliance risk bucket for regulatory checks"

**Implementation:**
1. Update prompt.py schema to include compliance bucket

2. Update ci/risk_buckets.py:
```python
def evaluate_risk_buckets(
    data: dict,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str,
    compliance_threshold: str,
) -> tuple[bool, list[str], dict]:
    # Add compliance evaluation
    compliance = data["risk_assessment"]["compliance"]
    if _exceeds_threshold(compliance["risk_level"], compliance_threshold):
        failed_buckets.append("compliance")
```

3. Add --compliance-threshold flag to cli.py

4. Update docs:
   - 08-RISK-ASSESSMENT.md (spec)
   - RISK_ASSESSMENT.md (user guide - now four buckets)
   - USER_GUIDE.md (new threshold flag)
   - CLAUDE.md (risk bucket system)
   - README.md (how it works)

## Success Criteria

✅ **Code:**
- Feature works as intended
- Error handling is robust
- Follows existing patterns
- No breaking changes

✅ **Testing:**
- Manual testing completed
- Edge cases covered
- Examples verified

✅ **Documentation:**
- All specs updated with accurate details
- All user guides updated with examples
- Project files reflect changes
- No broken links
- Version consistency maintained

✅ **Commit:**
- Comprehensive commit message
- All changes included
- Ready for PR

## Tips

- **Start with user guides** - They help you understand what users need to know
- **Test as you go** - Don't wait until the end to test
- **Update docs immediately** - Don't let them fall behind
- **Be thorough** - Check all mapping tables
- **Verify examples** - Always test documented commands
- **Ask questions** - If unsure about documentation, ask the user

## Example Usage

```bash
# Invoke the skill
/new-feature

# Or with context
/new-feature "Add support for Azure OpenAI GPT-4o model"
```

The skill will guide you through:
1. Planning the feature
2. Implementing the code
3. Testing thoroughly
4. Updating all documentation
5. Creating a comprehensive commit
