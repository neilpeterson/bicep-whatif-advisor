# 03 - Provider System (LLM Abstraction)

## Purpose

The provider system abstracts differences between LLM APIs (Anthropic Claude, Azure OpenAI, Ollama) behind a common interface. This enables easy provider switching, consistent behavior, and local development without API costs.

**Files:**
- `bicep_whatif_advisor/providers/__init__.py` - Abstract base class and factory
- `bicep_whatif_advisor/providers/anthropic.py` - Anthropic Claude implementation
- `bicep_whatif_advisor/providers/azure_openai.py` - Azure OpenAI implementation
- `bicep_whatif_advisor/providers/ollama.py` - Ollama local LLM implementation

## Architecture

### Provider Interface (Abstract Base Class)

**File:** `providers/__init__.py` (lines 7-24)

```python
from abc import ABC, abstractmethod

class Provider(ABC):
    """Base class for LLM providers."""

    @abstractmethod
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to the LLM and return the raw response text.

        Args:
            system_prompt: The system prompt defining the assistant's behavior
            user_prompt: The user's prompt with the content to analyze

        Returns:
            Raw response text from the LLM (should be JSON)

        Raises:
            Exception: On API errors, missing credentials, etc.
        """
        pass
```

**Design Principles:**
1. **Single method interface:** All providers must implement `complete()`
2. **Consistent inputs:** All providers receive system + user prompts
3. **Consistent output:** All providers return raw text (JSON string)
4. **Error handling:** All providers raise exceptions on failure

**Why Abstract Base Class?**
- Enforces interface compliance at import time
- Type hints enable IDE autocomplete
- Clear contract for adding new providers

### Factory Pattern

**File:** `providers/__init__.py` (lines 27-58)

```python
def get_provider(name: str, model: str = None) -> Provider:
    """Get a provider instance by name.

    Args:
        name: Provider name (anthropic, azure-openai, or ollama)
        model: Optional model override

    Returns:
        Provider instance configured with the specified model

    Raises:
        ValueError: If provider name is invalid
        ImportError: If required SDK is not installed
    """
    # Allow environment variable override
    provider_name = os.environ.get("WHATIF_PROVIDER", name)
    model_name = os.environ.get("WHATIF_MODEL", model)

    if provider_name == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model=model_name)
    elif provider_name == "azure-openai":
        from .azure_openai import AzureOpenAIProvider
        return AzureOpenAIProvider(model=model_name)
    elif provider_name == "ollama":
        from .ollama import OllamaProvider
        return OllamaProvider(model=model_name)
    else:
        raise ValueError(
            f"Unknown provider: {provider_name}. "
            f"Valid options are: anthropic, azure-openai, ollama"
        )
```

**Features:**
- **Lazy imports:** Only import provider SDK when needed
- **Environment override:** `WHATIF_PROVIDER` and `WHATIF_MODEL` env vars
- **Clear errors:** ValueError with list of valid options

**Usage:**
```python
# In cli.py
llm_provider = get_provider(provider, model)
response_text = llm_provider.complete(system_prompt, user_prompt)
```

## Provider Implementations

### 1. Anthropic Claude Provider

**File:** `providers/anthropic.py` (99 lines)

#### Configuration

```python
class AnthropicProvider(Provider):
    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, model: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
```

| Setting | Value | Source |
|---------|-------|--------|
| Default Model | `claude-sonnet-4-20250514` | Class constant |
| API Key | Required | `ANTHROPIC_API_KEY` env var |
| Model Override | Optional | Constructor parameter or `WHATIF_MODEL` env var |

#### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` | ✅ Yes | API authentication |
| `WHATIF_MODEL` | ❌ No | Model override (via factory) |

**Missing API Key Error:**
```
Error: ANTHROPIC_API_KEY environment variable not set.
Get your API key from: https://console.anthropic.com/
```

#### complete() Implementation (lines 30-98)

