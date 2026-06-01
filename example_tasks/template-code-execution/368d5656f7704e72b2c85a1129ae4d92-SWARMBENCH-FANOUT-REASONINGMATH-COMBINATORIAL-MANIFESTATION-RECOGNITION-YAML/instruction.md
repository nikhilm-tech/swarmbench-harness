# Recognising combinatorial families from paraphrased prose

You are the answer-key assembler for a draft chapter of an enumerative-
combinatorics workbook. The chapter author has rewritten every counting
question of the chapter into a long-form English paraphrase, deliberately
stripping out the family's published name, its OEIS A-number, and any
textbook citation tag — anything that would let a reader skip recognition
and look the answer up directly. Your role is to reconstruct the chapter's
integer answer key from the prose alone.

For each of the 36 chapter entries, the work breaks into four steps:
(a) read the English paraphrase; (b) recognise which canonical
combinatorial family the prose corresponds to — drawn from the standard
repertoire of enumerative combinatorics (Catalan, Motzkin, Bell, large
Schröder, Narayana, integer-partition, and the small set of related
families that appear in canonical references such as Stanley's
*Enumerative Combinatorics*); (c) evaluate the recognised family's closed
form at the integer argument(s) the paraphrase supplies; (d) commit the
resulting integer into a YAML answer-key file at a single fixed
deliverable path. Step (b), the recognition step, is the substantive
intellectual workload — the chapter is constructed so that lookup-driven
bypasses are not possible.

## Reading the chapter

The chapter is a single JSON document at
`/input_artifacts/combinatorial_handbook/corpus.json`, mounted read-only.
`json.loads` of the file's bytes yields an object with these top-level
keys: `corpus_format` (string version stamp, presently
`combinatorial-handbook-v1`); `origin` (a paragraph naming the published
references the paraphrases were sourced from); `editorial_note` (a
paragraph on the recognition convention); `item_count` (the integer 36);
and `items` (an array of length 36).

Each member of `items` carries exactly three keys:

  - **`tag`** — a string matching `^COUNT-\d{2}$`, drawn from
    `COUNT-01`..`COUNT-36`; this is the per-entry handle the answer-key
    file is keyed on.
  - **`description`** — the English paraphrase; the only authoritative
    statement of the counting problem, and the place where the
    combinatorial family lives, hidden inside the prose.
  - **`parameters`** — an array of one non-negative integer for
    single-index families (Catalan, Motzkin, Bell, large Schröder,
    integer partition), or two non-negative integers `[n, k]` in that
    order for two-index families (Narayana).

The entries do not interact — recognising or evaluating one carries no
information for any other. Process the entries in any order; parallel
processing across entries is fine.

## Writing the answer-key file

There is exactly one deliverable, at the absolute path:

    /logs/agent/integer_counts.yaml

Bytewise: UTF-8 encoding; line breaks are the single `0x0A` byte (no `\r`,
no `\r\n`); the body, after stripping at most one leading UTF-8 byte-order
mark, must parse cleanly under PyYAML's `safe_load` to a YAML mapping in
block style. A missing file, a non-mapping root (sequence, scalar, or
flow-style mapping), a zero-byte body, an embedded carriage return, or a
PyYAML parse exception each short-circuits the whole score to `0.000000`.

A data line in the file body has the shape `COUNT-XX: <integer>` and must
satisfy four conditions, all four required:

| name | condition                                                                                                |
|------|----------------------------------------------------------------------------------------------------------|
| C1   | left of `:` is exactly one of `COUNT-01`..`COUNT-36` — no case change, no leading whitespace, no `COUNT-1` short form, no `COUNT-001` over-padded form |
| C2   | exactly one ASCII colon and exactly one ASCII space (`0x20`) separate the handle and the integer literal |
| C3   | integer literal matches `^-?\d+$` — optional minus, then one-or-more decimal digits; nothing else        |
| C4   | the entire data line is exhausted by the `handle: integer` pair — no second pair, no trailing `#`-comment after the integer, no embedded sequence, no comma-list, no surrounding brackets |

C3 specifically rejects: YAML floats (`5.0`, `5e0`, `.5`, `5.`), quoted
forms (`"5"`, `'5'`), YAML booleans (`true`/`false`/`yes`/`no`/`on`/`off`),
YAML null tokens (`~`, `null`, an empty value after the colon), the
thousands separator in any flavour (`,`, `_`, space), scientific notation
(`5e0`, `5E0`), hexadecimal/binary/octal prefixes (`0x`, `0b`, `0o`),
whitespace embedded inside the digit run, and leading-zero padding on a
non-zero magnitude
(write `7`, not `007`; write `-8`, not `-008`; the bare token `0` is the
sole admissible zero). All gold answers in the present chapter are
non-negative; the minus-sign branch of C3 is retained for forward
compatibility with future chapters and a committed negative integer
simply scores zero on its handle.

