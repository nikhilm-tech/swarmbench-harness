import argparse
import json
import os
import re
import time

from openai import OpenAI


def extract_json(text: str) -> str:
    """Strip markdown code blocks and return raw JSON string."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return match.group(1).strip()
    return text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--agent-output")
    parser.add_argument("--oracle")
    parser.add_argument("--reward-out")
    args = parser.parse_args()

    try:
        agent_output = json.load(open(args.agent_output))
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"ERROR: Could not load agent output: {e}")
        json.dump({"reward": 0.0}, open(args.reward_out, "w"))
        with open("/logs/agent/judge_justification.txt", "w") as f:
            f.write(f"Score: 0.0\n\nAgent output file missing or invalid: {e}")
        return

    oracle = json.load(open(args.oracle))

    # Exact match shortcut — oracle agent run always gets 1.0
    if agent_output == oracle:
        json.dump({"reward": 1.0}, open(args.reward_out, "w"))
        with open("/logs/agent/judge_justification.txt", "w") as f:
            f.write("Score: 1.0\n\nAgent output exactly matches oracle. Reward = 1.0.")
        return

    client = OpenAI(
        api_key=os.environ["FIREWORKS_API_KEY"],
        base_url="https://api.fireworks.ai/inference/v1",
    )

    prompt = (
        "You are an evaluation judge grading an agent's output against a gold oracle.\n\n"
        f"ORACLE:\n{json.dumps(oracle, indent=2)}\n\n"
        f"AGENT OUTPUT:\n{json.dumps(agent_output, indent=2)}\n\n"
        "Evaluate the agent output field by field against the oracle.\n\n"
        "Scoring rules:\n"
        "- Score 1.0 if ALL fields are correct.\n"
        "- Score 0.0 if the output is completely wrong or missing.\n"
        "- Score between 0.0 and 1.0 based on the fraction of fields/criteria that pass.\n"
        "  For example: 3 out of 5 criteria correct → score 0.6\n\n"
        "In your justification, list EACH field or criterion evaluated, whether it PASSED or FAILED, "
        "and a brief reason. Then state the final score as passed/total.\n\n"
        "Respond in JSON only (no markdown):\n"
        '{"score": <float 0.0-1.0>, "passed": <int>, "total": <int>, '
        '"justification": "<detailed field-by-field breakdown>"}'
    )

    # Retry up to 3 times with exponential backoff for transient API errors
    raw = ""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="accounts/fireworks/models/kimi-k2p5",
                messages=[{"role": "user", "content": prompt}],
                temperature=0,
            )
            raw = response.choices[0].message.content or ""
            break
        except Exception as e:
            print(f"Judge API error (attempt {attempt + 1}/3): {e}")
            if attempt < 2:
                time.sleep(5 * (2 ** attempt))  # 5s, 10s
            else:
                json.dump({"reward": 0.0}, open(args.reward_out, "w"))
                with open("/logs/agent/judge_justification.txt", "w") as f:
                    f.write(f"Score: 0.0\n\nJudge API failed after 3 attempts: {e}")
                return
    try:
        result = json.loads(extract_json(raw))
    except json.JSONDecodeError as e:
        print(f"ERROR: Judge response not valid JSON: {e}\nRaw: {raw!r}")
        json.dump({"reward": 0.0}, open(args.reward_out, "w"))
        with open("/logs/agent/judge_justification.txt", "w") as f:
            f.write(f"Score: 0.0\n\nJudge parse error: {e}\nRaw response: {raw}")
        return

    score = float(result.get("score", 0.0))
    passed = result.get("passed", "?")
    total = result.get("total", "?")

    json.dump({"reward": score}, open(args.reward_out, "w"))

    with open("/logs/agent/judge_justification.txt", "w") as f:
        f.write(
            f"Score: {score} ({passed}/{total} criteria passed)\n\n"
            f"{result.get('justification', '')}"
        )


if __name__ == "__main__":
    main()
