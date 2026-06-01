# Cycle-mean, closure and cyclicity fingerprint of twenty-four tropical adjacency operators

## §1. The corpus

Let $\mathcal{C} = \{ A^{(i)} \}_{i=1}^{24}$ denote a 24-element corpus of square integer matrices interpreted over the **min-plus (tropical) semiring** $(\mathbb{R} \cup \{+\infty\},\,\oplus,\,\otimes)$ with $a \oplus b := \min(a,b)$ and $a \otimes b := a + b$. The additive identity is $+\infty$ and the multiplicative identity is $0$. Sizes $n_i \in \{4, 5, 6, 7, 8\}$ with the distribution $\#\{n_i = 4\} = \#\{n_i = 5\} = \#\{n_i = 6\} = \#\{n_i = 7\} = 5$ and $\#\{n_i = 8\} = 4$.

Each $A^{(i)}$ is the weighted-arc adjacency operator of a directed multigraph $G_i$ on $n_i$ vertices: $A^{(i)}_{jk}$ is the weight of the arc $j \to k$ in $G_i$, and $A^{(i)}_{jk} = +\infty$ encodes the absence of the arc $j \to k$. Self-loops are permitted; the diagonal is **not** identically $0$ — the tropical-multiplicative identity $0$ on the diagonal of $A^{(i)}$ would mean every vertex carries a zero-weight self-loop, which is the conventional formalisation of the identity matrix and is generically not what these operators look like.

Each finite arc weight is a non-negative integer in the range $[0,\,99]$. Three structural families partition the corpus, eight matrices apiece, with the family token embedded in the matrix identifier:

| Family token | Family name | Defining structural property |
|:---:|:---|:---|
| `PRI` | **Primitive** | $G_i$ is strongly connected; the gcd of cycle lengths in $G_i$ is $1$ (primitivity in the sense of non-negative integer matrix theory, lifted to the tropical setting via the support digraph). |
| `RED` | **Reducible** | $G_i$ has $\ge 2$ strongly connected components; arc weights are distributed so that at least one inter-component arc carries finite weight in exactly one direction. |
| `NCC` | **Near-circulant** | $G_i$ is the support of a circulant matrix on $n_i$ vertices perturbed by exactly one arc reweight (a finite arc replaced by $+\infty$, or vice versa); cyclicity is non-trivial by construction. |

The corpus mounts read-only at $/input\_artifacts/$ as a single newline-delimited JSON shard:

```
/input_artifacts/tropical_matrices.jsonl
```

A single line carries a JSON object with four keys: `id` (matching `^TRP_2025_(PRI|RED|NCC)_N0[4-8]_\d{2}$`), `n` (integer in $\{4,\dots,8\}$, equal to the matrix size), `family` (the three-letter token between `TRP_2025_` and `_N0`), and `matrix` (an $n \times n$ array of rows, each row an $n$-array whose entries are JSON integers in $[0, 99]$ or the string `"inf"` denoting $+\infty$). Entries are addressed by zero-based row/column indices. The vertex labelling is fixed by the position in `matrix` and is the same labelling under which every fingerprint atom below must be reported.

## §2. The four-tuple per-matrix fingerprint

For each operator $A = A^{(i)}$ define the tropical *max-plus dual* $A' = -A$ to land in the conventional max-plus formulation if convenient, but every quantity below is named in the min-plus convention used by the corpus.

Recall the **tropical matrix power** $A^{\otimes k}$, $k \ge 0$, where $A^{\otimes 0} = E$ is the tropical-identity matrix with $E_{ii} = 0$ and $E_{ij} = +\infty$ for $i \ne j$, and $A^{\otimes k}_{ij} = \min_{\ell \in [n]} (A^{\otimes (k-1)}_{i\ell} + A_{\ell j})$. The entry $A^{\otimes k}_{ij}$ is the minimum weight of a directed walk of *exactly* length $k$ from $i$ to $j$ in $G$ (where the weight of a walk is the sum of its arc weights, and a walk of length $0$ from $i$ to $i$ has weight $0$).

