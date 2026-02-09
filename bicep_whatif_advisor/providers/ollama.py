"""Ollama local LLM provider implementation."""

import os
import sys
import time
from . import Provider


class OllamaProvider(Provider):
    """Ollama local LLM provider."""

    DEFAULT_MODEL = "llama3.1"
    DEFAULT_HOST = "http://localhost:11434"

    def __init__(self, model: str = None):
        """Initialize Ollama provider.

        Args:
            model: Optional model override (default: llama3.1)
        """
        self.model = model or self.DEFAULT_MODEL
        self.host = os.environ.get("OLLAMA_HOST", self.DEFAULT_HOST)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send prompts to Ollama API.

        Args:
            system_prompt: System prompt defining behavior
            user_prompt: User prompt with content to analyze

        Returns:
            Raw response text from Ollama (JSON)

        Raises:
            SystemExit: On API errors after retry
        """
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
                    # First attempt failed, retry once
                    sys.stderr.write(f"Connection error, retrying...\n")
                    time.sleep(1)
                    continue
                else:
                    # Second attempt failed
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

        # Should not reach here
        sys.stderr.write("Error: Failed to get response from Ollama API.\n")
        sys.exit(1)
