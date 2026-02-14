# Phase 4 Implementation Prompt: Risk Assessment System

## Objective

Implement the three-bucket risk assessment system with independent threshold evaluation for CI mode deployment gates.

## Context

This phase builds the deployment safety gate logic. The system evaluates three independent risk dimensions (infrastructure drift, PR intent alignment, risky operations) and blocks deployment if ANY bucket exceeds its threshold. This is the core safety mechanism for CI/CD integration.

## Specifications to Reference

Read these specification files before starting:
- `specifications/06-RISK-ASSESSMENT.md` - Risk bucket system and evaluation logic
- `specifications/03-PROMPT-ENGINEERING.md` - CI mode prompt structure

## Tasks

### Task 1: Risk Evaluation Module

Create `bicep_whatif_advisor/ci/verdict.py`:

```python
"""Risk level constants for deployment safety evaluation."""

from typing import List

# Risk levels in ascending order (index = severity)
RISK_LEVELS: List[str] = ["low", "medium", "high"]
```

Create `bicep_whatif_advisor/ci/risk_buckets.py`:

#### Step 1.1: Imports and Helper Functions

```python
"""Three-bucket risk assessment for deployment safety gates."""

import sys
from typing import Tuple, List, Dict, Any
from .verdict import RISK_LEVELS


def _validate_risk_level(risk_level: str) -> str:
    """Validate and normalize risk level from LLM response.

    Args:
        risk_level: Risk level string from LLM

    Returns:
        Normalized risk level ("low", "medium", or "high")
    """
    normalized = risk_level.lower().strip()
    if normalized in RISK_LEVELS:
        return normalized
    # Defensive default for malformed LLM responses
    sys.stderr.write(f"Warning: Invalid risk level '{risk_level}', defaulting to 'low'\n")
    return "low"


def _exceeds_threshold(risk_level: str, threshold: str) -> bool:
    """Check if risk level meets or exceeds threshold.

    Args:
        risk_level: Current risk level
        threshold: Threshold to check against

    Returns:
        True if risk_level >= threshold
    """
    risk_index = RISK_LEVELS.index(risk_level.lower())
    threshold_index = RISK_LEVELS.index(threshold.lower())
    return risk_index >= threshold_index
```

#### Step 1.2: Main Evaluation Function

```python
def evaluate_risk_buckets(
    data: dict,
    drift_threshold: str,
    intent_threshold: str,
    operations_threshold: str
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Evaluate risk buckets against thresholds.

    CRITICAL: This function expects PRE-FILTERED data containing ONLY
    medium/high-confidence resources. Low-confidence resources (Azure What-If
    noise) must be filtered out before calling this function.

    Args:
        data: Parsed LLM response with risk_assessment field (high-confidence only)
        drift_threshold: Fail if drift risk >= this (low|medium|high)
        intent_threshold: Fail if intent risk >= this (low|medium|high)
        operations_threshold: Fail if operations risk >= this (low|medium|high)

    Returns:
        Tuple of:
        - is_safe: True if all buckets pass their thresholds
        - failed_buckets: List of bucket names that exceeded thresholds
        - risk_assessment: Risk assessment dict from LLM response
    """
    # Extract risk assessment from LLM response
    risk_assessment = data.get("risk_assessment", {})

    # Handle missing risk assessment (defensive coding)
    if not risk_assessment:
        sys.stderr.write("Warning: No risk assessment in LLM response, defaulting to safe\n")
        return True, [], {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": "No risk assessment provided"}
        }

    # Extract bucket assessments
    drift_bucket = risk_assessment.get("drift", {})
    intent_bucket = risk_assessment.get("intent")  # May be None
    operations_bucket = risk_assessment.get("operations", {})

    # Validate and normalize risk levels
    drift_risk = _validate_risk_level(drift_bucket.get("risk_level", "low"))
    operations_risk = _validate_risk_level(operations_bucket.get("risk_level", "low"))

    # Evaluate each bucket against threshold
    failed_buckets = []

    # Drift bucket (always evaluated)
    if _exceeds_threshold(drift_risk, drift_threshold):
        failed_buckets.append("drift")

    # Intent bucket (only if evaluated by LLM - i.e., PR metadata provided)
    if intent_bucket is not None:
        intent_risk = _validate_risk_level(intent_bucket.get("risk_level", "low"))
        if _exceeds_threshold(intent_risk, intent_threshold):
            failed_buckets.append("intent")

    # Operations bucket (always evaluated)
    if _exceeds_threshold(operations_risk, operations_threshold):
        failed_buckets.append("operations")

    # Deployment is safe only if ALL buckets pass
    is_safe = len(failed_buckets) == 0

    return is_safe, failed_buckets, risk_assessment
```

