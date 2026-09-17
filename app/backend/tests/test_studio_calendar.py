from datetime import UTC, date, datetime

import pytest
import yaml
from sqlalchemy import select

from app.engine import calendar as declared
from app.models import Asset, AssetVersion, SkillRun, SlotSkip
from app.skills import runner
from app.studio import calendar

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
SHA = "c" * 64
SLOTS = {
    "newsletter_weekly": {
        "kind": "newsletter",
        "skill": "dw-newsletter",
        "when": "weekly",
        "day": "mon",
        "time": "06:00",
        "theme": "What changed this week.",
    },
    "linkedin_post": {
        "kind": "post",
        "skill": "dw-linkedin-post",
        "when": "weekly",
        "days": ["tue", "fri"],
        "time": "06:00",
        "look": "stat-card",
        "ratio": "1:1",
        "theme": "One thing a spreadsheet cannot do.",
    },
    "blog_fortnightly": {
        "kind": "blog",
        "skill": "dw-blog",
        "when": "fortnightly",
        "day": "thu",
        "time": "06:00",
        "theme": "One pillar, explained.",
    },
    "carousel_monthly": {
        "kind": "carousel",
        "skill": "dw-carousel",
        "when": "monthly",
        "day": 1,
        "time": "06:00",
        "look": "carousel",
        "ratio": "4:5",
        "theme": "One objection, answered.",
    },
}
WEEK = (date(2026, 9, 1), date(2026, 9, 7))
FRIDAY = date(2026, 9, 4)


@pytest.fixture
def slots(tmp_path, monkeypatch):
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump({"slots": SLOTS}, sort_keys=False))
    monkeypatch.setattr(declared, "DEFAULT_CALENDAR", path)


