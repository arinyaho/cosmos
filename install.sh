#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Installing code-assistants from: $SCRIPT_DIR"
echo ""

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
