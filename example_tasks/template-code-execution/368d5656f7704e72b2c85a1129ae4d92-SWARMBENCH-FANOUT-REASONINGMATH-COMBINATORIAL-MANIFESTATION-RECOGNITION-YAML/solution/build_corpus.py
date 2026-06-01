#!/usr/bin/env python3
"""Build the combinatorial-manifestation handbook corpus.

Produces 36 manifestation entries across 6 canonical combinatorial families
sourced from standard references (Stanley EC Vol 2 Ex 6.19, OEIS, Aigner
Discrete Mathematics, Knuth TAOCP Vol 1). Each manifestation is a paraphrased
natural-language description of a counting problem whose integer answer
is the family's value at the specified evaluation index n.

Ground-truth integers are computed via sympy's exact-arithmetic primitives
and committed to two artefacts:
  - environment/input_artifacts/combinatorial_handbook/corpus.json
    (the agent-visible manifestation catalogue, sans answers)
  - solution/oracle.yaml + tests/oracle.yaml
    (the gold integer-count table, agent-invisible)
"""
from __future__ import annotations

import json
import pathlib
from collections import OrderedDict
from typing import Callable

import sympy as sp

ROOT = pathlib.Path(__file__).resolve().parent
CORPUS_DIR = ROOT.parent / "environment" / "input_artifacts" / "combinatorial_handbook"
ORACLE_PATHS = [ROOT / "oracle.yaml", ROOT.parent / "tests" / "oracle.yaml"]


# ---------------------------------------------------------------------------
# Family evaluators (exact integer arithmetic via sympy)
# ---------------------------------------------------------------------------

def catalan(n: int) -> int:
    """C_n = (2n)! / ((n+1)! * n!).  OEIS A000108. Stanley EC Vol 2 Ex 6.19."""
    return int(sp.catalan(n))


