# 11 - Testing Strategy

## Purpose

This document outlines the testing approach for `bicep-whatif-advisor`, covering test fixtures, mocking strategies, and recommended test coverage for each module.

**Current State:** Test fixtures exist, Python test suite to be implemented.

## Test Fixtures

### Location

```
tests/fixtures/
├── create_only.txt       # Only create operations
├── deletes.txt           # Only deletion operations
├── large_output.txt      # 50+ resources for truncation testing
├── mixed_changes.txt     # Creates, modifies, and deletes
└── no_changes.txt        # All NoChange/Ignore resources
```

### Usage

```bash
# Manual testing with fixtures
cat tests/fixtures/create_only.txt | bicep-whatif-advisor
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor --ci --diff-ref HEAD~1

# Or via Python module
cat tests/fixtures/create_only.txt | python -m bicep_whatif_advisor.cli
```

### Sample Bicep Deployment

**Location:** `tests/sample-bicep-deployment/`

**Contents:**
- `main.bicep` - Example Bicep template
- `pre-production.bicepparam` - Parameter file

**Test What-If Command:**
```bash
az deployment group what-if \
  --template-file ./tests/sample-bicep-deployment/main.bicep \
  --parameters ./tests/sample-bicep-deployment/pre-production.bicepparam \
  -g <resource-group> \
  --exclude-change-types NoChange Ignore
```

## Testing Layers

### 1. Unit Tests

Test individual functions in isolation with mocked dependencies.

#### Input Validation (`test_input.py`)

```python
import pytest
from bicep_whatif_advisor.input import read_stdin, InputError

def test_empty_input():
    # Mock sys.stdin
    with mock.patch('sys.stdin.read', return_value=''):
        with pytest.raises(InputError, match="Input is empty"):
            read_stdin()

def test_truncation():
    large_input = 'x' * 150000
    with mock.patch('sys.stdin.read', return_value=large_input):
        result = read_stdin()
        assert len(result) == 100000

def test_tty_detection():
    with mock.patch('sys.stdin.isatty', return_value=True):
        with pytest.raises(InputError, match="No input detected"):
            read_stdin()
```

#### Provider System (`test_providers.py`)

```python
from bicep_whatif_advisor.providers import get_provider

def test_get_provider():
    provider = get_provider("anthropic", model="claude-sonnet-4-20250514")
    assert provider.model == "claude-sonnet-4-20250514"

def test_provider_env_override():
    with mock.patch.dict(os.environ, {'WHATIF_PROVIDER': 'ollama'}):
        provider = get_provider("anthropic")  # Overridden
        assert isinstance(provider, OllamaProvider)

# Mock provider for testing
class MockProvider(Provider):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return '{"resources": [], "overall_summary": "Mock response"}'
```

#### Prompt Engineering (`test_prompt.py`)

```python
from bicep_whatif_advisor.prompt import build_system_prompt, build_user_prompt

def test_standard_mode_prompt():
    prompt = build_system_prompt(verbose=False, ci_mode=False)
    assert "Azure infrastructure expert" in prompt
    assert "risk_assessment" not in prompt  # Not in standard mode

def test_ci_mode_prompt_with_pr():
    prompt = build_system_prompt(ci_mode=True, pr_title="Test", pr_description="Test PR")
    assert "risk_assessment" in prompt
    assert "intent" in prompt  # Intent bucket included

def test_ci_mode_prompt_without_pr():
    prompt = build_system_prompt(ci_mode=True)
    assert "risk_assessment" in prompt
    assert "intent alignment analysis is SKIPPED" in prompt
```

#### Noise Filtering (`test_noise_filter.py`)

```python
from bicep_whatif_advisor.noise_filter import calculate_similarity, match_noise_pattern, apply_noise_filtering

def test_similarity_calculation():
    assert calculate_similarity("Change to IPv6", "change to ipv6") == 1.0  # Case-insensitive
    assert calculate_similarity("Change to IPv6", "Modify IPv6 flag") > 0.5
    assert calculate_similarity("Create storage", "Delete database") < 0.3

def test_pattern_matching():
    patterns = ["Change to IPv6", "Update to etag"]
    assert match_noise_pattern("Change to IPv6 settings", patterns, 0.80) == True
    assert match_noise_pattern("Create storage account", patterns, 0.80) == False

def test_filtering():
    data = {
        "resources": [
            {"summary": "Change to IPv6", "confidence_level": "medium"},
            {"summary": "Create storage", "confidence_level": "high"}
        ]
    }

    # Create temp pattern file
    with open('/tmp/patterns.txt', 'w') as f:
        f.write("Change to IPv6\n")

    filtered = apply_noise_filtering(data, '/tmp/patterns.txt', 0.80)
    assert filtered["resources"][0]["confidence_level"] == "noise"
    assert filtered["resources"][1]["confidence_level"] == "high"
```

