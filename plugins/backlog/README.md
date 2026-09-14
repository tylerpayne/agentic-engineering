# backlog

Fire-and-forget note capture for Claude Code.

Type `/backlog:add fix the flaky auth spec` mid-session and the note lands in a
per-project SQLite kanban board. **Claude never sees it** — no model turn, no
tokens, nothing added to the transcript, and whatever Claude was doing carries
on undisturbed. Then a skill teaches Claude to read the board back and work
items off it.

```
/backlog:add upgrade to node 22      # file a note
/backlog:list [page]                 # print the board, 10 at a time
/backlog:doing 3                     # claim #3 and start
/backlog:done 3                      # close it, releasing the claim
```

There is one command per verb (`add`, `list`, `doing`, `done`, `todo`,
`wontfix`, `rm`), so the verb is never guessed from your text —
`/backlog:add done with the migration` files a note rather than closing item #0.

## How it skips the model loop

A plain slash command cannot do this. Every slash command renders its body into
a user message and queries the model; there is no frontmatter flag to suppress
that. (`disable-model-invocation` only stops *Claude* from invoking a command —
the user typing it still costs a turn.)

What does work is the **`UserPromptExpansion`** hook event. It fires when a slash
command expands, *before* the body is rendered, and its matcher is tested against
the command name. When the hook blocks, Claude Code returns `shouldQuery: false`
— the model is never called — and the only artifact is a local UI system
message. Nothing reaches the API.

So `/backlog` is really two pieces:

- `hooks/hooks.json` matches `^(backlog:)?(add|list|doing|done|todo|wontfix|rm)$`
  on `UserPromptExpansion` and runs `hooks/backlog_hook.py`, which applies the
  change and blocks. The hook reads the verb from `command_name`.
- `commands/*.md` exist only so those are real commands. Each body renders
  **only if the hook failed to fire**, and says so rather than guessing.

The same event is used by the official `claude-security` plugin, which matches
`^claude-security:claude-security$` to print its banner.

## Install

```bash
claude plugin marketplace add tylerpayne/claude-code-plugins
claude plugin install backlog@tylerpayne
```

Claude Code namespaces plugin commands, so they read as `/backlog:add`,
`/backlog:list`, and so on. Lookup is exact-match on the full name — there is no
prefix stripping — so a bare `/add` will not resolve. Tab completion from
`/backlog:` lists them all.

While the plugin is enabled, `bin/` is added to `PATH`, so `backlog` also works
as a normal terminal command.

For iterating on the plugin itself:

```bash
claude --plugin-dir /path/to/claude-code-plugins/plugins/backlog
```

Requires `python3` (standard library only -- no dependencies).

## The `backlog` CLI

`bin/` is added to `PATH` for enabled plugins, so `backlog` also works from a
normal terminal:

```
backlog add <text...>                 file a new item as todo
backlog list [--status s1,s2] [--all] [--json] [--limit N] [--offset N]
backlog doing <id> [--steal]          claim it and start work
backlog todo|done|wontfix <id>        move it, releasing the claim
backlog claim <id> [--steal] [--no-doing]
backlog release <id> [--force]
backlog edit <id> <text...>           rewrite an item
backlog rm <id>                       delete outright
backlog sessions [--json]             live Claude sessions in this project
backlog whoami                        this session's id and name
backlog path                          print the resolved db path
```

`list` shows open items (`todo`, `doing`) by default. The project root is found
by walking up from the cwd for `.claude/` or `.git/`, so it works from any
subdirectory of a repo.

### Paging

Reads are capped at the **10 most recent items**. The board is read into a
model's context far more often than into a terminal, and an unbounded read of a
board with months of notes on it is the one thing here that can blow up a context
window — so the cap is the default rather than an opt-in.

```
backlog list                     # the 10 most recent open items
backlog list --offset 10         # the 10 before those
backlog list --limit 25          # a bigger page
backlog list --limit 0           # no cap; ask for this deliberately
/backlog:list 2                  # page 2, from the slash command
```

`--offset` counts back from the newest item, so paging never reshuffles under a
note filed mid-read. A truncated listing says what it left out and prints the
exact command for the next page:

```
TODO (10 of 84)
  ...
10 most recent of 84 - 74 older: backlog list --offset 10
```

`--json` returns the page inside an envelope carrying `total`, `shown`,
`offset`, `older`, `has_more`, and `next_offset` alongside `items`, so a reader
always knows how much of the board it is not looking at.

## Concurrent sessions

Several Claude sessions can share one project and one board, so items carry a
**claim** naming the session working them. `backlog doing <id>` takes the claim;
moving an item to `todo`, `done`, or `wontfix` releases it. Status and ownership
are one concept — you cannot work an item without holding it.

