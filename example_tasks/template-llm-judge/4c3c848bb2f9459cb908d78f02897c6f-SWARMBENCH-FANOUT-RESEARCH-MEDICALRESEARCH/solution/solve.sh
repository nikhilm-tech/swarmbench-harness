#!/bin/bash
set -euo pipefail
# Oracle solution: copy the known correct answer to the agent output location.
# Harbor volume-mounts /logs/agent/ so this file appears on host automatically.
cp /solution/oracle.json /logs/agent/output.json
echo "Oracle solution applied."
