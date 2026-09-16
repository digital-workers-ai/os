from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app import clock
from app.engine import calendar as declared
from app.models import Asset, SlotSkip
from app.skills import runner

CHAT = "chat"
EMPTY, BUILT, SKIPPED = "empty", "built", "skipped"


class SlotError(ValueError):
    pass


class UnknownSlot(SlotError):
    pass


def _spec(name) -> dict:
    slots = declared.slots()
    if name not in slots:
        raise UnknownSlot(f"no slot named {name!r} — known: {sorted(slots)}")
    return slots[name]


async def _built(session, frm, to) -> dict:
    found = await session.execute(
        select(Asset.slot_date, Asset.slot_name, Asset.seq)
        .where(Asset.slot_date.between(frm, to))
        .order_by(Asset.seq)
    )
    return {(day, name): seq for day, name, seq in found.all()}


async def _skipped(session, frm, to) -> set:
    found = await session.execute(
        select(SlotSkip.slot_date, SlotSkip.slot_name).where(
            SlotSkip.slot_date.between(frm, to)
        )
    )
    return {(day, name) for day, name in found.all()}


def _slot(day, name, spec) -> dict:
    return {
        "date": day.isoformat(),
        "time": spec["time"],
        "name": name,
        "kind": spec["kind"],
        "skill": spec["skill"],
        "look": spec.get("look"),
        "ratio": spec.get("ratio"),
        "theme": spec["theme"],
        "state": EMPTY,
        "asset_seq": None,
    }


async def slots(session, frm, to) -> list[dict]:
    built = await _built(session, frm, to)
    skipped = await _skipped(session, frm, to)
    expanded = []
    for name, spec in declared.slots().items():
        for day in declared.dates(spec, frm, to):
            slot = _slot(day, name, spec)
            if (day, name) in built:
                slot["state"], slot["asset_seq"] = BUILT, built[(day, name)]
            elif (day, name) in skipped:
                slot["state"] = SKIPPED
            expanded.append(slot)
    return sorted(expanded, key=lambda slot: (slot["date"], slot["name"]))


def cadence(slot_rows) -> list[dict]:
    counts = {kind: {"kind": kind, "done": 0, "planned": 0} for kind in declared.KINDS}
    for slot in slot_rows:
        if slot["state"] == SKIPPED:
            continue
        counts[slot["kind"]]["planned"] += 1
        if slot["state"] == BUILT:
            counts[slot["kind"]]["done"] += 1
    return [count for count in counts.values() if count["planned"]]


async def skip(session, day, name) -> None:
    _spec(name)
    await session.execute(
        insert(SlotSkip)
        .values(slot_date=day, slot_name=name, created_at=clock.now())
        .on_conflict_do_nothing()
    )


async def run(session, day, name):
    spec = _spec(name)
    if day not in declared.dates(spec, day, day):
        raise SlotError(f"{name} does not fall on {day.isoformat()}")
    if (day, name) in await _built(session, day, day):
        raise SlotError(f"{name} on {day.isoformat()} is already built")
    ask = runner.Ask(
        skill=spec["skill"],
        caller=CHAT,
        input=spec["theme"],
        look=spec.get("look"),
        ratio=spec.get("ratio"),
        slot_date=day,
        slot_name=name,
    )
    return await runner.open_run(session, ask), ask
