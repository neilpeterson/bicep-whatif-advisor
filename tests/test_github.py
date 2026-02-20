"""Tests for bicep_whatif_advisor.ci.github module."""

import requests

import pytest

from bicep_whatif_advisor.ci.github import post_github_comment


@pytest.mark.unit
class TestPostGitHubComment:

    def test_missing_token_returns_false(self, monkeypatch):
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        result = post_github_comment("test comment")
        assert result is False

    def test_parses_pr_url(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        result = post_github_comment(
            "test comment", pr_url="https://github.com/owner/repo/pull/42"
        )
        assert result is True
        url = mock_post.call_args[0][0]
        assert "/repos/owner/repo/issues/42/comments" in url

    def test_invalid_pr_url(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        result = post_github_comment("test", pr_url="https://example.com/not/a/pr")
        assert result is False

    def test_auto_detect_from_env(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "myorg/myrepo")
        monkeypatch.setenv("GITHUB_REF", "refs/pull/123/merge")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        result = post_github_comment("test comment")
        assert result is True
        url = mock_post.call_args[0][0]
        assert "/repos/myorg/myrepo/issues/123/comments" in url

    def test_auto_detect_missing_repo(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)
        monkeypatch.delenv("GITHUB_REF", raising=False)
        result = post_github_comment("test")
        assert result is False

    def test_auto_detect_invalid_repo_format(self, monkeypatch):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        monkeypatch.setenv("GITHUB_REPOSITORY", "invalid-no-slash")
        monkeypatch.setenv("GITHUB_REF", "refs/pull/1/merge")
        result = post_github_comment("test")
        assert result is False

    def test_http_error_returns_false(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status.side_effect = requests.exceptions.HTTPError("403")
        mocker.patch("requests.post", return_value=mock_resp)
        result = post_github_comment("test", pr_url="https://github.com/o/r/pull/1")
        assert result is False

    def test_connection_error_returns_false(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
        mocker.patch(
            "requests.post",
            side_effect=requests.exceptions.ConnectionError("fail"),
        )
        result = post_github_comment("test", pr_url="https://github.com/o/r/pull/1")
        assert result is False

    def test_auth_header_set(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "my-secret-token")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_github_comment("test", pr_url="https://github.com/o/r/pull/1")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer my-secret-token"

    def test_payload_contains_body(self, monkeypatch, mocker):
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        mock_resp = mocker.Mock()
        mock_resp.raise_for_status = mocker.Mock()
        mock_post = mocker.patch("requests.post", return_value=mock_resp)
        post_github_comment("## My Comment", pr_url="https://github.com/o/r/pull/1")
        payload = mock_post.call_args[1]["json"]
        assert payload["body"] == "## My Comment"
