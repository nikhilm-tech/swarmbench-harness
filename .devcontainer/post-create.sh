#!/usr/bin/env bash
# Portable post-create for the SwarmBench / Harbor Codespaces harness.
# Works in any repo name: all paths are relative to the workspace root.
set -euo pipefail

echo "[post-create] Installing apt tools (tmux, htop, jq, ncdu)..."
sudo apt-get update -qq
sudo apt-get install -y -qq tmux htop jq ncdu

echo "[post-create] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Persist PATH for future shells
for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  if [[ -f "$rc" ]] && ! grep -q '.local/bin' "$rc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$rc"
  fi
done

# Make uv / uvx visible to non-interactive ssh sessions too
sudo ln -sf "$HOME/.local/bin/uv"  /usr/local/bin/uv  2>/dev/null || true
sudo ln -sf "$HOME/.local/bin/uvx" /usr/local/bin/uvx 2>/dev/null || true

# Wire SWARM_MODEL from the dedicated secret (devcontainer secrets can't do
# shell substitution, so we do it here once).
if [[ -n "${SWARM_MODEL_DEDICATED:-}" ]] && ! grep -q 'SWARM_MODEL=' "$HOME/.bashrc" 2>/dev/null; then
  echo "export SWARM_MODEL=\"\${SWARM_MODEL:-\$SWARM_MODEL_DEDICATED}\"" >> "$HOME/.bashrc"
fi

echo "[post-create] uv version: $(uv --version 2>&1 || echo 'NOT INSTALLED')"

echo "[post-create] Verifying Docker-in-Docker..."
docker version --format '{{.Server.Version}}' 2>&1 || \
  echo "WARN: docker daemon not reachable yet (usually up a few seconds after start)"

# Harbor is the SwarmBench runner; pin it to a known-good commit so reruns
# are deterministic. Cloning into ./harbor (not harbor_src) so env.sh's
# secondary lookup matches without restructuring.
HARBOR_REPO_URL="${HARBOR_REPO_URL:-https://github.com/harbor-framework/harbor.git}"
HARBOR_PINNED_COMMIT="${HARBOR_PINNED_COMMIT:-e70d5f060ffeb4525f320669d50b290925b55425}"

if [[ ! -d harbor/.git && ! -f harbor/pyproject.toml && ! -f harbor/harbor_src/pyproject.toml ]]; then
  echo "[post-create] Cloning harbor at pinned commit ${HARBOR_PINNED_COMMIT:0:12}..."
  if git clone --filter=blob:none "$HARBOR_REPO_URL" harbor; then
    (cd harbor && git checkout --quiet "$HARBOR_PINNED_COMMIT") \
      || echo "WARNING: harbor checkout of pinned commit failed; staying on default branch."
  else
    echo "WARNING: harbor clone failed; run scripts/bootstrap_harbor.sh manually."
  fi
fi

if [[ -f harbor/harbor_src/pyproject.toml ]]; then
  echo "[post-create] Found harbor at ./harbor/harbor_src — syncing venv..."
  (cd harbor/harbor_src && uv sync --no-dev) || echo "WARNING: harbor uv sync failed; run it manually."
elif [[ -f harbor/pyproject.toml ]]; then
  echo "[post-create] Found harbor at ./harbor — syncing venv..."
  (cd harbor && uv sync --no-dev) || echo "WARNING: harbor uv sync failed; run it manually."
else
  echo "[post-create] NOTE: no harbor/ found and clone failed."
  echo "               This harness expects harbor vendored at ./harbor (or ./harbor/harbor_src)."
  echo "               Re-run this script after fixing connectivity, or clone manually:"
  echo "                 git clone $HARBOR_REPO_URL harbor && (cd harbor && git checkout $HARBOR_PINNED_COMMIT && uv sync --no-dev)"
fi

echo "[post-create] Done."
echo "  - workspace:             $(pwd)"
echo "  - docker:                $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'unreachable')"
echo "  - uv:                    $(uv --version 2>/dev/null || echo 'missing')"
echo "  - FIREWORKS_API_KEY:     $([[ -n "${FIREWORKS_API_KEY:-}" ]] && echo set || echo MISSING)"
echo "  - SWARM_MODEL_DEDICATED: ${SWARM_MODEL_DEDICATED:-unset}"
echo "  - SWARM_MODEL_SHARED:    ${SWARM_MODEL_SHARED:-unset}"
