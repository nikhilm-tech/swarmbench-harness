#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Ensure PyYAML is importable (the worksheet scorer needs it). If the
# pinned numerical stack is already installed in the image, this is a
# no-op; otherwise we install just the YAML dep so the scorer can run.
python3 -c "import yaml" >/dev/null 2>&1 || pip install --quiet PyYAML==6.0.2

python3 "${SCRIPT_DIR}/verify.py"
