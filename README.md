# claude-code-plugins

My Claude Code plugins.

| Plugin | What it does |
|---|---|
| [backlog](plugins/backlog) | `/backlog:add <note>` files a thought into a per-project SQLite kanban board **without invoking the model** — no turn, no tokens, no derailing what Claude is doing. A companion skill reads and works the board, and coordinates across concurrent sessions. |

## Install

```bash
claude plugin marketplace add tylerpayne/claude-code-plugins
claude plugin install backlog@tylerpayne
```

Update everything later with `claude plugin marketplace update tylerpayne`.

Plugin commands are namespaced by Claude Code, so they read as `/backlog:add`,
`/backlog:list`, and so on. Tab completion from `/backlog:` lists them.

## Adding a plugin

Drop it under `plugins/<name>/` and add an entry to
`.claude-plugin/marketplace.json`. Everything else is discovered from the
directory layout:

```
plugins/<name>/
  .claude-plugin/plugin.json    name, description, author
  commands/*.md                 slash commands
  skills/<skill>/SKILL.md       skills
  bin/*                         added to PATH while the plugin is enabled
  hooks/hooks.json              hooks; ${CLAUDE_PLUGIN_ROOT} resolves to the plugin dir
  README.md
```
