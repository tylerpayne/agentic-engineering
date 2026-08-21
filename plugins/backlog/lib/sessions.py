"""Reading Claude Code's session registry, to tell live holders from dead ones.

Claude Code writes one record per session to ~/.claude/sessions/<pid>.json:

    {"pid": 75115, "sessionId": "4466b59b-...", "cwd": "/path/to/repo",
     "name": "backlog-plugin-design", "status": "busy", "kind": "interactive",
     "procStart": "Fri Aug 21 18:38:40 2026", "startedAt": 1787337523143, ...}

That gives us three things a backlog claim needs: whether the holder is still
running, what to call it when messaging, and which project it is working in.

Standard library only.
"""

import calendar
import errno
import json
import glob
import os
import subprocess
import time

# CLAUDE_CONFIG_DIR relocates the whole config tree; honour it.
def sessions_dir() -> str:
    base = os.environ.get("CLAUDE_CONFIG_DIR") or os.path.join(
        os.path.expanduser("~"), ".claude"
    )
    return os.path.join(base, "sessions")


def current_session_id():
    """This Claude session's UUID, or None outside Claude Code."""
    return os.environ.get("CLAUDE_CODE_SESSION_ID") or None


def local_holder_id() -> str:
    """Identity for `backlog` run from a plain terminal, with no session."""
    return "pid:%d" % os.getpid()


def load_records():
    out = []
    for path in glob.glob(os.path.join(sessions_dir(), "*.json")):
        try:
            with open(path) as fh:
                record = json.load(fh)
        except (OSError, ValueError):
            continue  # a half-written or stale record is just absent
        if isinstance(record, dict) and record.get("pid"):
            out.append(record)
    return out


def find_by_session_id(session_id: str):
    if not session_id:
        return None
    for record in load_records():
        if record.get("sessionId") == session_id:
            return record
    return None


def _pid_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError as exc:
        # EPERM means it exists but belongs to someone else.
        return exc.errno == errno.EPERM
    except (TypeError, ValueError):
        return False


def _proc_start_epoch(pid: int):
    """Actual start time of `pid`, as a local-time epoch, or None."""
    try:
        out = subprocess.run(
            ["ps", "-o", "lstart=", "-p", str(pid)],
            capture_output=True, text=True, timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    text = " ".join(out.stdout.split())
    if not text:
        return None
    try:
        return time.mktime(time.strptime(text, "%a %b %d %H:%M:%S %Y"))
    except ValueError:
        return None


def _record_start_epoch(record):
    """procStart from the record, as an epoch.

    Claude Code writes procStart in UTC while `ps` prints local time, so the
    two are parsed with different calendars and then compared as instants.
    Verified to agree to the second on this machine.
    """
    text = record.get("procStart")
    if not text:
        return None
    try:
        return calendar.timegm(time.strptime(text, "%a %b %d %H:%M:%S %Y"))
    except ValueError:
        return None


def is_alive(record) -> bool:
    """Is the process behind this session record still the same process?

    kill(0) alone is not enough: PIDs get reused, and a recycled PID would
    otherwise pin a claim forever. When both start times are available they
    must agree; if we cannot read one, fall back to kill(0) rather than
    declaring a live session dead.
    """
    pid = record.get("pid")
    if not _pid_running(pid):
        return False
    recorded = _record_start_epoch(record)
    actual = _proc_start_epoch(pid)
    if recorded is None or actual is None:
        return True
    return abs(recorded - actual) <= 2  # seconds of slack for rounding


def holder_status(holder_id: str):
    """Resolve a stored claim owner.

    Returns (alive: bool, name: str|None, record: dict|None). `name` is the
    session's current name from the registry -- always re-resolved rather than
    trusted from the database, because sessions can be renamed.
    """
    if not holder_id:
        return False, None, None
    if holder_id.startswith("pid:"):
        try:
            pid = int(holder_id.split(":", 1)[1])
        except ValueError:
            return False, None, None
        return _pid_running(pid), None, None
    record = find_by_session_id(holder_id)
    if record is None:
        return False, None, None
    return is_alive(record), record.get("name"), record


def live_sessions(cwd: str = None):
    """Live sessions, optionally only those working in/under `cwd`."""
    out = []
    root = os.path.realpath(cwd) if cwd else None
    for record in load_records():
        if not is_alive(record):
            continue
        if root:
            here = os.path.realpath(record.get("cwd") or "")
            if here != root and not here.startswith(root + os.sep):
                continue
        out.append(record)
    out.sort(key=lambda r: r.get("startedAt") or 0)
    return out


def describe_self():
    """Identity of the caller, for stamping onto a claim."""
    session_id = current_session_id()
    if session_id:
        record = find_by_session_id(session_id)
        return session_id, (record or {}).get("name")
    return local_holder_id(), None
