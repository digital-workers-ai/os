import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app import main
from app.agents import marketer
from app.config import settings
from app.models import AgentRun
from tests.conftest import NOW

TODAY = NOW.date()
HOUR = 3600


class Stop(Exception):
    pass


def _slot(name="linkedin_post", state="empty", day=TODAY, **overrides):
    slot = {
        "date": day.isoformat(),
        "name": name,
        "kind": "post",
        "skill": "dw-post",
        "look": "stat-card",
        "ratio": "1:1",
        "theme": "One number from the quarter",
        "state": state,
        "asset_seq": None,
    }
    return {**slot, **overrides}


@pytest.fixture
def calendar(monkeypatch):
    found: list = []
    windows: list = []

    async def slots(session, frm, to):
        windows.append((frm, to))
        return list(found)

    monkeypatch.setattr(marketer.calendar, "slots", slots)
    return SimpleNamespace(found=found, windows=windows)


@pytest.fixture
def studio(monkeypatch):
    opened: list = []
    executed: list = []
    statuses: dict = {}
    refused: dict = {}
    crashes: dict = {}

    async def open_run(session, ask):
        if ask.slot_name in refused:
            raise marketer.runner.SkillError(refused[ask.slot_name])
        opened.append(ask)
        return SimpleNamespace(skill_run=len(opened), asset_seq=len(opened), version=1)

    async def execute(session, seq, ask):
        if ask.slot_name in crashes:
            raise crashes[ask.slot_name]
        executed.append((seq, ask.slot_name))
        return {"status": statuses.get(ask.slot_name, "ok")}

    monkeypatch.setattr(marketer.runner, "open_run", open_run)
    monkeypatch.setattr(marketer.runner, "execute", execute)
    return SimpleNamespace(
        opened=opened,
        executed=executed,
        statuses=statuses,
        refused=refused,
        crashes=crashes,
    )


async def _stored(session) -> list[AgentRun]:
    return (
        (await session.execute(select(AgentRun).order_by(AgentRun.seq))).scalars().all()
    )


class TestFill:
    async def test_no_slots_writes_a_run_that_made_nothing(
        self, session, calendar, studio
    ):
        run = await marketer.fill(session)
        assert (run.agent, run.trigger) == ("marketer", "manual")
        assert run.read_detail == "0 slots, 0 empty"
        assert (run.made, run.ok, run.error) == (0, True, None)
        assert run.duration_ms >= 0
        assert run.created_at == NOW
        assert calendar.windows == [(TODAY, TODAY + timedelta(days=14))]
        assert studio.opened == []
        [stored] = await _stored(session)
        assert stored.seq == run.seq

    async def test_the_window_and_the_trigger_are_the_callers(
        self, session, calendar, studio
    ):
        run = await marketer.fill(session, days=3, trigger="daily")
        assert run.trigger == "daily"
        assert calendar.windows == [(TODAY, TODAY + timedelta(days=3))]

    async def test_only_empty_slots_are_filled(self, session, calendar, studio):
        calendar.found += [
            _slot(),
            _slot("newsletter_weekly", "built", asset_seq=4, look=None, ratio=None),
            _slot("blog_fortnightly", "skipped", day=TODAY + timedelta(days=2)),
        ]
        run = await marketer.fill(session)
        [ask] = studio.opened
        assert (ask.skill, ask.caller) == ("dw-post", "marketer")
        assert ask.input == "One number from the quarter"
        assert (ask.look, ask.ratio) == ("stat-card", "1:1")
        assert (ask.slot_date, ask.slot_name) == (date(2026, 9, 4), "linkedin_post")
        assert studio.executed == [(1, "linkedin_post")]
        assert run.read_detail == "3 slots, 1 empty"
        assert (run.made, run.ok, run.error) == (1, True, None)

    async def test_a_refused_slot_is_recorded_and_the_rest_are_filled(
        self, session, calendar, studio
    ):
        calendar.found += [_slot(), _slot("newsletter_weekly", skill="dw-newsletter")]
        studio.refused["linkedin_post"] = "STUDIO_ENABLED is off"
        run = await marketer.fill(session)
        assert [ask.slot_name for ask in studio.opened] == ["newsletter_weekly"]
        assert studio.executed == [(1, "newsletter_weekly")]
        assert (run.made, run.ok) == (1, False)
        assert "2026-09-04 linkedin_post" in run.error
        assert "STUDIO_ENABLED is off" in run.error

    async def test_a_crashing_execute_marks_the_run_failed_and_stops(
        self, session, calendar, studio
    ):
        calendar.found += [
            _slot(),
            _slot("newsletter_weekly"),
            _slot("blog_fortnightly"),
        ]
        studio.crashes["newsletter_weekly"] = RuntimeError("the render is down")
        run = await marketer.fill(session)
        assert [ask.slot_name for ask in studio.opened] == [
            "linkedin_post",
            "newsletter_weekly",
        ]
        assert studio.executed == [(1, "linkedin_post")]
        assert (run.made, run.ok) == (1, False)
        assert run.error == "RuntimeError: the render is down"
        assert run.read_detail == "3 slots, 3 empty"
        [stored] = await _stored(session)
        assert stored.ok is False

    async def test_made_counts_the_runs_that_finished_ok_or_held(
        self, session, calendar, studio
    ):
        calendar.found += [
            _slot(),
            _slot("newsletter_weekly"),
            _slot("blog_fortnightly"),
        ]
        studio.statuses.update(
            {
                "linkedin_post": "ok",
                "newsletter_weekly": "held",
                "blog_fortnightly": "failed",
            }
        )
        run = await marketer.fill(session)
        assert len(studio.executed) == 3
        assert (run.made, run.ok, run.error) == (2, True, None)