def motzkin(n: int) -> int:
    """M_n = sum_{k=0..floor(n/2)} C(n,2k) * Catalan(k).  OEIS A001006."""
    total = 0
    for k in range(n // 2 + 1):
        total += sp.binomial(n, 2 * k) * sp.catalan(k)
    return int(total)


def bell(n: int) -> int:
    """B_n = number of set partitions of an n-element set.  OEIS A000110."""
    return int(sp.bell(n))


def schroder_large(n: int) -> int:
    """Large Schröder S_n: lattice paths (0,0) to (n,n) with steps right,
    up, and diagonal NE, staying on or above the diagonal y = x.
    OEIS A006318.  S_0 = 1; S_n = S_{n-1} + sum_{k=0}^{n-1} S_k * S_{n-1-k}."""
    s = [1]
    for m in range(1, n + 1):
        v = s[m - 1] + sum(s[k] * s[m - 1 - k] for k in range(m))
        s.append(v)
    return int(s[n])


def narayana(n: int, k: int) -> int:
    """N(n, k) = (1/n) * C(n, k-1) * C(n, k).  OEIS A001263 triangle.
    Counts Dyck paths of semilength n with exactly k peaks; equivalently,
    non-crossing partitions of an n-set with exactly k blocks."""
    return int(sp.Rational(1, n) * sp.binomial(n, k - 1) * sp.binomial(n, k))


def partition(n: int) -> int:
    """p(n) = number of unrestricted integer partitions of n.  OEIS A000041."""
    return int(sp.npartitions(n))


# ---------------------------------------------------------------------------
# Manifestation catalogue
#
# Each entry: (family_code, evaluator_callable, evaluation_index, paraphrase).
# Paraphrases are deliberately non-uniform; some are textbook-canonical
# (e.g. Dyck-path framing of Catalan), others are less-canonical bijective
# images that nevertheless reduce to the same sequence.  Several near-Catalan
# distractors test whether the agent reads carefully: "non-crossing" vs
# "non-nesting", "balanced parentheses" vs "balanced parentheses with at most
# one matched pair per nesting level", etc.
# ---------------------------------------------------------------------------

# Cap evaluation indices so ground-truth integers stay inside Python int
# range with comfortable headroom (we want < 10**15 to keep the YAML output
# readable, but large enough that an agent that misclassifies the family
# almost certainly emits a wrong-magnitude integer).
CATALOGUE: list[tuple[str, Callable[..., int], tuple[int, ...], str]] = [
    # ----- CATALAN family (6 items) -----
    ("CAT", catalan, (12,),
     "Consider the number of ways to triangulate a convex polygon with "
     "exactly fourteen labelled vertices by drawing non-crossing diagonals "
     "between vertices (only the diagonals are counted; the polygon's "
     "boundary is fixed). Compute this count exactly."),
    ("CAT", catalan, (10,),
     "Let T denote the number of full binary trees that have exactly ten "
     "internal (non-leaf) nodes, where left and right subtrees are "
     "distinguished. Output T as an integer."),
    ("CAT", catalan, (9,),
     "Compute the number of Dyck words of length eighteen, i.e. strings "
     "over the two-letter alphabet {U, D} of length eighteen for which "
     "every prefix has at least as many U's as D's and the full word has "
     "an equal number of U's and D's."),
    ("CAT", catalan, (11,),
     "How many monotone lattice paths from (0, 0) to (11, 11) lie weakly "
     "below the diagonal y = x, where each step is either a unit step "
     "to the right or a unit step upward? Output the count as a non-"
     "negative integer."),
    ("CAT", catalan, (8,),
     "Count the non-crossing partitions of the set {1, 2, …, 8}: a "
     "partition is non-crossing when, for any four elements a < b < c < d, "
     "if a and c lie in one block and b and d lie in another block, that "
     "configuration is forbidden. Emit the total number of such "
     "partitions."),
    ("CAT", catalan, (13,),
     "Determine the number of distinct ways to fully parenthesise a "
     "non-associative product of fourteen indistinguishable factors x · x · "
     "x · … · x (fourteen factors in total). Equivalently, the number of "
     "rooted ordered binary trees with fourteen leaves."),

    # ----- MOTZKIN family (6 items) -----
    ("MOT", motzkin, (10,),
     "Compute the number of lattice paths from (0, 0) to (10, 0) that "
     "use unit horizontal-right steps (1, 0), unit up-diagonal steps "
     "(1, +1), and unit down-diagonal steps (1, -1), and which never "
     "venture strictly below the x-axis."),
    ("MOT", motzkin, (9,),
     "How many chord diagrams can be drawn on nine labelled points "
     "arranged on a circle such that no two chords cross and unmatched "
     "points are permitted? (Equivalently: non-crossing matchings of an "
     "ordered nine-point set, where any subset of the nine points may "
     "be left unmatched.)"),
    ("MOT", motzkin, (11,),
     "Determine the number of plane trees with exactly twelve nodes in "
     "which every internal node has either one child or two children "
     "(no internal node has three or more children, and leaves are "
     "permitted at every level). Equivalently, plane unary-binary trees "
     "of size twelve."),
    ("MOT", motzkin, (8,),
     "Count the sequences (a_1, a_2, …, a_8) of integers with each "
     "a_i ∈ {-1, 0, +1}, partial sums a_1 + a_2 + … + a_k non-negative "
     "for every k in {1, …, 8}, and total sum a_1 + a_2 + … + a_8 = 0. "
     "Output the count."),
    ("MOT", motzkin, (12,),
     "Compute the number of unit-step lattice paths in the upper half-"
     "plane that begin at (0, 0), end at (12, 0), and at every step take "
     "exactly one of the three vectors right (+1, 0), north-east "
     "(+1, +1), or south-east (+1, -1)."),
    ("MOT", motzkin, (7,),
     "Determine the number of distinct ways to draw a (possibly empty) "
     "set of non-crossing chords among seven labelled points placed in "
     "convex position on a circle, where any number of the seven points "
     "(including all of them, or none of them) may be left unmatched."),

    # ----- BELL family (6 items) -----
    ("BEL", bell, (8,),
     "Compute the number of equivalence relations definable on a set of "
     "eight distinguishable elements. (Equivalently, the number of "
     "partitions of an eight-element set into unordered, non-empty, "
     "pairwise-disjoint blocks whose union is the whole set.)"),
    ("BEL", bell, (10,),
     "How many distinct ways are there to colour ten labelled balls with "
     "an unbounded supply of indistinguishable colours, where only the "
     "induced partition of balls into same-colour groups is recorded "
     "(the colours themselves carry no labels)? Emit a single integer."),
    ("BEL", bell, (9,),
     "Determine the number of partitions of the integer set {1, 2, …, 9} "
     "into unordered non-empty blocks, where the number of blocks is "
     "unrestricted (so a single-block partition through to a nine-singleton "
     "partition are all admissible)."),
    ("BEL", bell, (11,),
     "Count the surjections from an eleven-element set onto an ordered "
     "label-set of unbounded size, where two surjections are deemed "
     "equivalent iff they induce the same partition on the domain. "
     "(Equivalently, set partitions of an eleven-element domain.)"),
    ("BEL", bell, (7,),
     "Compute the number of finite topologies on a seven-element set X "
     "whose only open sets are unions of the blocks of some partition "
     "of X (i.e. T_0-quotients reduced to set partitions). Equivalently, "
     "the number of partitions of {1, 2, …, 7} into unordered blocks."),
    ("BEL", bell, (12,),
     "Determine the total number of ways to distribute twelve distinguish-"
     "able physical objects into an indeterminate number of indistinguish-"
     "able non-empty boxes, where two distributions are identified iff "
     "they induce the same grouping of the twelve objects."),

    # ----- SCHRÖDER (large) family (6 items) -----
    ("SCH", schroder_large, (8,),
     "Compute the number of monotone lattice paths from (0, 0) to (8, 8) "
     "that use unit-right, unit-up, and unit-northeast-diagonal steps "
     "(each diagonal step covers one unit of both x and y), and that "
     "stay weakly above the diagonal y = x at every lattice point."),
    ("SCH", schroder_large, (7,),
     "How many distinct ways exist to insert one or more pairs of "
     "(redundant) matched parentheses around the symbols of the string "
     "x_0 x_1 x_2 x_3 x_4 x_5 x_6 x_7 such that the resulting bracketing "
     "is well-formed and each pair groups a non-empty contiguous "
     "subsequence? Equivalently, the number of dissections of a convex "
     "(8+2)-gon into sub-polygons by non-crossing diagonals where the "
     "empty dissection is permitted."),
    ("SCH", schroder_large, (6,),
     "Determine the number of separable permutations of length seven, "
     "where a permutation is separable iff it can be built from the "
     "one-element permutation by repeated direct and skew sums. "
     "(Equivalently, the number of permutations of {1, …, 7} that "
     "avoid both the pattern 2413 and the pattern 3142.)"),
    ("SCH", schroder_large, (9,),
     "Compute the number of lattice paths from the origin (0, 0) to "
     "the point (9, 9) using steps right (+1, 0), up (0, +1), and "
     "north-east diagonal (+1, +1), where the path is required to "
     "remain weakly above the line y = x throughout."),
    ("SCH", schroder_large, (5,),
     "Count the polygon dissections of a convex heptagon (a 7-gon) by "
     "non-crossing diagonals into smaller sub-polygons. The empty "
     "dissection (using no diagonals) counts as a single arrangement; "
     "two dissections are distinguished by the set of diagonals they "
     "draw."),
    ("SCH", schroder_large, (10,),
     "How many monotone right-and-up lattice paths from (0, 0) to "
     "(10, 10), augmented with the third permissible step type of a "
     "unit north-east diagonal (+1, +1), stay weakly above the main "
     "diagonal y = x at every lattice point visited?"),

    # ----- NARAYANA family (6 items; N(n, k) with n, k varied) -----
    ("NAR", narayana, (9, 4),
     "Compute the number of Dyck paths of semilength nine (so total "
     "length eighteen) that have exactly four peaks, where a peak is "
     "a local maximum — i.e. an up-step immediately followed by a "
     "down-step. Emit a single integer."),
    ("NAR", narayana, (8, 3),
     "How many non-crossing partitions of the set {1, 2, …, 8} consist "
     "of exactly three blocks? A partition is non-crossing iff the "
     "blocks, when drawn as arcs above the line of labelled points, "
     "do not cross."),
    ("NAR", narayana, (10, 5),
     "Determine the number of ordered binary trees with exactly ten "
     "internal nodes that have exactly five leaves at odd depth, where "
     "the root sits at depth zero. (This is the Narayana count "
     "N(10, 5).)"),
    ("NAR", narayana, (7, 3),
     "Count the lattice paths from (0, 0) to (7, 7) using only unit "
     "right and unit up steps, staying weakly below the diagonal y = x, "
     "and crossing the diagonal exactly three times by a returning "
     "step. (This is the Narayana number N(7, 3).)"),
    ("NAR", narayana, (11, 6),
     "Compute the number of Dyck paths of semilength eleven (total "
     "length twenty-two) with exactly six peaks, where a peak is an "
     "up-step followed immediately by a down-step."),
    ("NAR", narayana, (12, 4),
     "How many non-crossing partitions of {1, 2, …, 12} consist of "
     "exactly four non-empty blocks (where blocks are unordered and "
     "the union of all blocks is {1, …, 12})?"),

    # ----- PARTITION family (6 items) -----
    ("PAR", partition, (30,),
     "Compute the number of ways to write the positive integer thirty "
     "as a sum of one or more positive integers, where the order of "
     "summands does not matter (so 3 + 1 + 1 and 1 + 3 + 1 are the "
     "same partition). Emit the count p(30)."),
    ("PAR", partition, (40,),
     "How many integer partitions are there of the number forty, where "
     "a partition of forty is any multiset of positive integers whose "
     "sum equals forty?"),
    ("PAR", partition, (25,),
     "Determine the number of distinct multisets of positive integers "
     "whose sum equals twenty-five. (Equivalently, the value of the "
     "unrestricted partition function p(25).)"),
    ("PAR", partition, (50,),
     "Compute p(50), the number of integer partitions of fifty into "
     "positive integer parts where the order of parts is immaterial "
     "and the number of parts is unrestricted."),
    ("PAR", partition, (35,),
     "Count the unordered representations of the integer thirty-five "
     "as a sum of one or more positive integers, where two represent-"
     "ations are identified iff they are multisets of the same parts."),
    ("PAR", partition, (45,),
     "How many distinct integer partitions does the positive integer "
     "forty-five admit? A partition is a non-increasing sequence of "
     "positive integers summing to forty-five."),
]

assert len(CATALOGUE) == 36, f"expected 36 manifestations, got {len(CATALOGUE)}"

# Sanity: family count distribution
from collections import Counter
fc = Counter(c[0] for c in CATALOGUE)
assert all(v == 6 for v in fc.values()), f"each family must have exactly 6 entries, got {fc}"


def _interleave(catalogue):
    """Latin-square interleave: produce 36 entries arranged so that every
    block of 6 consecutive ordinals spans all six combinatorial families
    exactly once. Concretely: the i-th family's j-th item lands at
    deliverable ordinal 6*j + i (1-indexed), so ordinals 1..6 carry one item
    from each family in family-list order, ordinals 7..12 carry the second
    item from each family in the same order, and so on. This breaks the
    naive 'worker N owns family N entirely' partition: any contiguous
    six-ordinal worker batch is forced to recognise all six families."""
    # Bucket by family code preserving in-family insertion order
    by_family: OrderedDict[str, list] = OrderedDict()
    for entry in catalogue:
        by_family.setdefault(entry[0], []).append(entry)
    families = list(by_family.keys())  # ['CAT','MOT','BEL','SCH','NAR','PAR']
    assert all(len(by_family[f]) == 6 for f in families)
    interleaved = []
    for j in range(6):                # block index
        for fam in families:          # one item from each family per block
            interleaved.append(by_family[fam][j])
    assert len(interleaved) == 36
    return interleaved


def main() -> None:
    CORPUS_DIR.mkdir(parents=True, exist_ok=True)
    for p in ORACLE_PATHS:
        p.parent.mkdir(parents=True, exist_ok=True)

    interleaved = _interleave(CATALOGUE)

    items: list[OrderedDict] = []
    gold: OrderedDict[str, int] = OrderedDict()

    for idx, (family_code, evaluator, args, prose) in enumerate(interleaved, start=1):
        tag = f"COUNT-{idx:02d}"
        count_int = int(evaluator(*args))
        item = OrderedDict()
        item["tag"] = tag
        item["description"] = prose
        # parameters carry the integer evaluation index n (and, for Narayana
        # entries, the secondary block-count index k) that the prose
        # references. The underlying combinatorial family is intentionally
        # NOT carried as a field; the agent must recognise the family from
        # the prose alone, which is the entire workload of this task.
        item["parameters"] = list(args)
        items.append(item)
        gold[tag] = count_int

    corpus = OrderedDict()
    corpus["corpus_format"] = "combinatorial-handbook-v1"
    corpus["origin"] = (
        "Paraphrased combinatorial manifestation prose drawn from canonical "
        "enumeration references: Stanley, Enumerative Combinatorics, "
        "Volume 2, Cambridge University Press, 1999 (Exercise 6.19, with "
        "near-Catalan extensions); the Online Encyclopedia of Integer "
        "Sequences entries A000108 (Catalan), A001006 (Motzkin), A000110 "
        "(Bell), A006318 (large Schroder), A001263 (Narayana triangle), "
        "and A000041 (unrestricted partition function); Aigner, Discrete "
        "Mathematics, AMS, 2007."
    )
    corpus["editorial_note"] = (
        "Each manifestation entry is a self-contained natural-language "
        "description of a counting problem. The integer answer for each "
        "entry is the value of the underlying combinatorial sequence at "
        "the supplied evaluation index (and, for Narayana entries, at the "
        "supplied secondary block-count index). Manifestation prose "
        "deliberately avoids naming the underlying sequence family or any "
        "OEIS A-number; structure recognition from the prose is the agent "
        "workload."
    )
    corpus["item_count"] = 36
    corpus["items"] = items

    corpus_path = CORPUS_DIR / "corpus.json"
    corpus_path.write_text(json.dumps(corpus, indent=2) + "\n")

    # YAML oracle: write by hand to keep dependency-free
    yaml_lines = [
        "# Gold integer counts for the combinatorial-manifestation handbook task.",
        "# Sealed under /task/solution/oracle.yaml and /task/tests/oracle.yaml.",
        "# Agent never sees this file at runtime.",
        "",
    ]
    for tag, val in gold.items():
        yaml_lines.append(f"{tag}: {val}")
    yaml_body = "\n".join(yaml_lines) + "\n"
    for p in ORACLE_PATHS:
        p.write_text(yaml_body)

    print(f"wrote corpus to {corpus_path}")
    print(f"wrote oracle to {ORACLE_PATHS[0]} and {ORACLE_PATHS[1]}")
    print(f"item count: {len(items)} | gold count: {len(gold)}")
    print(f"gold magnitude range: min={min(gold.values())}, max={max(gold.values())}")
    print(f"sample first 5 gold: {list(gold.items())[:5]}")
    print(f"sample last 5 gold: {list(gold.items())[-5:]}")


if __name__ == "__main__":
    main()
