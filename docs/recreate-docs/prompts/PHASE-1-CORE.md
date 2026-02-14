# Phase 1 Implementation Prompt: Core Foundation

## Objective

Build the core CLI framework, input validation, and LLM provider system for the bicep-whatif-advisor project.

## Context

You are building a Python CLI tool that analyzes Azure What-If deployment output using LLMs. This phase establishes the foundation: project structure, CLI argument parsing, input validation, and a pluggable provider system for multiple LLM backends.

## Specifications to Reference

Read these specification files before starting:
- `specifications/00-OVERVIEW.md` - Project architecture
- `specifications/01-CLI-INPUT.md` - CLI and input handling details
- `specifications/02-PROVIDER-SYSTEM.md` - Provider architecture

## Tasks

### Task 1: Project Structure and Packaging

Create the project structure:

```
bicep-whatif-advisor/
├── bicep_whatif_advisor/
│   ├── __init__.py
│   ├── cli.py
│   ├── input.py
│   └── providers/
│       ├── __init__.py
│       ├── anthropic.py
│       ├── azure_openai.py
│       └── ollama.py
├── tests/
│   └── fixtures/
├── pyproject.toml
├── README.md
└── LICENSE
```

**Create `pyproject.toml`:**

```toml
[build-system]
requires = ["setuptools>=61.0"]
build-backend = "setuptools.build_meta"

[project]
name = "bicep-whatif-advisor"
version = "1.4.0"
description = "AI-powered Azure Bicep What-If deployment advisor with automated safety reviews"
readme = "README.md"
requires-python = ">=3.8"
license = {text = "MIT"}
authors = [
    {name = "Azure Tools Contributors"}
]
keywords = ["azure", "bicep", "arm", "deployment", "what-if", "llm", "infrastructure"]
classifiers = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.8",
    "Programming Language :: Python :: 3.9",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
]

dependencies = [
    "click>=8.0.0",
    "rich>=13.0.0",
    "requests>=2.31.0",
]

[project.optional-dependencies]
anthropic = ["anthropic>=0.40.0"]
azure = ["openai>=1.0.0"]
ollama = ["requests>=2.31.0"]
all = [
    "anthropic>=0.40.0",
    "openai>=1.0.0",
    "requests>=2.31.0",
]
dev = [
    "pytest>=7.0.0",
    "pytest-mock>=3.10.0",
]

[project.scripts]
bicep-whatif-advisor = "bicep_whatif_advisor.cli:main"

[project.urls]
Homepage = "https://github.com/neilpeterson/bicep-whatif-advisor"
Issues = "https://github.com/neilpeterson/bicep-whatif-advisor/issues"

[tool.setuptools.packages.find]
where = ["."]
include = ["bicep_whatif_advisor*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --strict-markers"
```

**Create `bicep_whatif_advisor/__init__.py`:**

```python
"""bicep-whatif-advisor: AI-powered Azure deployment safety gate."""

__version__ = "1.4.0"
```

### Task 2: Input Validation (input.py)

Create `bicep_whatif_advisor/input.py`:

**Requirements:**
1. Define `InputError` exception class
2. Implement `read_stdin()` function that:
   - Detects if stdin is a TTY (terminal) and shows usage hint
   - Validates input contains What-If markers
   - Truncates inputs exceeding 100,000 characters
   - Returns validated content as string

**What-If Markers to Check:**
- "Resource changes:"
- "Resource and property changes:"
- Action symbols: "+ Create", "~ Modify", "- Delete", "= Deploy", "* NoChange", "x Ignore"

**Error Messages:**
- TTY: "Error: No input provided. Pipe Azure What-If output to this command:\n\naz deployment group what-if ... | bicep-whatif-advisor\n"
- Invalid: "Error: Input does not appear to be Azure What-If output"
- Truncation: "Warning: Input truncated to 100,000 characters to avoid excessive API costs.\n" (to stderr)

**Reference:** `specifications/01-CLI-INPUT.md` section "Input Validation"

### Task 3: Provider System (providers/)

#### Step 3.1: Provider Base Class

Create `bicep_whatif_advisor/providers/__init__.py`:

```python
"""LLM provider interfaces."""

from abc import ABC, abstractmethod


class Provider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to LLM and return raw response text.

        Args:
            system_prompt: System-level instructions
            user_prompt: User content (What-If output + context)

        Returns:
            Raw text response from LLM

        Raises:
            Exception: If API call fails
        """
        pass


def get_provider(provider_name: str, model: str = None) -> Provider:
    """Get provider instance by name.

    Args:
        provider_name: Provider identifier (anthropic, azure-openai, ollama)
        model: Optional model override

    Returns:
        Initialized provider instance

    Raises:
        ValueError: If provider_name is invalid
        ImportError: If provider SDK not installed
    """
    if provider_name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model)
    elif provider_name == "azure-openai":
        from .azure_openai import AzureOpenAIProvider
        return AzureOpenAIProvider(model)
    elif provider_name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(model)
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
```

#### Step 3.2: Anthropic Provider

Create `bicep_whatif_advisor/providers/anthropic.py`:

**Requirements:**
- Import anthropic SDK (with try/except for ImportError)
- Get API key from `ANTHROPIC_API_KEY` environment variable
- Default model: `claude-sonnet-4-20250514`
- Use temperature 0, max_tokens 16000
- Return text from first content block

**Error Messages:**
- Missing SDK: "Anthropic SDK not installed. Install with: pip install bicep-whatif-advisor[anthropic]"
- Missing API key: "Missing ANTHROPIC_API_KEY environment variable. Get your API key from https://console.anthropic.com/"

