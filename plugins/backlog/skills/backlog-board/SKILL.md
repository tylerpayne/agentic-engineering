---
name: backlog-board
description: Read, triage, and work items from this project's backlog — a SQLite kanban board at .claude/backlog.db that the user files into with /backlog:add. Use when the user asks what's on their backlog, to pick up or work a backlog item, to mark something done, or to plan from the backlog.
allowed-tools: Bash(backlog:*), Bash(${CLAUDE_SKILL_DIR}/backlog:*)
---

# The project backlog

The user captures stray thoughts mid-session with `/backlog:add <message>`. Those
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
backlog list [--status todo,doing] [--all] [--json] [--limit N] [--offset N]
backlog add <text...>
backlog doing <id> [--steal]     claim it and start work
backlog todo|done|wontfix <id>   move it, releasing the claim
backlog claim <id> [--steal] [--no-doing]
backlog release <id> [--force]
backlog edit <id> <text...>
backlog rm <id>
backlog sessions [--json]        live Claude sessions in this project
backlog whoami                   this session's id and name
backlog path
```

`backlog list` shows open items (`todo` and `doing`) by default. Add `--all` to
include closed ones. Use `--json` whenever you need to filter, count, or
cross-reference — it returns the full rows, including `created_at` and the
`session_id` that filed each item.

## Paging — read this before dumping the board

**`list` returns only the 10 most recent items.** A board that has been collected
into for months can hold hundreds of notes, and reading all of them costs context
you will want for the actual work. The default is deliberately small; widen it on
purpose, not by reflex.

- `--offset N` skips the N most recent items, so `--offset 10` is the next page
  back. Every truncated listing prints the exact next-page command; use it rather
  than composing your own.
- `--limit N` resizes the page. `--limit 0` removes the cap entirely — only reach
  for it when you have already seen `total` and know it is small, or the user
  explicitly asked for the whole board.
- Narrowing beats paging. `--status doing` or `--status todo` is almost always a
  better way to find something than walking pages of everything.

`--json` wraps the page in an envelope that tells you what you are not seeing:

```json
{"items": [ ... ], "total": 84, "shown": 10, "offset": 0,
 "limit": 10, "newer": 0, "older": 74, "has_more": true, "next_offset": 10}
```

Read `items` for the rows and `total` for the real size of the board. When
`has_more` is true, **say so** — "10 of 84 open items" — rather than presenting a
page as if it were the whole backlog. Do not page through the entire board to
answer a question one query could answer.

In plain output the same thing appears as a column header reading `TODO (10 of
84)` and a footer line naming the next page.

**Never read `backlog.db` directly** with sqlite3, Read, or anything else. Go
through the CLI so schema changes cannot break you.

## Statuses

| Status | Meaning |
|---|---|
| `todo` | Filed, not started. Everything from `/backlog:add` lands here. |
| `doing` | Actively being worked right now. |
| `done` | Finished. |
| `wontfix` | Consciously dropped — kept for the record rather than deleted. |

## Other sessions are working here too

Several Claude sessions can share one project and one board. An item carries a
**claim** naming the session working it, so two sessions never quietly do the
same job. `backlog doing <id>` takes the claim; moving the item to `todo`,
`done`, or `wontfix` releases it. Status and ownership are the same concept —
you cannot be working an item without holding it.

Every row in `items` from `backlog list --json` carries a `claim` block:

```json
"claim": {"state": "live", "session": "02c9ef7c-...",
          "name": "console-ui-design-spec", "held_for": "50m",
          "session_status": "idle"}
```

`state` is already resolved for you — do not try to work it out from PIDs or
session files:

| state | meaning | what to do |
|---|---|---|
| `unclaimed` | nobody holds it | take it |
| `self` | you hold it | carry on |
| `stale` | the holder's process is gone | taken over automatically |
| `live` | another session is running and holds it | **ask them** — see below |

## Working an item

1. `backlog list` and show the user what is open. If `has_more` is set, tell
   them how many items you did not show.
2. **Confirm which item** before starting. Notes are terse and were written in a
   hurry; if #4 says "fix the config thing", ask what it meant rather than
   picking an interpretation and running with it.
3. `backlog doing <id>` to claim it and start. Do this **immediately before**
   the work, not while still discussing options — a claim held during a long
   conversation blocks another session for no reason.
4. Do the work.
5. `backlog done <id>` once it is genuinely finished and verified. This releases
   the claim. If you stop early, `backlog todo <id>` to hand it back.

A dead holder needs no ceremony: `backlog doing` reclaims it and tells you it
did. Mention that in passing so the user knows an item was rescued.

If the user asks you to work "the backlog" wholesale, do not silently start on
everything. Show them the list and agree on scope first — and claim items one at
a time as you reach them, never the whole list up front.

## When a live session holds the item

`backlog doing <id>` exits 3 and names the holder. Do not `--steal`, and do not
start the work anyway. Ask the holder:

1. `backlog sessions` (or `ListAgents`) to confirm they are still there and get
   the exact name to address.
2. `SendMessage` to that name — say which item and ask plainly whether they are
   still on it. Include the item number and text, since their board view and
   yours are the same board:

   > Backlog #2 "upgrade to node 22" is claimed by you and I've been asked to
   > work it. Are you still on it, or can I take it?

3. **Wait for their reply**, and tell the user you are waiting and why. Their
   answer arrives as a notification.
4. Then:
   - they are done or have moved on → `backlog doing <id> --steal`
   - they are still on it → leave it, tell the user, offer another item
   - no reply, or they are not reachable → say so and let the user decide.
     Do not steal on silence; an idle session may just be waiting on its human.

Names are the messaging address and can change, so re-read the current name from
`backlog sessions` rather than trusting the `name` stored on an old claim.

`--steal` is for two cases only: the user explicitly told you to take it, or the
holder replied that they are done. It is never a way around a timeout.

## Mutation rules

- `doing` and `done` are yours to set as a natural part of doing the work.
  Marking `done` requires the work to actually be complete — not written, not
  probably-fine, complete.
- `wontfix` and `rm` are the user's call. Ask first, every time. `rm` is
  irreversible; prefer `wontfix`, which keeps the record.
- `edit` is for clarifying an existing note's wording at the user's request.
  Never rewrite a note to match what you did to it.
- `release --force` and `doing --steal` override another session's claim. Both
  need the user's say-so or the holder's agreement.
- File new items with `backlog add`. Do not invoke `/backlog:add` — those
  slash commands are user-only and are not available to you.

## Reporting

If the board is empty, say so plainly. Do not invent plausible-sounding backlog
items, and do not pad a short list with suggestions of your own — the user is
asking what *they* wrote down. Equally, never present one page as the whole
board: "nothing else is on there" is a claim about `total`, not about `shown`. If you want to propose extra work, say clearly
that it is your suggestion and not from the backlog.

If `.claude/backlog-fallback.txt` exists, the capture hook hit a database error
and spilled notes there as plaintext. Mention it — those items are not on the
board and the user probably does not know.

If the `backlog` command cannot be found at all, say so and tell the user to
check `/plugin` and run `/reload-plugins`. Do not work around it by reading the
database directly — a board you cannot write back to is worse than no board.