### Task 2: Update Prompts for CI Mode

Ensure `bicep_whatif_advisor/prompt.py` CI mode system prompt includes detailed risk bucket definitions. This was started in Phase 2 but should be verified:

**Verify `_build_ci_system_prompt()` includes:**

1. Clear separation of three risk buckets
2. Risk level definitions (low/medium/high) for each bucket
3. Conditional intent bucket based on PR metadata
4. Complete JSON schema with all risk fields

**Example snippet to include:**

```python
def _build_ci_system_prompt(pr_title: str = None, pr_description: str = None) -> str:
    """Build system prompt for CI mode deployment safety review."""

    has_pr_metadata = bool(pr_title or pr_description)

    prompt = """You are an Azure infrastructure deployment safety reviewer. You are given:
1. The Azure What-If output showing planned infrastructure changes
2. The source code diff (Bicep/ARM template changes) that produced these changes
"""

    if has_pr_metadata:
        prompt += """3. The pull request title and description stating the INTENDED purpose of this change

Evaluate the deployment for safety and correctness across three independent risk buckets:
"""
    else:
        prompt += """
Evaluate the deployment for safety and correctness across TWO independent risk buckets:
(Note: Pull request intent alignment is NOT evaluated since no PR metadata was provided)
"""

    # Add risk bucket definitions
    prompt += """
## Risk Bucket 1: Infrastructure Drift

Compare What-If output to code diff. Identify resources changing that are NOT modified in the diff.

Risk levels:
- high: Critical resources drifting (security, identity, stateful), broad scope drift
- medium: Multiple resources drifting, configuration drift on important resources
- low: Minor drift (tags, display names), single resource drift on non-critical resources

## Risk Bucket 2: Risky Azure Operations

Evaluate inherent risk of operations, regardless of intent.

Risk levels:
- high: Deletion of stateful resources, RBAC deletions, broad network security changes, encryption changes, SKU downgrades
- medium: Behavioral modifications, new public endpoints, firewall changes
- low: Adding new resources, tags, diagnostic/monitoring resources
"""

    if has_pr_metadata:
        prompt += """
## Risk Bucket 3: Pull Request Intent Alignment

Compare What-If output to PR title/description. Flag unmentioned or unexpected changes.

Risk levels:
- high: Destructive changes not mentioned, security/auth changes not mentioned
- medium: Modifications not aligned with PR intent, unexpected resource types
- low: New resources not mentioned but aligned with intent, minor scope differences
"""

    # Add JSON schema (conditional on has_pr_metadata)
    # ... rest of prompt construction

    return prompt
```

### Task 3: Update CLI for Risk Evaluation

Update `bicep_whatif_advisor/cli.py` to add risk threshold flags and evaluation:

#### Step 3.1: Add CLI Options

```python
@click.command()
# ... existing options ...
@click.option("--ci", is_flag=True, help="Enable CI mode with deployment safety review")
@click.option("--diff-ref", type=str, default=None, help="Git reference for diff (default: auto-detect)")
@click.option("--pr-title", type=str, default=None, help="PR title (default: auto-detect)")
@click.option("--pr-description", type=str, default=None, help="PR description (default: auto-detect)")
@click.option("--drift-threshold", type=click.Choice(["low", "medium", "high"]), default="high",
              help="Drift risk threshold (default: high)")
@click.option("--intent-threshold", type=click.Choice(["low", "medium", "high"]), default="high",
              help="Intent risk threshold (default: high)")
@click.option("--operations-threshold", type=click.Choice(["low", "medium", "high"]), default="high",
              help="Operations risk threshold (default: high)")
@click.version_option(version=__version__)
def main(provider, model, format, verbose, ci, diff_ref, pr_title, pr_description,
         drift_threshold, intent_threshold, operations_threshold):
    """Analyze Azure What-If deployment output using LLMs."""
```

#### Step 3.2: CI Mode Evaluation

Update the CI mode section in `main()`:

