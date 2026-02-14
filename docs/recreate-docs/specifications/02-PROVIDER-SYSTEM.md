# Feature Specification: LLM Provider System

## Overview

The provider system is a pluggable architecture for supporting multiple LLM backends. It uses abstract base classes and a provider registry pattern.

## Design Principles

1. **Provider Agnostic** - Core logic doesn't depend on specific provider
2. **Lazy Loading** - Provider SDKs only imported when needed
3. **Clear Interface** - All providers implement same contract
4. **Graceful Degradation** - Missing API keys produce clear error messages
5. **Deterministic Output** - All providers use temperature 0

## Provider Interface

### Module: `providers/__init__.py`

### Base Class

```python
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
```

### Provider Registry

```python
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

## Anthropic Provider

### Module: `providers/anthropic.py`

### Implementation

```python
import os
from . import Provider

class AnthropicProvider(Provider):
    """Anthropic Claude provider."""

    def __init__(self, model: str = None):
        """Initialize Anthropic provider.

        Args:
            model: Optional model override (default: claude-sonnet-4-20250514)
        """
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "Anthropic SDK not installed. "
                "Install with: pip install bicep-whatif-advisor[anthropic]"
            )

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "Missing ANTHROPIC_API_KEY environment variable. "
                "Get your API key from https://console.anthropic.com/"
            )

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model or "claude-sonnet-4-20250514"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Call Anthropic API."""
        response = self.client.messages.create(
            model=self.model,
            max_tokens=16000,
            temperature=0,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        # Extract text from response
        return response.content[0].text
```

### Configuration

**Environment Variables:**
- `ANTHROPIC_API_KEY` (required)

**Default Model:**
- `claude-sonnet-4-20250514`

**Parameters:**
- Temperature: 0 (deterministic)
- Max tokens: 16,000

## Azure OpenAI Provider

### Module: `providers/azure_openai.py`

### Implementation

```python
import os
from . import Provider

class AzureOpenAIProvider(Provider):
    """Azure OpenAI provider."""

    def __init__(self, model: str = None):
        """Initialize Azure OpenAI provider.

        Args:
            model: Deployment name (required for Azure OpenAI)
        """
        try:
            from openai import AzureOpenAI
        except ImportError:
            raise ImportError(
                "OpenAI SDK not installed. "
                "Install with: pip install bicep-whatif-advisor[azure]"
            )

        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")

        if not endpoint:
            raise ValueError("Missing AZURE_OPENAI_ENDPOINT environment variable")
        if not api_key:
            raise ValueError("Missing AZURE_OPENAI_API_KEY environment variable")
        if not deployment:
            raise ValueError(
                "Missing deployment name. "
                "Set AZURE_OPENAI_DEPLOYMENT or use --model flag"
            )

        self.client = AzureOpenAI(
            api_version="2024-02-15-preview",
            azure_endpoint=endpoint,
            api_key=api_key
        )
        self.deployment = deployment

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Call Azure OpenAI API."""
        response = self.client.chat.completions.create(
            model=self.deployment,
            temperature=0,
            max_tokens=16000,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        return response.choices[0].message.content
```

### Configuration

**Environment Variables:**
- `AZURE_OPENAI_ENDPOINT` (required)
- `AZURE_OPENAI_API_KEY` (required)
- `AZURE_OPENAI_DEPLOYMENT` (required if --model not specified)

**Parameters:**
- Temperature: 0 (deterministic)
- Max tokens: 16,000
- API version: 2024-02-15-preview

## Ollama Provider

### Module: `providers/ollama.py`

### Implementation

```python
import os
import requests
from . import Provider

class OllamaProvider(Provider):
    """Ollama local LLM provider."""

    def __init__(self, model: str = None):
        """Initialize Ollama provider.

        Args:
            model: Model name (default: llama3.1)
        """
        self.base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or "llama3.1"

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Call Ollama API."""
        url = f"{self.base_url}/api/chat"

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "stream": False,
            "options": {
                "temperature": 0
            }
        }

        try:
            response = requests.post(url, json=payload, timeout=120)
            response.raise_for_status()
            data = response.json()
            return data["message"]["content"]
        except requests.RequestException as e:
            raise Exception(f"Ollama API error: {e}")
```

### Configuration

**Environment Variables:**
- `OLLAMA_BASE_URL` (optional, default: http://localhost:11434)

**Default Model:**
- `llama3.1`

**Parameters:**
- Temperature: 0 (deterministic)
- Stream: False
- Timeout: 120 seconds

## Error Handling

### Missing API Keys

Clear, actionable error messages:

```python
raise ValueError(
    "Missing ANTHROPIC_API_KEY environment variable. "
    "Get your API key from https://console.anthropic.com/"
)
```

### Missing SDK

Instruct users on installation:

```python
raise ImportError(
    "Anthropic SDK not installed. "
    "Install with: pip install bicep-whatif-advisor[anthropic]"
)
```

### Network Errors

Ollama provider uses requests with timeout and proper exception handling:

```python
try:
    response = requests.post(url, json=payload, timeout=120)
    response.raise_for_status()
except requests.RequestException as e:
    raise Exception(f"Ollama API error: {e}")
```

## Adding New Providers

To add a new provider:

1. Create `providers/new_provider.py`
2. Implement `Provider` base class
3. Add to registry in `providers/__init__.py`
4. Update CLI choices in `cli.py`
5. Document in README

Example skeleton:

```python
from . import Provider

class NewProvider(Provider):
    def __init__(self, model: str = None):
        # Initialize SDK
        # Validate environment variables
        pass

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        # Call API
        # Return text response
        pass
```

## Implementation Checklist

- [ ] Create `providers/__init__.py` with `Provider` base class
- [ ] Implement `get_provider()` registry function
- [ ] Create `providers/anthropic.py`
- [ ] Implement `AnthropicProvider.__init__()`
- [ ] Implement `AnthropicProvider.complete()`
- [ ] Add Anthropic API key validation
- [ ] Create `providers/azure_openai.py`
- [ ] Implement `AzureOpenAIProvider.__init__()`
- [ ] Implement `AzureOpenAIProvider.complete()`
- [ ] Add Azure OpenAI configuration validation
- [ ] Create `providers/ollama.py`
- [ ] Implement `OllamaProvider.__init__()`
- [ ] Implement `OllamaProvider.complete()`
- [ ] Add requests timeout and error handling
- [ ] Test all three providers with sample prompts
- [ ] Test missing API key errors
- [ ] Test missing SDK errors
- [ ] Document provider-specific environment variables
