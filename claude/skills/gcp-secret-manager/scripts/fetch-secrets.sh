#!/usr/bin/env bash
# Fetch secrets from GCP Secret Manager and export as environment variables
# Usage: eval "$(fetch-secrets.sh)"
set -euo pipefail

TOKENS_FILE="${HOME}/.code-assistant.json"

if [ ! -f "$TOKENS_FILE" ]; then
  echo "# ERROR: $TOKENS_FILE not found" >&2
  exit 1
fi

if ! command -v gcloud >/dev/null 2>&1; then
  echo "# ERROR: gcloud CLI required" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "# ERROR: jq required" >&2
  exit 1
fi

PROJECT=$(jq -r '.gcp_project // empty' "$TOKENS_FILE")
if [ -z "$PROJECT" ]; then
  echo "# ERROR: gcp_project not set in $TOKENS_FILE" >&2
  exit 1
fi

# Iterate over secrets mapping
jq -r '.secrets | to_entries[] | "\(.key) \(.value)"' "$TOKENS_FILE" 2>/dev/null | while read -r env_var secret_name; do
  if [ -n "$env_var" ] && [ -n "$secret_name" ]; then
    value=$(gcloud secrets versions access latest --secret="$secret_name" --project="$PROJECT" 2>/dev/null || echo "")
    if [ -n "$value" ]; then
      # Escape single quotes for safe export
      escaped=$(printf '%s' "$value" | sed "s/'/'\\\\''/g")
      echo "export ${env_var}='${escaped}'"
    else
      echo "# WARN: Failed to fetch $secret_name" >&2
    fi
  fi
done
