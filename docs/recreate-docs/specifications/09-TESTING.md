# Feature Specification: Testing

## Overview

Comprehensive testing strategy for bicep-whatif-advisor covering unit tests, integration tests, and fixture-based testing. Tests use pytest with mocked LLM providers to avoid API calls during testing.

## Testing Framework

**Framework:** pytest

**Dependencies:**
```toml
[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.10.0",
]
```

**Installation:**
```bash
pip install -e .[all,dev]
```

**Run Tests:**
```bash
pytest                    # Run all tests
pytest -v                 # Verbose output
pytest -k test_name       # Run specific test
pytest tests/test_input.py  # Run specific file
```

## Fixture Directory Structure

**Location:** `/tests/fixtures/`

**Required Fixtures:**

```
tests/
├── fixtures/
│   ├── create_only.txt        # Only Create operations
│   ├── mixed_changes.txt      # Creates, Modifies, Deletes
│   ├── deletes.txt            # Only Delete operations
│   ├── no_changes.txt         # All NoChange/Ignore resources
│   └── large_output.txt       # 50+ resources for truncation testing
└── (test files will go here)
```

### Fixture Content Specifications

**create_only.txt:**
- Contains only `+ Create` operations
- 3-5 different resource types
- Example: API Management diagnostics, policies, policy fragments
- No modifications or deletions
- Used to test: Action detection, creation risk assessment

**mixed_changes.txt:**
- Contains mix of Create, Modify, Delete operations
- At least 2 of each action type
- Modify operations should include property-level changes
- Delete operations should include stateful resources (for high-risk testing)
- Used to test: Mixed action handling, risk bucket evaluation, comprehensive rendering

**deletes.txt:**
- Contains only `- Delete` operations
- Include mix of:
  - Stateful resources (databases, storage) → high risk
  - Networking resources → medium risk
  - Tags/metadata → low risk
- Used to test: Deletion risk assessment, high-risk operation detection

**no_changes.txt:**
- Contains only `= NoChange` and `* Ignore` operations
- 5-10 resources
- Should result in empty resource list (filtered out)
- Used to test: NoChange/Ignore filtering, empty result handling

**large_output.txt:**
- Contains 50+ resources
- Mix of all action types
- Total character count > 100,000 for truncation testing
- Used to test: Input truncation, performance, large table rendering

### Fixture Format

All fixtures should use authentic Azure What-If output format:

```
Resource and property changes are indicated with this symbol:
  + Create
  ~ Modify
  - Delete
  = NoChange
  * Ignore

The deployment will update the following scope:

Scope: /subscriptions/12345678-1234-1234-1234-123456789012/resourceGroups/rg-example

  + Microsoft.ApiManagement/service/diagnostics/applicationinsights [2023-03-01-preview]

      id:           "/subscriptions/.../diagnostics/applicationinsights"
      location:     "eastus"
      name:         "applicationinsights"
      properties.alwaysLog:             "allErrors"
      properties.logClientIp:           true
      type:         "Microsoft.ApiManagement/service/diagnostics"

  ~ Microsoft.ApiManagement/service/apis/production-api [2023-03-01-preview]

      ~ properties.publicIPAddressConfiguration.enabled: false => true

  - Microsoft.Sql/servers/databases/production-db [2023-05-01]

      id:         "/subscriptions/.../databases/production-db"
      name:       "production-db"
      type:       "Microsoft.Sql/servers/databases"
```

## Mock LLM Providers

### Mock Provider Pattern

**Purpose:** Avoid API calls during testing, return predictable responses

**Implementation:**

```python
import pytest
from unittest.mock import Mock

@pytest.fixture
def mock_anthropic_provider(mocker):
    """Mock Anthropic provider that returns canned JSON response."""
    mock_provider = Mock()
    mock_provider.complete.return_value = '''{
        "resources": [
            {
                "resource_name": "test-resource",
                "resource_type": "Storage Account",
                "action": "Create",
                "summary": "Creates new storage account",
                "confidence_level": "high",
                "confidence_reason": "New resource creation"
            }
        ],
        "overall_summary": "1 create: Adds storage account"
    }'''

    # Mock the provider factory
    mocker.patch('bicep_whatif_advisor.providers.get_provider', return_value=mock_provider)

    return mock_provider
```