The **Kleene star**

$$
A^* \;=\; \bigoplus_{k=0}^{2n-1} A^{\otimes k}
$$

is the matrix whose $(i,j)$-entry is the minimum weight of any walk from $i$ to $j$ in $G$, with $A^*_{ii} \le 0$ since the length-zero walk contributes $0$; one extends the sum to $\bigoplus_{k=0}^{\infty}$ in the literature, but the truncation at $2n-1$ suffices on this corpus because the tropical Kleene-star series stabilises within $n-1$ steps when $\lambda(A) \ge 0$ and detects a strictly-negative-cycle short-circuit within $2n-1$ steps otherwise.

The **max cycle mean** $\lambda(A)$ is the minimum-over-cycles arithmetic mean of arc weights along directed simple cycles of $G$:

$$
\lambda(A) \;=\; \min_{C \text{ simple cycle of } G}\; \frac{\sum_{(j,k) \in C} A_{jk}}{|C|}.
$$

If $G$ has no directed cycle (an acyclic support digraph), set $\lambda(A) := +\infty$ as a sentinel and report $\lambda\_floor := -1$ at the JSON level (see the per-slot interval below).

The **critical graph** $G_c(A)$ is the subgraph of $G$ retaining exactly the arcs that lie on a cycle achieving $\lambda(A)$. Equivalently, working in the rescaled matrix $\tilde A_{jk} := A_{jk} - \lambda(A)$ (subtracting the min cycle mean from every finite arc), the critical graph is the support of the set of arcs $(j,k)$ with $\tilde A_{jk} = 0$ that participate in at least one zero-weight cycle of $\tilde A$. The **cyclicity** $\sigma(A)$ of $A$ is the gcd of the lengths of the elementary circuits of $G_c(A)$. If $G_c(A)$ has no arc (which happens exactly when $\lambda(A) = +\infty$), set $\sigma(A) := 0$.

For each operator define the four-tuple

$$
\Phi(A) \;=\; \big(\, \lambda\_\mathrm{floor},\; \mathrm{kleene\_finite\_count},\; \sigma,\; \mathrm{critical\_arc\_count}\,\big)
$$

with components

- $\lambda\_\mathrm{floor} := \lfloor \lambda(A) \rfloor$ when $\lambda(A) < +\infty$, else $-1$. Since arc weights are integers, the cycle mean is a rational $p/q$ with $1 \le q \le n$ and $0 \le p \le 99 \cdot n$, so the floor is a well-defined integer in $[0,\, 99]$ for cyclic $G$ and $-1$ otherwise.
- $\mathrm{kleene\_finite\_count} := \#\{(i,j) : A^*_{ij} \ne +\infty\}$. Equivalently, the number of ordered pairs $(i,j)$ for which $j$ is reachable from $i$ in the support digraph (including $i = j$, contributed by the length-zero walk). Always in $[n,\, n^2]$.
- $\sigma$ (cyclicity) as defined above; in $[0,\, n]$ for cyclic $G$, equals $0$ for acyclic $G$.
- $\mathrm{critical\_arc\_count} := |E(G_c(A))|$, the count of arcs in the critical subgraph. In $[0,\, n^2]$.

Map the four components onto the JSON array slots in this exact positional order — the per-matrix value is a four-element JSON array of integers, **not** a four-key object.

## §3. The three-family rollup

Partition $\mathcal{C}$ into the three structural families $\mathcal{C}_t$, $t \in \{\mathrm{PRI},\,\mathrm{RED},\,\mathrm{NCC}\}$, each of size eight (the family of an operator is the three-letter token between `TRP_2025_` and `_N0` in its `id`). For each family assemble the four-tuple summary

$$
R_t \;=\; \Big(\, |\mathcal{C}_t|,\; \textstyle\sum_{A \in \mathcal{C}_t} \lambda\_\mathrm{floor}(A),\; \max_{A \in \mathcal{C}_t} \mathrm{kleene\_finite\_count}(A),\; \sum_{A \in \mathcal{C}_t} \mathrm{critical\_arc\_count}(A) \,\Big)
$$

