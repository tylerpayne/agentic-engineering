"""Storage for the per-project later queue.

One SQLite queue per project, at <project>/.claude/later.db. Imported by both the
/later capture hook and the standalone `later` CLI, so the two can never drift on
schema or rendering.

Nothing is ever deleted. A pop marks its rows resolved and stamps them with a
batch id, which is what makes `later unpop` possible: a mistimed /later:pop would
otherwise destroy notes the user cannot retype.

Standard library only.
"""

import os
import sqlite3
from datetime import datetime, timezone

STATES = ("queued", "popped", "dropped")

SCHEMA_VERSION = 1

# `peek` is read by a human in a terminal and by nobody else, so it can afford a
# larger default than the backlog board. A pop is deliberately unbounded: the
# whole point is that everything queued arrives together.
PEEK_LIMIT = 20

_SCHEMA = """
CREATE TABLE IF NOT EXISTS notes (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  content     TEXT NOT NULL,
  created_at  TEXT NOT NULL,
  session_id  TEXT,
  source      TEXT,
  state       TEXT NOT NULL DEFAULT 'queued'
              CHECK (state IN ('queued','popped','dropped')),
  resolved_at TEXT,
  batch       INTEGER
);
CREATE INDEX IF NOT EXISTS idx_notes_state ON notes(state, id);
CREATE INDEX IF NOT EXISTS idx_notes_batch ON notes(batch);
"""


def now() -> str:
    """ISO8601 UTC, second precision, no microsecond noise."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# --- location -------------------------------------------------------------


def resolve_project(start: str = None) -> str:
    """Walk up from `start` looking for a project root.

    A directory counts as a root if it holds .claude/ or .git/. This is what
    lets `later` work from any subdirectory of a repo and still hit the same
    queue. Falls back to `start` itself when nothing matches.
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
    return os.path.join(project, ".claude", "later.db")


def fallback_path(project: str) -> str:
    return os.path.join(project, ".claude", "later-fallback.txt")


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
    if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()
    return conn


# --- mutations ------------------------------------------------------------


def queue(conn, content: str, session_id: str = None, source: str = "cli") -> int:
    cur = conn.execute(
        "INSERT INTO notes (content, created_at, session_id, source, state)"
        " VALUES (?, ?, ?, ?, 'queued')",
        (content, now(), session_id, source),
    )
    conn.commit()
    return cur.lastrowid


def pending(conn, limit: int = None):
    """Everything still queued, oldest first, which is the order it went in."""
    sql = "SELECT * FROM notes WHERE state = 'queued' ORDER BY id"
    if limit:
        sql += f" LIMIT {int(limit)}"
    return conn.execute(sql).fetchall()


def count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM notes WHERE state = 'queued'"
    ).fetchone()[0]


def resolve(conn, state: str, session_id: str = None):
    """Move every queued note to `state` as one batch, and return the rows.

    BEGIN IMMEDIATE takes the write lock before the read, so two sessions
    popping at the same moment cannot both come away with the same notes.
    """
    if state not in ("popped", "dropped"):
        raise ValueError(f"cannot resolve to {state!r}")
    conn.execute("BEGIN IMMEDIATE")
    try:
        rows = conn.execute(
            "SELECT * FROM notes WHERE state = 'queued' ORDER BY id"
        ).fetchall()
        if not rows:
            conn.commit()
            return [], None
        batch = (conn.execute("SELECT MAX(batch) FROM notes").fetchone()[0] or 0) + 1
        conn.execute(
            "UPDATE notes SET state = ?, resolved_at = ?, batch = ?"
            " WHERE state = 'queued'",
            (state, now(), batch),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return rows, batch


def unpop(conn):
    """Put the most recent resolved batch back on the queue.

    Restores a drop as readily as a pop. Both lose notes the user cannot
    reconstruct, and the difference between them does not matter to whoever is
    trying to get their notes back.
    """
    row = conn.execute(
        "SELECT batch, state FROM notes WHERE batch IS NOT NULL"
        " ORDER BY batch DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return [], None
    batch, state = row["batch"], row["state"]
    rows = conn.execute(
        "SELECT * FROM notes WHERE batch = ? ORDER BY id", (batch,)
    ).fetchall()
    conn.execute(
        "UPDATE notes SET state = 'queued', resolved_at = NULL, batch = NULL"
        " WHERE batch = ?",
        (batch,),
    )
    conn.commit()
    return rows, state


def history(conn, limit: int = 20):
    return conn.execute(
        "SELECT * FROM notes WHERE state != 'queued' ORDER BY id DESC LIMIT ?",
        (int(limit),),
    ).fetchall()


# --- rendering ------------------------------------------------------------


def age(iso: str) -> str:
    """Rough elapsed time, for telling a note from ten minutes ago from one
    filed last Tuesday."""
    try:
        then = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return "?"
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - then).total_seconds()))
    for size, suffix in ((86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return f"{seconds // size}{suffix}"
    return f"{seconds}s"


def _indent(content: str) -> str:
    """Keep a multi-line note readable under its own number."""
    lines = content.rstrip().split("\n")
    return "\n".join([lines[0]] + [f"   {line}" for line in lines[1:]])


def render_notes(rows) -> str:
    return "\n".join(
        f"{n}. ({age(row['created_at'])} ago) {_indent(row['content'])}"
        for n, row in enumerate(rows, 1)
    )


def render_prompt(rows) -> str:
    """The block /later:pop hands to the model.

    It reads as the user's own words because that is what it is. The framing
    line matters: without it a bare list of terse notes invites Claude to
    summarise them back rather than act on them.
    """
    if not rows:
        return "The later queue is empty. Nothing was queued, so there is nothing to do here."
    count_word = "note" if len(rows) == 1 else "notes"
    return (
        f"{len(rows)} {count_word} I queued earlier with /later:push, oldest first.\n"
        "Treat each one as something I am asking you for now, and work through\n"
        "them together rather than one at a time.\n\n" + render_notes(rows)
    )


def render_queue(conn, limit: int = None) -> str:
    total = count(conn)
    if not total:
        return "Nothing queued for later."
    rows = pending(conn, limit=limit)
    head = f"{total} queued"
    if len(rows) < total:
        head += f", showing {len(rows)}"
    return f"{head}:\n{render_notes(rows)}\n\n/later:pop sends all {total} to Claude."