**CI Mode Mock:**

```python
@pytest.fixture
def mock_ci_provider(mocker):
    """Mock provider for CI mode with risk assessment."""
    mock_provider = Mock()
    mock_provider.complete.return_value = '''{
        "resources": [ ... ],
        "overall_summary": "...",
        "risk_assessment": {
            "drift": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "All changes match code diff"
            },
            "intent": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "All changes match PR description"
            },
            "operations": {
                "risk_level": "low",
                "concerns": [],
                "reasoning": "No risky operations detected"
            }
        },
        "verdict": {
            "safe": true,
            "highest_risk_bucket": "none",
            "overall_risk_level": "low",
            "reasoning": "All risk buckets within acceptable thresholds"
        }
    }'''

    mocker.patch('bicep_whatif_advisor.providers.get_provider', return_value=mock_provider)

    return mock_provider
```

## Test Cases by Module

### Module: `input.py`

**Test File:** `tests/test_input.py`

**Test Cases:**

1. **test_read_stdin_success**
   - Mock stdin with valid What-If output
   - Assert content returned correctly
   - Assert no truncation

2. **test_read_stdin_truncate**
   - Mock stdin with > 100,000 characters
   - Assert content truncated
   - Assert warning printed to stderr

3. **test_validate_whatif_valid**
   - Valid What-If output with "Resource changes:"
   - Assert validation passes

4. **test_validate_whatif_invalid**
   - Plain text without What-If markers
   - Assert raises InputError

5. **test_detect_tty**
   - Mock sys.stdin.isatty() = True
   - Assert raises InputError with usage hint

6. **test_empty_input**
   - Empty string input
   - Assert raises InputError

### Module: `prompt.py`

**Test File:** `tests/test_prompt.py`

**Test Cases:**

1. **test_build_standard_system_prompt**
   - Assert contains JSON schema
   - Assert contains confidence instructions
   - Assert does NOT contain risk assessment

2. **test_build_standard_system_prompt_verbose**
   - verbose=True
   - Assert includes "changes" field instruction

3. **test_build_ci_system_prompt_with_pr_metadata**
   - pr_title and pr_description provided
   - Assert includes all three risk buckets
   - Assert intent bucket in schema

4. **test_build_ci_system_prompt_without_pr_metadata**
   - pr_title and pr_description None
   - Assert only drift and operations buckets
   - Assert intent bucket NOT in schema

5. **test_build_user_prompt_standard**
   - diff_content=None
   - Assert contains <whatif_output> tags
   - Assert does NOT contain <code_diff>

6. **test_build_user_prompt_ci**
   - diff_content provided
   - Assert contains all sections: intent, whatif, diff, bicep

### Module: `render.py`

**Test File:** `tests/test_render.py`

**Test Cases:**

1. **test_render_table_standard_mode**
   - Standard data with 3 resources
   - Assert table printed (mock console.print)
   - Assert columns: #, Resource, Type, Action, Summary

2. **test_render_table_ci_mode**
   - CI data with risk_assessment
   - Assert risk bucket table printed
   - Assert columns include Risk column

3. **test_render_table_with_noise**
   - high_conf_data and low_conf_data provided
   - Assert noise section printed
   - Assert separate table for low-confidence

4. **test_render_json**
   - Assert JSON output with high_confidence and low_confidence keys
   - Assert valid JSON (json.loads succeeds)

5. **test_render_markdown**
   - CI mode
   - Assert contains risk assessment table
   - Assert contains <details> sections
   - Assert contains verdict

6. **test_render_markdown_escaping**
   - Summary with pipe character
   - Assert pipes escaped in output: `\|`

### Module: `ci/platform.py`

**Test File:** `tests/test_platform.py`

**Test Cases:**

1. **test_detect_github_actions**
   - Set GITHUB_ACTIONS=true env var
   - Mock event file with PR metadata
   - Assert platform="github"
   - Assert pr_number, pr_title, pr_description extracted

2. **test_detect_github_no_event_file**
   - GITHUB_ACTIONS=true but no event file
   - Assert platform="github" but pr metadata None

