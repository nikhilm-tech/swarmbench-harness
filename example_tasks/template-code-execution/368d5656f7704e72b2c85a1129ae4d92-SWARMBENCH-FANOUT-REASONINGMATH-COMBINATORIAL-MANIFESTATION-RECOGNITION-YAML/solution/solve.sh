#!/bin/bash
# -----------------------------------------------------------------------------
# Oracle solver — reference-answer reader, not a derivation pipeline.
#
# instruction.md prescribes that the SwarmBench AGENT (single- or multi-agent
# run) must read each handbook entry's natural-language description, recognise
# the underlying combinatorial family, and evaluate the family's closed-form
# expression at the supplied parameters to derive each integer count. This
# shell script is NOT an agent; it is the oracle (gold) reference solver that
# Harbor invokes only to validate the verifier pipeline end-to-end (file path,
# YAML mapping shape, per-handle integer-equality scoring, reward-write path,
# structural-failure handling).
#
# The oracle is therefore allowed — and expected — to short-circuit the
# recognition-and-evaluation work by copying the trainer-curated ground-truth
# YAML from the private solution/oracle.yaml file shipped under solution/ (a
# file the agent never sees: it lives in /task/solution/ which is mounted
# only for this oracle invocation, never for the agent's container). The
# oracle's job is to produce the byte-perfect /logs/agent/integer_counts.yaml
# that a hypothetical perfect agent would have produced, so the verifier
# round-trip can confirm reward = 1.000000 against a known-good worksheet.
# Performing actual family recognition and closed-form evaluation here would
# defeat the purpose of the oracle — the oracle MUST agree with the
# verifier's ground truth bit-for-bit, and the only source of that ground
# truth on this task is the trainer-curated oracle.yaml that was generated
# when the corpus was assembled.
#
# This pattern is the standard SwarmBench oracle-shortcut convention for
# verifier_type = "executable" tasks (see the matching documentation header
# at the top of task.toml). It is permitted under QD-02 check 9 because the
# instruction.md derivation requirement applies to the AGENT, not to the
# oracle; the oracle is a verifier-pipeline integrity check, not a competitor
# in the benchmark.
# -----------------------------------------------------------------------------
set -euo pipefail

LOGS_ROOT="${LOGS_ROOT:-/logs}"
SOLVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_YAML="${SOLVER_DIR}/oracle.yaml"

if [ ! -f "${ORACLE_YAML}" ]; then
    echo "ORACLE ERROR: oracle.yaml not found at ${ORACLE_YAML}" >&2
    exit 1
fi

OUT_DIR="${LOGS_ROOT}/agent"
mkdir -p "${OUT_DIR}"
OUT_PATH="${OUT_DIR}/integer_counts.yaml"

# Strip the YAML comment header and emit only the mapping lines so the
# scorer's per-line shape walker sees a clean block-style mapping.
python3 - <<PY
import re, sys, pathlib
src = pathlib.Path("${ORACLE_YAML}").read_text()
out_lines = []
for line in src.splitlines():
    stripped = line.lstrip()
    if not stripped or stripped.startswith("#"):
        continue
    out_lines.append(line)
body = "\n".join(out_lines) + "\n"
pathlib.Path("${OUT_PATH}").write_text(body, encoding="utf-8")
print(f"oracle: wrote ${OUT_PATH} ({len(out_lines)} mapping lines)")
PY
