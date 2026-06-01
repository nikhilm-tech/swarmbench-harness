#!/usr/bin/env python3
"""Deterministic builder for the tropical-matrix corpus.

Generates 24 integer matrices over the min-plus semiring under the
per-family / per-size assignment from instruction.md, computes the
108-atom ground-truth fingerprint table using exact rational arithmetic,
and writes:
  - environment/input_artifacts/tropical_matrices.jsonl    (agent-visible corpus)
  - solution/oracle.json                                    (private gold for oracle)
  - tests/oracle.json                                       (sealed gold for verifier)

Usage:
  python3 solution/build_corpus.py

Determinism: a fixed RNG seed makes the corpus and the oracle byte-identical
across runs. To regenerate with a different draw, change SEED.

Family generators:
  PRI (primitive)     -> Hamiltonian-cycle backbone + random chords;
                         post-condition: support is strongly connected AND
                         gcd of cycle lengths in the support digraph == 1.
  RED (reducible)     -> partition vertices into 2-3 groups, build an
                         internal cycle in each, add DAG arcs between
                         groups; post-condition: >= 2 SCCs AND at least
                         one inter-SCC finite arc.
  NCC (near-circulant)-> circulant pattern (2-3 active offsets) perturbed
                         by deleting one finite arc or adding one
                         finite arc; post-condition: support has at
                         least one cycle (cyclicity > 0).

Fingerprint computation (exact, no float drift):
  - max cycle mean via networkx.simple_cycles + sympy.Rational
  - lambda_floor via sympy.floor on the rational mean
  - kleene_finite_count via Floyd-Warshall reachability on the support
  - critical subgraph via rescale-and-extract-zero-mean-cycles
  - cyclicity = gcd of elementary-circuit lengths of critical subgraph
  - critical_arc_count = arc count of critical subgraph
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Optional

import networkx as nx
from sympy import Rational, floor as sym_floor

SEED = 20260601
MIN_W, MAX_W = 1, 99  # finite arc weights drawn from [1, 99]; the spec
                     # allows 0 but excluding 0 here gives more distinct
                     # lambda values and avoids the degenerate "every
                     # cycle has zero mean" case on small corpora.

# Per-family per-size assignment (sums: 8 per family, sizes {4: 5, 5: 5, 6: 5, 7: 5, 8: 4}).
SIZES = [4, 5, 6, 7, 8]
ASSIGN: dict[str, list[int]] = {
    "PRI": [2, 2, 2, 1, 1],
    "RED": [2, 2, 1, 2, 1],
    "NCC": [1, 1, 2, 2, 2],
}

INF = math.inf

THIS_DIR = Path(__file__).resolve().parent
TASK_ROOT = THIS_DIR.parent
CORPUS_PATH = TASK_ROOT / "environment" / "input_artifacts" / "tropical_matrices.jsonl"
SOLUTION_ORACLE = TASK_ROOT / "solution" / "oracle.json"
TESTS_ORACLE = TASK_ROOT / "tests" / "oracle.json"


# -- family generators --------------------------------------------------------


def support_scc_count(A: list[list[float]]) -> int:
    n = len(A)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(n):
            if A[i][j] != INF:
                G.add_edge(i, j)
    return nx.number_strongly_connected_components(G)


def support_cycle_lengths(A: list[list[float]]) -> list[int]:
    n = len(A)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(n):
            if A[i][j] != INF:
                G.add_edge(i, j)
    return [len(c) for c in nx.simple_cycles(G)]


def gen_primitive(n: int, rng: random.Random) -> list[list[float]]:
    for _ in range(500):
        perm = list(range(n))
        rng.shuffle(perm)
        A = [[INF] * n for _ in range(n)]
        for i in range(n):
            A[perm[i]][perm[(i + 1) % n]] = rng.randint(MIN_W, MAX_W)
        # add chords so the cycle-length gcd drops to 1
        n_chords = rng.randint(max(2, n // 3), max(3, n // 2 + 1))
        attempts = 0
        added = 0
        while added < n_chords and attempts < 6 * n_chords:
            attempts += 1
            i, j = rng.randint(0, n - 1), rng.randint(0, n - 1)
            if A[i][j] == INF:
                A[i][j] = rng.randint(MIN_W, MAX_W)
                added += 1
        if support_scc_count(A) != 1:
            continue
        lens = support_cycle_lengths(A)
        if not lens:
            continue
        g = lens[0]
        for L in lens[1:]:
            g = math.gcd(g, L)
        if g == 1:
            return A
    raise RuntimeError(f"gen_primitive: failed for n={n}")


def gen_reducible(n: int, rng: random.Random) -> list[list[float]]:
    for _ in range(500):
        k = 2 if n < 6 else rng.choice([2, 3])
        verts = list(range(n))
        rng.shuffle(verts)
        groups: list[list[int]] = [[] for _ in range(k)]
        for idx, v in enumerate(verts):
            groups[idx % k].append(v)
        if any(len(g) == 0 for g in groups):
            continue
        A = [[INF] * n for _ in range(n)]
        # internal cycle / self-loop per group
        for g in groups:
            if len(g) == 1:
                A[g[0]][g[0]] = rng.randint(MIN_W, MAX_W)
            else:
                rng.shuffle(g)
                for i in range(len(g)):
                    A[g[i]][g[(i + 1) % len(g)]] = rng.randint(MIN_W, MAX_W)
                # optional extra internal chord
                if len(g) >= 3 and rng.random() < 0.6:
                    i = rng.randrange(len(g))
                    j = rng.randrange(len(g))
                    if i != j and A[g[i]][g[j]] == INF:
                        A[g[i]][g[j]] = rng.randint(MIN_W, MAX_W)
        # DAG arcs between groups (lower-index group -> higher-index group only)
        added_inter = 0
        for src_idx in range(k - 1):
            for dst_idx in range(src_idx + 1, k):
                n_arcs = rng.randint(1, 2)
                for _a in range(n_arcs):
                    s = rng.choice(groups[src_idx])
                    d = rng.choice(groups[dst_idx])
                    if A[s][d] == INF:
                        A[s][d] = rng.randint(MIN_W, MAX_W)
                        added_inter += 1
        if added_inter == 0:
            continue
        if support_scc_count(A) < 2:
            continue
        return A
    raise RuntimeError(f"gen_reducible: failed for n={n}")


def gen_near_circulant(n: int, rng: random.Random) -> list[list[float]]:
    for _ in range(500):
        offsets = sorted(rng.sample(range(1, n), rng.randint(2, min(3, n - 1))))
        weights = {off: rng.randint(MIN_W, MAX_W) for off in offsets}
        A: list[list[float]] = [[INF] * n for _ in range(n)]
        for i in range(n):
            for off, w in weights.items():
                A[i][(i + off) % n] = w
        # exactly one perturbation: delete a finite arc, or add a +inf arc
        finite = [(i, j) for i in range(n) for j in range(n) if A[i][j] != INF]
        inf_arcs = [(i, j) for i in range(n) for j in range(n) if A[i][j] == INF and i != j]
        if rng.random() < 0.5 and finite:
            i, j = rng.choice(finite)
            A[i][j] = INF
        elif inf_arcs:
            i, j = rng.choice(inf_arcs)
            A[i][j] = rng.randint(MIN_W, MAX_W)
        elif finite:
            i, j = rng.choice(finite)
            A[i][j] = INF
        # require at least one cycle so cyclicity > 0
        if not support_cycle_lengths(A):
            continue
        return A
    raise RuntimeError(f"gen_near_circulant: failed for n={n}")


# -- fingerprint computation --------------------------------------------------


def support_simple_cycles(A: list[list[float]]) -> list[list[int]]:
    n = len(A)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    for i in range(n):
        for j in range(n):
            if A[i][j] != INF:
                G.add_edge(i, j)
    return list(nx.simple_cycles(G))


def cycle_total_weight(A: list[list[float]], cyc: list[int]) -> int:
    L = len(cyc)
    return sum(int(A[cyc[i]][cyc[(i + 1) % L]]) for i in range(L))


def max_cycle_mean(A: list[list[float]]) -> Optional[Rational]:
    cycles = support_simple_cycles(A)
    if not cycles:
        return None
    best: Optional[Rational] = None
    for cyc in cycles:
        L = len(cyc)
        total = cycle_total_weight(A, cyc)
        mean = Rational(total, L)
        if best is None or mean < best:
            best = mean
    return best


def lambda_floor(A: list[list[float]]) -> int:
    m = max_cycle_mean(A)
    if m is None:
        return -1
    return int(sym_floor(m))


def kleene_finite_count(A: list[list[float]]) -> int:
    n = len(A)
    reach = [[False] * n for _ in range(n)]
    for i in range(n):
        reach[i][i] = True  # length-0 walk
        for j in range(n):
            if A[i][j] != INF:
                reach[i][j] = True
    for k in range(n):
        for i in range(n):
            if not reach[i][k]:
                continue
            row_k = reach[k]
            row_i = reach[i]
            for j in range(n):
                if row_k[j]:
                    row_i[j] = True
    return sum(1 for i in range(n) for j in range(n) if reach[i][j])


def critical_arcs(A: list[list[float]]) -> set[tuple[int, int]]:
    cycles = support_simple_cycles(A)
    if not cycles:
        return set()
    means = []
    for cyc in cycles:
        L = len(cyc)
        total = cycle_total_weight(A, cyc)
        means.append((cyc, Rational(total, L)))
    lam = min(m for _, m in means)
    arcs: set[tuple[int, int]] = set()
    for cyc, m in means:
        if m == lam:
            L = len(cyc)
            for i in range(L):
                arcs.add((cyc[i], cyc[(i + 1) % L]))
    return arcs


def critical_cycles(A: list[list[float]]) -> list[list[int]]:
    arcs = critical_arcs(A)
    if not arcs:
        return []
    G = nx.DiGraph()
    G.add_edges_from(arcs)
    return list(nx.simple_cycles(G))


def cyclicity(A: list[list[float]]) -> int:
    cycs = critical_cycles(A)
    if not cycs:
        return 0
    g = 0
    for c in cycs:
        g = math.gcd(g, len(c))
    return g


def critical_arc_count(A: list[list[float]]) -> int:
    return len(critical_arcs(A))


def fingerprint(A: list[list[float]]) -> list[int]:
    lf = lambda_floor(A)
    kfc = kleene_finite_count(A)
    cyc = cyclicity(A)
    cac = critical_arc_count(A)
    return [lf, kfc, cyc, cac]


# -- corpus driver ------------------------------------------------------------


def to_jsonable_matrix(A: list[list[float]]) -> list[list[object]]:
    return [["inf" if x == INF else int(x) for x in row] for row in A]


def main() -> None:
    rng = random.Random(SEED)
    records: list[dict] = []
    for family, counts in ASSIGN.items():
        for size_idx, n in enumerate(SIZES):
            for ord_idx in range(1, counts[size_idx] + 1):
                if family == "PRI":
                    A = gen_primitive(n, rng)
                elif family == "RED":
                    A = gen_reducible(n, rng)
                else:
                    A = gen_near_circulant(n, rng)
                mid = f"TRP_2025_{family}_N{n:02d}_{ord_idx:02d}"
                records.append({
                    "id": mid,
                    "n": n,
                    "family": family,
                    "matrix": to_jsonable_matrix(A),
                })

    # Compute fingerprints
    per_matrix: dict[str, list[int]] = {}
    inner_matrices: dict[str, list[list[float]]] = {}
    for rec in records:
        A = [[INF if x == "inf" else float(x) for x in row] for row in rec["matrix"]]
        per_matrix[rec["id"]] = fingerprint(A)
        inner_matrices[rec["id"]] = A

    # Family rollup
    family_rollup: dict[str, list[int]] = {}
    for fam in ("PRI", "RED", "NCC"):
        ids = [r["id"] for r in records if r["family"] == fam]
        fps = [per_matrix[i] for i in ids]
        count = len(fps)
        sum_lam = sum(fp[0] for fp in fps)
        max_kfc = max(fp[1] for fp in fps)
        sum_cac = sum(fp[3] for fp in fps)
        family_rollup[fam] = [count, sum_lam, max_kfc, sum_cac]

    # Write corpus (JSONL)
    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CORPUS_PATH.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec, separators=(",", ":")) + "\n")

    # Write oracles (JSON)
    oracle = {"per_matrix": per_matrix, "family_rollup": family_rollup}
    text = json.dumps(oracle, indent=2, sort_keys=True) + "\n"
    SOLUTION_ORACLE.write_text(text)
    TESTS_ORACLE.write_text(text)

    print(f"wrote {len(records)} matrices -> {CORPUS_PATH}")
    print(f"wrote oracle -> {SOLUTION_ORACLE}")
    print(f"wrote oracle -> {TESTS_ORACLE}")
    print()
    print("per-family summary:")
    for fam, tup in family_rollup.items():
        n_fam = sum(1 for r in records if r["family"] == fam)
        print(f"  {fam}: n={n_fam}, rollup={tup}")
    print()
    print("per-matrix fingerprints (lambda_floor, kleene_finite_count, cyclicity, critical_arc_count):")
    for mid, fp in per_matrix.items():
        print(f"  {mid}  {fp}")


if __name__ == "__main__":
    main()
