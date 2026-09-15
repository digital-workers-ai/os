from datetime import UTC, date, datetime, timedelta
from importlib import import_module

from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from app import clock
from app.engine import calendar as spec
from app.models import Proposal, ProposalEvidence, SlotSkip

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

STATES = {"open": "proposed", "approved": "approved", "built": "built"}

RANK = {"built": 3, "approved": 2, "open": 1}


def _named_days(slot):
    days = slot.get("days")
    if isinstance(days, list):
        return days
    return [slot.get("day")]


def _week(day):
    return (day.toordinal() - 1) // 7


def _weekly(slot, frm, to, fortnightly):
    named = set(_named_days(slot))
    return [
        day
        for day in (
            date.fromordinal(n) for n in range(frm.toordinal(), to.toordinal() + 1)
        )
        if WEEKDAYS[day.weekday()] in named and not (fortnightly and _week(day) % 2)
    ]


def _monthly(slot, frm, to):
    days = []
    year, month = frm.year, frm.month
    while (year, month) <= (to.year, to.month):
        landing = date(year, month, slot["day"])
        if frm <= landing <= to:
            days.append(landing)
        year, month = year + month // 12, month % 12 + 1
    return days


def _dates(slot, frm, to):
    when = slot["when"]
    if when == "reactive":
        return []
    if when == "monthly":
        return _monthly(slot, frm, to)
    return _weekly(slot, frm, to, when == "fortnightly")


def _midnight(day):
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


async def _skips(session, frm, to):
    rows = (
        await session.execute(
            select(SlotSkip.slot_date, SlotSkip.slot_name).where(
                SlotSkip.slot_date.between(frm, to)
            )
        )
    ).all()
    return {(row.slot_date, row.slot_name) for row in rows}


async def _carried(session, names, frm, to):
    rows = (
        (
            await session.execute(
                select(Proposal)
                .where(
                    Proposal.slot_name.in_(names),
                    Proposal.status != "rejected",
                    or_(
                        Proposal.slot_date.between(frm, to),
                        and_(
                            Proposal.slot_date.is_(None),
                            Proposal.created_at >= _midnight(frm),
                            Proposal.created_at < _midnight(to) + timedelta(days=1),
                        ),
                    ),
                )
                .order_by(Proposal.seq)
            )
        )
        .scalars()
        .all()
    )
    carried: dict = {}
    for row in rows:
        key = (row.slot_date or row.created_at.date(), row.slot_name)
        standing = carried.get(key)
        if standing is None or (RANK[row.status], row.seq) > (
            RANK[standing.status],
            standing.seq,
        ):
            carried[key] = row
    return carried


async def _reasons(session, seqs):
    rows = (
        await session.execute(
            select(ProposalEvidence.proposal_seq, ProposalEvidence.detail)
            .where(ProposalEvidence.proposal_seq.in_(seqs))
            .order_by(ProposalEvidence.id)
        )
    ).all()
    reasons: dict = {}
    for seq, detail in rows:
        reasons.setdefault(seq, detail)
    return reasons


def _line(value):
    if isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def _state(day, name, skips, carried):
    if (day, name) in skips:
        return "skipped"
    if carried is None:
        return "empty"
    return STATES[carried.status]


def _slot(name, slot, day, skips, carried, reasons):
    standing = carried.get((day, name))
    reactive = slot["when"] == "reactive"
    return {
        "date": day.isoformat(),
        "time": None if slot.get("time") is None else str(slot["time"]),
        "name": name,
        "kind": slot["kind"],
        "look": slot.get("look"),
        "theme": slot.get("theme"),
        "reactive": reactive,
        "state": _state(day, name, skips, standing),
        "proposal_seq": None if standing is None else standing.seq,
        "reason": reasons.get(standing.seq) if reactive and standing else None,
        "spec": [f"{key}: {_line(value)}" for key, value in slot.items()],
    }


async def slots(session, frm, to):
    declared = spec.slots()
    skips = await _skips(session, frm, to)
    carried = await _carried(session, list(declared), frm, to)
    reasons = await _reasons(session, [row.seq for row in carried.values()])
    rows = [
        _slot(name, slot, day, skips, carried, reasons)
        for name, slot in declared.items()
        for day in _dates(slot, frm, to)
    ]
    rows += [
        _slot(name, declared[name], day, skips, carried, reasons)
        for (day, name) in carried
        if declared[name]["when"] == "reactive"
    ]
    return sorted(rows, key=lambda row: (row["date"], row["name"]))


def cadence(rows):
    counted: dict = {}
    for row in rows:
        if row["state"] == "skipped":
            continue
        done, planned = counted.get(row["kind"], (0, 0))
        counted[row["kind"]] = (done + (row["state"] == "built"), planned + 1)
    return [
        {"kind": kind, "done": done, "planned": planned}
        for kind, (done, planned) in sorted(
            counted.items(), key=lambda entry: spec.KINDS.index(entry[0])
        )
    ]


async def skip(session, day, name):
    await session.execute(
        insert(SlotSkip)
        .values(slot_date=day, slot_name=name, created_at=clock.now())
        .on_conflict_do_nothing()
    )


async def fill(session, days):
    return await import_module("app.agents.marketer").fill(session, days)