Lines failing any of C1..C4 are silently dropped from contributing to
their handle's credit. Two further line kinds are tolerated and skipped
without contributing anywhere: a **comment line** (first non-whitespace
byte is `#`) and a **blank line** (zero bytes between two consecutive
`\n`).

Order within the body is irrelevant — the answer-key reader sorts by
handle at parse time. If a handle is committed on more than one
admissible data line, the integer from whichever admissible line appeared
first is kept; later duplicates are dropped without penalty.

## Crediting

After the agent's container exits, a standalone Python checker takes
over. The checker can read only the file at
`/logs/agent/integer_counts.yaml`; everything else inside the agent's
filesystem is invisible to it.

The checker first performs the structural-short-circuit tests above (file
exists; no carriage-return byte anywhere; non-empty after stripping at
most one leading UTF-8 byte-order mark; parses to a block-mapping root).
On any short-circuit, it emits `0.000000` directly to
`/logs/verifier/reward.txt` and stops.

Otherwise it walks the body line-by-line under C1..C4, building a private
`tag -> integer` lookup, keeping each tag's first admissible occurrence.
It then opens the held-out gold table at `./oracle.yaml` (a path NOT
mounted into the agent's container — opening it from inside the agent
raises `FileNotFoundError`), and for each of the 36 gold tags advances a
match counter by one whenever the agent's integer at that tag exactly
equals the gold integer under Python's arbitrary-precision `int` equality.

The fractional accuracy — the match counter divided by the chapter size,
truncated into the closed unit interval to guard against any subsequent
edits — is the numeric score, formatted to six decimal places and
deposited at `/logs/verifier/reward.txt`. A per-handle audit document at
`/logs/verifier/report.json` names what was committed, what was expected,
and the defect class on misses; it distinguishes a structural-short-
circuit `0.000000` from a 36-individually-wrong `0.000000`.

## Two recognition pitfalls

**Magnitude spread.** Some chapter entries have answers in the hundreds;
others cross seven decimal digits. The chapter does not warn which entry
sits where. A recognised family that returns a multi-digit integer at the
supplied argument must be committed in full unrounded magnitude — no
truncation of high digits "for tidiness", no modular reduction, no
rounding. Python's `int` is arbitrary precision; sympy's combinatorial
primitives (`sympy.catalan`, `sympy.bell`, `sympy.binomial`,
`sympy.Rational(1, n)`, `sympy.npartitions`) all return Python `int`
objects with no further casting required.

**Look-alike families.** Several entries are deliberately worded so that
a fast first read points at a close-cousin family. Common look-alike
pairs: *non-crossing* vs *non-nesting* partitions of `[n]`; *Dyck path of
length 2n* vs *Dyck path of semilength n with k peaks*; *lattice path
with two step types* vs *with three step types*; *set partition* of `[n]`
vs *ordered set partition* of `[n]`. A near-miss family identification
typically produces an answer in the correct order of magnitude — exactly
what makes the slip hard to catch by eye. Cross-check with (i) the
`parameters` array shape (length 1 for single-index families; length 2
for two-index families), (ii) hand-evaluating the closed form at a tiny
index and matching the first few published terms of the candidate
sequence, or (iii) re-reading the prose for distinctive qualifiers.

## Agent-container facts

The agent starts in working directory `/workspace`. Pre-installed and
importable without further install: `sympy 1.13.3`, `numpy 2.1.3`,
`scipy 1.14.1`, `mpmath 1.3.0`, `PyYAML 6.0.2`. Two mounts: `/input_artifacts/`
(read-only; holds `combinatorial_handbook/corpus.json`) and `/logs/agent/`
(writable; the deliverable lands here). Paths under `/tests/`,
`/solution/`, and the gold table at `./oracle.yaml` are not mounted into
the agent's container — any open attempt raises `FileNotFoundError`. No
outbound network is available during the run; `oeis.org` is unreachable,
and the chapter prose deliberately omits each family's A-number for the
same reason — even if the network were open, an OEIS lookup would not
short-circuit the recognition workload.

## Worksheet skeleton (illustrative — fill in every `<integer>`)

```
COUNT-01: <integer>
COUNT-02: <integer>
COUNT-03: <integer>
# ... 32 more lines, one COUNT-XX: <integer> per remaining handle ...
COUNT-36: <integer>
```
