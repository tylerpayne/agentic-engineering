#!/usr/bin/env bash
# Install the backlog plugin at user level, so the command is a bare /backlog.
#
# Installed as a plugin, Claude Code namespaces the command to /backlog:backlog.
# Symlinking into ~/.claude instead gives the bare name. The repo stays the
# single source of truth -- everything here is a symlink, so `git pull` is
# enough to update.
#
#   ./install.sh              install
#   ./install.sh --uninstall  remove
#   ./install.sh --config-dir DIR   target a different config dir (for testing)

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$REPO/plugins/backlog"
CONFIG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
BIN_DIR="$HOME/.local/bin"
UNINSTALL=0

while [ $# -gt 0 ]; do
  case "$1" in
    --uninstall) UNINSTALL=1; shift ;;
    --config-dir) CONFIG_DIR="$2"; shift 2 ;;
    --bin-dir) BIN_DIR="$2"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
done

command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

SETTINGS="$CONFIG_DIR/settings.json"

# The hook block is written by python so the merge into an existing
# settings.json is structural rather than textual.
merge_settings() {
  python3 - "$SETTINGS" "$PLUGIN" "$1" <<'PY'
import json, os, shutil, sys

settings_path, plugin, action = sys.argv[1], sys.argv[2], sys.argv[3]
EVENT = "UserPromptExpansion"
MATCHER = "^(backlog:)?backlog$"

settings = {}
if os.path.exists(settings_path):
    with open(settings_path) as fh:
        text = fh.read().strip()
    if text:
        try:
            settings = json.loads(text)
        except json.JSONDecodeError as exc:
            sys.exit(f"{settings_path} is not valid JSON ({exc}); fix it before installing")
    # Back up whatever was there before we touch it.
    shutil.copy2(settings_path, settings_path + ".backlog-bak")

hooks = settings.setdefault("hooks", {})
entries = hooks.setdefault(EVENT, [])
# Drop any previous entry of ours; leave every other hook untouched.
entries[:] = [e for e in entries if e.get("matcher") != MATCHER]

if action == "install":
    entries.append({
        "matcher": MATCHER,
        "hooks": [{
            "type": "command",
            "command": "python3",
            "args": [
                os.path.join(plugin, "hooks", "backlog_hook.py"),
                "--project", "${CLAUDE_PROJECT_DIR}",
            ],
            "timeout": 10,
        }],
    })

if not entries:
    hooks.pop(EVENT, None)
if not hooks:
    settings.pop("hooks", None)

os.makedirs(os.path.dirname(settings_path), exist_ok=True)
tmp = settings_path + ".tmp"
with open(tmp, "w") as fh:
    json.dump(settings, fh, indent=2)
    fh.write("\n")
os.replace(tmp, settings_path)
print(f"  {action}ed {EVENT} hook in {settings_path}")
PY
}

# Only ever remove a link we own, never a real file someone else put there.
unlink_ours() {
  local path="$1" target="$2"
  if [ -L "$path" ] && [ "$(readlink "$path")" = "$target" ]; then
    rm "$path"; echo "  removed $path"
  elif [ -e "$path" ]; then
    echo "  left $path alone (not our symlink)"
  fi
}

link_ours() {
  local target="$1" path="$2"
  if [ -e "$path" ] && [ ! -L "$path" ]; then
    echo "  refusing to overwrite existing file $path" >&2; return 1
  fi
  mkdir -p "$(dirname "$path")"
  ln -sfn "$target" "$path"
  echo "  linked $path"
}

if [ "$UNINSTALL" = 1 ]; then
  echo "Uninstalling backlog from $CONFIG_DIR"
  unlink_ours "$CONFIG_DIR/commands/backlog.md" "$PLUGIN/commands/backlog.md"
  unlink_ours "$CONFIG_DIR/skills/backlog-board" "$PLUGIN/skills/backlog-board"
  unlink_ours "$BIN_DIR/backlog" "$PLUGIN/bin/backlog"
  merge_settings uninstall
  echo "Done. Your backlog databases were not touched."
  exit 0
fi

echo "Installing backlog from $REPO into $CONFIG_DIR"
link_ours "$PLUGIN/commands/backlog.md" "$CONFIG_DIR/commands/backlog.md"
link_ours "$PLUGIN/skills/backlog-board" "$CONFIG_DIR/skills/backlog-board"
link_ours "$PLUGIN/bin/backlog" "$BIN_DIR/backlog"
merge_settings install

echo
echo "Done. In a new session (or after /reload-plugins):"
echo "  /backlog <message>   file a note, without involving Claude"
echo "  /backlog             show the board"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo; echo "Note: $BIN_DIR is not on your PATH; add it to use \`backlog\` in a terminal." ;;
esac
