# agentic-engineering

Skills, command-line tools, and Claude Code plugins for agentic engineering.

| Plugin | What it does |
|---|---|
| [backlog](plugins/backlog) | `/backlog:add <note>` files a thought into a per-project SQLite kanban board **without invoking the model** — no turn, no tokens, no derailing what Claude is doing. A companion skill reads and works the board, and coordinates across concurrent sessions. |
| [later](plugins/later) | `/later:push <note>` parks a thought **without invoking the model**, and `/later:pop` hands Claude everything parked as one message. Use it when a thought arrives mid-task and you do not want to redirect what Claude is doing. |
| [plain-english](plugins/plain-english) | A skill that constrains how Claude writes prose. It bans the sentence shapes, punctuation, and cadence that make text read as machine-generated, and it applies to every kind of writing. |
| [python](plugins/python) | Python conventions with `python-style bootstrap` and `python-style verify`: uv, Hatchling, Poe, Ruff, ty, pytest, and typed records. |

## Install

```bash
claude plugin marketplace add tylerpayne/agentic-engineering
claude plugin install backlog@tylerpayne
claude plugin install plain-english@tylerpayne
claude plugin install later@tylerpayne
claude plugin install python@tylerpayne
```

Update everything later with `claude plugin marketplace update tylerpayne`.

Plugin commands are namespaced by Claude Code, so they read as `/backlog:add`,
`/backlog:list`, and so on. Tab completion from `/backlog:` lists them.

## GitHub Pages

The static catalog is configured to publish at
[tylerpayne.github.io/agentic-engineering](https://tylerpayne.github.io/agentic-engineering/).
To enable publishing, open the repository's **Settings → Pages** and select
**GitHub Actions** as the build source, then push this setup to `main`.
The **GitHub Pages** workflow also supports manual runs and builds pull requests
without deploying them.

The web version serves agents that do not support Claude marketplaces:

- `llms.txt` explains discovery, downloads, dependencies, and adaptation.
- `index.json` lists every skill, binary, downloadable file, and SHA-256 checksum.
- `downloads/<plugin>.tar.gz` bundles each plugin's skills, binaries, supporting
  libraries, documentation, and license with the directory layout preserved.
- `plugins/<plugin>/...` serves individual files at direct URLs.

`site/plugins.json` supplies factual descriptions and custom invocation metadata:

- `agent_invoked`: the agent applies the skill or invokes its actions.
- `user_invoked`: the user directly operates its commands or actions.
- `invocation_notes`: explains the intended workflow.

The flags are independent. Backlog is both; later is user-invoked only; python
and plain-english are agent-invoked only. A user activating a skill does not count
as invoking its actions. These describe intended usage, not access permissions.
All bundles remain downloadable; agents should select `agent_invoked: true`.

These fields appear in `index.json` (schema version 2), the page, and the agent
guide. They are our convention, not marketplace schema fields. Every new plugin
needs an explicit entry; the build fails if one is missing.

The Python CLIs work independently; Claude-specific hooks and session integration
are not automatically available to other agents. The generated guide explains
how to substitute local binary paths for Claude-specific skill variables.

Claude Code users can also add the hosted catalog:

```bash
claude plugin marketplace add https://tylerpayne.github.io/agentic-engineering/marketplace.json
```

The build reads `.claude-plugin/marketplace.json` and generates the page and a
web-compatible catalog with Git subdirectory sources. Plugin code is fetched
from GitHub, pinned to the deployed commit. The existing GitHub marketplace
install command still works. No plugin list needs to be maintained in the page.

Preview locally with Python 3.9 or newer:

```bash
python3 scripts/build_site.py
python3 -m http.server 8000 --directory _site
```

Open `http://localhost:8000`. Edit `site/index.html` to change the page design.
Build output in `_site/` is ignored by Git; only generated site files are deployed.

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
