sim# SwarmBench Harness

Evaluation harness for SwarmBench — runs single-agent and multi-agent benchmarks using [Harbor](https://github.com/harbor-framework/harbor).

---

## Prerequisites

- Docker Desktop running
- [uv](https://docs.astral.sh/uv/) installed

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

---

## Setup

### 1. Clone Harbor and apply SwarmBench patch

```bash
git clone https://github.com/harbor-framework/harbor.git
cd harbor
git checkout e70d5f060ffeb4525f320669d50b290925b55425
git apply ../swarmbench_harbor_changes.diff
uv sync --all-extras
```

> The commit SHA is pinned to ensure the diff applies cleanly. Do not skip `git checkout`.

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
TASK=../example_tasks/template-llm-judge/4c3c848bb2f9459cb908d78f02897c6f-SWARMBENCH-FANOUT-RESEARCH-MEDICALRESEARCH
```

### Oracle Validation (expected reward = 1.0)

```bash
uv run harbor run -p $TASK -a oracle \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY
```

### Single Agent

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

### Multi Agent

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

---

## Results

```
{task}/execution_logs/
├── single-kimi-agent/
│   ├── result.json
│   └── {trial}/
│       ├── agent/kimi-cli.txt
│       ├── agent/trajectory.json
│       └── verifier/reward.json
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
| `-k` | Number of runs per task |
| `-n` | Concurrent trials within the run |
| `--job-name` | Output folder name under `--jobs-dir` |
| `--jobs-dir` | Where Harbor saves results |
| `--ve` | Env var for verifier |
| `--ae` | Env var for agent |
| `--quiet` | Show summary table only |

---

## Troubleshooting

**Patch fails to apply**
Make sure you ran `git checkout e70d5f060ffeb4525f320669d50b290925b55425` before `git apply`. Applying on a different Harbor commit will cause context mismatches.

**`NonZeroAgentExitCodeError` / `curl: (6) Could not resolve host`**
The Docker container needs outbound internet access to install `kimi-cli`. Check Docker network settings — containers must be able to reach `astral.sh` and `pypi.org`.

**`trajectory.json` not created**
This file is written only after `kimi-cli` runs successfully. If the agent crashed at install (see above), fix the network issue first and re-run.