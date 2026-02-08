#!/usr/bin/env bash
# SessionStart hook: Fetch secrets from GCP and inject into CLAUDE_ENV_FILE
set -euo pipefail

TOKENS_FILE="${HOME}/.code-assistant.json"

# Only run if CLAUDE_ENV_FILE is set (SessionStart hook)
if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
  echo "# WARN: CLAUDE_ENV_FILE not set, skipping secret injection" >&2
  exit 0
fi

if [ ! -f "$TOKENS_FILE" ]; then
  echo "# WARN: $TOKENS_FILE not found, skipping" >&2
  exit 0
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "# WARN: gcloud CLI not found, skipping" >&2
  exit 0
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "# WARN: jq not found, skipping" >&2
  exit 0
fi

# Check if new format (has gcp_project)
PROJECT=$(jq -r '.gcp_project // empty' "$TOKENS_FILE" 2>/dev/null)
if [ -z "$PROJECT" ]; then
  # Old format - skip
  exit 0
fi

# Check gcloud auth
if ! gcloud auth print-access-token >/dev/null 2>&1; then
  echo "# WARN: gcloud not authenticated, run 'gcloud auth login'" >&2
  exit 0
fi

# Fetch each secret and append to CLAUDE_ENV_FILE
jq -r '.secrets | to_entries[] | "\(.key) \(.value)"' "$TOKENS_FILE" 2>/dev/null | while read -r env_var secret_name; do
  if [ -n "$env_var" ] && [ -n "$secret_name" ]; then
    value=$(gcloud secrets versions access latest --secret="$secret_name" --project="$PROJECT" 2>/dev/null || echo "")
    if [ -n "$value" ]; then
      # Escape for safe shell export
      escaped=$(printf '%s' "$value" | sed "s/'/'\\\\''/g")
      echo "export ${env_var}='${escaped}'" >> "$CLAUDE_ENV_FILE"
    fi
  fi
done

exit 0
