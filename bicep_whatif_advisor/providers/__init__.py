"""LLM provider implementations for bicep-whatif-advisor."""

from abc import ABC, abstractmethod
import os


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
