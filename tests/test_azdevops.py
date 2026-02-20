"""Tests for bicep_whatif_advisor.ci.azdevops module."""

import pytest
import requests

from bicep_whatif_advisor.ci.azdevops import post_azdevops_comment


@pytest.mark.unit
class TestPostAzDevOpsComment:
    @pytest.fixture
    def ado_env(self, monkeypatch):
        """Set all required ADO env vars."""
        monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "fake-token")
        monkeypatch.setenv("SYSTEM_COLLECTIONURI", "https://dev.azure.com/myorg/")
        monkeypatch.setenv("SYSTEM_TEAMPROJECT", "myproject")
        monkeypatch.setenv("SYSTEM_PULLREQUEST_PULLREQUESTID", "42")
        monkeypatch.setenv("BUILD_REPOSITORY_ID", "repo-guid")

    def test_missing_token_returns_false(self, monkeypatch):
        monkeypatch.delenv("SYSTEM_ACCESSTOKEN", raising=False)
        monkeypatch.delenv("SYSTEM_COLLECTIONURI", raising=False)
        result = post_azdevops_comment("test")
        assert result is False

    def test_missing_multiple_vars(self, monkeypatch):
        for var in [
            "SYSTEM_ACCESSTOKEN",
            "SYSTEM_COLLECTIONURI",
            "SYSTEM_TEAMPROJECT",
            "SYSTEM_PULLREQUEST_PULLREQUESTID",
            "BUILD_REPOSITORY_ID",
        ]:
            monkeypatch.delenv(var, raising=False)
        result = post_azdevops_comment("test")
        assert result is False

    def test_http_collection_uri_rejected(self, ado_env, monkeypatch):
        monkeypatch.setenv("SYSTEM_COLLECTIONURI", "http://dev.azure.com/myorg/")
        result = post_azdevops_comment("test")
        assert result is False

    def test_success(self, ado_env, mocker):
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mocker.patch("requests.post", return_value=mock_resp)
        result = post_azdevops_comment("## Comment")
        assert result is True

    def test_url_construction(self, ado_env, mocker):
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_azdevops_comment("test")
        url = mock_post.call_args[0][0]
        assert "myproject/_apis/git/repositories/repo-guid/pullRequests/42/threads" in url
        assert "api-version=7.0" in url

    def test_auth_header(self, ado_env, mocker):
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_azdevops_comment("test")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer fake-token"

    def test_payload_structure(self, ado_env, mocker):
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_azdevops_comment("## My Comment")
        payload = mock_post.call_args[1]["json"]
        assert payload["comments"][0]["content"] == "## My Comment"
        assert payload["comments"][0]["commentType"] == 1
        assert payload["status"] == 1

    def test_http_error_returns_false(self, ado_env, mocker):
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("500")
        mock_resp.status_code = 500
        mocker.patch("requests.post", return_value=mock_resp)
        result = post_azdevops_comment("test")
        assert result is False

    def test_connection_error_returns_false(self, ado_env, mocker):
        mocker.patch(
            "requests.post",
            side_effect=requests.exceptions.ConnectionError("fail"),
        )
        result = post_azdevops_comment("test")
        assert result is False

    def test_trailing_slash_stripped(self, ado_env, monkeypatch, mocker):
        """Collection URI trailing slash should be stripped before building URL."""
        monkeypatch.setenv("SYSTEM_COLLECTIONURI", "https://dev.azure.com/myorg/")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_azdevops_comment("test")
        url = mock_post.call_args[0][0]
        assert "//myproject" not in url
