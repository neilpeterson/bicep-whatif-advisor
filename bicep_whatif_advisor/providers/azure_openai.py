"""Azure OpenAI provider implementation."""

import os
import sys
import time
from . import Provider


class AzureOpenAIProvider(Provider):
    """Azure OpenAI API provider."""

    def __init__(self, model: str = None):
        """Initialize Azure OpenAI provider.

        Args:
            model: Optional model override (uses deployment name)
        """
        self.endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        self.api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        self.deployment = model or os.environ.get("AZURE_OPENAI_DEPLOYMENT")

        # Validate required environment variables
        missing = []
        if not self.endpoint:
            missing.append("AZURE_OPENAI_ENDPOINT")
        if not self.api_key:
            missing.append("AZURE_OPENAI_API_KEY")
        if not self.deployment:
            missing.append("AZURE_OPENAI_DEPLOYMENT")

        if missing:
            sys.stderr.write(
                f"Error: Missing required environment variables: {', '.join(missing)}\n"
                f"Set them to use Azure OpenAI provider.\n"
            )
            sys.exit(1)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to Azure OpenAI API.

        Args:
            system_prompt: System prompt defining behavior
            user_prompt: User prompt with content to analyze

        Returns:
            Raw response text from Azure OpenAI (JSON)

        Raises:
            SystemExit: On API errors after retry
        """
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
                    # First attempt failed, retry once
                    sys.stderr.write(f"Network error, retrying... ({e})\n")
                    time.sleep(1)
                    continue
                else:
                    # Second attempt failed
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

        # Should not reach here
        sys.stderr.write("Error: Failed to get response from Azure OpenAI API.\n")
        sys.exit(1)
