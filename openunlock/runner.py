"""Subprocess runner: the single place external tools are executed.

- Locates binaries with shutil.which and raises ToolNotFoundError with a
  helpful message instead of a bare FileNotFoundError.
- Enforces a timeout so a hung adb/fastboot never hangs the UI.
- Returns stdout as text; raises CommandFailedError on non-zero exit.
"""
import shutil
import subprocess

from .errors import CommandFailedError, ToolNotFoundError

DEFAULT_TIMEOUT = 120


def which_or_raise(tool):
    path = shutil.which(tool)
    if path is None:
        raise ToolNotFoundError(tool)
    return path


def run(argv, timeout=DEFAULT_TIMEOUT, check=True):
    """Run argv (list). Returns stdout (str). Raises on failure."""
    which_or_raise(argv[0])
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise CommandFailedError(argv, -1,
                                 f"timed out after {timeout}s") from exc
    if check and proc.returncode != 0:
        raise CommandFailedError(argv, proc.returncode,
                                 proc.stdout + proc.stderr)
    return proc.stdout


def run_quiet(argv, timeout=DEFAULT_TIMEOUT):
    """Like run(), but returns (returncode, stdout) instead of raising."""
    try:
        which_or_raise(argv[0])
    except ToolNotFoundError:
        return -1, ""
    try:
        proc = subprocess.run(
            argv, capture_output=True, text=True, timeout=timeout)
        return proc.returncode, proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        return -1, ""