#### Risk Assessment (`test_risk_buckets.py`)

```python
from bicep_whatif_advisor.ci.risk_buckets import evaluate_risk_buckets, _exceeds_threshold

def test_threshold_comparison():
    assert _exceeds_threshold("low", "high") == False
    assert _exceeds_threshold("high", "high") == True
    assert _exceeds_threshold("medium", "low") == True

def test_all_buckets_pass():
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "low"},
            "operations": {"risk_level": "low"}
        }
    }
    is_safe, failed, _ = evaluate_risk_buckets(data, "high", "high", "high")
    assert is_safe == True
    assert len(failed) == 0

def test_one_bucket_fails():
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "high"},
            "operations": {"risk_level": "low"}
        }
    }
    is_safe, failed, _ = evaluate_risk_buckets(data, "high", "high", "high")
    assert is_safe == False
    assert "drift" in failed
```

### 2. Integration Tests

Test complete workflows with mocked LLM providers.

#### End-to-End Standard Mode

```python
def test_standard_mode_workflow():
    # Mock provider
    mock_provider = MockProvider()

    with mock.patch('bicep_whatif_advisor.cli.get_provider', return_value=mock_provider):
        # Simulate stdin
        whatif_content = open('tests/fixtures/create_only.txt').read()
        with mock.patch('sys.stdin.read', return_value=whatif_content):
            # Run CLI
            from bicep_whatif_advisor.cli import main
            # ... test execution
```

#### End-to-End CI Mode

```python
def test_ci_mode_workflow():
    mock_provider = MockProvider()
    mock_provider.response = '''{
        "resources": [{...}],
        "risk_assessment": {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": "..."},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": "..."}
        },
        "verdict": {"safe": true, "overall_risk_level": "low", "reasoning": "..."}
    }'''

    # Test with mock provider and mocked git diff
    # ...
```

### 3. Fixture-Based Tests

Test with real Azure What-If output.

```python
def test_create_only_fixture():
    content = open('tests/fixtures/create_only.txt').read()
    # Run through pipeline
    # Verify resources extracted
    # Verify no deletions detected

def test_mixed_changes_fixture():
    content = open('tests/fixtures/mixed_changes.txt').read()
    # Verify creates, modifies, and deletes all detected

def test_large_output_fixture():
    content = open('tests/fixtures/large_output.txt').read()
    # Verify truncation handling
    # Verify performance (< 10s end-to-end)
```

### 4. Platform Integration Tests

Test with real CI/CD platforms (optional, requires credentials).

```python
@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="No API key")
def test_real_anthropic_provider():
    provider = get_provider("anthropic")
    response = provider.complete("You are a test.", "Say 'test successful'")
    assert "test successful" in response.lower()

@pytest.mark.integration
@pytest.mark.skipif(not os.environ.get("GITHUB_TOKEN"), reason="No GitHub token")
def test_real_github_comment():
    from bicep_whatif_advisor.ci.github import post_github_comment
    # Post to test PR
    # Verify comment appears
```

## Mocking Strategies

### LLM Provider Mocking

```python
class MockProvider(Provider):
    def __init__(self, response_file=None):
        self.response_file = response_file

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self.response_file:
            with open(self.response_file) as f:
                return f.read()
        return '{"resources": [], "overall_summary": "Mock"}'
```

### Environment Variable Mocking

```python
@mock.patch.dict(os.environ, {
    'GITHUB_ACTIONS': 'true',
    'GITHUB_REPOSITORY': 'owner/repo',
    'GITHUB_REF': 'refs/pull/123/merge'
})
def test_github_detection():
    from bicep_whatif_advisor.ci.platform import detect_platform
    ctx = detect_platform()
    assert ctx.platform == "github"
```

### Subprocess Mocking (Git)

```python
@mock.patch('subprocess.run')
def test_git_diff(mock_run):
    mock_run.return_value.returncode = 0
    mock_run.return_value.stdout = 'diff --git a/main.bicep...'

    from bicep_whatif_advisor.ci.diff import get_diff
    diff = get_diff(diff_ref='origin/main')
    assert 'main.bicep' in diff
```

## Test Coverage Goals

| Module | Target Coverage | Priority |
|--------|-----------------|----------|
| `input.py` | 100% | High |
| `prompt.py` | 90% | High |
| `providers/*.py` | 80% | Medium (mocking required) |
| `render.py` | 70% | Medium (visual output) |
| `noise_filter.py` | 100% | High |
| `ci/platform.py` | 90% | High |
| `ci/risk_buckets.py` | 100% | High |
| `ci/diff.py` | 90% | High |
| `ci/github.py` | 50% | Low (requires real API) |
| `ci/azdevops.py` | 50% | Low (requires real API) |
| `cli.py` | 70% | Medium (orchestration) |

