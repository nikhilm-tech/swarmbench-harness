# SwarmBench — Harbor Format Delivery

This package contains SwarmBench tasks in Harbor evaluation format, ready to run.

---

## What's Included

```
example_tasks/
├── README_HARBOR_RUN.md           ← this file
├── {task_id}/                     ← one folder per task
│   ├── instruction.md             ← task prompt
│   ├── task.toml                  ← metadata + config
│   ├── decomposition.yaml         ← multi-agent coordination guide
│   ├── environment/
│   │   ├── Dockerfile             ← container image definition
│   │   └── input_artifacts/       ← input files for the agent
│   ├── tests/
│   │   ├── test.sh                ← verifier entrypoint
│   │   ├── judge.py               ← LLM judge (scores agent output 0.0–1.0)
│   │   └── oracle.json            ← expected answer
│   └── solution/
│       ├── solve.sh               ← gold solution (for oracle validation only)
│       └── oracle.json            ← copy of expected answer
```

**Harbor changes diff:** Apply `swarmbench_harbor_changes.diff` to a clean Harbor clone to add the SwarmBench agent classes.

---

## Prerequisites

- Docker Desktop running
- [uv](https://docs.astral.sh/uv/) installed

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Clone Harbor and apply SwarmBench changes

```bash
git clone https://github.com/harbor-framework/harbor.git
cd harbor
git checkout e70d5f060ffeb4525f320669d50b290925b55425
git apply ../swarmbench_harbor_changes.diff
uv sync --all-extras
```

> The commit SHA is pinned to ensure the diff applies cleanly. Do not skip `git checkout`.
> Last updated: 2026-05-05 — if the patch fails, the upstream may have moved ahead. Request an updated diff from the SwarmBench team.

Verify:
```bash
uv run harbor --version
```

### 2. Set API Key

```bash
export FIREWORKS_API_KEY=your_fireworks_api_key_here
```

---

## Running Tasks

All commands run from inside the `harbor/` directory.

### Set your task path

```bash
TASK=../example_tasks/4c3c848bb2f9459cb908d78f02897c6f-SWARMBENCH-FANOUT-RESEARCH-MEDICALRESEARCH
```

### Oracle Validation (confirms pipeline works — expected reward = 1.0)

```bash
uv run harbor run -p $TASK -a oracle \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY
```

### Single Agent (1 run)

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-single \
  -m fireworks_ai/accounts/fireworks/models/kimi-k2p5 \
  -k 1 -n 1 \
  --job-name "single-kimi-agent" \
  --jobs-dir "$TASK/execution_logs" \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --ae FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --quiet
```

### Multi Agent (1 run)

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-multi \
  -m fireworks_ai/accounts/fireworks/models/kimi-k2p5 \
  -k 1 -n 1 \
  --job-name "multi-kimi-agent" \
  --jobs-dir "$TASK/execution_logs" \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --ae FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --quiet
```

### Run All Tasks (batch script)

```bash
bash scripts/run_all_tasks.sh
```

---

## Results

Results are saved inside each task:

```
{task}/execution_logs/
├── single-kimi-agent/
│   ├── result.json              ← reward from 1 run
│   └── {trial}/
│       ├── agent/output.json    ← agent's answer
│       ├── agent/trajectory.json← step-by-step trace
│       ├── agent/judge_justification.txt ← scoring breakdown
│       └── verifier/reward.json ← score for this run
└── multi-kimi-agent/
    └── (same structure)
```

Browse results interactively:
```bash
cd harbor && uv run harbor view ../example_tasks/
```

---

## Flag Reference

| Flag | Purpose |
|---|---|
| `-p` | Path to task directory |
| `-a` | Agent: `oracle`, `swarm-kimi-single`, `swarm-kimi-multi` |
| `-m` | Model: `fireworks_ai/accounts/fireworks/models/kimi-k2p5` |
| `-k` | Number of runs (attempts) per task |
| `-n` | Concurrent trials within the run |
| `--job-name` | Output folder name under `--jobs-dir` |
| `--jobs-dir` | Where Harbor saves results |
| `--ve` | Env var for verifier (`judge.py` LLM call) |
| `--ae` | Env var for agent (kimi API call) |
| `--quiet` | Show summary table only |

---

## Tasks in This Delivery

| Task | Domain | Pattern | Sub-Agents |
|---|---|---|---|
| `07803259...AGENTBENCHLANDSCAPE` | knowledge-research | fan-out-synthesize | 23 |
| `18477d2e...VENDORCROSSREF-MEDIUM-V3` | data-analysis | specialist-routing | 5 |
| `4c3c848b...MEDICALRESEARCH` | knowledge-research | fan-out-synthesize | 19 |