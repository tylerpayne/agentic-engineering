"""Storage for the per-project backlog.

One SQLite board per project, at <project>/.claude/backlog.db. Imported by both
the /backlog capture hook and the standalone `backlog` CLI, so the two can never
drift on schema or rendering.

Standard library only.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

STATUSES = ("todo", "doing", "done", "wontfix")
OPEN_STATUSES = ("todo", "doing")

SCHEMA_VERSION = 1

# How many closed items the board shows before collapsing to a count.
CLOSED_PREVIEW = 3

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  content    TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'todo'
             CHECK (status IN ('todo','doing','done','wontfix')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  session_id TEXT,
  source     TEXT
);
CREATE INDEX IF NOT EXISTS idx_items_status ON items(status, id);
"""


def now() -> str:
    """ISO8601 UTC, second precision, no microsecond noise."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- location -------------------------------------------------------------


def resolve_project(start: str = None) -> str:
    """Walk up from `start` looking for a project root.

    A directory counts as a root if it holds .claude/ or .git/. This is what
    lets `backlog` work from any subdirectory of a repo and still hit the same
    board. Falls back to `start` itself when nothing matches.
    """
    start = os.path.abspath(start or os.getcwd())
    cur = start
    while True:
        if os.path.isdir(os.path.join(cur, ".claude")) or os.path.isdir(
            os.path.join(cur, ".git")
        ):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return start
        cur = parent


def db_path(project: str) -> str:
    return os.path.join(project, ".claude", "backlog.db")


def fallback_path(project: str) -> str:
    return os.path.join(project, ".claude", "backlog-fallback.txt")


# --- connection -----------------------------------------------------------


def connect(project: str) -> sqlite3.Connection:
    path = db_path(project)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    conn = sqlite3.connect(path, timeout=5.0)
    conn.row_factory = sqlite3.Row
    # WAL so a hook write never blocks on a concurrent read from another session.
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.DatabaseError:
        pass  # e.g. a network filesystem; the default journal still works
    conn.execute("PRAGMA busy_timeout=3000")
    conn.executescript(_SCHEMA)
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < SCHEMA_VERSION:
        # No migrations to run yet; future ones gate on `version` here.
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()
    return conn


# --- mutations ------------------------------------------------------------


def add(conn, content: str, session_id: str = None, source: str = "cli") -> int:
    ts = now()
    cur = conn.execute(
        "INSERT INTO items (content, status, created_at, updated_at, session_id, source)"
        " VALUES (?, 'todo', ?, ?, ?, ?)",
        (content, ts, ts, session_id, source),
    )
    conn.commit()
    return cur.lastrowid


def set_status(conn, item_id: int, status: str) -> bool:
    """Returns False when no such item, so callers can report it cleanly."""
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r} (want one of {', '.join(STATUSES)})")
    cur = conn.execute(
        "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
        (status, now(), item_id),
    )
    conn.commit()
    return cur.rowcount > 0


def edit(conn, item_id: int, content: str) -> bool:
    cur = conn.execute(
        "UPDATE items SET content = ?, updated_at = ? WHERE id = ?",
        (content, now(), item_id),
    )
    conn.commit()
    return cur.rowcount > 0


def remove(conn, item_id: int) -> bool:
    cur = conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return cur.rowcount > 0


# --- reads ----------------------------------------------------------------


def get(conn, item_id: int):
    return conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()


def list_items(conn, statuses=None, limit: int = None):
    sql = "SELECT * FROM items"
    params = []
    if statuses:
        sql += " WHERE status IN (%s)" % ",".join("?" * len(statuses))
        params.extend(statuses)
    sql += " ORDER BY id"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


# --- rendering ------------------------------------------------------------


def render_json(rows) -> str:
    return json.dumps([dict(r) for r in rows], indent=2)


def render_board(rows, show_all: bool = False) -> str:
    """Grouped plaintext board. Closed columns collapse unless show_all."""
    if not rows:
        return "Backlog is empty."

    by_status = {s: [] for s in STATUSES}
    for r in rows:
        by_status.setdefault(r["status"], []).append(r)

    width = max(len(str(r["id"])) for r in rows)
    out = []
    for status in STATUSES:
        items = by_status.get(status) or []
        if not items:
            continue
        closed = status in ("done", "wontfix")
        hidden = 0
        shown = items
        if closed and not show_all and len(items) > CLOSED_PREVIEW:
            shown = items[-CLOSED_PREVIEW:]
            hidden = len(items) - CLOSED_PREVIEW
        out.append(f"{status.upper()} ({len(items)})")
        for r in shown:
            out.append(f"  {str(r['id']).rjust(width)}  {r['content']}")
        if hidden:
            out.append(f"  {' ' * width}  ... and {hidden} older")
        out.append("")
    return "\n".join(out).rstrip()


def render_counts(conn) -> str:
    """One-line summary, e.g. '4 todo, 1 doing, 12 done'."""
    rows = conn.execute(
        "SELECT status, COUNT(*) n FROM items GROUP BY status"
    ).fetchall()
    counts = {r["status"]: r["n"] for r in rows}
    parts = [f"{counts[s]} {s}" for s in STATUSES if counts.get(s)]
    return ", ".join(parts) if parts else "empty"
