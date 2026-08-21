# backlog

A Claude Code plugin for fire-and-forget note capture.

Type `/backlog fix the flaky auth spec` mid-session and the note lands in a
per-project SQLite kanban board. **Claude never sees it** — no model turn, no
tokens, nothing added to the transcript, and whatever Claude was doing carries
on undisturbed. Then a skill teaches Claude to read the board back and work
items off it.

```
/backlog upgrade to node 22          # file a note
/backlog                             # print the board
/backlog doing 3                     # move #3 to doing
/backlog done 3                      # close it
```

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

- `hooks/hooks.json` matches `^(backlog:)?backlog$` on `UserPromptExpansion` and
  runs `hooks/backlog_hook.py`, which writes to SQLite and blocks.
- `commands/backlog.md` exists only so `/backlog` is a real command. Its body
  renders **only if the hook failed to fire**, and it says so rather than trying
  to guess at the note.

The same event is used by the official `claude-security` plugin, which matches
`^claude-security:claude-security$` to print its banner.

## Install

**Recommended — user level, gives you a bare `/backlog`:**

```bash
./install.sh
```

This symlinks the command, the skill, and the CLI into `~/.claude` and
`~/.local/bin`, and merges the hook into `~/.claude/settings.json` (backing the
file up first, and touching nothing else in it). Everything is a symlink, so the
repo stays the source of truth and `git pull` is enough to update.
`./install.sh --uninstall` reverses it and leaves your databases alone.

**Alternative — as a plugin:**

```bash
claude plugin marketplace add /Users/tylerpayne/Code/claude-code-plugin-backlog
claude plugin install backlog@backlog-local
```

Note the tradeoff: Claude Code namespaces every plugin command, so installed this
way the command is **`/backlog:backlog`**, not `/backlog`. Command lookup is
exact-match on the full name — there is no prefix stripping — so the bare form
will not resolve, though tab completion fills it in. If you want to type
`/backlog`, use `install.sh`.

For iterating on the plugin itself:

```bash
claude --plugin-dir /Users/tylerpayne/Code/claude-code-plugin-backlog/plugins/backlog
```

Requires `python3` (standard library only — no dependencies).

## The `backlog` CLI

`bin/` is added to `PATH` for enabled plugins, so `backlog` also works from a
normal terminal:

```
backlog add <text...>                 file a new item as todo
backlog list [--status s1,s2] [--all] [--json] [--limit N]
backlog todo|doing|done|wontfix <id>  move an item
backlog edit <id> <text...>           rewrite an item
backlog rm <id>                       delete outright
backlog path                          print the resolved db path
```

`list` shows open items (`todo`, `doing`) by default. The project root is found
by walking up from the cwd for `.claude/` or `.git/`, so it works from any
subdirectory of a repo.

## Storage

`<project>/.claude/backlog.db` — one board per project, WAL mode.

```sql
CREATE TABLE items (
  id         INTEGER PRIMARY KEY AUTOINCREMENT,
  content    TEXT NOT NULL,
  status     TEXT NOT NULL DEFAULT 'todo'
             CHECK (status IN ('todo','doing','done','wontfix')),
  created_at TEXT NOT NULL,   -- ISO8601 UTC
  updated_at TEXT NOT NULL,
  session_id TEXT,            -- the Claude session that filed it
  source     TEXT             -- 'slash' | 'cli' | 'skill'
);
```

Argument parsing is deliberately strict: a subcommand is only recognised as
`<verb> <integer>` and nothing else, so `/backlog done with the migration, need
to clean up` files a note instead of closing item #0.

If the database is ever unreadable, the hook appends the raw note to
`.claude/backlog-fallback.txt` and still blocks — it will not lose a note, and it
will not forward one to the model as a prompt.

## Layout

```
install.sh                          # user-level install/uninstall
.claude-plugin/marketplace.json     # local marketplace, one entry
plugins/backlog/
  .claude-plugin/plugin.json
  commands/backlog.md               # /backlog; body is a fallback diagnostic only
  hooks/hooks.json                  # UserPromptExpansion matcher (plugin mode)
  hooks/backlog_hook.py             # the capture path
  lib/backlog_db.py                 # storage + rendering, shared
  bin/backlog                       # standalone CLI
  skills/backlog-board/SKILL.md     # model-facing read/triage skill
  skills/backlog-board/backlog      # -> ../../bin/backlog, so ${CLAUDE_SKILL_DIR}/backlog resolves
```

Both entrypoints resolve `lib/` through `os.path.realpath(__file__)`, so they
keep working when invoked through the installer's symlinks.

## Known rough edge

The confirmation renders under a prefix Claude Code hardcodes:

```
UserPromptExpansion operation blocked by hook:
#3 filed - upgrade to node 22
```

It cannot be suppressed from the plugin side. If it grates, set
`BLOCK_STYLE = "stop"` in `hooks/backlog_hook.py` for the one-line
`Operation stopped by hook: ...` variant — which reads better but adds one
`isMeta` entry to the transcript.