```python
if ci:
    # Use auto-detected values as defaults, allow CLI overrides
    diff_ref = diff_ref or platform_ctx.get_diff_ref()
    pr_title = pr_title or platform_ctx.pr_title
    pr_description = pr_description or platform_ctx.pr_description

    # Get git diff
    from .ci.diff import get_diff
    diff_content = get_diff(diff_ref)

    if diff_content is None:
        sys.stderr.write("Warning: Could not get git diff. CI mode requires git diff.\n")
        sys.exit(2)

    # Build CI prompts
    system_prompt = build_system_prompt(
        ci_mode=True,
        pr_title=pr_title,
        pr_description=pr_description
    )
    user_prompt = build_user_prompt(
        whatif_content,
        diff_content=diff_content,
        pr_title=pr_title,
        pr_description=pr_description
    )

    # Call LLM
    response_text = llm_provider.complete(system_prompt, user_prompt)
    data = extract_json(response_text)

    # For now, assume data is already filtered (Phase 5 will add filtering)
    # In Phase 5, we'll add: high_conf_data, low_conf_data = filter_by_confidence(data)

    # Evaluate risk buckets
    from .ci.risk_buckets import evaluate_risk_buckets
    is_safe, failed_buckets, risk_assessment = evaluate_risk_buckets(
        data,
        drift_threshold,
        intent_threshold,
        operations_threshold
    )

    # Render output
    if format == "table":
        render_table(data, ci_mode=True)
    elif format == "json":
        render_json(data)
    elif format == "markdown":
        markdown = render_markdown(data, ci_mode=True)
        print(markdown)

    # Print verdict
    print()
    if is_safe:
        print("✅ SAFE: All risk buckets within acceptable thresholds")
        sys.exit(0)
    else:
        print(f"❌ UNSAFE: Failed buckets: {', '.join(failed_buckets)}")
        sys.exit(1)
```

### Task 4: Update Rendering for CI Mode

Ensure `bicep_whatif_advisor/render.py` properly displays risk assessment. This was started in Phase 2 but verify:

#### Step 4.1: Risk Bucket Summary Table

Verify `_print_risk_bucket_summary()` implementation shows all three buckets with proper handling of None intent bucket:

```python
def _print_risk_bucket_summary(console: Console, risk_assessment: dict, use_color: bool) -> None:
    """Print risk bucket summary table.

    Args:
        console: Rich console
        risk_assessment: Risk assessment dict from LLM
        use_color: Whether to use colors
    """
    bucket_table = Table(box=box.ROUNDED, show_header=True, padding=(0, 1))
    bucket_table.add_column("Risk Bucket", style="bold")
    bucket_table.add_column("Risk Level", justify="center")
    bucket_table.add_column("Status", justify="center")
    bucket_table.add_column("Key Concerns")

    # Drift bucket
    drift = risk_assessment.get("drift", {})
    drift_risk = drift.get("risk_level", "low")
    drift_concerns = drift.get("concerns", [])
    drift_symbol, drift_color = RISK_STYLES.get(drift_risk, ("", ""))

    bucket_table.add_row(
        "Infrastructure Drift",
        _colorize(drift_risk.capitalize(), drift_color, use_color),
        _colorize("●", drift_color, use_color),
        drift_concerns[0] if drift_concerns else "None"
    )

    # Intent bucket (may be None)
    intent = risk_assessment.get("intent")
    if intent is not None:
        intent_risk = intent.get("risk_level", "low")
        intent_concerns = intent.get("concerns", [])
        intent_symbol, intent_color = RISK_STYLES.get(intent_risk, ("", ""))

        bucket_table.add_row(
            "PR Intent Alignment",
            _colorize(intent_risk.capitalize(), intent_color, use_color),
            _colorize("●", intent_color, use_color),
            intent_concerns[0] if intent_concerns else "None"
        )
    else:
        bucket_table.add_row(
            "PR Intent Alignment",
            _colorize("Not evaluated", "dim", use_color),
            _colorize("-", "dim", use_color),
            "No PR metadata provided"
        )

    # Operations bucket
    operations = risk_assessment.get("operations", {})
    ops_risk = operations.get("risk_level", "low")
    ops_concerns = operations.get("concerns", [])
    ops_symbol, ops_color = RISK_STYLES.get(ops_risk, ("", ""))

    bucket_table.add_row(
        "Risky Operations",
        _colorize(ops_risk.capitalize(), ops_color, use_color),
        _colorize("●", ops_color, use_color),
        ops_concerns[0] if ops_concerns else "None"
    )

    console.print(bucket_table)
    console.print()
```

#### Step 4.2: Verdict Display

Verify `_print_ci_verdict()` shows safe/unsafe status:

```python
def _print_ci_verdict(console: Console, verdict: dict, use_color: bool) -> None:
    """Print CI mode verdict.

    Args:
        console: Rich console
        verdict: Verdict dict from LLM
        use_color: Whether to use colors
    """
    safe = verdict.get("safe", True)
    overall_risk = verdict.get("overall_risk_level", "low")
    highest_bucket = verdict.get("highest_risk_bucket", "none")
    reasoning = verdict.get("reasoning", "")

    # Print verdict header
    if safe:
        console.print(_colorize("Verdict: SAFE", "green", use_color), style="bold")
    else:
        console.print(_colorize("Verdict: UNSAFE", "red", use_color), style="bold")

    console.print()

    # Print details
    console.print(f"Overall Risk Level: {overall_risk.capitalize()}")

    if highest_bucket != "none":
        console.print(f"Highest Risk Bucket: {highest_bucket.capitalize()}")

    console.print(f"Reasoning: {reasoning}")
```

### Task 5: Testing

#### Step 5.1: Unit Tests

Create `tests/test_risk_buckets.py`:

```python
import pytest
from bicep_whatif_advisor.ci.risk_buckets import (
    evaluate_risk_buckets,
    _validate_risk_level,
    _exceeds_threshold,
)


def test_validate_risk_level():
    """Test risk level validation and normalization."""
    assert _validate_risk_level("low") == "low"
    assert _validate_risk_level("MEDIUM") == "medium"
    assert _validate_risk_level("High") == "high"
    assert _validate_risk_level("invalid") == "low"  # Default


def test_exceeds_threshold():
    """Test threshold comparison logic."""
    # low threshold
    assert _exceeds_threshold("low", "low") is True
    assert _exceeds_threshold("medium", "low") is True
    assert _exceeds_threshold("high", "low") is True

    # medium threshold
    assert _exceeds_threshold("low", "medium") is False
    assert _exceeds_threshold("medium", "medium") is True
    assert _exceeds_threshold("high", "medium") is True

    # high threshold
    assert _exceeds_threshold("low", "high") is False
    assert _exceeds_threshold("medium", "high") is False
    assert _exceeds_threshold("high", "high") is True


def test_evaluate_risk_buckets_all_pass():
    """Test all buckets passing thresholds."""
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": ""},
            "intent": {"risk_level": "low", "concerns": [], "reasoning": ""},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": ""}
        }
    }

    is_safe, failed, risk_assessment = evaluate_risk_buckets(
        data, "high", "high", "high"
    )

    assert is_safe is True
    assert failed == []


def test_evaluate_risk_buckets_drift_fails():
    """Test drift bucket failing."""
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "high", "concerns": ["Drift detected"], "reasoning": ""},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": ""}
        }
    }

    is_safe, failed, risk_assessment = evaluate_risk_buckets(
        data, "high", "high", "high"
    )

    assert is_safe is False
    assert "drift" in failed


def test_evaluate_risk_buckets_multiple_failures():
    """Test multiple buckets failing."""
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "high", "concerns": [], "reasoning": ""},
            "intent": {"risk_level": "medium", "concerns": [], "reasoning": ""},
            "operations": {"risk_level": "medium", "concerns": [], "reasoning": ""}
        }
    }

    is_safe, failed, risk_assessment = evaluate_risk_buckets(
        data, "medium", "medium", "medium"
    )

    assert is_safe is False
    assert set(failed) == {"drift", "intent", "operations"}


def test_evaluate_risk_buckets_no_intent():
    """Test with intent bucket missing (no PR metadata)."""
    data = {
        "risk_assessment": {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": ""},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": ""}
            # No "intent" key
        }
    }

    is_safe, failed, risk_assessment = evaluate_risk_buckets(
        data, "high", "high", "high"
    )

    assert is_safe is True
    assert failed == []


def test_evaluate_risk_buckets_missing_assessment():
    """Test graceful handling of missing risk assessment."""
    data = {
        "resources": []
        # No "risk_assessment" key
    }

    is_safe, failed, risk_assessment = evaluate_risk_buckets(
        data, "high", "high", "high"
    )

    assert is_safe is True  # Default to safe
    assert failed == []
    assert "drift" in risk_assessment
    assert "operations" in risk_assessment
```

#### Step 5.2: Integration Tests

Create `tests/test_ci_integration.py`:

```python
import pytest
from unittest.mock import Mock
from bicep_whatif_advisor.cli import main
from click.testing import CliRunner


def test_ci_mode_safe_deployment(mocker):
    """Test CI mode with safe deployment."""
    # Mock platform detection
    from bicep_whatif_advisor.ci.platform import PlatformContext
    mock_ctx = PlatformContext(
        platform="github",
        pr_number="123",
        pr_title="Add monitoring",
        base_branch="main"
    )
    mocker.patch('bicep_whatif_advisor.ci.platform.detect_platform', return_value=mock_ctx)

    # Mock git diff
    mocker.patch('bicep_whatif_advisor.ci.diff.get_diff', return_value="diff content")

    # Mock LLM provider
    mock_provider = Mock()
    mock_provider.complete.return_value = '''{
        "resources": [],
        "overall_summary": "No changes",
        "risk_assessment": {
            "drift": {"risk_level": "low", "concerns": [], "reasoning": ""},
            "intent": {"risk_level": "low", "concerns": [], "reasoning": ""},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": ""}
        },
        "verdict": {
            "safe": true,
            "highest_risk_bucket": "none",
            "overall_risk_level": "low",
            "reasoning": "All safe"
        }
    }'''
    mocker.patch('bicep_whatif_advisor.providers.get_provider', return_value=mock_provider)

    # Mock stdin
    mocker.patch('bicep_whatif_advisor.input.read_stdin', return_value="Resource changes:\n+ Create")

    # Run CLI
    runner = CliRunner()
    result = runner.invoke(main, ['--ci'])

    assert result.exit_code == 0
    assert "SAFE" in result.output


def test_ci_mode_unsafe_deployment(mocker):
    """Test CI mode with unsafe deployment."""
    # Similar setup but with high risk
    mock_provider = Mock()
    mock_provider.complete.return_value = '''{
        "resources": [],
        "overall_summary": "Drift detected",
        "risk_assessment": {
            "drift": {"risk_level": "high", "concerns": ["Critical drift"], "reasoning": ""},
            "operations": {"risk_level": "low", "concerns": [], "reasoning": ""}
        },
        "verdict": {
            "safe": false,
            "highest_risk_bucket": "drift",
            "overall_risk_level": "high",
            "reasoning": "Unsafe"
        }
    }'''
    mocker.patch('bicep_whatif_advisor.providers.get_provider', return_value=mock_provider)
    mocker.patch('bicep_whatif_advisor.input.read_stdin', return_value="Resource changes:\n+ Create")
    mocker.patch('bicep_whatif_advisor.ci.diff.get_diff', return_value="diff")

    runner = CliRunner()
    result = runner.invoke(main, ['--ci', '--drift-threshold', 'high'])

    assert result.exit_code == 1
    assert "UNSAFE" in result.output
```

#### Step 5.3: Manual Testing

```bash
# Test with different thresholds
cat tests/fixtures/mixed_changes.txt | bicep-whatif-advisor --ci \
  --drift-threshold medium \
  --intent-threshold medium \
  --operations-threshold medium

# Test exit codes
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --ci
echo "Exit code: $?"  # Should be 0 or 1

# Test without PR metadata (intent bucket skipped)
cat tests/fixtures/create_only.txt | bicep-whatif-advisor --ci --diff-ref HEAD~1
```

## Validation Checklist

- [ ] `ci/verdict.py` created with RISK_LEVELS constant
- [ ] `ci/risk_buckets.py` created
- [ ] `_validate_risk_level()` normalizes and validates risk levels
- [ ] `_exceeds_threshold()` compares using index-based logic
- [ ] `evaluate_risk_buckets()` evaluates all three buckets independently
- [ ] Intent bucket evaluation skipped if None
- [ ] Failed buckets list returned correctly
- [ ] is_safe is False if ANY bucket fails
- [ ] CLI threshold flags added (drift, intent, operations)
- [ ] CLI defaults to "high" thresholds
- [ ] CI mode calls evaluate_risk_buckets()
- [ ] Exit code 0 for safe, 1 for unsafe
- [ ] Risk bucket summary table displayed
- [ ] Verdict displayed with safe/unsafe status
- [ ] Intent bucket shows "Not evaluated" when None
- [ ] Unit tests pass for threshold logic
- [ ] Integration tests pass for safe/unsafe scenarios
- [ ] Manual testing confirms correct behavior

## Next Phase

Once Phase 4 is complete and validated, proceed to Phase 5 (Noise Filtering and PR Comments).

Phase 5 will add:
- LLM confidence scoring
- Pattern-based noise filtering
- Re-analysis after filtering in CI mode
- GitHub/Azure DevOps PR comment posting

## Notes

- Risk assessment operates on PRE-FILTERED data (Phase 5 adds filtering)
- All three buckets are independent - no cascading dependencies
- Threshold comparison uses >= operator (meets or exceeds)
- Intent bucket is truly optional - code must handle None safely
- Exit codes are critical for CI/CD pipeline integration
- Failed buckets list helps users understand why deployment blocked