reported in that fixed positional order as a four-element JSON array of integers. The summary is a function of the per-matrix fingerprints in `per_matrix`; computing it either by aggregation over `per_matrix` or by an independent second pass over the corpus must produce the same four integers.

## §4. Deliverable

Emit the JSON document

```json
{
  "per_matrix": {
    "TRP_2025_PRI_N04_01": [<lambda_floor>, <kleene_finite_count>, <cyclicity>, <critical_arc_count>],
    "TRP_2025_PRI_N04_02": [...],
    "...": "24 entries in total",
    "TRP_2025_NCC_N08_04": [...]
  },
  "family_rollup": {
    "PRI": [<count>, <sum_lambda_floor>, <max_kleene_finite_count>, <sum_critical_arc_count>],
    "RED": [...],
    "NCC": [...]
  }
}
```

to the workspace path `/logs/agent/tropical_fingerprint.json`. The deliverable carries $24 \cdot 4 + 3 \cdot 4 = 108$ integer slots. The `per_matrix` object holds exactly $24$ keys (one per matrix `id`, in any order — the verifier reorders by `id` at parse time); the `family_rollup` object holds exactly the three family tokens `PRI`, `RED`, `NCC`. No third top-level key is permitted at the document root.

## §5. Reference comparison and scoring

Each scalar slot is filled with a JSON integer literal: booleans, IEEE-754 floats, quoted-numeral strings, single-element arrays, nested objects, and the bare token `null` are all rejected as wrong type and forfeit the slot. Each scalar must additionally lie inside its admissible interval; values outside the interval forfeit the slot even when typed correctly. The intervals are

- per-matrix: $\lambda\_\mathrm{floor} \in [-1, 99]$, $\mathrm{kleene\_finite\_count} \in [0, 64]$, $\sigma \in [0, 8]$, $\mathrm{critical\_arc\_count} \in [0, 64]$;
- per-family: $\mathrm{count} \in [0, 24]$, $\sum \lambda\_\mathrm{floor} \in [-24, 800]$, $\max\,\mathrm{kleene\_finite\_count} \in [0, 64]$, $\sum \mathrm{critical\_arc\_count} \in [0, 512]$.

A scalar slot is valid only when its type, its interval membership, and its exact integer value all coincide with the reference value held in `/tests/oracle.json` (sealed and inaccessible from the agent shell during the run; any open from agent code raises `ENOENT`). Reward equals (count of valid slots)/108, clamped to $[0,1]$, written as a six-decimal float at `/logs/verifier/reward.json` next to a `failures` field listing the first thirty paths that did not validate. Five short-circuit conditions force reward $0.0$ without per-slot scoring: the deliverable file is absent at the deliverable path; its body does not parse as JSON; the parsed root is not a JSON object; the parsed root carries any top-level key besides the two documented ones (`per_matrix`, `family_rollup`); either documented sub-object has the wrong cardinality (`per_matrix` $\ne 24$ keys, or `family_rollup` $\ne 3$ keys with tokens exactly $\{\mathrm{PRI}, \mathrm{RED}, \mathrm{NCC}\}$).

## §6. Runtime

Working directory `/workspace`; the interpreter `python3` exposes the pinned numerical stack `sympy==1.13.3`, `numpy==2.1.3`, `scipy==1.14.1`, `mpmath==1.3.0`, `networkx==3.6.1`, and `PyYAML==6.0.2`; outbound TCP is disabled. The standard tropical primitives (`A^{\otimes k}$ as a min-plus matrix product, the cycle-mean Karp algorithm, the Floyd-Warshall variant for tropical Kleene-star evaluation, Bron-Kerbosch on the critical graph for elementary-circuit enumeration) are not packaged as a single library and must be implemented from `numpy` / `networkx` primitives or via direct loops in pure Python — choosing the implementation discipline that recovers each integer slot exactly (no float drift on the $\lfloor \lambda \rfloor$ snap and no missed elementary circuit on the cyclicity gcd) is part of the work this task evaluates.