3. **test_detect_azure_devops**
   - Set TF_BUILD=True env var
   - Assert platform="azuredevops"
   - Assert pr_number extracted

4. **test_detect_local**
   - No CI env vars
   - Assert platform="local"

5. **test_get_diff_ref_with_branch**
   - base_branch="main"
   - Assert get_diff_ref() returns "origin/main"

6. **test_get_diff_ref_with_refs_heads**
   - base_branch="refs/heads/develop"
   - Assert get_diff_ref() returns "origin/develop"

7. **test_has_pr_metadata**
   - pr_number and pr_title set
   - Assert has_pr_metadata() = True

8. **test_has_pr_metadata_false**
   - pr_number set but no title/description
   - Assert has_pr_metadata() = False

### Module: `ci/risk_buckets.py`

**Test File:** `tests/test_risk_buckets.py`

**Test Cases:**

1. **test_evaluate_risk_buckets_all_pass**
   - All buckets "low"
   - All thresholds "high"
   - Assert is_safe=True, failed_buckets=[]

2. **test_evaluate_risk_buckets_drift_fails**
   - drift risk "high", threshold "high"
   - Assert is_safe=False, failed_buckets=["drift"]

3. **test_evaluate_risk_buckets_multiple_failures**
   - drift "high", operations "medium"
   - thresholds "medium"
   - Assert failed_buckets=["drift", "operations"]

4. **test_evaluate_risk_buckets_no_intent**
   - intent bucket None (no PR metadata)
   - Assert intent not evaluated
   - Assert doesn't fail on missing intent

5. **test_exceeds_threshold**
   - Test all combinations:
     - low >= low → True
     - medium >= low → True
     - high >= low → True
     - low >= medium → False
     - medium >= medium → True
     - high >= medium → True
     - low >= high → False
     - medium >= high → False
     - high >= high → True

6. **test_validate_risk_level**
   - Valid: "low", "medium", "high"
   - Invalid: "unknown" → defaults to "low"
   - Case insensitive: "HIGH" → "high"

### Module: `ci/github.py`

**Test File:** `tests/test_github_comments.py`

**Test Cases:**

1. **test_post_github_comment_success**
   - Mock requests.post to return 200
   - Assert function returns True

2. **test_post_github_comment_no_token**
   - GITHUB_TOKEN not set
   - Assert returns False
   - Assert warning printed

3. **test_post_github_comment_parse_url**
   - pr_url="https://github.com/owner/repo/pull/123"
   - Mock requests.post
   - Assert correct API endpoint called

4. **test_post_github_comment_auto_detect**
   - Set GITHUB_REPOSITORY and GITHUB_REF
   - Mock requests.post
   - Assert auto-detection works

5. **test_post_github_comment_api_error**
   - Mock requests.post to raise HTTPError
   - Assert returns False
   - Assert error logged

### Module: `ci/azdevops.py`

**Test File:** `tests/test_azdevops_comments.py`

**Test Cases:**

1. **test_post_azdevops_comment_success**
   - Mock all env vars
   - Mock requests.post to return 200
   - Assert returns True

2. **test_post_azdevops_comment_missing_vars**
   - Missing SYSTEM_ACCESSTOKEN
   - Assert returns False
   - Assert lists missing variables

3. **test_post_azdevops_comment_https_validation**
   - SYSTEM_COLLECTIONURI="http://..."
   - Assert returns False
   - Assert HTTPS requirement message

4. **test_post_azdevops_comment_api_error**
   - Mock requests.post to raise HTTPError
   - Assert returns False

### Module: `noise_filter.py`

**Test File:** `tests/test_noise_filter.py`

**Test Cases:**

1. **test_load_noise_patterns**
   - Create temp file with patterns and comments
   - Assert comments/blank lines filtered out
   - Assert patterns loaded correctly

2. **test_load_noise_patterns_file_not_found**
   - Non-existent file
   - Assert raises FileNotFoundError

3. **test_calculate_similarity_exact_match**
   - Same strings
   - Assert returns 1.0

4. **test_calculate_similarity_case_insensitive**
   - "Hello" vs "hello"
   - Assert returns 1.0