```python
def complete(self, system_prompt: str, user_prompt: str) -> str:
    try:
        from anthropic import Anthropic, APIError, RateLimitError
    except ImportError:
        sys.stderr.write(
            "Error: anthropic package not installed.\n"
            "Install it with: pip install bicep-whatif-advisor[anthropic]\n"
        )
        sys.exit(1)

    client = Anthropic(api_key=self.api_key)

    # Try with automatic retry on network errors
    for attempt in range(2):
        try:
            response = client.messages.create(
                model=self.model,
                max_tokens=4096,
                temperature=0,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.content[0].text

        except RateLimitError as e:
            sys.stderr.write(
                f"Error: Rate limited by Anthropic API.\n"
                f"Try again in a moment. Details: {e}\n"
            )
            sys.exit(1)

        except APIError as e:
            if attempt == 0:
                # First attempt failed, retry once
                sys.stderr.write(f"Network error, retrying... ({e})\n")
                time.sleep(1)
                continue
            else:
                # Second attempt failed
                sys.stderr.write(
                    f"Error: Network error contacting Anthropic API after retry.\n"
                    f"Details: {e}\n"
                )
                sys.exit(1)

        except Exception as e:
            sys.stderr.write(
                f"Error: Unexpected error calling Anthropic API.\n"
                f"Details: {e}\n"
            )
            sys.exit(1)
```

**API Parameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `model` | `claude-sonnet-4-20250514` | Latest Sonnet model (as of v1.4.0) |
| `max_tokens` | `4096` | Sufficient for JSON responses with 50+ resources |
| `temperature` | `0` | Deterministic output for consistent risk assessment |
| `system` | System prompt | Defines assistant behavior |
| `messages` | Single user message | Contains What-If output and context |

**Retry Logic:**
- **Attempts:** 2 (initial + 1 retry)
- **Backoff:** 1 second fixed delay
- **Retryable errors:** `APIError` (network/server errors)
- **Non-retryable errors:** `RateLimitError` (immediate fail)

**Error Handling:**

| Error Type | Behavior |
|------------|----------|
| `ImportError` | Exit with installation instructions |
| `RateLimitError` | Exit immediately (no retry) |
| `APIError` | Retry once with 1s delay |
| Other exceptions | Exit with error details |

### 2. Azure OpenAI Provider

**File:** `providers/azure_openai.py` (110 lines)

#### Configuration

```python
class AzureOpenAIProvider(Provider):
    def __init__(self, model: str = None):
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        self.deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")
```

**No default model:** Azure OpenAI uses deployment names, which are user-defined.

#### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `AZURE_OPENAI_ENDPOINT` | ✅ Yes | Azure resource endpoint URL |
| `AZURE_OPENAI_API_KEY` | ✅ Yes | API authentication |
| `AZURE_OPENAI_DEPLOYMENT` | ✅ Yes | Deployment name (unless `--model` flag used) |

**Missing Variables Error:**
```
Error: Missing required environment variables: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY
Set them to use Azure OpenAI provider.
```

#### complete() Implementation (lines 38-109)

```python
def complete(self, system_prompt: str, user_prompt: str) -> str:
    try:
        from openai import AzureOpenAI, APIError, RateLimitError
    except ImportError:
        sys.stderr.write(
            "Error: openai package not installed.\n"
            "Install it with: pip install bicep-whatif-advisor[azure]\n"
        )
        sys.exit(1)

    client = AzureOpenAI(
        azure_endpoint=self.endpoint,
        api_key=self.api_key,
        api_version="2024-02-15-preview"
    )

    # Try with automatic retry on network errors
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=self.deployment,
                temperature=0,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            sys.stderr.write(
                f"Error: Rate limited by Azure OpenAI API.\n"
                f"Try again in a moment. Details: {e}\n"
            )
            sys.exit(1)

        except APIError as e:
            if attempt == 0:
                sys.stderr.write(f"Network error, retrying... ({e})\n")
                time.sleep(1)
                continue
            else:
                sys.stderr.write(
                    f"Error: Network error contacting Azure OpenAI API after retry.\n"
                    f"Details: {e}\n"
                )
                sys.exit(1)

        except Exception as e:
            sys.stderr.write(
                f"Error: Unexpected error calling Azure OpenAI API.\n"
                f"Details: {e}\n"
            )
            sys.exit(1)
```

**API Parameters:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `api_version` | `2024-02-15-preview` | Stable Azure OpenAI API version |
| `model` | User's deployment name | Deployment-specific (e.g., "gpt-4") |
| `temperature` | `0` | Deterministic output |
| `messages` | System + user messages | OpenAI chat format |

**Note:** Unlike Anthropic, Azure OpenAI uses `messages` array for both system and user prompts.

**Retry Logic:** Identical to Anthropic provider (2 attempts, 1s delay).

### 3. Ollama Local LLM Provider

**File:** `providers/ollama.py` (107 lines)

#### Configuration

```python
class OllamaProvider(Provider):
    DEFAULT_MODEL = "llama3.1"
    DEFAULT_HOST = "http://localhost:11434"

    def __init__(self, model: str = None):
        self.model = model or self.DEFAULT_MODEL
        self.host = os.environ.get("OLLAMA_HOST", self.DEFAULT_HOST)
```

