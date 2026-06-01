#!/bin/bash
# -----------------------------------------------------------------------------
# Oracle solver -- reference-answer reader, not a derivation pipeline.
#
# instruction.md prescribes that the SwarmBench AGENT compute four tropical
# invariants (lambda_floor, kleene_finite_count, cyclicity, critical_arc_count)
# per matrix from first principles, plus the three-family rollup. This shell
# script is NOT an agent; it is the oracle reference solver that Harbor
# invokes only to round-trip the verifier pipeline.
#
# The oracle short-circuits the computation by copying the trainer-curated
# ground-truth JSON from solution/oracle.json (mounted only for this oracle
# invocation, never for the agent's container). The oracle must produce the
# byte-perfect /logs/agent/tropical_fingerprint.json that a hypothetical
# perfect agent would have produced, so the verifier round-trip can confirm
# reward = 1.000000 against a known-good fingerprint table.
#
# Standard SwarmBench oracle-shortcut convention for verifier_type =
# "executable" tasks; permitted under QD-02 check 9.
# -----------------------------------------------------------------------------
set -euo pipefail

LOGS_ROOT="${LOGS_ROOT:-/logs}"
SOLVER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORACLE_JSON="${SOLVER_DIR}/oracle.json"

if [ ! -f "${ORACLE_JSON}" ]; then
    echo "ORACLE ERROR: oracle.json not found at ${ORACLE_JSON}" >&2
    exit 1
fi

OUT_DIR="${LOGS_ROOT}/agent"
mkdir -p "${OUT_DIR}"
OUT_PATH="${OUT_DIR}/tropical_fingerprint.json"

python3 - <<PY
import json, pathlib
src = json.loads(pathlib.Path("${ORACLE_JSON}").read_text())
body = json.dumps(src, indent=2, sort_keys=True) + "\n"
pathlib.Path("${OUT_PATH}").write_text(body, encoding="utf-8")
per_matrix_count = len(src.get("per_matrix", {}))
family_count = len(src.get("family_rollup", {}))
print(f"oracle: wrote ${OUT_PATH} (per_matrix={per_matrix_count}, family_rollup={family_count})")
PY
