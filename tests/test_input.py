"""Tests for bicep_whatif_advisor.input module."""

import io
import sys

import pytest

from bicep_whatif_advisor.input import InputError, read_stdin


@pytest.mark.unit
class TestReadStdin:
    """Tests for read_stdin() — TTY detection, validation, truncation."""

    def test_tty_raises_input_error(self, mocker):
        """Raise InputError when stdin is a terminal (not piped)."""
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = True
        with pytest.raises(InputError, match="No input detected"):
            read_stdin()

    def test_empty_input_raises_input_error(self, mocker):
        """Raise InputError on empty stdin."""
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = ""
        with pytest.raises(InputError, match="Input is empty"):
            read_stdin()

    def test_whitespace_only_raises_input_error(self, mocker):
        """Raise InputError on whitespace-only stdin."""
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "   \n\t  \n  "
        with pytest.raises(InputError, match="Input is empty"):
            read_stdin()

    def test_valid_whatif_output_returns_content(self, mocker):
        """Return content when valid What-If output is piped."""
        content = "Resource changes: 1 to create.\n+ Microsoft.Storage/storageAccounts/test"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin()
        assert result == content

    def test_truncation_at_max_chars(self, mocker):
        """Truncate input exceeding max_chars limit."""
        content = "Resource changes:" + "x" * 200
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin(max_chars=50)
        assert len(result) == 50

    def test_truncation_writes_warning(self, mocker):
        """Write truncation warning to stderr."""
        content = "Resource changes:" + "x" * 200
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        mock_stderr = mocker.patch("bicep_whatif_advisor.input.sys.stderr", new_callable=io.StringIO)
        read_stdin(max_chars=50)
        assert "truncated" in mock_stderr.getvalue().lower()

    def test_missing_markers_warns_but_returns(self, mocker):
        """Warn on missing What-If markers but still return content."""
        content = "This is some random text with no Azure markers"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        mock_stderr = mocker.patch("bicep_whatif_advisor.input.sys.stderr", new_callable=io.StringIO)
        result = read_stdin()
        assert result == content
        assert "may not be Azure What-If output" in mock_stderr.getvalue()

    def test_create_marker_accepted(self, mocker):
        """Accept input containing '+ Create' marker."""
        content = "  + Create\nSome resource details"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin()
        assert result == content

    def test_modify_marker_accepted(self, mocker):
        """Accept input containing '~ Modify' marker."""
        content = "  ~ Modify\nSome resource details"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin()
        assert result == content

    def test_delete_marker_accepted(self, mocker):
        """Accept input containing '- Delete' marker."""
        content = "  - Delete\nSome resource details"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin()
        assert result == content

    def test_scope_marker_accepted(self, mocker):
        """Accept input containing 'Scope:' marker."""
        content = "Scope: /subscriptions/12345"
        mock_stdin = mocker.patch("bicep_whatif_advisor.input.sys.stdin")
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = content
        result = read_stdin()
        assert result == content
