---
name: backlog-board
description: Read, triage, and work items from this project's backlog — a SQLite kanban board at .claude/backlog.db that the user files into with /backlog. Use when the user asks what's on their backlog, to pick up or work a backlog item, to mark something done, or to plan from the backlog.
allowed-tools: Bash(backlog:*), Bash(${CLAUDE_SKILL_DIR}/backlog:*)
---

# The project backlog

The user captures stray thoughts mid-session with `/backlog <message>`. Those
notes land in a SQLite kanban board at `<project>/.claude/backlog.db` without
ever entering the conversation — so the backlog holds things you have never
seen. Read it; do not reconstruct it from memory.

## The CLI

Everything goes through the `backlog` command. Invoke it as
`${CLAUDE_SKILL_DIR}/backlog` — that path ships next to this file and always
resolves. The bare name `backlog` also works when it is on `PATH`, which both
install modes arrange, but prefer the explicit path: it cannot be shadowed and
it does not depend on how the shell was started.

```
backlog list [--status todo,doing] [--all] [--json] [--limit N]
backlog add <text...>
backlog todo|doing|done|wontfix <id>
backlog edit <id> <text...>
backlog rm <id>
backlog path
```

`backlog list` shows open items (`todo` and `doing`) by default. Add `--all` to
include closed ones. Use `--json` whenever you need to filter, count, or
cross-reference — it returns the full rows, including `created_at` and the
`session_id` that filed each item.

**Never read `backlog.db` directly** with sqlite3, Read, or anything else. Go
through the CLI so schema changes cannot break you.

## Statuses

| Status | Meaning |
|---|---|
| `todo` | Filed, not started. Everything from `/backlog` lands here. |
| `doing` | Actively being worked right now. |
| `done` | Finished. |
| `wontfix` | Consciously dropped — kept for the record rather than deleted. |

## Working an item

1. `backlog list` and show the user what is open.
2. **Confirm which item** before starting. Notes are terse and were written in a
   hurry; if #4 says "fix the config thing", ask what it meant rather than
   picking an interpretation and running with it.
3. `backlog doing <id>` when you start.
4. Do the work.
5. `backlog done <id>` once it is genuinely finished and verified.

If the user asks you to work "the backlog" wholesale, do not silently start on
everything. Show them the list and agree on scope first.

## Mutation rules

- `doing` and `done` are yours to set as a natural part of doing the work.
  Marking `done` requires the work to actually be complete — not written, not
  probably-fine, complete.
- `wontfix` and `rm` are the user's call. Ask first, every time. `rm` is
  irreversible; prefer `wontfix`, which keeps the record.
- `edit` is for clarifying an existing note's wording at the user's request.
  Never rewrite a note to match what you did to it.
- File new items with `backlog add`. Do not invoke `/backlog` — that is a
  user-only command and it is not available to you.

## Reporting

If the board is empty, say so plainly. Do not invent plausible-sounding backlog
items, and do not pad a short list with suggestions of your own — the user is
asking what *they* wrote down. If you want to propose extra work, say clearly
that it is your suggestion and not from the backlog.

If `.claude/backlog-fallback.txt` exists, the capture hook hit a database error
and spilled notes there as plaintext. Mention it — those items are not on the
board and the user probably does not know.

If the `backlog` command cannot be found at all, say so and point the user at
`install.sh` in the plugin repo. Do not work around it by reading the database
directly — a board you cannot write back to is worse than no board.
