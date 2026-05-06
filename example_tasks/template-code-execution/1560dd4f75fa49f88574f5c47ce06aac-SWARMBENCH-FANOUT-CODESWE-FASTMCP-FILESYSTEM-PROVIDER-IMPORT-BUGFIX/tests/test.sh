#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier

cd /testbed

pip install -q pytest==8.3.4 pytest-asyncio==0.24.0 2>/dev/null

set +e
python3 /tests/verify.py 2>&1 | tee /logs/verifier/test-output.log
set -e

# verify.py writes the fractional reward to reward.txt before exiting.
# Only write 0 as a safety fallback if verify.py crashed before creating the file.
if [ ! -f /logs/verifier/reward.txt ]; then
  echo 0 > /logs/verifier/reward.txt
fi
