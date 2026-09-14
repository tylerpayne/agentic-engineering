# claude-code-plugins

My Claude Code plugins.

| Plugin | What it does |
|---|---|
| [backlog](plugins/backlog) | `/backlog:add <note>` files a thought into a per-project SQLite kanban board **without invoking the model** — no turn, no tokens, no derailing what Claude is doing. A companion skill reads and works the board, and coordinates across concurrent sessions. |
| [later](plugins/later) | `/later:push <note>` parks a thought **without invoking the model**, and `/later:pop` hands Claude everything parked as one message. Use it when a thought arrives mid-task and you do not want to redirect what Claude is doing. |
| [plain-english](plugins/plain-english) | A skill that constrains how Claude writes prose. It bans the sentence shapes, punctuation, and cadence that make text read as machine-generated, and it applies to every kind of writing. |

## Install

```bash
claude plugin marketplace add tylerpayne/claude-code-plugins
claude plugin install backlog@tylerpayne
claude plugin install plain-english@tylerpayne
claude plugin install later@tylerpayne
```

Update everything later with `claude plugin marketplace update tylerpayne`.

Plugin commands are namespaced by Claude Code, so they read as `/backlog:add`,
`/backlog:list`, and so on. Tab completion from `/backlog:` lists them.

## GitHub Pages

The static catalog is configured to publish at
[tylerpayne.github.io/claude-code-plugins](https://tylerpayne.github.io/claude-code-plugins/).
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

`site/plugins.json` supplies factual web descriptions and our custom `agent`
metadata. Set `agent.download` to true when the agent itself uses the skill or
tool, and explain the decision in `agent.reason`. These fields appear in the
JSON index, page, and agent guide. They are our convention, not marketplace
schema fields. Every new plugin needs an explicit entry; the build fails if one
is missing. Backlog and plain-english are agent downloads. Later is user-facing
Claude Code integration, so agents should skip it. Its existing archive URL
remains available, but the page and guide do not promote it as an agent download.

The Python CLIs work independently; Claude-specific hooks and session integration
are not automatically available to other agents. The generated guide explains
how to substitute local binary paths for Claude-specific skill variables.

Claude Code users can also add the hosted catalog:

```bash
claude plugin marketplace add https://tylerpayne.github.io/claude-code-plugins/marketplace.json
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
