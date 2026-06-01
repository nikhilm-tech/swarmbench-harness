#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

python3 -c "import yaml" >/dev/null 2>&1 || pip install --quiet PyYAML==6.0.2

python3 "${SCRIPT_DIR}/verify.py"
