#!/usr/bin/env python3
"""UserPromptExpansion hook: capture /backlog without invoking the model.

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

# Status verbs, plus delete. Matched only as `<verb> <integer>` and nothing else,
# so "/backlog done with the migration, need to clean up" files a note rather
# than being misread as a status change.
_VERBS = set(db.STATUSES) | {"rm"}
_SUBCOMMAND = re.compile(r"^(%s)\s+#?(\d+)$" % "|".join(sorted(_VERBS)), re.IGNORECASE)
_LIST = re.compile(r"^(ls|list)$", re.IGNORECASE)


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


def handle(args_text: str, project: str, session_id: str) -> str:
    """Do the work and return the text to show the user."""
    text = (args_text or "").strip()
    conn = db.connect(project)

    if not text or _LIST.match(text):
        rows = db.list_items(conn, list(db.OPEN_STATUSES))
        board = db.render_board(rows, me=session_id or sessions.local_holder_id())
        if not rows:
            closed = db.render_counts(conn)
            if closed != "empty":
                return f"No open items. ({closed})"
            return "Backlog is empty."
        return board

    match = _SUBCOMMAND.match(text)
    if match:
        verb, raw_id = match.group(1).lower(), int(match.group(2))
        if verb == "rm":
            row = db.get(conn, raw_id)
            if row is None:
                return f"No item #{raw_id}."
            db.remove(conn, raw_id)
            return f"#{raw_id} deleted - {row['content']}"
        if verb == "doing":
            return _start(conn, raw_id, session_id)
        if not db.set_status(conn, raw_id, verb):
            return f"No item #{raw_id}."
        row = db.get(conn, raw_id)
        return f"#{raw_id} -> {verb} - {row['content']}\n\n{db.render_counts(conn)}"

    item_id = db.add(conn, text, session_id=session_id, source="slash")
    return f"#{item_id} filed - {text}\n\n{db.render_counts(conn)}"


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

    payload, text, project = {}, "", os.getcwd()
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        text = (payload.get("command_args") or "").strip()
        project = resolve_project(arg_project, payload)
        message = handle(text, project, payload.get("session_id"))
    except Exception as exc:  # noqa: BLE001 - a hook must never leak the prompt
        message = salvage(project, text, exc)

    emit(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
