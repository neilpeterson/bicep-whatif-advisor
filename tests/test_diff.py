"""Tests for bicep_whatif_advisor.ci.diff module."""

import subprocess

import pytest

from bicep_whatif_advisor.ci.diff import get_diff


@pytest.mark.unit
class TestGetDiff:
    def test_reads_from_file(self, tmp_path):
        diff_file = tmp_path / "test.diff"
        diff_file.write_text("diff --git a/main.bicep b/main.bicep\n+resource")
        result = get_diff(diff_path=str(diff_file))
        assert "diff --git" in result

    def test_file_not_found_exits(self):
        with pytest.raises(SystemExit) as exc_info:
            get_diff(diff_path="/nonexistent/path/test.diff")
        assert exc_info.value.code == 1

    def test_git_diff_success(self, mocker):
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = "diff --git a/file\n"
        mocker.patch("subprocess.run", return_value=mock_result)
        result = get_diff(diff_ref="HEAD~1")
        assert "diff --git" in result

    def test_git_diff_failure_returns_empty(self, mocker):
        mock_result = mocker.Mock()
        mock_result.returncode = 128
        mock_result.stderr = "fatal: bad revision"
        mocker.patch("subprocess.run", return_value=mock_result)
        result = get_diff(diff_ref="nonexistent-ref")
        assert result == ""

    def test_git_not_found_exits(self, mocker):
        mocker.patch("subprocess.run", side_effect=FileNotFoundError())
        with pytest.raises(SystemExit) as exc_info:
            get_diff()
        assert exc_info.value.code == 1

    def test_git_timeout_exits(self, mocker):
        mocker.patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30))
        with pytest.raises(SystemExit) as exc_info:
            get_diff()
        assert exc_info.value.code == 1

    def test_git_general_exception_exits(self, mocker):
        mocker.patch("subprocess.run", side_effect=RuntimeError("unexpected"))
        with pytest.raises(SystemExit) as exc_info:
            get_diff()
        assert exc_info.value.code == 1

    def test_git_diff_uses_correct_ref(self, mocker):
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run = mocker.patch("subprocess.run", return_value=mock_result)
        get_diff(diff_ref="origin/main")
        args = mock_run.call_args[0][0]
        assert args == ["git", "diff", "origin/main"]

    def test_default_diff_ref(self, mocker):
        mock_result = mocker.Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_run = mocker.patch("subprocess.run", return_value=mock_result)
        get_diff()
        args = mock_run.call_args[0][0]
        assert args == ["git", "diff", "HEAD~1"]