**Reference:** `specifications/02-PROVIDER-SYSTEM.md` section "Anthropic Provider"

#### Step 3.3: Azure OpenAI Provider

Create `bicep_whatif_advisor/providers/azure_openai.py`:

**Requirements:**
- Import `AzureOpenAI` from openai SDK (with try/except for ImportError)
- Get environment variables: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_DEPLOYMENT`
- Use API version: `2024-02-15-preview`
- Use temperature 0, max_tokens 16000
- Return content from first choice

**Error Messages:**
- Missing SDK: "OpenAI SDK not installed. Install with: pip install bicep-whatif-advisor[azure]"
- Missing endpoint: "Missing AZURE_OPENAI_ENDPOINT environment variable"
- Missing API key: "Missing AZURE_OPENAI_API_KEY environment variable"
- Missing deployment: "Missing deployment name. Set AZURE_OPENAI_DEPLOYMENT or use --model flag"

**Reference:** `specifications/02-PROVIDER-SYSTEM.md` section "Azure OpenAI Provider"

#### Step 3.4: Ollama Provider

Create `bicep_whatif_advisor/providers/ollama.py`:

**Requirements:**
- Use requests library (no external SDK needed)
- Get base URL from `OLLAMA_BASE_URL` (default: `http://localhost:11434`)
- Default model: `llama3.1`
- Use temperature 0, stream: false, timeout: 120 seconds
- Return content from response

**Error Messages:**
- API error: "Ollama API error: {exception_message}"

**Reference:** `specifications/02-PROVIDER-SYSTEM.md` section "Ollama Provider"

### Task 4: CLI Framework (cli.py)

Create `bicep_whatif_advisor/cli.py`:

**Requirements:**

1. **Imports:**
   ```python
   import os
   import sys
   import json
   from typing import Optional
   import click
   from . import __version__
   from .input import read_stdin, InputError
   # More imports will be added in later phases
   ```

2. **Create `extract_json()` helper function:**
   - Try parsing as-is first
   - Find balanced braces if direct parsing fails
   - Handle nested JSON, string escaping
   - Raise ValueError if no valid JSON found

3. **Create Click command with these options (minimal for Phase 1):**
   ```python
   @click.command()
   @click.option("--provider", "-p", type=click.Choice([...]), default="anthropic")
   @click.option("--model", "-m", type=str, default=None)
   @click.option("--format", "-f", type=click.Choice([...]), default="table")
   @click.version_option(version=__version__)
   def main(provider, model, format):
       """Analyze Azure What-If deployment output using LLMs."""
   ```

4. **Main function structure:**
   ```python
   def main(...):
       try:
           # Read stdin
           whatif_content = read_stdin()

           # Get provider
           llm_provider = get_provider(provider, model)

           # TODO: Build prompts (Phase 2)
           # TODO: Call LLM (Phase 2)
           # TODO: Parse response (Phase 2)
           # TODO: Render output (Phase 2)

           # For now, just print a success message
           print(f"Successfully validated What-If input ({len(whatif_content)} chars)")
           print(f"Provider: {provider}")
           sys.exit(0)

       except InputError as e:
           sys.stderr.write(f"Error: {e}\n")
           sys.exit(2)
       except KeyboardInterrupt:
           sys.stderr.write("\nInterrupted by user.\n")
           sys.exit(130)
       except Exception as e:
           sys.stderr.write(f"Error: {e}\n")
           sys.exit(1)
   ```

**Reference:** `specifications/01-CLI-INPUT.md` section "Orchestration Logic"

### Task 5: Testing

Create basic test to validate the phase 1 deliverables:

```bash
# Test 1: CLI loads and shows help
python -m bicep_whatif_advisor.cli --help

# Test 2: Input validation rejects empty input
echo "" | python -m bicep_whatif_advisor.cli
# Should exit with code 2

# Test 3: Provider initialization
python -c "from bicep_whatif_advisor.providers import get_provider; print(get_provider('anthropic'))"
# Should fail with missing API key error

# Test 4: Version display
python -m bicep_whatif_advisor.cli --version
# Should show: bicep-whatif-advisor, version 1.4.0
```

## Validation Checklist

- [ ] `pyproject.toml` created with all dependencies
- [ ] `bicep_whatif_advisor/__init__.py` created with version
- [ ] `bicep_whatif_advisor/input.py` created with `read_stdin()` and `InputError`
- [ ] TTY detection works (shows usage hint if not piped)
- [ ] What-If marker validation works (rejects invalid input)
- [ ] Input truncation works (100K limit)
- [ ] Provider base class created in `providers/__init__.py`
- [ ] `get_provider()` registry function works
- [ ] Anthropic provider created and initializes correctly
- [ ] Azure OpenAI provider created and initializes correctly
- [ ] Ollama provider created and initializes correctly
- [ ] All providers validate API keys/configuration
- [ ] All providers show clear error messages when misconfigured
- [ ] `cli.py` created with Click command
- [ ] CLI shows help text
- [ ] CLI shows version
- [ ] CLI reads stdin successfully
- [ ] CLI initializes provider successfully
- [ ] Error handling works (exit codes 0, 1, 2, 130)

## Next Phase

Once Phase 1 is complete and validated, proceed to Phase 2 (Prompt Engineering and Output Rendering).

Phase 2 will add:
- Prompt construction (system + user prompts)
- LLM API calls
- JSON response parsing
- Output rendering (table, JSON, markdown)

## Notes

- Use type hints for all function signatures
- Write clear docstrings for all functions and classes
- Follow PEP 8 style guidelines
- Keep functions focused and single-purpose
- Write defensive code (validate inputs, handle errors gracefully)
