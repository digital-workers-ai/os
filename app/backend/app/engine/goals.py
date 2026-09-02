from app import caches
from app.engine import metrics, strategies

DEFAULT_GOALS = caches.KNOWLEDGE_DIR / "goals.yaml"

REQUIRED = ("metric", "target", "strategy")

VERDICTS = {True: "met", False: "missed", None: "unknown"}


class GoalError(ValueError):
    pass


def load(path=None):
    return caches.load_mapping(path or DEFAULT_GOALS, GoalError)


definitions = caches.cached(load)


def _refusal(row):
    if row is None:
        return "metric unavailable: no such metric in the catalog"
    if row.get("error"):
        return f"metric unavailable: {row['error']}"
    if row.get("mixed_currencies"):
        return (
            "metric unavailable: it spans currencies "
            f"{row['mixed_currencies']} and refuses to sum across them"
        )
    if row.get("value") is None:
        return "metric unavailable: it produced no value"
    if not row.get("entities") and not row.get("population_size"):
        return (
            "no entities matched, so the number measures nothing rather "
            "than measuring zero"
        )
    return None


async def _history_for(session, metric):
    series = await metrics.history(session, metric)
    if not series["comparable"]:
        return [], (
            "the stored series is not comparable: it spans "
            f"{series['breaks'] + 1} runs produced by different "
            "vocabularies, models or prompts"
        )
    runs = series["runs"]
    if not runs:
        return [], None
    return [
        point["value"] for point in runs[-1]["points"] if point["value"] is not None
    ], None


async def evaluate_over(session, defs, metric_values):
    results = []
    for name, spec in sorted(defs.items()):
        label = spec.get("label", name) if isinstance(spec, dict) else name
        if not isinstance(spec, dict) or any(spec.get(k) is None for k in REQUIRED):
            results.append(
                {
                    "goal": name,
                    "label": label,
                    "met": None,
                    "error": f"goal is missing one of {list(REQUIRED)}",
                }
            )
            continue

        metric, strategy_name = str(spec["metric"]), str(spec["strategy"])
        strategy = strategies.STRATEGIES.get(strategy_name)
        if strategy is None:
            results.append(
                {
                    "goal": name,
                    "label": label,
                    "met": None,
                    "error": f"unknown strategy {strategy_name!r}",
                }
            )
            continue
        try:
            target = float(spec["target"])
        except (TypeError, ValueError):
            results.append(
                {
                    "goal": name,
                    "label": label,
                    "met": None,
                    "error": f"target {spec['target']!r} is not numeric",
                }
            )
            continue

        row = metric_values.get(metric)
        base = {
            "goal": name,
            "label": label,
            "metric": metric,
            "target": target,
            "strategy": strategy_name,
        }
        refusal = _refusal(row)
        if refusal:
            results.append({**base, "current": None, "met": None, "unknown": refusal})
            continue

        history, history_refusal = [], None
        if strategy_name in strategies.NEEDS_HISTORY:
            history, history_refusal = await _history_for(session, metric)
        if history_refusal:
            results.append(
                {
                    **base,
                    "current": row.get("value"),
                    "met": None,
                    "unknown": history_refusal,
                }
            )
            continue
        params = {**strategies.defaults(strategy_name), **(spec.get("params") or {})}
        outcome = strategy(float(row["value"]), target, history, params)
        result = {
            **base,
            "current": row["value"],
            "met": outcome.met,
            "progress": outcome.progress,
            "entities": row.get("entities"),
            **outcome.detail,
        }
        if outcome.met is None and "unknown" not in result:
            result["unknown"] = "the strategy could not decide from these inputs"
        if row.get("inferred"):
            result["inferred"] = True
            for key in ("reading", "vocabulary_sha", "produced_by"):
                if row.get(key):
                    result[key] = row[key]
        results.append(result)
    return results


async def evaluate(session):
    values = await metrics.evaluate(session)
    rows = await evaluate_over(session, definitions(), values)
    counts = {"met": 0, "missed": 0, "unknown": 0}
    for row in rows:
        counts[VERDICTS[row["met"]]] += 1
    return {"goals": rows, **counts}
