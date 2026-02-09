"""Anthropic Claude provider implementation."""

import os
import sys
import time
from . import Provider


class AnthropicProvider(Provider):
    """Anthropic Claude API provider."""

    DEFAULT_MODEL = "claude-sonnet-4-20250514"

    def __init__(self, model: str = None):
        """Initialize Anthropic provider.

        Args:
            model: Optional model override (default: claude-sonnet-4-20250514)
        """
        self.model = model or self.DEFAULT_MODEL
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")

        if not self.api_key:
            sys.stderr.write(
                "Error: ANTHROPIC_API_KEY environment variable not set.\n"
                "Get your API key from: https://console.anthropic.com/\n"
            )
            sys.exit(1)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to Anthropic Claude API.

        Args:
            system_prompt: System prompt defining behavior
            user_prompt: User prompt with content to analyze

        Returns:
            Raw response text from Claude (JSON)

        Raises:
            SystemExit: On API errors after retry
        """
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

        # Should not reach here
        sys.stderr.write("Error: Failed to get response from Anthropic API.\n")
        sys.exit(1)
