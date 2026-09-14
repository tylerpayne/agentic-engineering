# later

Park a thought while Claude is working, then hand it all of them at once.

`/later:push <text>` stores the text and blocks the prompt, so no model turn
happens and nothing enters the transcript. Claude never sees it. When you are
ready, `/later:pop` drains the queue into a single user message that Claude does
see and acts on.

The point is that a thought can arrive while Claude is mid-task. Typing it as a
prompt queues a turn and redirects the work. `/later:push` stores it instead, and
you decide when the batch lands.

```
/later:push rename the widget module to panel
/later:push the CI cache key ignores the lockfile
/later:push drop the unused legacy exporter
      ... Claude finishes what it was doing ...
/later:pop
```

Claude receives one message holding all three notes, oldest first, framed as
things you are asking for now.

## Commands

| Command | What it does | Costs a turn |
|---|---|---|
| `/later:push <text>` | Park a note | no |
| `/later:pop` | Send everything parked to Claude and empty the queue | yes |
| `/later:peek` | Show the queue without sending it | no |
| `/later:clear` | Drop the queue without sending it | no |
| `/later:unpop` | Put the last popped or dropped notes back | no |

Everything except `/later:pop` runs inside a hook and never reaches the model.

## How it works

Two mechanisms, one per direction.

**Capture** uses the `UserPromptExpansion` hook event, which fires when a slash
command expands and before the command body becomes a prompt. The hook writes to
SQLite and returns `decision: "block"`, which makes the handler return
`shouldQuery: false`. The model is never called, and the only artifact is a
system message in the terminal. `suppressOriginalPrompt` drops the echo of what
you typed.

`hooks.json` matches `^(later:)?(push|peek|clear|unpop)$`. Pop is missing from
that list deliberately, because pop is the one verb whose purpose is to reach the
model.

**Delivery** uses bash execution inside a command body. `commands/pop.md` runs
``!`"${CLAUDE_PLUGIN_ROOT}/bin/later" pop` `` and Claude Code substitutes the
output into the user message before sending it. A `UserPromptExpansion` hook
cannot do this half: its output schema carries only `additionalContext` and
`suppressOriginalPrompt`, and it has no way to rewrite a prompt.

## Nothing is deleted

A pop marks its rows resolved and stamps them with a batch number rather than
removing them. `/later:unpop` restores the most recent batch, whether it was
popped or dropped. A mistimed pop would otherwise destroy notes you cannot
retype.

`resolve()` opens with `BEGIN IMMEDIATE`, so two sessions popping the same queue
at the same moment cannot both come away with the same notes.

## The CLI

`bin/` joins `PATH` while the plugin is enabled, so `later` works from a terminal
on the same queue the slash commands write to.

```
later push <text...>         park a note (alias: later add)
later pop [--json]           drain the queue and print it
later peek [--limit N]       show the queue
later count                  how many are waiting
later clear                  drop the queue
later unpop                  restore the last batch
later history [--limit N]    notes already popped or dropped
later path                   print the resolved database path
```

## Storage

One queue per project at `<project>/.claude/later.db`. The project root is the
nearest ancestor directory holding `.claude/` or `.git/`, so `later` finds the
same queue from any subdirectory.

```sql
CREATE TABLE notes (
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
```

The queue belongs to the project rather than to a session, so you can park a note
in one terminal and pop it in another.

If the database cannot be opened, the hook appends the note to
`.claude/later-fallback.txt` and reports the error. It still blocks the prompt.
Forwarding a note to the model as a prompt is the outcome this plugin exists to
prevent, so a broken write never falls back to that.