@pytest.fixture
def opened(monkeypatch):
    asks = []

    async def open_run(session, ask):
        asks.append(ask)
        asset = Asset(
            name=ask.input,
            kind=ask.skill.removeprefix("dw-"),
            skill=ask.skill,
            look=ask.look,
            ratio=ask.ratio,
            origin=ask.caller,
            slot_date=ask.slot_date,
            slot_name=ask.slot_name,
            created_at=NOW,
        )
        session.add(asset)
        await session.flush()
        session.add(AssetVersion(asset_seq=asset.seq, version=1, note=ask.input))
        run = SkillRun(
            skill=ask.skill,
            skill_sha=SHA,
            caller=ask.caller,
            asset_seq=asset.seq,
            version=1,
            status="running",
            started_at=NOW,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return runner.Started(run, asset.seq, 1)

    monkeypatch.setattr(runner, "open_run", open_run)
    return asks


async def _filled(session, day, name, **overrides):
    fields = {
        "name": "Filled",
        "kind": "post",
        "skill": "dw-linkedin-post",
        "origin": "marketer",
        "slot_date": day,
        "slot_name": name,
    }
    asset = Asset(**{**fields, **overrides})
    session.add(asset)
    await session.flush()
    return asset


async def _skipped(session, day, name):
    session.add(SlotSkip(slot_date=day, slot_name=name))
    await session.flush()


def _keys(rows):
    return [(row["date"], row["name"]) for row in rows]


class TestSlots:
    async def test_every_declared_slot_expands_sorted_by_date_then_name(
        self, session, slots
    ):
        rows = await calendar.slots(session, *WEEK)
        assert _keys(rows) == [
            ("2026-09-01", "carousel_monthly"),
            ("2026-09-01", "linkedin_post"),
            ("2026-09-03", "blog_fortnightly"),
            ("2026-09-04", "linkedin_post"),
            ("2026-09-07", "newsletter_weekly"),
        ]

    async def test_a_slot_carries_the_wire_shape(self, session, slots):
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert row == {
            "date": "2026-09-04",
            "time": "06:00",
            "name": "linkedin_post",
            "kind": "post",
            "skill": "dw-linkedin-post",
            "look": "stat-card",
            "ratio": "1:1",
            "theme": "One thing a spreadsheet cannot do.",
            "state": "empty",
            "asset_seq": None,
        }

    async def test_a_text_slot_has_no_look_or_ratio(self, session, slots):
        monday = date(2026, 9, 7)
        [row] = await calendar.slots(session, monday, monday)
        assert (row["look"], row["ratio"]) == (None, None)

    async def test_a_filled_slot_is_built_and_names_its_asset(self, session, slots):
        asset = await _filled(session, FRIDAY, "linkedin_post")
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert (row["state"], row["asset_seq"]) == ("built", asset.seq)

    async def test_a_skipped_slot_is_skipped(self, session, slots):
        await _skipped(session, FRIDAY, "linkedin_post")
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert (row["state"], row["asset_seq"]) == ("skipped", None)

    async def test_built_wins_over_skipped(self, session, slots):
        await _skipped(session, FRIDAY, "linkedin_post")
        asset = await _filled(session, FRIDAY, "linkedin_post")
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert (row["state"], row["asset_seq"]) == ("built", asset.seq)

    async def test_the_newest_asset_names_a_slot_filled_twice(self, session, slots):
        await _filled(session, FRIDAY, "linkedin_post")
        newer = await _filled(session, FRIDAY, "linkedin_post")
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert row["asset_seq"] == newer.seq

    async def test_an_asset_outside_the_range_or_slot_does_not_count(
        self, session, slots
    ):
        await _filled(session, date(2026, 9, 1), "linkedin_post")
        await _filled(session, FRIDAY, "newsletter_weekly")
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert row["state"] == "empty"

    async def test_a_reversed_range_has_no_slots(self, session, slots):
        assert await calendar.slots(session, date(2026, 9, 7), FRIDAY) == []


class TestCadence:
    def _row(self, kind, state):
        return {"kind": kind, "state": state}

    def test_counts_done_and_planned_per_kind_in_kinds_order(self):
        rows = [
            self._row("newsletter", "empty"),
            self._row("post", "built"),
            self._row("post", "empty"),
            self._row("carousel", "skipped"),
            self._row("blog", "built"),
        ]
        assert calendar.cadence(rows) == [
            {"kind": "post", "done": 1, "planned": 2},
            {"kind": "newsletter", "done": 0, "planned": 1},
            {"kind": "blog", "done": 1, "planned": 1},
        ]

    def test_no_rows_is_no_cadence(self):
        assert calendar.cadence([]) == []


class TestSkip:
    async def test_writes_one_row_stamped_by_the_clock(self, session, slots):
        await calendar.skip(session, FRIDAY, "linkedin_post")
        await calendar.skip(session, FRIDAY, "linkedin_post")
        [row] = (await session.execute(select(SlotSkip))).scalars().all()
        assert (row.slot_date, row.slot_name) == (FRIDAY, "linkedin_post")
        assert row.created_at == NOW

    async def test_refuses_a_slot_the_calendar_does_not_declare(self, session, slots):
        with pytest.raises(calendar.SlotError, match="nope"):
            await calendar.skip(session, FRIDAY, "nope")
        assert (await session.execute(select(SlotSkip))).scalars().all() == []


class TestRun:
    async def test_opens_a_run_with_the_slots_theme_look_and_ratio(
        self, session, slots, opened
    ):
        started, ask = await calendar.run(session, FRIDAY, "linkedin_post")
        assert opened == [ask]
        assert ask == runner.Ask(
            skill="dw-linkedin-post",
            caller="chat",
            input="One thing a spreadsheet cannot do.",
            look="stat-card",
            ratio="1:1",
            slot_date=FRIDAY,
            slot_name="linkedin_post",
        )
        assert started.skill_run.status == "running"
        assert started.version == 1
        [row] = await calendar.slots(session, FRIDAY, FRIDAY)
        assert (row["state"], row["asset_seq"]) == ("built", started.asset_seq)

    async def test_a_text_slot_asks_without_a_look(self, session, slots, opened):
        monday = date(2026, 9, 7)
        _started, ask = await calendar.run(session, monday, "newsletter_weekly")
        assert (ask.skill, ask.look, ask.ratio) == ("dw-newsletter", None, None)

    async def test_an_unknown_slot_is_unknown(self, session, slots, opened):
        with pytest.raises(calendar.UnknownSlot, match="nope"):
            await calendar.run(session, FRIDAY, "nope")
        assert issubclass(calendar.UnknownSlot, calendar.SlotError)
        assert opened == []

    async def test_a_day_the_slot_does_not_fall_on_is_refused(
        self, session, slots, opened
    ):
        with pytest.raises(calendar.SlotError, match="2026-09-03"):
            await calendar.run(session, date(2026, 9, 3), "linkedin_post")
        assert opened == []

    async def test_a_built_slot_is_refused(self, session, slots, opened):
        await _filled(session, FRIDAY, "linkedin_post")
        with pytest.raises(calendar.SlotError, match="already built"):
            await calendar.run(session, FRIDAY, "linkedin_post")
        assert opened == []

    async def test_a_skipped_slot_may_still_run(self, session, slots, opened):
        await _skipped(session, FRIDAY, "linkedin_post")
        await calendar.run(session, FRIDAY, "linkedin_post")
        assert len(opened) == 1

    async def test_the_runners_refusal_passes_through(
        self, session, slots, monkeypatch
    ):
        async def refuse(session, ask):
            raise runner.SkillError("Studio is off")

        monkeypatch.setattr(runner, "open_run", refuse)
        with pytest.raises(runner.SkillError, match="Studio is off"):
            await calendar.run(session, FRIDAY, "linkedin_post")