The claim column is not the lock. The lock is an atomic compare-and-swap:

```sql
UPDATE items SET claimed_by = ?, ... WHERE id = ? AND (claimed_by IS NULL OR claimed_by IN (...))
```

Both racing sessions issue it, SQLite serialises them, and exactly one sees
`rowcount` 1. Verified with 240 concurrent claim attempts across 20 contested
items: exactly one winner each, zero double-claims.

**Liveness** comes from Claude Code's session registry
(`~/.claude/sessions/<pid>.json`), which records each session's `sessionId`,
`pid`, `procStart`, `cwd`, current `name`, and `status`. A holder is live if its
PID is running *and* the process start time matches the record — `kill(0)` alone
would let a recycled PID pin a claim forever. The registry is stored in UTC while
`ps` prints local time, so the two are compared as instants, not strings.

The CLI resolves all of this into a single `state` the skill can act on:

| state | meaning |
|---|---|
| `unclaimed` | nobody holds it |
| `self` | this session holds it |
| `stale` | the holder's process is gone — reclaimed automatically |
| `live` | another session is running and holds it |

A stale claim is taken over silently and reported. A **live** claim is refused
(exit 3, naming the holder); the skill is told to use `ListAgents`/`SendMessage`
to ask that session whether they are still on it, wait for the reply, and only
then `--steal`. It never steals on silence.

The stored session UUID is the identity; the session *name* is re-resolved from
the registry at check time, because sessions can be renamed after claiming.

## Storage

`<project>/.claude/backlog.db` — one board per project, WAL mode.

```sql
CREATE TABLE items (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  content         TEXT NOT NULL,
  status          TEXT NOT NULL DEFAULT 'todo'
                  CHECK (status IN ('todo','doing','done','wontfix')),
  created_at      TEXT NOT NULL,   -- ISO8601 UTC
  updated_at      TEXT NOT NULL,
  session_id      TEXT,            -- the Claude session that filed it
  source          TEXT,            -- 'slash' | 'cli' | 'skill'
  claimed_by      TEXT,            -- session UUID, or "pid:N" outside Claude
  claimed_by_name TEXT,            -- last-known label; registry is authoritative
  claimed_at      TEXT
);
```

Schema changes migrate on open, gated on `PRAGMA user_version` *and* the columns
actually present, so a v1 database upgrades in place without losing rows.

Argument parsing is deliberately strict: a subcommand is only recognised as
`<verb> <integer>` and nothing else, so `/backlog done with the migration, need
to clean up` files a note instead of closing item #0.

If the database is ever unreadable, the hook appends the raw note to
`.claude/backlog-fallback.txt` and still blocks — it will not lose a note, and it
will not forward one to the model as a prompt.

## Layout

```
.claude-plugin/plugin.json
commands/*.md                     # one per verb; bodies are fallback diagnostics
hooks/hooks.json                  # UserPromptExpansion matcher
hooks/backlog_hook.py             # the capture path
lib/backlog_db.py                 # storage, claims, rendering
lib/sessions.py                   # session registry + liveness
bin/backlog                       # standalone CLI
skills/backlog-board/SKILL.md     # model-facing read/triage skill
skills/backlog-board/backlog      # -> ../../bin/backlog, so ${CLAUDE_SKILL_DIR}/backlog resolves
```

Both entrypoints resolve `lib/` through `os.path.realpath(__file__)`, so they
keep working when invoked through the installer's symlinks.

## Known rough edges

The confirmation renders under a prefix Claude Code hardcodes, which cannot be
suppressed from the plugin side:

```
UserPromptExpansion operation blocked by hook:
#3 filed - upgrade to node 22
```

The hook also sets `suppressOriginalPrompt: true`, which normally stops Claude
Code from echoing `Original prompt: /backlog:add ...` underneath. That flag is
read from `hookSpecificOutput` and honoured identically in 2.1.238 and 2.1.239,
but it has been observed to be dropped in a long-running interactive session. If
you see the echo, restart the session; it does not reproduce in a fresh one.

**Do not switch `BLOCK_STYLE` to `"stop"`.** The `{"continue": false}` variant
avoids the prefix and never echoes the prompt, but it pushes an `isMeta` message
into the transcript that **is sent to the model** — a note filed that way is
recited back on the next turn, which defeats the entire point of the plugin.
Measured, not assumed: with `"stop"`, a following turn repeated a nonsense
phrase from a filed note; with `"block"` the same test returns "NONE". The
constant stays for experiments, but `"block"` is the only correct setting.
