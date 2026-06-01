#!/usr/bin/env python3
"""Deterministic scorer for the tropical-matrix fingerprint task.

Reads the agent deliverable from /logs/agent/tropical_fingerprint.json and the
gold table from ./oracle.json (resolved relative to this scorer file).

Per instruction.md §5 the verifier in its production form ENFORCES exact
cardinality: per_matrix == 24 keys and family_rollup == 3 keys with the
token set {PRI, RED, NCC}. The scaffold's placeholder oracle.json carries
fewer entries (2 + 1) to make the local oracle round-trip smoke test fast;
when the user grows the oracle to the full 24 + 3, the verifier scales
automatically because it counts atoms from the oracle, not from a hardcoded
constant. To switch on the production cardinality gate, set the constant
PRODUCTION_CARDINALITY = True below.

Reward formula: (count of valid atoms) / (total atoms in oracle), clamped to
[0.0, 1.0], written as a six-decimal float at /logs/verifier/reward.json
next to a `failures` field listing the first thirty paths that did not
validate.

Short-circuit conditions per instruction.md §5 (force reward 0.0 without
per-slot scoring):
  - deliverable file absent
  - body not parseable JSON
  - root not a JSON object
  - root carries any top-level key besides per_matrix / family_rollup
  - per_matrix not a JSON object (or, in production mode, != 24 keys)
  - family_rollup not a JSON object (or, in production mode, != 3 keys
    exactly {PRI, RED, NCC})
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

VERIFIER_DIR = Path(__file__).resolve().parent
ORACLE_PATH = VERIFIER_DIR / "oracle.json"

LOGS_ROOT = Path(os.environ.get("LOGS_ROOT", "/logs"))
DELIVERABLE_FILENAME = "tropical_fingerprint.json"
AGENT_OUTPUT_PATH = LOGS_ROOT / "agent" / DELIVERABLE_FILENAME

VERIFIER_LOG_DIR = LOGS_ROOT / "verifier"
REWARD_PATH = VERIFIER_LOG_DIR / "reward.json"
REPORT_PATH = VERIFIER_LOG_DIR / "report.json"

# Toggle to True once you have generated the full 24-matrix + 3-family
# oracle.json. Keeps cardinality gates loose during scaffold iteration.
PRODUCTION_CARDINALITY = True

EXPECTED_PER_MATRIX_COUNT = 24
EXPECTED_FAMILY_TOKENS = ("PRI", "RED", "NCC")

# Per instruction.md §5 admissible intervals (positional per the 4-tuple
# order: lambda_floor, kleene_finite_count, cyclicity, critical_arc_count).
PER_MATRIX_INTERVALS = (
    (-1, 99),   # lambda_floor
    (0, 64),    # kleene_finite_count
    (0, 8),     # cyclicity
    (0, 64),    # critical_arc_count
)
# Per-family positional order: count, sum_lambda_floor,
# max_kleene_finite_count, sum_critical_arc_count.
FAMILY_INTERVALS = (
    (0, 24),    # count
    (-24, 800), # sum_lambda_floor
    (0, 64),    # max_kleene_finite_count
    (0, 512),   # sum_critical_arc_count
)


def _write_reward(reward: float, extra: dict[str, Any] | None = None) -> None:
    """Write reward.json. Harbor parses this file as a flat dict of numeric
    rewards (Pydantic `dict[str, float | int]`), so EVERY value MUST be a
    bare number; non-numeric diagnostics (lists, strings, dicts) belong in
    report.json instead, otherwise harbor raises VerifierResult validation
    errors and discards the trial.
    """
    VERIFIER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    payload: dict[str, float | int] = {"reward": float(reward)}
    if extra:
        for k, v in extra.items():
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                continue
            payload[k] = v
    REWARD_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _write_report(report: dict[str, Any]) -> None:
    VERIFIER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _fail_structural(reason: str, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"structural_failure": reason}
    if extra:
        payload.update(extra)
    _write_reward(0.0, payload)
    _write_report({"reward": 0.0, "structural_failure": reason, **(extra or {})})
    print(f"VERIFIER STRUCTURAL FAILURE: {reason}", file=sys.stderr)
    return 0


def _is_bare_int(value: Any) -> bool:
    """True iff value is a Python int and NOT a bool (bool is an int subtype)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_tuple(
    value: Any, intervals: tuple[tuple[int, int], ...]
) -> tuple[bool, str]:
    """Return (ok, reason). value must be a list of len(intervals) bare ints,
    each in its interval."""
    if not isinstance(value, list):
        return False, f"not a JSON array (got {type(value).__name__})"
    if len(value) != len(intervals):
        return False, f"wrong arity {len(value)} (expected {len(intervals)})"
    for i, (entry, (lo, hi)) in enumerate(zip(value, intervals)):
        if not _is_bare_int(entry):
            return False, f"slot {i} is not a bare JSON int (got {type(entry).__name__})"
        if not (lo <= entry <= hi):
            return False, f"slot {i} = {entry} outside admissible [{lo}, {hi}]"
    return True, ""


