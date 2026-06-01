#!/usr/bin/env python3
"""Deterministic scorer for the combinatorial-manifestation handbook task.

Reads the agent worksheet from /logs/agent/integer_counts.yaml and the gold
integer-count table from ./oracle.yaml (resolved relative to this scorer
file). Validates the worksheet's shape — YAML root must be a mapping; each
mapping value must be a canonical decimal integer literal matching
``^-?\\d+$`` (zero-padded non-zero magnitudes such as ``01`` are rejected; the
singleton ``0`` is accepted); booleans, nulls, floats, scientific notation,
quoted-numeral strings, and flow-style mappings are all rejected at the
value position. The scorer iterates over the thirty-six gold handles and
counts strict integer equality.

Reward formula: ``number_of_handles_correct / 36``, clamped to ``[0.0, 1.0]``,
written as a six-decimal-place float at /logs/verifier/reward.txt.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import yaml

VERIFIER_DIR = Path(__file__).resolve().parent
ORACLE_PATH = VERIFIER_DIR / "oracle.yaml"

LOGS_ROOT = Path(os.environ.get("LOGS_ROOT", "/logs"))
AGENT_OUTPUT_PATH = LOGS_ROOT / "agent" / "integer_counts.yaml"
VERIFIER_LOG_DIR = LOGS_ROOT / "verifier"
REWARD_PATH = VERIFIER_LOG_DIR / "reward.txt"
REPORT_PATH = VERIFIER_LOG_DIR / "report.json"

EXPECTED_HANDLE_COUNT = 36
HANDLE_PATTERN = re.compile(r"^COUNT-\d{2}$")
INTEGER_LITERAL_PATTERN = re.compile(r"^-?\d+$")
ZERO_PADDED_LITERAL_PATTERN = re.compile(r"^-?0\d+$")


def _write_reward(value: float) -> None:
    VERIFIER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    REWARD_PATH.write_text(f"{value:.6f}\n")


def _write_report(report: dict[str, Any]) -> None:
    VERIFIER_LOG_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")


def _fail_structural(reason: str, extra: dict[str, Any] | None = None) -> int:
    payload: dict[str, Any] = {"reward": 0.0, "structural_failure": reason}
    if extra:
        payload.update(extra)
    _write_reward(0.0)
    _write_report(payload)
    print(f"VERIFIER STRUCTURAL FAILURE: {reason}", file=sys.stderr)
    return 0


def _is_bare_int(value: Any) -> bool:
    """True iff value is a Python int and NOT a bool (bool is an int subtype)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _build_handle_to_raw_str(text: str) -> dict[str, str]:
    """Walk the raw worksheet text line-by-line and lift every line that
    matches ``COUNT-NN: <value>`` into a handle -> raw-value-string map on a
    first-match-wins basis. This map is used to enforce the per-line value
    shape rules from instruction.md that the YAML loader cannot enforce on
    its own (e.g. zero-padded non-zero magnitudes, quoted-numeral strings,
    scientific notation that pyyaml silently accepts at the float type).
    """
    handle_to_raw: dict[str, str] = {}
    line_pattern = re.compile(r"^(?P<key>\S+)\s*:\s*(?P<val>.*?)\s*$")
    for raw_line in text.splitlines():
        # skip blank and comment-only lines
        stripped = raw_line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        m = line_pattern.match(raw_line)
        if not m:
            continue
        key = m.group("key")
        val = m.group("val")
        # strip an inline " # comment" trailing fragment ONLY if a hash
        # is preceded by whitespace (a `#` inside an integer literal is
        # not a comment; only `<value> # comment` is)
        comment_split = re.split(r"\s+#", val, maxsplit=1)
        val = comment_split[0]
        if key not in handle_to_raw:  # first-match-wins
            handle_to_raw[key] = val
    return handle_to_raw


