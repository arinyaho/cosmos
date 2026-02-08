#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$HOME/.code-assistant.json"
TEMPLATE="$SCRIPT_DIR/config.json.template"

ORIGIN=$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || echo "(unknown)")
echo "Installing code-assistants from: $SCRIPT_DIR"
echo "  Origin: $ORIGIN"
echo ""

# --- Phase 0: Config file check ---
# First run: copy template and exit so the user can fill it in.
# Second run: config exists, proceed to symlink setup.

if [ ! -f "$CONFIG_FILE" ]; then
  echo "=== First-time setup ==="
  echo ""
  cp "$TEMPLATE" "$CONFIG_FILE"
  chmod 600 "$CONFIG_FILE"
  echo "  Copied template to ~/.code-assistant.json (mode 600)"
  echo ""
  echo "  Edit the file and replace the placeholders:"
  echo "    \$EDITOR ~/.code-assistant.json"
  echo ""
  echo "  Placeholders to fill in:"
  echo "    <GCP_PROJECT_ID>    - your GCP project (e.g. my-project)"
  echo "    <YOUR_ORG>          - Jira org (e.g. myorg)"
  echo "    <YOUR_EMAIL>        - Jira login email"
  echo "    <JIRA_PROJECT_KEY>  - Jira project key (e.g. MYPROJ)"
  echo "    <USERNAME>          - your org username for secret names"
  echo ""
  echo "  Remove any secrets entries you don't need."
  echo ""
  echo "  When done, run install.sh again to finish setup."
  exit 0
fi

echo "  Config: ~/.code-assistant.json found"

# Sanity check: warn if placeholders are still present
if grep -q '<GCP_PROJECT_ID>\|<YOUR_ORG>\|<YOUR_EMAIL>\|<JIRA_PROJECT_KEY>\|<USERNAME>' "$CONFIG_FILE" 2>/dev/null; then
  echo ""
  echo "  WARNING: ~/.code-assistant.json still contains placeholders."
  echo "  Edit the file first:  \$EDITOR ~/.code-assistant.json"
  echo ""
  read -rp "  Continue anyway? [y/N] " CONTINUE
  if [[ ! "$CONTINUE" =~ ^[Yy]$ ]]; then
    exit 1
  fi
fi
echo ""

# --- Phase 1: Symlink setup ---

backup_and_link() {
  local source="$1"
  local target="$2"
  local name="$(basename "$target")"

  if [ -L "$target" ]; then
    echo "  Removing existing symlink: $name"
    rm "$target"
  elif [ -e "$target" ]; then
    echo "  Backing up existing: $name -> ${name}.bak"
    mv "$target" "${target}.bak"
  fi

  ln -s "$source" "$target"
  echo "  Linked: $target -> $source"
}

# Claude
echo "=== Claude Code ==="
mkdir -p "$HOME/.claude"

backup_and_link "$SCRIPT_DIR/claude/agents" "$HOME/.claude/agents"
backup_and_link "$SCRIPT_DIR/claude/skills" "$HOME/.claude/skills"
if [ -d "$SCRIPT_DIR/claude/hooks" ]; then
  backup_and_link "$SCRIPT_DIR/claude/hooks" "$HOME/.claude/hooks"
fi

# Codex
echo ""
echo "=== Codex ==="
mkdir -p "$HOME/.codex"

backup_and_link "$SCRIPT_DIR/codex/skills" "$HOME/.codex/skills"

echo ""
echo "Done! Restart Claude Code / Codex sessions to pick up changes."
echo "To update: cd $SCRIPT_DIR && git pull"