## Running Tests

### Test Framework

**Recommendation:** `pytest` for test framework, `pytest-cov` for coverage.

```bash
pip install pytest pytest-cov pytest-mock
```

### Test Execution

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=bicep_whatif_advisor --cov-report=html

# Run specific test file
pytest tests/test_input.py

# Run specific test
pytest tests/test_input.py::test_empty_input

# Run integration tests only
pytest -m integration

# Skip integration tests
pytest -m "not integration"

# Verbose output
pytest -v
```

### Continuous Integration

**GitHub Actions:**
```yaml
- name: Run tests
  run: |
    pip install -e .[all,dev]
    pytest --cov=bicep_whatif_advisor --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## Test Organization

```
tests/
├── fixtures/                    # Test data
│   ├── create_only.txt
│   ├── deletes.txt
│   ├── large_output.txt
│   ├── mixed_changes.txt
│   └── no_changes.txt
├── sample-bicep-deployment/     # Example Bicep templates
│   ├── main.bicep
│   └── pre-production.bicepparam
├── test_input.py                # Input validation tests
├── test_providers.py            # Provider system tests
├── test_prompt.py               # Prompt engineering tests
├── test_render.py               # Output rendering tests
├── test_noise_filter.py         # Noise filtering tests
├── test_risk_buckets.py         # Risk assessment tests
├── test_platform.py             # Platform detection tests
├── test_diff.py                 # Git diff tests
├── test_github.py               # GitHub integration tests
├── test_azdevops.py             # Azure DevOps integration tests
├── test_cli.py                  # CLI orchestration tests
├── test_integration.py          # End-to-end integration tests
└── conftest.py                  # Pytest configuration and fixtures
```

## Test Fixtures (conftest.py)

```python
import pytest
from bicep_whatif_advisor.providers import Provider

@pytest.fixture
def mock_provider():
    """Provide a mock LLM provider."""
    class MockProvider(Provider):
        def complete(self, system_prompt: str, user_prompt: str) -> str:
            return '{"resources": [], "overall_summary": "Mock"}'
    return MockProvider()

@pytest.fixture
def create_only_fixture():
    """Load create_only.txt fixture."""
    with open('tests/fixtures/create_only.txt') as f:
        return f.read()

@pytest.fixture
def mixed_changes_fixture():
    """Load mixed_changes.txt fixture."""
    with open('tests/fixtures/mixed_changes.txt') as f:
        return f.read()
```

## Testing Best Practices

### 1. Test Isolation

Each test should be independent:
```python
def test_function():
    # Setup
    data = {...}
    # Test
    result = function(data)
    # Assert
    assert result == expected
    # Cleanup (if needed)
```

### 2. Clear Test Names

```python
def test_threshold_comparison_low_below_high():
    assert _exceeds_threshold("low", "high") == False

def test_threshold_comparison_equal_levels():
    assert _exceeds_threshold("high", "high") == True
```

### 3. Parameterized Tests

```python
@pytest.mark.parametrize("risk,threshold,expected", [
    ("low", "high", False),
    ("high", "high", True),
    ("medium", "low", True),
])
def test_threshold_comparison(risk, threshold, expected):
    assert _exceeds_threshold(risk, threshold) == expected
```

### 4. Test Markers

```python
@pytest.mark.unit
def test_unit_level():
    pass

@pytest.mark.integration
def test_integration_level():
    pass

@pytest.mark.slow
def test_slow_operation():
    pass
```

## Future Testing Enhancements

1. **Mutation testing:** Verify test quality with `mutmut`
2. **Property-based testing:** Use `hypothesis` for edge cases
3. **Performance benchmarks:** Track latency regressions
4. **Visual regression testing:** Snapshot testing for rendered output
5. **Contract testing:** Verify LLM response schemas

## Next Steps

For implementation details of each module:
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - CLI orchestration logic
- [02-INPUT-VALIDATION.md](02-INPUT-VALIDATION.md) - Input validation
- [03-PROVIDER-SYSTEM.md](03-PROVIDER-SYSTEM.md) - LLM providers
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - Prompt construction
- [05-OUTPUT-RENDERING.md](05-OUTPUT-RENDERING.md) - Output formatting
- [06-NOISE-FILTERING.md](06-NOISE-FILTERING.md) - Confidence filtering
- [07-PLATFORM-DETECTION.md](07-PLATFORM-DETECTION.md) - CI/CD detection
- [08-RISK-ASSESSMENT.md](08-RISK-ASSESSMENT.md) - Risk buckets
- [09-PR-INTEGRATION.md](09-PR-INTEGRATION.md) - PR comments
- [10-GIT-DIFF.md](10-GIT-DIFF.md) - Git diff collection
