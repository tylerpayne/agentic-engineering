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

SCHEMA_VERSION = 2

# How many closed items the board shows before collapsing to a count. Only
# applies to an unpaginated board; a page is already bounded.
CLOSED_PREVIEW = 3

# Reads default to one page of the most recent items. The board is read into a
# model's context far more often than a human's terminal, and an unbounded read
# of a long-lived board is the one thing here that can blow up a context window.
# `limit=0` means no limit and has to be asked for explicitly.
DEFAULT_LIMIT = 10

_SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  content    TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'todo'
             CHECK (status IN ('todo','doing','done','wontfix')),
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  session_id TEXT,
  source     TEXT,
  claimed_by      TEXT,   -- session UUID, or "pid:N" for plain terminal use
  claimed_by_name TEXT,   -- last-known label; the registry is authoritative
  claimed_at      TEXT
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
    _migrate(conn)
    return conn


def _migrate(conn) -> None:
    """Bring an existing database up to SCHEMA_VERSION.

    CREATE TABLE IF NOT EXISTS leaves a v1 table untouched, so the claim
    columns are added here. Guarded on the existing columns as well as
    user_version, so a database that predates versioning still upgrades.
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    have = {r[1] for r in conn.execute("PRAGMA table_info(items)")}
    for column in ("claimed_by", "claimed_by_name", "claimed_at"):
        if column not in have:
            conn.execute(f"ALTER TABLE items ADD COLUMN {column} TEXT")
    if version < SCHEMA_VERSION:
        conn.execute(f"PRAGMA user_version={SCHEMA_VERSION}")
    conn.commit()


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
    """Returns False when no such item, so callers can report it cleanly.

    Status and ownership are one concept: moving an item out of `doing`
    releases whatever claim it carried. Taking it *into* `doing` is done via
    claim(), which is atomic; this path only clears.
    """
    if status not in STATUSES:
        raise ValueError(f"unknown status {status!r} (want one of {', '.join(STATUSES)})")
    if status == "doing":
        cur = conn.execute(
            "UPDATE items SET status = ?, updated_at = ? WHERE id = ?",
            (status, now(), item_id),
        )
    else:
        cur = conn.execute(
            "UPDATE items SET status = ?, updated_at = ?,"
            " claimed_by = NULL, claimed_by_name = NULL, claimed_at = NULL"
            " WHERE id = ?",
            (status, now(), item_id),
        )
    conn.commit()
    return cur.rowcount > 0


# --- claims ---------------------------------------------------------------
#
# The claim column is not the lock. The lock is the conditional UPDATE below:
# both racing sessions issue it, SQLite serialises them, and exactly one sees
# rowcount 1. A read-then-write would leave a window where both read "free".


def claim(conn, item_id: int, holder: str, holder_name: str = None,
          steal_from: str = None, set_doing: bool = True):
    """Try to take item `item_id` for `holder`.

    Succeeds if the item is unclaimed, already ours, or held by
    `steal_from` (the caller having established that holder is dead).
    Returns (ok, row). On failure `row` is the current state so the caller
    can report who holds it.
    """
    row = get(conn, item_id)
    if row is None:
        return False, None

    allowed = [holder]
    if steal_from:
        allowed.append(steal_from)
    placeholders = ",".join("?" * len(allowed))
    sql = (
        "UPDATE items SET claimed_by = ?, claimed_by_name = ?, claimed_at = ?,"
        " updated_at = ?"
        + (", status = 'doing'" if set_doing else "")
        + f" WHERE id = ? AND (claimed_by IS NULL OR claimed_by IN ({placeholders}))"
    )
    ts = now()
    cur = conn.execute(sql, [holder, holder_name, ts, ts, item_id] + allowed)
    conn.commit()
    if cur.rowcount > 0:
        return True, get(conn, item_id)
    return False, get(conn, item_id)


def release(conn, item_id: int, holder: str = None) -> bool:
    """Drop our claim. With `holder` set, only if we are the one holding it."""
    sql = ("UPDATE items SET claimed_by = NULL, claimed_by_name = NULL,"
           " claimed_at = NULL, updated_at = ? WHERE id = ?")
    params = [now(), item_id]
    if holder:
        sql += " AND claimed_by = ?"
        params.append(holder)
    cur = conn.execute(sql, params)
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


def page(conn, statuses=None, limit: int = DEFAULT_LIMIT, offset: int = 0):
    """One page of the board, newest first, plus enough to describe the rest.

    `offset` counts back from the newest item, so offset=0 is the most recent
    page and offset=10 the ten before those. Rows come back oldest-first within
    the page, which is how the board reads; the paging itself is newest-first so
    that a stale item filed months ago never crowds out this morning's note.

    `limit=0` disables the limit. Callers that hand results to a model should
    not do that without knowing how big the board is.
    """
    limit = max(0, int(limit or 0))
    offset = max(0, int(offset or 0))

    where, params = "", []
    if statuses:
        where = " WHERE status IN (%s)" % ",".join("?" * len(statuses))
        params = list(statuses)

    counts = {
        r["status"]: r["n"]
        for r in conn.execute(
            "SELECT status, COUNT(*) n FROM items" + where + " GROUP BY status", params
        )
    }
    total = sum(counts.values())

    sql = "SELECT * FROM items" + where + " ORDER BY id DESC"
    args = list(params)
    if limit:
        sql += " LIMIT ? OFFSET ?"
        args += [limit, offset]
    elif offset:
        sql += " LIMIT -1 OFFSET ?"  # SQLite wants a LIMIT before OFFSET
        args.append(offset)
    rows = list(reversed(conn.execute(sql, args).fetchall()))

    return {
        "rows": rows,
        "total": total,
        "shown": len(rows),
        "offset": offset,
        "limit": limit,
        "newer": offset,
        "older": max(0, total - offset - len(rows)),
        # Per-status totals across the whole filtered board, not just this page,
        # so a column header can say "3 of 21" instead of implying 3 is all.
        "counts": counts,
    }



# --- rendering ------------------------------------------------------------


def _age(iso: str) -> str:
    """Compact human age of an ISO8601 timestamp, e.g. '2h', '15m'."""
    if not iso:
        return ""
    try:
        then = datetime.fromisoformat(iso)
    except ValueError:
        return ""
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    secs = max(0, int((datetime.now(timezone.utc) - then).total_seconds()))
    if secs < 90:
        return f"{secs}s"
    if secs < 5400:
        return f"{secs // 60}m"
    if secs < 172800:
        return f"{secs // 3600}h"
    return f"{secs // 86400}d"


def claim_info(row, me: str = None):
    """Resolve a row's claim into something a caller can act on without
    knowing anything about PIDs or the session registry.

    state is one of:
      unclaimed  nobody holds it
      self       this session holds it
      live       another session holds it and is still running -- ask first
      stale      the holder is gone; taking it over is safe
    """
    import sessions  # local import: the DB layer works without it

    holder = row["claimed_by"] if "claimed_by" in row.keys() else None
    if not holder:
        return {"state": "unclaimed", "session": None, "name": None,
                "held_for": None, "session_status": None}
    if me and holder == me:
        state = "self"
        alive, name, record = True, None, None
    else:
        alive, name, record = sessions.holder_status(holder)
        state = "live" if alive else "stale"
    stored = row["claimed_by_name"] if "claimed_by_name" in row.keys() else None
    held = row["claimed_at"] if "claimed_at" in row.keys() else None
    return {
        "state": state,
        "session": holder,
        # Registry name wins: sessions can be renamed after claiming.
        "name": name or stored,
        "held_for": _age(held),
        "claimed_at": held,
        "session_status": (record or {}).get("status"),
    }


def render_page_json(pg, me: str = None) -> str:
    """The page plus its own extent, so a reader knows what it is *not* seeing."""
    items = []
    for r in pg["rows"]:
        d = dict(r)
        d["claim"] = claim_info(r, me)
        items.append(d)
    return json.dumps(
        {
            "items": items,
            "total": pg["total"],
            "shown": pg["shown"],
            "offset": pg["offset"],
            "limit": pg["limit"],
            "newer": pg["newer"],
            "older": pg["older"],
            "has_more": pg["older"] > 0,
            "next_offset": (pg["offset"] + pg["shown"]) if pg["older"] > 0 else None,
        },
        indent=2,
    )


def render_page_note(pg, next_cmd: str = "backlog list") -> str:
    """One line describing the page, or "" when the page is the whole board."""
    if not pg["limit"] or (pg["older"] == 0 and pg["newer"] == 0):
        return ""
    if pg["shown"] == 0:
        return f"Nothing at offset {pg['offset']} ({pg['total']} total)."
    if pg["newer"]:
        head = f"{pg['shown']} of {pg['total']}, skipping {pg['newer']} newer"
    else:
        head = f"{pg['shown']} most recent of {pg['total']}"
    if pg["older"]:
        return f"{head} - {pg['older']} older: {next_cmd}"
    return head


def render_board(rows, show_all: bool = False, me: str = None,
                 collapse_closed: bool = True, counts=None) -> str:
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
        if closed and collapse_closed and not show_all and len(items) > CLOSED_PREVIEW:
            shown = items[-CLOSED_PREVIEW:]
            hidden = len(items) - CLOSED_PREVIEW
        overall = (counts or {}).get(status, len(items))
        tally = len(items) if overall == len(items) else f"{len(items)} of {overall}"
        out.append(f"{status.upper()} ({tally})")
        for r in shown:
            line = f"  {str(r['id']).rjust(width)}  {r['content']}"
            info = claim_info(r, me)
            if info["state"] == "self":
                line += "  [mine]"
            elif info["state"] == "live":
                line += f"  [held by {info['name'] or info['session']}, {info['held_for']}]"
            elif info["state"] == "stale":
                line += f"  [stale claim: {info['name'] or info['session']} is gone]"
            out.append(line)
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