5. **test_calculate_similarity_partial_match**
   - "Changes subnet reference" vs "Change subnet references"
   - Assert returns > 0.80

6. **test_match_noise_pattern_match**
   - Summary matches pattern above threshold
   - Assert returns True

7. **test_match_noise_pattern_no_match**
   - Summary doesn't match any pattern
   - Assert returns False

8. **test_apply_noise_filtering**
   - Data with 3 resources
   - 1 matches noise pattern
   - Assert confidence_level changed to "noise"

9. **test_apply_noise_filtering_empty_patterns**
   - Empty patterns file
   - Assert data unchanged

### Module: `cli.py`

**Test File:** `tests/test_cli.py`

**Test Cases:**

1. **test_extract_json_valid**
   - Valid JSON string
   - Assert parsed correctly

2. **test_extract_json_with_surrounding_text**
   - JSON wrapped in explanation text
   - Assert JSON extracted

3. **test_extract_json_deeply_nested**
   - JSON with nested objects/arrays
   - Assert extracted correctly

4. **test_extract_json_invalid**
   - No valid JSON in text
   - Assert raises ValueError

5. **test_filter_by_confidence**
   - Mix of low, medium, high confidence
   - Assert split correctly
   - Assert CI fields preserved in high_conf_data

6. **test_filter_by_confidence_noise_level**
   - confidence_level="noise"
   - Assert treated as low confidence

## Integration Test Scenarios

**Test File:** `tests/test_integration.py`

### Scenario 1: End-to-End Standard Mode

```python
def test_e2e_standard_mode(mock_anthropic_provider, tmp_path):
    """Test complete flow: fixture → LLM → table output."""
    # Read fixture
    with open('tests/fixtures/create_only.txt', 'r') as f:
        whatif_content = f.read()

    # Mock stdin
    mocker.patch('sys.stdin', StringIO(whatif_content))

    # Run CLI
    runner = CliRunner()
    result = runner.invoke(cli, ['--format', 'table'])

    # Assert
    assert result.exit_code == 0
    assert 'Create' in result.output
    assert mock_anthropic_provider.complete.called
```

### Scenario 2: End-to-End CI Mode

```python
def test_e2e_ci_mode(mock_ci_provider, mocker):
    """Test CI mode with risk assessment."""
    # Mock platform detection
    mock_ctx = PlatformContext(
        platform="github",
        pr_number="123",
        pr_title="Add monitoring",
        base_branch="main"
    )
    mocker.patch('bicep_whatif_advisor.ci.platform.detect_platform', return_value=mock_ctx)

    # Mock git diff
    mocker.patch('subprocess.run', return_value=Mock(stdout="diff content", returncode=0))

    # Read fixture
    with open('tests/fixtures/mixed_changes.txt', 'r') as f:
        whatif_content = f.read()

    mocker.patch('sys.stdin', StringIO(whatif_content))

    # Run CLI
    runner = CliRunner()
    result = runner.invoke(cli, ['--ci'])

    # Assert
    assert result.exit_code == 0  # Safe verdict
    assert 'SAFE' in result.output
    assert 'Risk Assessment' in result.output
```

### Scenario 3: Noise Filtering Integration

```python
def test_e2e_noise_filtering(mock_anthropic_provider, tmp_path):
    """Test noise filtering with pattern file."""
    # Create noise patterns file
    noise_file = tmp_path / "noise.txt"
    noise_file.write_text("Computed property change\nMetadata-only update\n")

    # Mock LLM to return resources with low confidence
    mock_anthropic_provider.complete.return_value = '''{
        "resources": [
            {
                "resource_name": "subnet",
                "resource_type": "Subnet",
                "action": "Modify",
                "summary": "Computed property change",
                "confidence_level": "medium",
                "confidence_reason": "Uncertain"
            }
        ],
        "overall_summary": "1 modify"
    }'''

    # Read fixture
    with open('tests/fixtures/mixed_changes.txt', 'r') as f:
        whatif_content = f.read()

    mocker.patch('sys.stdin', StringIO(whatif_content))

    # Run CLI with noise filtering
    runner = CliRunner()
    result = runner.invoke(cli, ['--noise-filter', str(noise_file)])

    # Assert
    assert result.exit_code == 0
    assert 'Potential Azure What-If Noise' in result.output
```

