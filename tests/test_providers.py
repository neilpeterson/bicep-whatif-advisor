"""Tests for bicep_whatif_advisor.providers module."""

import pytest

from bicep_whatif_advisor.providers import Provider, get_provider


@pytest.mark.unit
class TestProviderRegistry:
    def test_get_provider_invalid_name(self, clean_env):
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider("invalid-provider")

    def test_get_provider_env_override(self, monkeypatch):
        """WHATIF_PROVIDER env var overrides the name argument."""
        monkeypatch.setenv("WHATIF_PROVIDER", "invalid-from-env")
        with pytest.raises(ValueError, match="invalid-from-env"):
            get_provider("anthropic")

    def test_provider_abc(self):
        """Provider is abstract — cannot be instantiated directly."""
        with pytest.raises(TypeError):
            Provider()


@pytest.mark.unit
class TestAnthropicProvider:
    def test_missing_api_key_exits(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(SystemExit):
            get_provider("anthropic")

    def test_default_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("anthropic")
        assert provider.model == "claude-sonnet-4-20250514"

    def test_custom_model(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("anthropic", model="claude-3-opus-20240229")
        assert provider.model == "claude-3-opus-20240229"

    def test_model_env_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.setenv("WHATIF_MODEL", "env-model")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        provider = get_provider("anthropic")
        assert provider.model == "env-model"

    def test_complete_success(self, monkeypatch, mocker):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("anthropic")

        mock_client = mocker.Mock()
        mock_response = mocker.Mock()
        mock_response.content = [mocker.Mock(text='{"resources": []}')]
        mock_client.messages.create.return_value = mock_response
        # Patch the SDK class where it's imported from
        mocker.patch("anthropic.Anthropic", return_value=mock_client)

        result = provider.complete("system", "user")
        assert result == '{"resources": []}'

    def test_complete_rate_limit_exits(self, monkeypatch, mocker):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("anthropic")

        mock_client = mocker.Mock()
        from anthropic import RateLimitError

        mock_resp = mocker.Mock()
        mock_resp.status_code = 429
        mock_resp.headers = {}
        err = RateLimitError(
            message="rate limited",
            response=mock_resp,
            body=None,
        )
        mock_client.messages.create.side_effect = err
        mocker.patch("anthropic.Anthropic", return_value=mock_client)

        with pytest.raises(SystemExit):
            provider.complete("system", "user")

    def test_complete_api_error_retries(self, monkeypatch, mocker):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("anthropic")

        mock_client = mocker.Mock()
        from anthropic import APIError

        err = APIError(
            message="server error",
            request=mocker.Mock(),
            body=None,
        )
        mock_client.messages.create.side_effect = err
        mocker.patch("anthropic.Anthropic", return_value=mock_client)
        mocker.patch("time.sleep")

        with pytest.raises(SystemExit):
            provider.complete("system", "user")
        # Should have retried once (2 total calls)
        assert mock_client.messages.create.call_count == 2


@pytest.mark.unit
class TestAzureOpenAIProvider:
    def test_missing_env_vars_exits(self, monkeypatch):
        monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("AZURE_OPENAI_DEPLOYMENT", raising=False)
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        with pytest.raises(SystemExit):
            get_provider("azure-openai")

    def test_complete_success(self, monkeypatch, mocker):
        monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com")
        monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
        monkeypatch.setenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4")
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("azure-openai")

        mock_client = mocker.Mock()
        mock_msg = mocker.Mock()
        mock_msg.content = '{"resources": []}'
        mock_choice = mocker.Mock()
        mock_choice.message = mock_msg
        mock_response = mocker.Mock()
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        # Patch at the SDK level
        mocker.patch("openai.AzureOpenAI", return_value=mock_client)

        result = provider.complete("system", "user")
        assert result == '{"resources": []}'


@pytest.mark.unit
class TestOllamaProvider:
    def test_default_model_and_host(self, monkeypatch):
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        monkeypatch.delenv("OLLAMA_HOST", raising=False)
        provider = get_provider("ollama")
        assert provider.model == "llama3.1"
        assert provider.host == "http://localhost:11434"

    def test_custom_host(self, monkeypatch):
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        monkeypatch.setenv("OLLAMA_HOST", "http://myhost:11434")
        provider = get_provider("ollama")
        assert provider.host == "http://myhost:11434"

    def test_complete_success(self, monkeypatch, mocker):
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("ollama")

        mock_response = mocker.Mock()
        mock_response.json.return_value = {"response": '{"resources": []}'}
        mock_response.raise_for_status = mocker.Mock()
        mocker.patch("requests.post", return_value=mock_response)

        result = provider.complete("system", "user")
        assert result == '{"resources": []}'

    def test_connection_error_retries_and_exits(self, monkeypatch, mocker):
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("ollama")

        import requests

        mocker.patch("requests.post", side_effect=requests.exceptions.ConnectionError("fail"))
        mocker.patch("time.sleep")

        with pytest.raises(SystemExit):
            provider.complete("system", "user")

    def test_timeout_exits(self, monkeypatch, mocker):
        monkeypatch.delenv("WHATIF_PROVIDER", raising=False)
        monkeypatch.delenv("WHATIF_MODEL", raising=False)
        provider = get_provider("ollama")

        import requests

        mocker.patch("requests.post", side_effect=requests.exceptions.Timeout("timeout"))

        with pytest.raises(SystemExit):
            provider.complete("system", "user")
