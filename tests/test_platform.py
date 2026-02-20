"""Tests for bicep_whatif_advisor.ci.platform module."""

import json

import pytest

from bicep_whatif_advisor.ci.platform import (
    PlatformContext,
    _detect_azuredevops,
    _detect_github,
    detect_platform,
)


@pytest.mark.unit
class TestPlatformContext:
    def test_has_pr_metadata_true(self):
        ctx = PlatformContext(platform="github", pr_number="42", pr_title="Test PR")
        assert ctx.has_pr_metadata() is True

    def test_has_pr_metadata_false_no_number(self):
        ctx = PlatformContext(platform="github", pr_title="Test PR")
        assert ctx.has_pr_metadata() is False

    def test_has_pr_metadata_false_no_title_or_desc(self):
        ctx = PlatformContext(platform="github", pr_number="42")
        assert ctx.has_pr_metadata() is False

    def test_get_diff_ref_with_base_branch(self):
        ctx = PlatformContext(platform="github", base_branch="main")
        assert ctx.get_diff_ref() == "origin/main"

    def test_get_diff_ref_strips_refs_heads(self):
        ctx = PlatformContext(platform="azuredevops", base_branch="refs/heads/develop")
        assert ctx.get_diff_ref() == "origin/develop"

    def test_get_diff_ref_fallback(self):
        ctx = PlatformContext(platform="local")
        assert ctx.get_diff_ref() == "HEAD~1"


@pytest.mark.unit
class TestDetectPlatform:
    def test_detects_local(self, clean_env):
        ctx = detect_platform()
        assert ctx.platform == "local"

    def test_detects_github(self, clean_env, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        ctx = detect_platform()
        assert ctx.platform == "github"

    def test_detects_azdevops_tf_build(self, clean_env, monkeypatch):
        monkeypatch.setenv("TF_BUILD", "True")
        ctx = detect_platform()
        assert ctx.platform == "azuredevops"

    def test_detects_azdevops_agent_id(self, clean_env, monkeypatch):
        monkeypatch.setenv("AGENT_ID", "1")
        ctx = detect_platform()
        assert ctx.platform == "azuredevops"


@pytest.mark.unit
class TestDetectGitHub:
    def test_extracts_repository(self, clean_env, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        ctx = _detect_github()
        assert ctx.repository == "owner/repo"

    def test_extracts_branches(self, clean_env, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_BASE_REF", "main")
        monkeypatch.setenv("GITHUB_HEAD_REF", "feature/test")
        ctx = _detect_github()
        assert ctx.base_branch == "main"
        assert ctx.source_branch == "feature/test"

    def test_extracts_pr_from_event_file(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
        event_file = tmp_path / "event.json"
        event_file.write_text(
            json.dumps(
                {
                    "pull_request": {
                        "number": 42,
                        "title": "Add feature",
                        "body": "This PR adds a feature",
                    }
                }
            )
        )
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
        ctx = _detect_github()
        assert ctx.pr_number == "42"
        assert ctx.pr_title == "Add feature"
        assert ctx.pr_description == "This PR adds a feature"

    def test_no_event_file_still_works(self, clean_env, monkeypatch):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "push")
        ctx = _detect_github()
        assert ctx.platform == "github"
        assert ctx.pr_number is None

    def test_invalid_event_file_graceful(self, clean_env, monkeypatch, tmp_path):
        monkeypatch.setenv("GITHUB_ACTIONS", "true")
        monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
        event_file = tmp_path / "event.json"
        event_file.write_text("not json")
        monkeypatch.setenv("GITHUB_EVENT_PATH", str(event_file))
        ctx = _detect_github()
        assert ctx.platform == "github"
        assert ctx.pr_number is None


@pytest.mark.unit
class TestDetectAzureDevOps:
    def test_extracts_pr_metadata(self, clean_env, azdevops_env):
        ctx = _detect_azuredevops()
        assert ctx.platform == "azuredevops"
        assert ctx.pr_number == "99"
        assert ctx.base_branch == "refs/heads/main"

    def test_fetches_pr_from_api(self, clean_env, azdevops_env, monkeypatch, mocker):
        monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "fake-token")
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "title": "My PR Title",
            "description": "My PR Description",
        }
        mock_response.raise_for_status = mocker.Mock()
        mocker.patch("requests.get", return_value=mock_response)

        ctx = _detect_azuredevops()
        assert ctx.pr_title == "My PR Title"
        assert ctx.pr_description == "My PR Description"

    def test_api_failure_graceful(self, clean_env, azdevops_env, monkeypatch, mocker):
        monkeypatch.setenv("SYSTEM_ACCESSTOKEN", "fake-token")
        import requests

        mocker.patch(
            "requests.get",
            side_effect=requests.exceptions.ConnectionError("fail"),
        )
        ctx = _detect_azuredevops()
        assert ctx.platform == "azuredevops"
        assert ctx.pr_title is None