class TestSecondsUntil:
    def test_before_the_hour_it_is_later_today(self):
        assert marketer.seconds_until(13, NOW) == HOUR

    def test_after_the_hour_it_is_tomorrow(self):
        assert marketer.seconds_until(6, NOW) == 18 * HOUR

    def test_on_the_hour_it_is_tomorrow(self):
        assert marketer.seconds_until(12, NOW) == 24 * HOUR

    def test_minutes_count(self):
        assert marketer.seconds_until(13, NOW + timedelta(minutes=45)) == 900


class TestDaily:
    @pytest.fixture
    def loop(self, monkeypatch, sessionmaker_for_test):
        sleeps: list = []
        fills: list = []

        async def sleep(seconds):
            sleeps.append(seconds)
            if len(sleeps) == 2:
                raise Stop()

        async def fill(session, days=marketer.WINDOW_DAYS, trigger="manual"):
            fills.append((session is not None, days, trigger))

        monkeypatch.setattr(settings, "MARKETER_HOUR", 6)
        monkeypatch.setattr(marketer, "sleep", sleep)
        monkeypatch.setattr(marketer, "fill", fill)
        monkeypatch.setattr(marketer, "async_session", sessionmaker_for_test)
        return SimpleNamespace(sleeps=sleeps, fills=fills)

    async def test_it_sleeps_to_the_hour_then_fills_then_sleeps_again(self, loop):
        with pytest.raises(Stop):
            await marketer.daily()
        assert loop.sleeps == [18 * HOUR, 18 * HOUR]
        assert loop.fills == [(True, marketer.WINDOW_DAYS, "daily")]

    async def test_a_fill_that_raises_does_not_end_the_loop(self, loop, monkeypatch):
        async def broken(session, days=marketer.WINDOW_DAYS, trigger="manual"):
            raise RuntimeError("the database went away")

        monkeypatch.setattr(marketer, "fill", broken)
        with pytest.raises(Stop):
            await marketer.daily()
        assert loop.sleeps == [18 * HOUR, 18 * HOUR]


class TestLifespan:
    @pytest.fixture
    def daily(self, monkeypatch):
        started = asyncio.Event()
        record: list = []

        async def run():
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                record.append("cancelled")
                raise

        monkeypatch.setattr(marketer, "daily", run)
        return SimpleNamespace(started=started, record=record)

    async def test_it_starts_the_task_when_on_and_cancels_it_on_shutdown(
        self, daily, monkeypatch
    ):
        monkeypatch.setattr(settings, "MARKETER_DAILY", True)
        async with main.lifespan(main.app):
            await asyncio.wait_for(daily.started.wait(), 5)
            assert daily.record == []
        assert daily.record == ["cancelled"]

    async def test_it_leaves_the_marketer_alone_when_off(self, daily, monkeypatch):
        monkeypatch.setattr(settings, "MARKETER_DAILY", False)
        async with main.lifespan(main.app):
            await asyncio.sleep(0)
        assert not daily.started.is_set()
        assert daily.record == []
