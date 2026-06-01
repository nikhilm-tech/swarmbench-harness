#!/bin/bash
# Sets the 3 Codespaces user secrets required by .devcontainer/devcontainer.json.
# Run this in your OWN Cursor IDE terminal (not via an agent shell) so secret
# values are read with `read -s` (no echo, no chat exposure).
#
# Usage:  bash scripts/set_codespaces_secrets.sh
#
# Prereqs: gh authenticated as the GitHub account that owns the fork
# (e.g. `nikhilm-tech`), with the `codespace` scope present.

set -euo pipefail

REPO="${REPO:-nikhilm-tech/swarmbench-harness}"
echo "Setting Codespaces user secrets, scoped to repo: $REPO"
echo "(values will not appear on screen; press Enter to skip an optional secret)"
echo

set_secret() {
  local name="$1"
  local required="$2"  # "required" or "optional"
  printf "  %-25s: " "$name"
  read -rs value
  echo
  if [ -z "$value" ]; then
    if [ "$required" = "required" ]; then
      echo "    ERROR: $name is required, aborting." >&2
      exit 1
    fi
    echo "    skipped (no value entered)"
    return
  fi
  printf '%s' "$value" | gh secret set "$name" \
    --user --app codespaces \
    --visibility selected --repos "$REPO" \
    --body -
  echo "    OK"
}

set_secret FIREWORKS_API_KEY required
set_secret SWARM_MODEL_DEDICATED optional
set_secret SWARM_MODEL_SHARED optional

echo
echo "Done. Confirming what's set (names only, never values):"
gh api /user/codespaces/secrets --jq '.secrets[] | .name' | sed 's/^/  - /'
