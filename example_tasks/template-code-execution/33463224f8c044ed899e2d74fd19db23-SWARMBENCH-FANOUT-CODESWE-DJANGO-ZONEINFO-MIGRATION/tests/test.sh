#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier

cd /testbed

set +e
python3 /tests/verify.py 2>&1 | tee /logs/verifier/test-output.log
set -e

# verify.py writes fractional reward to /logs/verifier/reward.txt directly.
# Do not overwrite it here — partial credit is meaningful for training signal.

exit 0
