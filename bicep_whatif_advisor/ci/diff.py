"""Git diff collection for CI mode."""

import subprocess
import sys
import os


def get_diff(diff_path: str = None, diff_ref: str = "HEAD~1") -> str:
    """Get git diff content for CI mode analysis.

    Args:
        diff_path: Path to diff file, or None to run git diff
        diff_ref: Git reference to diff against (default: HEAD~1)

    Returns:
        Diff content as string (may be empty if no changes)

    Raises:
        SystemExit: If git is not available or diff file not found
    """
    if diff_path:
        # Read from file
        if not os.path.exists(diff_path):
            sys.stderr.write(f"Error: Diff file not found: {diff_path}\n")
            sys.exit(1)

        try:
            with open(diff_path, 'r') as f:
                return f.read()
        except Exception as e:
            sys.stderr.write(f"Error reading diff file: {e}\n")
            sys.exit(1)

    else:
        # Run git diff
        try:
            result = subprocess.run(
                ["git", "diff", diff_ref],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                # Git failed - could be not a repo, or ref doesn't exist
                sys.stderr.write(
                    f"Warning: git diff failed (exit code {result.returncode}).\n"
                    f"Error: {result.stderr}\n"
                    f"Proceeding without diff context.\n"
                )
                return ""

            return result.stdout

        except FileNotFoundError:
            sys.stderr.write(
                "Error: git command not found.\n"
                "Install git or provide diff via --diff flag.\n"
            )
            sys.exit(1)

        except subprocess.TimeoutExpired:
            sys.stderr.write("Error: git diff command timed out.\n")
            sys.exit(1)

        except Exception as e:
            sys.stderr.write(f"Error running git diff: {e}\n")
            sys.exit(1)
