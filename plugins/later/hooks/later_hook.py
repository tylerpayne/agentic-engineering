#!/usr/bin/env python3
"""UserPromptExpansion hook: apply /later:* without invoking the model.

Claude Code fires this event when a slash command expands, *before* the command
body is rendered into a prompt. Blocking here returns shouldQuery: false, so the
note is stored and the main loop is never touched -- no turn, no tokens, and
nothing added to the transcript.

/later:pop is deliberately absent from this hook's matcher. Popping is the one
verb whose whole purpose is to reach the model, so it goes the ordinary route
and renders commands/pop.md instead.

Reads the hook payload as JSON on stdin, writes one JSON object to stdout,
always exits 0.
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "lib"))

import later_db as db  # noqa: E402

# "block" -> {"decision": "block", ...}: UI-only system message, nothing in the
#   transcript. Rendered under a hardcoded "operation blocked by hook:" prefix.
# "stop"  -> {"continue": false, "stopReason": ...}: reads as a single line, but
#   also pushes an isMeta entry into the transcript.
BLOCK_STYLE = "block"


def parse_verb(command_name: str) -> str:
    """`later:push` -> `push`. Bare `push` also works."""
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
    text = (args_text or "").strip()
    conn = db.connect(project)

    if verb == "push":
        if not text:
            # An empty /later:push is almost always a typo for /later:peek, so
            # show the queue rather than filing a blank note.
            return "Nothing to queue. Usage: /later:push <message>\n\n" + db.render_queue(
                conn, limit=db.PEEK_LIMIT
            )
        db.queue(conn, text, session_id=session_id, source="slash")
        total = db.count(conn)
        noun = "note" if total == 1 else "notes"
        return f"Queued. {total} {noun} waiting for /later:pop.\n  {text}"

    if verb == "peek":
        return db.render_queue(conn, limit=db.PEEK_LIMIT)

    if verb == "clear":
        rows, _batch = db.resolve(conn, "dropped")
        if not rows:
            return "The queue was already empty."
        noun = "note" if len(rows) == 1 else "notes"
        return (
            f"Dropped {len(rows)} {noun} without sending them.\n"
            f"{db.render_notes(rows)}\n\n/later:unpop puts them back."
        )

    if verb == "unpop":
        rows, state = db.unpop(conn)
        if not rows:
            return "Nothing to restore."
        noun = "note" if len(rows) == 1 else "notes"
        verb_word = "popped" if state == "popped" else "dropped"
        return (
            f"Restored {len(rows)} {verb_word} {noun}.\n{db.render_notes(rows)}"
        )

    return f"Unknown later command: /later:{verb}"


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
        return f"Queue unavailable - {detail}"
    try:
        path = db.fallback_path(project)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(f"{db.now()}\t{text}\n")
        return f"Queue DB unavailable - saved to {path} instead.\n{detail}"
    except Exception as nested:  # noqa: BLE001 - truly nothing left to try
        return f"Queue write FAILED, note not saved: {text}\n{detail} / {nested}"


def main() -> int:
    arg_project = None
    argv = sys.argv[1:]
    if "--project" in argv:
        idx = argv.index("--project")
        if idx + 1 < len(argv):
            arg_project = argv[idx + 1]

    text, project, verb = "", os.getcwd(), "push"
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        verb = parse_verb(payload.get("command_name")) or "push"
        text = (payload.get("command_args") or "").strip()
        project = resolve_project(arg_project, payload)
        message = handle(verb, text, project, payload.get("session_id"))
    except Exception as exc:  # noqa: BLE001 - a hook must never leak the prompt
        message = salvage(project, text if verb == "push" else "", exc)

    emit(message)
    return 0


if __name__ == "__main__":
    sys.exit(main())
