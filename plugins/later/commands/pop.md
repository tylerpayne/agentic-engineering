---
description: Hand Claude everything parked with /later:push, as one message
allowed-tools: Bash(later:*), Bash(${CLAUDE_PLUGIN_ROOT}/bin/later:*)
disable-model-invocation: true
---

The notes I parked earlier follow. If the command below errored instead of
listing them, tell me it failed and read the queue with `later peek` rather than
guessing what was in it. Popping already emptied the queue, so `later unpop`
puts it back.

!`"${CLAUDE_PLUGIN_ROOT}/bin/later" pop`
