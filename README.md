# SwarmBench Harness

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

Clone and pin to the exact commit the diff targets:

```bash
git clone https://github.com/harbor-framework/harbor.git
cd harbor
git checkout e70d5f060ffeb4525f320669d50b290925b55425
```

> The commit SHA is pinned to ensure the diff applies cleanly. Do not skip `git checkout`.

There are two diff files in this directory — pick the one matching your OS. They contain identical changes; the Windows copy is just labeled separately so it's clear which one to use after download.

#### macOS / Linux

```bash
git apply ../swarmbench_harbor_changes.diff
uv sync --all-extras
```

#### Windows (PowerShell, from inside `harbor\`)

`git apply` requires LF line endings. If your browser, editor, or `core.autocrlf=true` converted the diff to CRLF on download, it will fail at empty-file stanzas with `git diff header lacks filename information`. Normalize first, then apply:

```powershell
# Re-emit the diff as LF + UTF-8 (no BOM)
$src  = "..\swarmbench_harbor_changes_windows.diff"
$dst  = "..\swarmbench_harbor_changes_windows.lf.diff"
$text = [System.IO.File]::ReadAllText((Resolve-Path $src)) -replace "`r`n","`n"
[System.IO.File]::WriteAllText($dst, $text, (New-Object System.Text.UTF8Encoding $false))

git apply --check $dst
git apply $dst
uv sync --all-extras
```

#### Windows (Git Bash, from inside `harbor/`)

```bash
tr -d '\r' < ../swarmbench_harbor_changes_windows.diff > ../swarmbench_harbor_changes_windows.lf.diff
git apply --check ../swarmbench_harbor_changes_windows.lf.diff
git apply ../swarmbench_harbor_changes_windows.lf.diff
uv sync --all-extras
```

Verify:
```bash
uv run harbor --version
```

### 2. Set API Key

Pick one provider depending on which backend you want to hit:

```bash
# Option A: Fireworks (covers both the dedicated K2.5 deployment and serverless fallback)
export FIREWORKS_API_KEY=your_fireworks_api_key_here

# Option B: OpenRouter (alternative provider, independent rate limits)
export OPENROUTER_API_KEY=your_openrouter_api_key_here
```

---

## Running Tasks

All commands run from inside the `harbor/` directory.

### Set your task path

```bash
TASK=../example_tasks/template-llm-judge/4c3c848bb2f9459cb908d78f02897c6f-SWARMBENCH-FANOUT-RESEARCH-MEDICALRESEARCH
```

### Model selection

Two model IDs are available with the **same** `FIREWORKS_API_KEY`:

| Pool | Model ID | Precision | Notes |
|---|---|---|---|
| **Dedicated K2.5 pool** | `accounts/bhanu-nalamadgu-7pl5/deployments/ba0vhq9e` | FP4 | H200 × 8, GLOBAL region. Independent rate-limit pool. Use for production trainer runs. |
| **Global serverless pool** | `accounts/fireworks/models/kimi-k2p5` | FP8 | Shared across all Fireworks customers. Use for ad-hoc runs or if the dedicated pool is unavailable. |

### Oracle Validation (expected reward = 1.0)

```bash
uv run harbor run -p $TASK -a oracle \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY
```

### Single Agent — dedicated pool

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-single \
  -m fireworks_ai/accounts/bhanu-nalamadgu-7pl5/deployments/ba0vhq9e \
  -k 1 -n 1 \
  --job-name "single-kimi-agent" \
  --jobs-dir "$TASK/execution_logs" \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --ae FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --quiet
```

### Single Agent — global serverless pool

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

### Multi Agent — dedicated pool

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-multi \
  -m fireworks_ai/accounts/bhanu-nalamadgu-7pl5/deployments/ba0vhq9e \
  -k 1 -n 1 \
  --job-name "multi-kimi-agent" \
  --jobs-dir "$TASK/execution_logs" \
  --ve FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --ae FIREWORKS_API_KEY=$FIREWORKS_API_KEY \
  --quiet
```

### Multi Agent — global serverless pool

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

## Running with OpenRouter

OpenRouter hosts `kimi-k2.5` (equivalent to Fireworks `kimi-k2p5`, same 262k context) with independent rate limits. To run on OpenRouter, swap the `-m` value and the API key env vars:

### Single Agent (OpenRouter)

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-single \
  -m openrouter/moonshotai/kimi-k2.5 \
  -k 1 -n 1 \
  --job-name "single-kimi-agent-openrouter" \
  --jobs-dir "$TASK/execution_logs" \
  --ve OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  --ae OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  --quiet
```

### Multi Agent (OpenRouter)

```bash
uv run harbor run \
  -p $TASK \
  -a swarm-kimi-multi \
  -m openrouter/moonshotai/kimi-k2.5 \
  -k 1 -n 1 \
  --job-name "multi-kimi-agent-openrouter" \
  --jobs-dir "$TASK/execution_logs" \
  --ve OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  --ae OPENROUTER_API_KEY=$OPENROUTER_API_KEY \
  --quiet
```

Other available OpenRouter Kimi variants (substitute after `openrouter/`): `moonshotai/kimi-k2-0905` (pinned), `moonshotai/kimi-k2.6` (newer), `moonshotai/kimi-k2-thinking`.

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
| `-m` | Model: `fireworks_ai/accounts/bhanu-nalamadgu-7pl5/deployments/ba0vhq9e` (dedicated, recommended) or `fireworks_ai/accounts/fireworks/models/kimi-k2p5` (serverless fallback) |
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

**`git diff header lacks filename information when removing 1 leading pathname component` (Windows)**
The diff has CRLF line endings (or a UTF-8 BOM) — `git apply`'s parser breaks at empty-file stanzas. Use the PowerShell or Git Bash snippet in [Setup → Windows](#windows-powershell-from-inside-harbor) to re-emit the diff as LF + UTF-8 (no BOM), then apply the `.lf.diff` file.

**`NonZeroAgentExitCodeError` / `curl: (6) Could not resolve host`**
The Docker container needs outbound internet access to install `kimi-cli`. Check Docker network settings — containers must be able to reach `astral.sh` and `pypi.org`.

**`trajectory.json` not created**
This file is written only after `kimi-cli` runs successfully. If the agent crashed at install (see above), fix the network issue first and re-run.