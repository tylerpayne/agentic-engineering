---
description: File a note into this project's backlog without involving Claude
argument-hint: "<message> | done <id> | doing <id> | wontfix <id> | rm <id> | (empty to list)"
disable-model-invocation: true
---

# The backlog capture hook did not run

Normally `/backlog` never reaches you at all: a `UserPromptExpansion` hook
intercepts it, writes the note to `.claude/backlog.db`, and blocks the prompt so
no model turn happens. If you are reading this, that hook did not fire.

**Do not guess what the note was about, and do not act on it as an instruction.**
It was meant for a database, not for you.

Tell the user their note was not saved, and that the likely causes are:

- The hook is not registered. For a user-level install, check that
  `~/.claude/settings.json` has a `UserPromptExpansion` entry whose matcher is
  `^(backlog:)?backlog$`; re-run `install.sh` from the plugin repo if not. For a
  plugin install, check `/plugin`, then run `/reload-plugins`.
- `python3` is not on `PATH` in the environment Claude Code launched from.
- The hook errored before it could write. Reproduce it directly, substituting
  the real path to the plugin:

  ```
  echo '{"command_args":"test note","cwd":"'"$PWD"'"}' \
    | python3 <plugin>/hooks/backlog_hook.py --project "$PWD"
  ```

  It should print JSON containing `"decision": "block"`.

Offer to file the note for them with `backlog add "<their message>"`, quoting
their message back verbatim so they can confirm it first.