| Setting | Value | Source |
|---------|-------|--------|
| Default Model | `llama3.1` | Class constant |
| Default Host | `http://localhost:11434` | Class constant |
| API Key | Not required | Local server |

#### Environment Variables

| Variable | Required | Purpose | Default |
|----------|----------|---------|---------|
| `OLLAMA_HOST` | ❌ No | Ollama server URL | `http://localhost:11434` |
| `WHATIF_MODEL` | ❌ No | Model override | `llama3.1` |

#### complete() Implementation (lines 24-106)

```python
def complete(self, system_prompt: str, user_prompt: str) -> str:
    try:
        import requests
    except ImportError:
        sys.stderr.write(
            "Error: requests package not installed.\n"
            "Install it with: pip install bicep-whatif-advisor[ollama]\n"
        )
        sys.exit(1)

    # Combine system and user prompts for Ollama
    combined_prompt = f"{system_prompt}\n\n{user_prompt}"

    url = f"{self.host}/api/generate"
    payload = {
        "model": self.model,
        "prompt": combined_prompt,
        "stream": False,
        "options": {
            "temperature": 0
        }
    }

    # Try with automatic retry on network errors
    for attempt in range(2):
        try:
            response = requests.post(url, json=payload, timeout=120, verify=True)
            response.raise_for_status()

            data = response.json()
            return data.get("response", "")

        except requests.exceptions.ConnectionError:
            if attempt == 0:
                sys.stderr.write(f"Connection error, retrying...\n")
                time.sleep(1)
                continue
            else:
                sys.stderr.write(
                    f"Error: Cannot reach Ollama at {self.host}.\n"
                    f"Make sure Ollama is running and try again.\n"
                    f"Start Ollama with: ollama serve\n"
                )
                sys.exit(1)

        except requests.exceptions.Timeout:
            sys.stderr.write(
                f"Error: Request to Ollama timed out.\n"
                f"The model may be too slow or the prompt too large.\n"
            )
            sys.exit(1)

        except requests.exceptions.HTTPError as e:
            sys.stderr.write(
                f"Error: HTTP error from Ollama API.\n"
                f"Details: {e}\n"
            )
            sys.exit(1)

        except Exception as e:
            sys.stderr.write(
                f"Error: Unexpected error calling Ollama API.\n"
                f"Details: {e}\n"
            )
            sys.exit(1)
```

**API Details:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Endpoint | `/api/generate` | Ollama generation API |
| `model` | `llama3.1` (default) | Open-source model compatible with Ollama |
| `prompt` | Combined system + user | Ollama doesn't separate system/user prompts |
| `stream` | `False` | Wait for complete response |
| `temperature` | `0` | Deterministic output |
| `timeout` | `120` seconds | Allow time for large prompts on local hardware |

**Prompt Combination:**
```python
combined_prompt = f"{system_prompt}\n\n{user_prompt}"
```

**Why combine?** Ollama's `/api/generate` endpoint doesn't support separate system prompts like chat APIs.

**Error Handling:**

| Error Type | Behavior |
|------------|----------|
| `ConnectionError` | Retry once, then exit with "ollama serve" hint |
| `Timeout` | Exit immediately (120s timeout) |
| `HTTPError` | Exit with HTTP details |
| Other exceptions | Exit with error details |

## Provider Comparison

| Feature | Anthropic | Azure OpenAI | Ollama |
|---------|-----------|--------------|--------|
| **API Key Required** | ✅ Yes | ✅ Yes | ❌ No |
| **Default Model** | claude-sonnet-4-20250514 | None (deployment-based) | llama3.1 |
| **Max Tokens** | 4096 | Not specified | Not specified |
| **Temperature** | 0 | 0 | 0 |
| **Retry Logic** | 2 attempts, 1s delay | 2 attempts, 1s delay | 2 attempts, 1s delay |
| **Timeout** | Default (SDK) | Default (SDK) | 120 seconds |
| **Prompt Format** | Separate system/user | Separate system/user | Combined |
| **SDK Dependency** | `anthropic` | `openai` | `requests` |
| **Cost** | Per token | Per token | Free (local) |
| **Best For** | Production | Azure-native environments | Development/testing |

## Common Behavior Across Providers

### 1. Temperature = 0

All providers use `temperature=0` for deterministic output:
- Ensures consistent risk assessments
- Reduces variance in JSON structure
- Critical for CI/CD reliability

### 2. Retry Logic

