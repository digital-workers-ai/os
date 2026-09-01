import math
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Outcome:
    met: bool | None
    progress: float | None
    detail: dict = field(default_factory=dict)


NEEDS_HISTORY_REASON = "not enough history to judge a trend"


def _finite(*values):
    return all(isinstance(v, int | float) and math.isfinite(v) for v in values)


def _clamp(value):
    return round(min(100.0, max(0.0, value)), 1)


def _toward(current, target):
    if not _finite(current, target):
        return None
    if target <= 0:
        return 100.0 if current >= target else 0.0
    return _clamp(100.0 * current / target)


def _under(current, target):
    if not _finite(current, target):
        return None
    if current <= target:
        return 100.0
    if current <= 0:
        return 0.0
    return _clamp(100.0 * target / current)


def _unknown(reason):
    return Outcome(met=None, progress=None, detail={"unknown": reason})


def at_least(current, target, history, params):
    if not _finite(current, target):
        return _unknown("value is not a finite number")
    return Outcome(met=current >= target, progress=_toward(current, target))


def at_most(current, target, history, params):
    if not _finite(current, target):
        return _unknown("value is not a finite number")
    return Outcome(met=current <= target, progress=_under(current, target))


def _trend_refusal(current, target, history):
    if len(history) < 2:
        return _unknown(NEEDS_HISTORY_REASON)
    if not _finite(current, target, history[0], history[-1]):
        return _unknown("value is not a finite number")
    return None


def _rose(history):
    if history[-1] > history[0]:
        return True
    return all(b >= a for a, b in zip(history, history[1:], strict=False))


def increasing(current, target, history, params):
    refusal = _trend_refusal(current, target, history)
    if refusal:
        return refusal
    rising = _rose(history)
    return Outcome(
        met=bool(rising and current >= target),
        progress=_toward(current, target),
        detail={"trend": "up" if rising else "flat/down"},
    )


STRATEGIES = {"at_least": at_least, "at_most": at_most, "increasing": increasing}

NEEDS_HISTORY = {"increasing"}
