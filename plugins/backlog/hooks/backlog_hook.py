#!/usr/bin/env python3
"""UserPromptExpansion hook: apply /backlog:* without invoking the model.

Claude Code fires this event when a slash command expands, *before* the command
body is rendered into a prompt. Blocking here returns shouldQuery: false, so the
message is stored and the main loop is never touched -- no turn, no tokens, and
nothing added to the transcript.

Reads the hook payload as JSON on stdin, writes one JSON object to stdout,
always exits 0.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))

import backlog_db as db  # noqa: E402
import sessions  # noqa: E402

# "block" -> {"decision": "block", ...}: UI-only system message, nothing in the
#   transcript. Rendered under a hardcoded "operation blocked by hook:" prefix.
# "stop"  -> {"continue": false, "stopReason": ...}: reads as a single line, but
#   also pushes an isMeta entry into the transcript.
BLOCK_STYLE = "block"

# The verb is the command name (`/backlog:done 3`), not something parsed out of
# the arguments, so a note like "done with the migration" can never be mistaken
# for a status change.
_ID = re.compile(r"^#?(\d+)$")


def parse_verb(command_name: str) -> str:
    """`backlog:done` -> `done`. Bare `done` also works."""
    return (command_name or "").rsplit(":", 1)[-1].strip().lower()


def resolve_project(arg_project, payload):
    """Prefer --project, but only if it actually looks usable.

    The hook is invoked with ${CLAUDE_PROJECT_DIR}, which can arrive empty or
    literally unexpanded depending on how the session was started, so fall back
    to the cwd the payload reports.
    """
    for candidate in (arg_project, payload.get("cwd"), os.getcwd()):
        if not candidate or "${" in candidate:
            continue
        if os.path.isdir(candidate):
            return db.resolve_project(candidate)
    return db.resolve_project(os.getcwd())


def handle(verb: str, args_text: str, project: str, session_id: str) -> str:
    """Apply one verb and return the text to show the user."""
    text = (args_text or "").strip()
    conn = db.connect(project)
    me = session_id or sessions.local_holder_id()

    if verb == "list":
        return _list(conn, text, me)

    if verb == "add":
        if not text:
            return "Nothing to file. Usage: /backlog:add <message>"
        item_id = db.add(conn, text, session_id=session_id, source="slash")
        return f"#{item_id} filed - {text}\n\n{db.render_counts(conn)}"

    # Every remaining verb acts on an id.
    match = _ID.match(text)
    if not match:
        return f"Usage: /backlog:{verb} <id>" + (f"  (got {text!r})" if text else "")
    item_id = int(match.group(1))

    if verb == "rm":
        row = db.get(conn, item_id)
        if row is None:
            return f"No item #{item_id}."
        db.remove(conn, item_id)
        return f"#{item_id} deleted - {row['content']}"

    if verb == "doing":
        return _start(conn, item_id, session_id)

    if not db.set_status(conn, item_id, verb):
        return f"No item #{item_id}."
    row = db.get(conn, item_id)
    return f"#{item_id} -> {verb} - {row['content']}\n\n{db.render_counts(conn)}"


def _list(conn, text: str, me: str) -> str:
    """`/backlog:list [page]` -- one page of open items, most recent first.

    Unbounded by default was fine when a board was a day old. It is not fine
    once it has a few hundred rows, so the argument is a 1-based page number.
    """
    page_no = 1
    if text:
        match = _ID.match(text)
        if not match:
            return f"Usage: /backlog:list [page]  (got {text!r})"
        page_no = max(1, int(match.group(1)))

    offset = (page_no - 1) * db.DEFAULT_LIMIT
    pg = db.page(conn, list(db.OPEN_STATUSES), limit=db.DEFAULT_LIMIT, offset=offset)

    if not pg["rows"]:
        if pg["total"]:
            last = (pg["total"] + db.DEFAULT_LIMIT - 1) // db.DEFAULT_LIMIT
            return f"No open items on page {page_no} ({pg['total']} open, {last} pages)."
        closed = db.render_counts(conn)
        return f"No open items. ({closed})" if closed != "empty" else "Backlog is empty."

    board = db.render_board(pg["rows"], me=me, collapse_closed=False,
                            counts=pg["counts"])
    note = db.render_page_note(pg, f"/backlog:list {page_no + 1}")
    return f"{board}\n\n{note}" if note else board


def _start(conn, item_id: int, session_id: str) -> str:
    """`/backlog doing N` -- take the claim as the session that typed it.

    A dead holder is reclaimed silently; a live one is refused, because two
    sessions working the same item is the thing this whole column exists to
    prevent.
    """
    row = db.get(conn, item_id)
    if row is None:
        return f"No item #{item_id}."

    me = session_id or sessions.local_holder_id()
    record = sessions.find_by_session_id(me) if session_id else None
    my_name = (record or {}).get("name")

    info = db.claim_info(row, me)
    if info["state"] == "live":
        who = info["name"] or info["session"]
        return (
            f"#{item_id} is already held by {who}"
            f" ({info['session_status'] or 'unknown'}, held {info['held_for']}).\n"
            f"  {row['content']}\n"
            f"Ask them before starting, or run: backlog doing {item_id} --steal"
        )

    took = info["session"] if info["state"] == "stale" else None
    ok, row = db.claim(conn, item_id, me, my_name, steal_from=took)
    if not ok:
        fresh = db.claim_info(db.get(conn, item_id), me)
        return f"#{item_id} was just claimed by {fresh['name'] or fresh['session']}."
    note = ""
    if took:
        note = f" (took over from dead session {info['name'] or took}, held {info['held_for']})"
    return f"#{item_id} -> doing{note} - {row['content']}\n\n{db.render_counts(conn)}"


def emit(message: str) -> None:
    if BLOCK_STYLE == "stop":
        out = {"continue": False, "stopReason": message}
    else:
        out = {
            "decision": "block",
            "reason": message,
            "hookSpecificOutput": {
                "hookEventName": "UserPromptExpansion",
                "suppressOriginalPrompt": True,
            },
        }
    json.dump(out, sys.stdout)
    sys.stdout.write("\n")


def salvage(project: str, text: str, error: Exception) -> str:
    """Last resort when the database is unusable.

    Losing a note silently is the worst outcome here, and forwarding it to the
    model as a prompt is the second worst. Append it to a plaintext file and
    still block, reporting what broke.
    """
    detail = f"{type(error).__name__}: {error}"
    if not text:
        return f"Backlog unavailable - {detail}"
    try:
        path = db.fallback_path(project)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{db.now()}\t{text}\n")
        return f"Backlog DB unavailable - saved to {path} instead.\n{detail}"
    except Exception as nested:  # noqa: BLE001 - truly nothing left to try
        return f"Backlog write FAILED, note not saved: {text}\n{detail} / {nested}"


def main() -> int:
    arg_project = None
    argv = sys.argv[1:]
    if "--project" in argv:
        idx = argv.index("--project")
        if idx + 1 < len(argv):
            arg_project = argv[idx + 1]

    payload, text, project, verb = {}, "", os.getcwd(), "add"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        verb = parse_verb(payload.get("command_name")) or "add"
        text = (payload.get("command_args") or "").strip()
        project = resolve_project(arg_project, payload)
        message = handle(verb, text, project, payload.get("session_id"))
    except Exception as exc:  # noqa: BLE001 - a hook must never leak the prompt
        message = salvage(project, text if verb == "add" else "", exc)

    emit(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
