#!/usr/bin/env bash
# Idempotent: clones the Harbor SwarmBench runner at a pinned commit into
# ./harbor (if missing) and syncs its uv venv. Safe to re-run.
#
# Usage (from repo root):  ./scripts/bootstrap_harbor.sh
# Overrides:
#   HARBOR_REPO_URL       - default: https://github.com/harbor-framework/harbor.git
#   HARBOR_PINNED_COMMIT  - default: e70d5f060ffeb4525f320669d50b290925b55425
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$WORKSPACE_ROOT"

HARBOR_REPO_URL="${HARBOR_REPO_URL:-https://github.com/harbor-framework/harbor.git}"
HARBOR_PINNED_COMMIT="${HARBOR_PINNED_COMMIT:-e70d5f060ffeb4525f320669d50b290925b55425}"

if [[ -d harbor/.git ]]; then
  echo "[bootstrap_harbor] harbor/.git already present at $(pwd)/harbor"
  current="$(cd harbor && git rev-parse HEAD)"
  if [[ "$current" != "$HARBOR_PINNED_COMMIT" ]]; then
    echo "[bootstrap_harbor] harbor HEAD ($current) != pinned ($HARBOR_PINNED_COMMIT); attempting checkout..."
    (cd harbor && git fetch --quiet origin "$HARBOR_PINNED_COMMIT" 2>/dev/null || true)
    (cd harbor && git checkout --quiet "$HARBOR_PINNED_COMMIT") \
      || echo "WARNING: harbor checkout of pinned commit failed; staying on $(cd harbor && git rev-parse --short HEAD)."
  else
    echo "[bootstrap_harbor] harbor already on pinned commit."
  fi
else
  echo "[bootstrap_harbor] Cloning harbor at pinned commit ${HARBOR_PINNED_COMMIT:0:12}..."
  git clone --filter=blob:none "$HARBOR_REPO_URL" harbor
  (cd harbor && git checkout --quiet "$HARBOR_PINNED_COMMIT") \
    || echo "WARNING: harbor checkout of pinned commit failed; staying on default branch."
fi

if [[ -f harbor/harbor_src/pyproject.toml ]]; then
  HARBOR_PKG_DIR="harbor/harbor_src"
elif [[ -f harbor/pyproject.toml ]]; then
  HARBOR_PKG_DIR="harbor"
else
  echo "ERROR: harbor cloned but no pyproject.toml found at harbor/ or harbor/harbor_src/." >&2
  exit 1
fi

echo "[bootstrap_harbor] uv sync in $HARBOR_PKG_DIR (no-dev)..."
(cd "$HARBOR_PKG_DIR" && uv sync --no-dev)

echo "[bootstrap_harbor] Done. Harbor ready at $WORKSPACE_ROOT/$HARBOR_PKG_DIR"
echo "  - HEAD: $(cd "$HARBOR_PKG_DIR" && git rev-parse --short HEAD 2>/dev/null || echo n/a)"
echo "  - uv:   $(uv --version 2>/dev/null || echo missing)"