def main() -> int:
    if not ORACLE_PATH.exists():
        return _fail_structural(
            f"internal: oracle.json not found at {ORACLE_PATH}",
            {"oracle_path": str(ORACLE_PATH)},
        )
    if not AGENT_OUTPUT_PATH.exists():
        return _fail_structural(
            f"agent did not write {AGENT_OUTPUT_PATH}",
            {"expected_path": str(AGENT_OUTPUT_PATH)},
        )

    raw_bytes = AGENT_OUTPUT_PATH.read_bytes()
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    if len(raw_bytes) == 0:
        return _fail_structural(
            "agent deliverable is empty after BOM stripping",
            {"path": str(AGENT_OUTPUT_PATH)},
        )
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _fail_structural(
            "agent deliverable is not valid UTF-8",
            {"decode_error": str(exc), "path": str(AGENT_OUTPUT_PATH)},
        )
    try:
        agent_doc = json.loads(text)
    except json.JSONDecodeError as exc:
        return _fail_structural(
            "agent deliverable body is not parseable JSON",
            {"json_error": str(exc), "path": str(AGENT_OUTPUT_PATH)},
        )

    if not isinstance(agent_doc, dict):
        return _fail_structural(
            "agent deliverable root is not a JSON object",
            {"got_type": type(agent_doc).__name__},
        )

    allowed_root_keys = {"per_matrix", "family_rollup"}
    extra_root = sorted(set(agent_doc.keys()) - allowed_root_keys)
    if extra_root:
        return _fail_structural(
            "agent deliverable root carries unexpected top-level keys",
            {"unexpected_keys": extra_root, "allowed": sorted(allowed_root_keys)},
        )

    agent_per_matrix = agent_doc.get("per_matrix")
    agent_family_rollup = agent_doc.get("family_rollup")
    if not isinstance(agent_per_matrix, dict):
        return _fail_structural(
            "agent deliverable: 'per_matrix' is not a JSON object",
            {"got_type": type(agent_per_matrix).__name__},
        )
    if not isinstance(agent_family_rollup, dict):
        return _fail_structural(
            "agent deliverable: 'family_rollup' is not a JSON object",
            {"got_type": type(agent_family_rollup).__name__},
        )

    if PRODUCTION_CARDINALITY:
        if len(agent_per_matrix) != EXPECTED_PER_MATRIX_COUNT:
            return _fail_structural(
                f"agent deliverable: per_matrix has {len(agent_per_matrix)} keys, expected {EXPECTED_PER_MATRIX_COUNT}",
            )
        if set(agent_family_rollup.keys()) != set(EXPECTED_FAMILY_TOKENS):
            return _fail_structural(
                "agent deliverable: family_rollup keys must be exactly {PRI, RED, NCC}",
                {"got_keys": sorted(agent_family_rollup.keys())},
            )

    oracle_doc = json.loads(ORACLE_PATH.read_text())
    if not isinstance(oracle_doc, dict):
        return _fail_structural(
            f"internal: oracle.json root is not a JSON object (got {type(oracle_doc).__name__})",
        )
    oracle_per_matrix = oracle_doc.get("per_matrix", {})
    oracle_family_rollup = oracle_doc.get("family_rollup", {})

    total_atoms = (
        sum(len(intervals) for intervals in [PER_MATRIX_INTERVALS] * len(oracle_per_matrix))
        + sum(len(intervals) for intervals in [FAMILY_INTERVALS] * len(oracle_family_rollup))
    )
    valid_atoms = 0
    failures: list[str] = []

    for mat_id, gold_tuple in oracle_per_matrix.items():
        agent_tuple = agent_per_matrix.get(mat_id)
        if agent_tuple is None:
            for i in range(len(PER_MATRIX_INTERVALS)):
                failures.append(f"per_matrix.{mat_id}[{i}]: missing")
            continue
        ok, reason = _validate_tuple(agent_tuple, PER_MATRIX_INTERVALS)
        if not ok:
            for i in range(len(PER_MATRIX_INTERVALS)):
                failures.append(f"per_matrix.{mat_id}[{i}]: malformed_tuple ({reason})")
            continue
        for i, (got, gold) in enumerate(zip(agent_tuple, gold_tuple)):
            if got == gold:
                valid_atoms += 1
            else:
                failures.append(f"per_matrix.{mat_id}[{i}]: got {got}, expected {gold}")

    for fam, gold_tuple in oracle_family_rollup.items():
        agent_tuple = agent_family_rollup.get(fam)
        if agent_tuple is None:
            for i in range(len(FAMILY_INTERVALS)):
                failures.append(f"family_rollup.{fam}[{i}]: missing")
            continue
        ok, reason = _validate_tuple(agent_tuple, FAMILY_INTERVALS)
        if not ok:
            for i in range(len(FAMILY_INTERVALS)):
                failures.append(f"family_rollup.{fam}[{i}]: malformed_tuple ({reason})")
            continue
        for i, (got, gold) in enumerate(zip(agent_tuple, gold_tuple)):
            if got == gold:
                valid_atoms += 1
            else:
                failures.append(f"family_rollup.{fam}[{i}]: got {got}, expected {gold}")

    raw_reward = valid_atoms / total_atoms if total_atoms > 0 else 0.0
    reward = max(0.0, min(1.0, raw_reward))

    extra_per_matrix_keys = sorted(set(agent_per_matrix.keys()) - set(oracle_per_matrix.keys()))[:20]
    extra_family_keys = sorted(set(agent_family_rollup.keys()) - set(oracle_family_rollup.keys()))[:20]

    report = {
        "reward": reward,
        "valid_atoms": valid_atoms,
        "total_atoms": total_atoms,
        "failures": failures[:30],
        "extra_per_matrix_keys": extra_per_matrix_keys,
        "extra_family_keys": extra_family_keys,
        "production_cardinality_gate": PRODUCTION_CARDINALITY,
    }
    _write_reward(reward, {"valid_atoms": valid_atoms, "total_atoms": total_atoms})
    _write_report(report)
    print(f"verifier: reward={reward:.6f} valid_atoms={valid_atoms}/{total_atoms}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
