import json
import os
import sys


def load_entries(path):
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        raw = f.read().strip()
    try:
        if raw.startswith("["):
            return json.loads(raw)
        return [json.loads(line) for line in raw.splitlines() if line.strip()]
    except json.JSONDecodeError:
        return None


label = sys.argv[1]
entries = load_entries(os.environ["EXEC_FILE"])
if not isinstance(entries, list):
    sys.exit(0)
result = next(
    (e for e in reversed(entries) if isinstance(e, dict) and e.get("type") == "result"),
    {},
)
summary = result.get("result")
if isinstance(summary, str) and summary.strip():
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
        f.write(summary.rstrip() + "\n\n")
cost = result.get("total_cost_usd")
turns = result.get("num_turns", "?")
mins, secs = divmod(int(result.get("duration_ms", 0) / 1000), 60)
cost_s = f"${cost:.2f}" if isinstance(cost, (int, float)) else "n/a"
print(
    f"{label}: {cost_s} API · {turns} turns · {mins}m{secs:02d}s"
    f" · [logs]({os.environ['RUN_URL']})"
)
