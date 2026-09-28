"""Stop two backend instances from running against the same database at
once. A second instance silently races the first - each polling and writing
independently - which has caused confusing "my fix mysteriously reverted"
bugs more than once in practice (an old process outliving a code change and
undoing it every poll cycle)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

LOCK_FILE = Path(__file__).resolve().parent.parent / ".cadence.lock"


class AlreadyRunningError(RuntimeError):
    """Raised when another instance already holds the lock."""


def _pid_running(pid: int) -> bool:
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def acquire() -> None:
    """Claim the lock, or raise AlreadyRunningError if another live process
    already holds it. A lock file left behind by a crashed process (whose
    PID is no longer running) is treated as stale and silently reclaimed."""
    if LOCK_FILE.exists():
        try:
            existing_pid = int(LOCK_FILE.read_text().strip())
        except (ValueError, OSError):
            existing_pid = None
        if existing_pid and existing_pid != os.getpid() and _pid_running(existing_pid):
            raise AlreadyRunningError(
                f"This backend is already running (PID {existing_pid}). "
                "Close that window before starting another one - two copies "
                "running at once will silently overwrite each other's changes."
            )
    LOCK_FILE.write_text(str(os.getpid()))


def release() -> None:
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text().strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except OSError:
        pass