## CI/CD Testing Requirements

### GitHub Actions Test Workflow

**File:** `.github/workflows/test.yml`

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11', '3.12']

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v5
      with:
        python-version: ${{ matrix.python-version }}

    - name: Install dependencies
      run: |
        pip install -e .[all,dev]

    - name: Run tests
      run: |
        pytest -v

    - name: Check coverage
      run: |
        pytest --cov=bicep_whatif_advisor --cov-report=term-missing
```

### Azure DevOps Test Pipeline

**File:** `azure-pipelines-test.yml`

```yaml
trigger:
  - main
  - develop

pool:
  vmImage: ubuntu-latest

strategy:
  matrix:
    Python38:
      python.version: '3.8'
    Python312:
      python.version: '3.12'

steps:
- task: UsePythonVersion@0
  inputs:
    versionSpec: '$(python.version)'

- script: |
    pip install -e .[all,dev]
  displayName: 'Install dependencies'

- script: |
    pytest -v --junitxml=junit/test-results.xml
  displayName: 'Run tests'

- task: PublishTestResults@2
  inputs:
    testResultsFiles: 'junit/test-results.xml'
  condition: succeededOrFailed()
```

## Pytest Configuration

**File:** `pytest.ini` or `pyproject.toml`

```ini
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = [
    "-v",
    "--strict-markers",
    "--tb=short",
]
markers = [
    "unit: Unit tests",
    "integration: Integration tests",
    "slow: Slow tests",
]
```

## Coverage Requirements

**Minimum Coverage:** 80%

**Critical Paths Requiring 100% Coverage:**
- Input validation (TTY detection, What-If markers)
- Risk bucket evaluation logic
- Confidence filtering
- Threshold comparison

**Run Coverage:**
```bash
pytest --cov=bicep_whatif_advisor --cov-report=html
open htmlcov/index.html
```

## Test Data Management

**Fixture Generation:**

Create a script to generate fixtures from real Azure deployments:

```python
# scripts/generate_fixtures.py
import subprocess
import sys

def generate_whatif_fixture(bicep_file, resource_group, output_file):
    """Run az deployment what-if and save output as fixture."""
    result = subprocess.run(
        [
            'az', 'deployment', 'group', 'what-if',
            '--template-file', bicep_file,
            '-g', resource_group,
            '--exclude-change-types', 'NoChange', 'Ignore'
        ],
        capture_output=True,
        text=True
    )

    with open(output_file, 'w') as f:
        f.write(result.stdout)

    print(f"Fixture saved to {output_file}")

# Usage:
# python scripts/generate_fixtures.py main.bicep rg-example fixtures/mixed_changes.txt
```

## Implementation Requirements

1. **Mock all LLM calls:** Never call real APIs in tests
2. **Fixture-based testing:** Use authentic What-If output from real deployments
3. **Platform testing:** Mock environment variables for GitHub/ADO detection
4. **Error path testing:** Test all error scenarios (missing tokens, API errors, invalid input)
5. **Parametrized tests:** Use pytest.mark.parametrize for multiple input variations
6. **Temp files:** Use pytest tmp_path fixture for file-based tests
7. **Clean mocking:** Use pytest-mock for cleaner mock syntax
8. **No API keys in tests:** Never require real API keys for test execution
9. **Fast tests:** All tests should complete in < 10 seconds total
10. **Deterministic:** Tests must pass consistently (no flaky tests)

## Edge Cases to Test

1. **Empty What-If output:** No resources changed
2. **Malformed JSON from LLM:** Invalid JSON response
3. **Missing confidence fields:** LLM doesn't return confidence_level
4. **Very long resource names:** Truncation/wrapping in tables
5. **Special characters in summaries:** Unicode, markdown characters
6. **Platform detection edge cases:** Both GitHub and ADO vars set
7. **File operations:** Missing noise file, unreadable files
8. **Network errors:** Timeout, connection refused
9. **Large fixtures:** Memory usage with 1000+ resources
10. **Concurrent tests:** No shared state between tests
