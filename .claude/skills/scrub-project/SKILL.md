---
name: scrub-project
description: Clean up project by removing unnecessary code and updating documentation
---

# Project Scrub Command

Performs comprehensive project cleanup: removes unnecessary code, simplifies where possible, and ensures all documentation is current.

## Workflow:

### 1. **Pre-Scrub Assessment**
   - Read `CLAUDE.md` to understand current project state and structure
   - Review README.md to understand intended functionality
   - Create a checklist of areas to review
   - Ask user if there are specific areas of concern

### 2. **Code Cleanup**

   **A. Find Unused Code:**
   - Run `ruff check .` to find code quality issues
   - Check for unused imports, variables, and functions
   - Look for:
     - Commented-out code blocks
     - Unused imports (F401 in ruff)
     - Dead code paths
     - TODO/FIXME comments that need action or removal
     - Unreachable code after returns

   **B. Simplification Opportunities:**
   - Look for overly complex functions (C901 complexity in ruff)
   - Check for repeated code that could be refactored
   - Find magic numbers that should be constants
   - Identify functions that could be simplified
   - Check for unnecessary else clauses after return statements

   **C. File Organization:**
   - Check Python package structure (bicep_whatif_advisor/)
   - Look for duplicate or redundant files
   - Verify test fixtures in tests/fixtures/ are current
   - Verify bicep-sample/ examples are working
   - Check for temporary files (.pyc, __pycache__, .pytest_cache, etc.)
   - Check for empty __init__.py files that could be removed (Python 3.3+)

### 3. **Configuration & Build Files**

   **Review:**
   - `pyproject.toml` - Ensure dependencies are correct and minimal
   - `requirements.txt` or equivalent - Check if present and needed (should use pyproject.toml)
   - `.github/workflows/` - Ensure CI/CD configs are current
   - `ruff.toml` or ruff config in pyproject.toml - Check linter settings

   **Actions:**
   - Remove any unused dependencies from pyproject.toml
   - Update outdated package versions if needed
   - Simplify configuration where possible
   - Ensure optional dependencies are properly categorized

### 4. **Documentation Review**

   **A. README.md:**
   - Verify installation instructions work (`pip install -e .`)
   - Check all CLI examples are current and correct
   - Ensure feature list matches implementation
   - Verify links are not broken
   - Update roadmap/status if needed
   - Check that Quick Start examples actually work
   - Verify environment variable documentation is accurate

   **B. docs/IMPLEMENTATION_GUIDE.md:**
   - Verify installation steps are current
   - Check usage examples work
   - Ensure provider configuration examples are correct
   - Update any changed CLI flags or options
   - Verify output format examples match current implementation

   **C. docs/PIPELINE.md:**
   - Verify CI/CD integration examples are correct
   - Check GitHub Actions and Azure DevOps examples work
   - Ensure environment variable documentation is accurate
   - Update threshold and flag documentation
   - Verify PR comment format examples

   **D. docs/bicep-whatif-advisor-spec.md:**
   - Check if original spec is still accurate
   - Note any deviations from spec in current implementation
   - Consider archiving if superseded by other docs

   **E. CLAUDE.md:**
   - Verify project structure diagram matches actual layout
   - Check command examples are correct
   - Update tech stack if dependencies changed
   - Review development commands for accuracy
   - Ensure architecture notes reflect current implementation
   - Update Future Improvements section based on completed work

### 5. **Examples & Tests**

   **Test Fixtures (tests/fixtures/):**
   - Verify all fixture files are used by tests
   - Check for outdated or redundant fixtures
   - Ensure fixtures represent realistic What-If outputs
   - Remove any unused fixture files

   **Bicep Sample (bicep-sample/):**
   - Verify the sample Bicep template still works
   - Test the documented What-If command
   - Check that parameter files are current
   - Ensure example is referenced in documentation

   **Tests:**
   - Run full test suite: `pytest`
   - Check test coverage: `pytest --cov=bicep_whatif_advisor`
   - Look for obsolete tests
   - Ensure test names are descriptive
   - Check for skipped or disabled tests that should be removed
   - Verify mock configurations are still needed

### 6. **Dependencies**

   **Review:**
   - Check `pyproject.toml` for all dependencies
   - Verify core dependencies vs optional extras (anthropic, all, dev)
   - Look for unused imports in actual code
   - Check if any dependencies can be removed
   - Verify version constraints are appropriate
   - Test installation with: `pip install -e .[all,dev]`

### 7. **Repository Hygiene**

   **Check for:**
   - Uncommitted changes: `git status`
   - Untracked files that should be committed or gitignored
   - Large files that shouldn't be in repo
   - Sensitive data (API keys, credentials)
   - Branches that can be deleted

### 8. **Create Summary Report**

   **Document all changes made:**
   - What was removed and why
   - What was simplified
   - Documentation updates made
   - Any issues found but not fixed (and why)
   - Recommendations for future cleanup
   - Any Python-specific issues (unused imports, type hints, etc.)

### 9. **Update CLAUDE.md**

   - Update "Future Improvements / Backlog" section
   - Remove completed items
   - Add any new technical debt identified
   - Update project status if significant changes made

### 10. **Commit Changes**

   - Stage all changes
   - Create detailed commit message explaining cleanup
   - Follow project convention: include co-author line
   - Suggest whether changes should be in one commit or split
   - Ask user if they want to create PR or push directly

## Important Notes:

- **Be Conservative**: Only remove code you're certain is unused
- **Preserve History**: Don't remove comments that explain "why" decisions were made
- **Test After Changes**: Run tests after any code modifications
- **Ask Before Big Changes**: If unsure about removing something, ask the user
- **Document Everything**: Keep track of what was removed for the summary

## Tools to Use:

- `ruff check .` - Find code quality issues
- `ruff format .` - Format code consistently
- `pytest` - Run test suite
- `pytest --cov=bicep_whatif_advisor` - Check test coverage
- `pip install -e .[all,dev]` - Verify dependencies install
- `git status` - Check for untracked files
- Task tool with Explore agent - For comprehensive code exploration
- Grep tool - Search for patterns (TODO, FIXME, unused imports, etc.)
- Read tool - Review documentation files
- `cat tests/fixtures/*.txt | python -m bicep_whatif_advisor.cli` - Test CLI with fixtures

## Success Criteria:

- ✅ All tests still pass (`pytest`)
- ✅ All documentation is current and accurate
- ✅ No unnecessary files or __pycache__ directories remain
- ✅ Bicep sample example works
- ✅ Test fixtures are all used and relevant
- ✅ Dependencies in pyproject.toml are minimal
- ✅ Code passes `ruff check .` with no errors
- ✅ CLAUDE.md accurately reflects project state

## Example Usage:

```bash
/scrub
```

The command will systematically go through all areas and report findings.