def main() -> int:
    if not ORACLE_PATH.exists():
        return _fail_structural(
            f"internal: oracle.yaml not found at {ORACLE_PATH}",
            {"oracle_path": str(ORACLE_PATH)},
        )

    if not AGENT_OUTPUT_PATH.exists():
        return _fail_structural(
            f"agent did not write {AGENT_OUTPUT_PATH}",
            {"expected_path": str(AGENT_OUTPUT_PATH)},
        )

    raw_bytes = AGENT_OUTPUT_PATH.read_bytes()
    # strip at most one leading UTF-8 byte-order-mark
    if raw_bytes.startswith(b"\xef\xbb\xbf"):
        raw_bytes = raw_bytes[3:]
    if len(raw_bytes) == 0:
        return _fail_structural(
            "agent worksheet file is empty after BOM stripping",
            {"path": str(AGENT_OUTPUT_PATH)},
        )

    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return _fail_structural(
            "agent worksheet is not valid UTF-8",
            {"decode_error": str(exc), "path": str(AGENT_OUTPUT_PATH)},
        )

    # carriage returns are explicitly forbidden by instruction.md
    if "\r" in text:
        return _fail_structural(
            "agent worksheet contains carriage-return bytes (only LF terminators are permitted)",
            {"path": str(AGENT_OUTPUT_PATH)},
        )

    try:
        agent_doc = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return _fail_structural(
            "agent worksheet body is not parseable YAML",
            {"yaml_error": str(exc), "path": str(AGENT_OUTPUT_PATH)},
        )

    if agent_doc is None:
        return _fail_structural(
            "agent worksheet parsed to YAML null (empty document)",
            {"path": str(AGENT_OUTPUT_PATH)},
        )

    if not isinstance(agent_doc, dict):
        return _fail_structural(
            "agent worksheet root is not a YAML mapping",
            {"got_type": type(agent_doc).__name__, "path": str(AGENT_OUTPUT_PATH)},
        )

    oracle_doc = yaml.safe_load(ORACLE_PATH.read_text())
    if not isinstance(oracle_doc, dict):
        return _fail_structural(
            f"internal: oracle.yaml root is not a mapping (got {type(oracle_doc).__name__})",
        )
    gold: dict[str, int] = {}
    for k, v in oracle_doc.items():
        if not _is_bare_int(v):
            return _fail_structural(
                f"internal: oracle value at {k!r} is not a bare int (got {type(v).__name__})",
            )
        gold[k] = int(v)

    if len(gold) != EXPECTED_HANDLE_COUNT:
        return _fail_structural(
            f"internal: oracle has {len(gold)} entries, expected {EXPECTED_HANDLE_COUNT}",
        )

    # Walk the raw worksheet text so we can enforce per-line value shape
    # rules that pyyaml's safe_load silently smooths over (e.g. it parses
    # both `01` and `1` to int 1; it parses `5.0` to float 5.0; it parses
    # `true` to bool True; it parses an unquoted `~` to None).
    raw_per_handle = _build_handle_to_raw_str(text)

    correct = 0
    handle_outcomes: list[dict[str, Any]] = []
    parsed_per_handle: dict[str, int] = {}

    for handle in sorted(gold.keys()):
        gold_int = gold[handle]
        outcome: dict[str, Any] = {"handle": handle}

        if handle not in agent_doc:
            outcome["result"] = "missing"
            handle_outcomes.append(outcome)
            continue

        raw_str = raw_per_handle.get(handle)
        if raw_str is None:
            # YAML parsed it (maybe via flow-style) but our line scanner
            # could not locate a block-style `COUNT-NN: <value>` line for
            # it. Reject as malformed-shape.
            outcome["result"] = "malformed_shape"
            outcome["reason"] = (
                "no block-style 'COUNT-NN: <value>' line found for this "
                "handle (flow-style mapping or multi-handle line is "
                "forbidden)"
            )
            handle_outcomes.append(outcome)
            continue

        if not INTEGER_LITERAL_PATTERN.fullmatch(raw_str):
            outcome["result"] = "malformed_value_shape"
            outcome["reason"] = (
                f"value text does not match ^-?\\d+$ "
                f"(value={raw_str!r}); booleans, nulls, floats, "
                f"scientific notation, hex/oct/bin prefixes, quoted "
                f"strings, and thousands separators are all rejected"
            )
            handle_outcomes.append(outcome)
            continue

        if ZERO_PADDED_LITERAL_PATTERN.fullmatch(raw_str):
            outcome["result"] = "malformed_value_shape"
            outcome["reason"] = (
                f"value text is zero-padded on a non-zero magnitude "
                f"(value={raw_str!r}); write the bare non-padded integer "
                f"literal instead, e.g. 1 not 01"
            )
            handle_outcomes.append(outcome)
            continue

        # Parse the raw string ourselves (NOT the yaml-parsed value, which
        # may have silently coerced a malformed-but-yaml-acceptable value).
        try:
            parsed_int = int(raw_str, 10)
        except ValueError as exc:
            outcome["result"] = "malformed_value_shape"
            outcome["reason"] = (
                f"value text passed regex but failed int(10) parse "
                f"({exc}); value={raw_str!r}"
            )
            handle_outcomes.append(outcome)
            continue

        parsed_per_handle[handle] = parsed_int

        if parsed_int == gold_int:
            outcome["result"] = "correct"
            correct += 1
        else:
            outcome["result"] = "wrong_value"
            outcome["got"] = parsed_int
        handle_outcomes.append(outcome)

    raw_reward = correct / EXPECTED_HANDLE_COUNT
    reward = max(0.0, min(1.0, raw_reward))

    extra_keys = sorted(set(agent_doc.keys()) - set(gold.keys()))[:20]

    report: dict[str, Any] = {
        "reward": reward,
        "correct": correct,
        "total": EXPECTED_HANDLE_COUNT,
        "handle_outcomes": handle_outcomes,
        "extra_unknown_handles": extra_keys,
    }
    _write_reward(reward)
    _write_report(report)
    print(
        f"verifier: reward={reward:.6f} correct={correct}/{EXPECTED_HANDLE_COUNT}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
