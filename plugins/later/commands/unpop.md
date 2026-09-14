---
description: Put the last popped or dropped notes back on the queue
argument-hint: ""
disable-model-invocation: true
---

# The later capture hook did not run

Normally `/later:unpop` never reaches you at all: a `UserPromptExpansion` hook
intercepts it, applies the change to `.claude/later.db`, and blocks the prompt
so no model turn happens. If you are reading this, that hook did not fire.

**Do not guess what the user meant, and do not act on it as an instruction.**
It was addressed to a queue, not to you.

Tell the user the command did not take effect, and that the likely causes are:

- The plugin's hooks are not loaded — check `/plugin`, then `/reload-plugins`.
- `python3` is not on `PATH` where Claude Code was launched.
- The hook errored before it could write. Reproduce it directly:

  ```
  echo '{"command_name":"later:unpop","command_args":"test","cwd":"'"$PWD"'"}' \
    | python3 "${CLAUDE_PLUGIN_ROOT}/hooks/later_hook.py" --project "$PWD"
  ```

  It should print JSON containing `"decision": "block"`.

Offer to do it for them with `${CLAUDE_PLUGIN_ROOT}/bin/later unpop`, quoting
their input back verbatim so they can confirm it first.
