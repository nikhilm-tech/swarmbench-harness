#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
python3 /tests/judge.py \
  --agent-output /logs/agent/output.json \
  --oracle /tests/oracle.json \
  --reward-out /logs/verifier/reward.json