All providers implement identical retry logic:
```python
for attempt in range(2):
    try:
        # API call
        return response
    except RetryableError:
        if attempt == 0:
            sys.stderr.write("Retrying...\n")
            time.sleep(1)
            continue
        else:
            sys.stderr.write("Failed after retry.\n")
            sys.exit(1)
```

**Retryable errors:**
- Network errors (connection failures, timeouts)
- Server errors (5xx status codes)

**Non-retryable errors:**
- Rate limiting (fail immediately to avoid escalation)
- Authentication errors
- Invalid requests

### 3. SDK Import Handling

All providers check for SDK availability and provide installation instructions:
```python
try:
    from package import SDK
except ImportError:
    sys.stderr.write(
        "Error: package not installed.\n"
        "Install it with: pip install bicep-whatif-advisor[provider]\n"
    )
    sys.exit(1)
```

**Why lazy import?** Allows installing only needed dependencies via extras:
```bash
pip install bicep-whatif-advisor[anthropic]  # Only Anthropic SDK
pip install bicep-whatif-advisor[all]        # All SDKs
```

### 4. Exit on Error

All providers call `sys.exit(1)` on errors rather than raising exceptions:
- Provides clear, user-friendly error messages
- Prevents stack traces for expected errors (missing API keys)
- Ensures consistent exit codes

## Integration with CLI

### Usage in cli.py

```python
# Get provider instance
llm_provider = get_provider(provider, model)  # Line 341

# Call LLM
response_text = llm_provider.complete(system_prompt, user_prompt)  # Line 359

# Parse response
data = extract_json(response_text)  # Line 363
```

### Provider Selection Priority

1. **Command-line flag:** `--provider anthropic`
2. **Environment variable:** `WHATIF_PROVIDER=anthropic`
3. **Default:** `anthropic`

### Model Selection Priority

1. **Command-line flag:** `--model claude-opus-4-20250514`
2. **Environment variable:** `WHATIF_MODEL=claude-opus-4-20250514`
3. **Provider default:** Provider-specific default model

## Error Handling Strategy

### Exit Codes

All provider errors result in **exit code 1** (general error):
```python
sys.exit(1)
```

This is distinct from:
- Exit code `0` - Success
- Exit code `2` - Input validation errors (from `input.py`)

### Error Message Format

All providers follow consistent error message format:
```
Error: <Problem description>
<Optional: How to fix>
Details: <Technical details>
```

**Examples:**
```
Error: ANTHROPIC_API_KEY environment variable not set.
Get your API key from: https://console.anthropic.com/

Error: Cannot reach Ollama at http://localhost:11434.
Make sure Ollama is running and try again.
Start Ollama with: ollama serve
```

## Testing Strategy

### Mocking Providers

For unit tests, mock the provider interface:
```python
class MockProvider(Provider):
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        return '{"resources": [], "overall_summary": "Mock response"}'

# Use in tests
llm_provider = MockProvider()
```

### Testing Real Providers

For integration tests:
1. **Anthropic/Azure OpenAI:** Require API keys (skip if not available)
2. **Ollama:** Require local server running (skip if not available)

## Configuration Examples

### Anthropic
```bash
export ANTHROPIC_API_KEY=sk-ant-...
bicep-whatif-advisor --provider anthropic
```

### Azure OpenAI
```bash
export AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com/
export AZURE_OPENAI_API_KEY=...
export AZURE_OPENAI_DEPLOYMENT=gpt-4
bicep-whatif-advisor --provider azure-openai
```

### Ollama
```bash
ollama serve  # Start Ollama server
ollama pull llama3.1  # Download model
bicep-whatif-advisor --provider ollama
```

### Custom Model
```bash
# Override default model
bicep-whatif-advisor --provider anthropic --model claude-opus-4-20250514

# Or via environment
export WHATIF_MODEL=claude-opus-4-20250514
bicep-whatif-advisor --provider anthropic
```

## Future Improvements

Potential enhancements:

1. **More providers:** OpenAI (non-Azure), Google Gemini, local transformers
2. **Streaming responses:** For faster time-to-first-token
3. **Exponential backoff:** More sophisticated retry logic
4. **Provider auto-detection:** Infer provider from environment variables
5. **Response caching:** Cache identical What-If outputs to reduce API costs

## Next Steps

For details on how providers are used:
- [01-CLI-INTERFACE.md](01-CLI-INTERFACE.md) - `get_provider()` usage in CLI
- [04-PROMPT-ENGINEERING.md](04-PROMPT-ENGINEERING.md) - Prompts sent to `complete()`
