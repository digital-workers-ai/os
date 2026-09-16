from datetime import UTC, date, datetime, timedelta

import pytest
import yaml

from app.engine import calendar as declared
from app.models import AgentRun, Asset, SkillRun
from app.studio import today

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
MIDNIGHT = datetime(2026, 9, 4, tzinfo=UTC)
SHA = "d" * 64
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
        "skill": "dw-post",
        "when": "weekly",
        "days": ["tue", "fri", "sun"],
        "time": "06:00",
        "theme": "One thing a spreadsheet cannot do.",
    },
}


@pytest.fixture
def slots(tmp_path, monkeypatch):
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump({"slots": SLOTS}, sort_keys=False))
    monkeypatch.setattr(declared, "DEFAULT_CALENDAR", path)


async def _asset(session, created_at, name="Made"):
    asset = Asset(
        name=name, kind="post", skill="dw-post", origin="chat", created_at=created_at
    )
    session.add(asset)
    await session.flush()
    return asset


async def _run(session, status):
    run = SkillRun(skill="dw-post", skill_sha=SHA, caller="chat", status=status)
    session.add(run)
    await session.flush()
    return run


async def _agent_run(session, detail):
    run = AgentRun(agent="marketer", trigger="daily", read_detail=detail, ok=True)
    session.add(run)
    await session.flush()
    return run


class TestToday:
    async def test_an_empty_studio_has_a_date_a_week_and_nothing_else(
        self, session, slots
    ):
        body = await today.today(session)
        assert body["today"] == "2026-09-04"
        assert body["last_run"] is None
        assert body["building"] == []
        assert body["built_today"] == []
        assert [(slot["date"], slot["name"]) for slot in body["week"]] == [
            ("2026-08-31", "newsletter_weekly"),
            ("2026-09-01", "linkedin_post"),
            ("2026-09-04", "linkedin_post"),
            ("2026-09-06", "linkedin_post"),
        ]

    async def test_last_run_is_the_newest_agent_run(self, session, slots):
        await _agent_run(session, "older")
        newest = await _agent_run(session, "newest")
        body = await today.today(session)
        assert body["last_run"]["seq"] == newest.seq
        assert body["last_run"]["read_detail"] == "newest"

    async def test_building_lists_running_runs_newest_first(self, session, slots):
        first = await _run(session, "running")
        await _run(session, "ok")
        second = await _run(session, "running")
        body = await today.today(session)
        assert [run["seq"] for run in body["building"]] == [second.seq, first.seq]
        assert body["building"][0]["status"] == "running"

    async def test_built_today_is_since_midnight_utc_newest_first(self, session, slots):
        await _asset(session, MIDNIGHT - timedelta(microseconds=1), "yesterday")
        first = await _asset(session, MIDNIGHT, "at midnight")
        second = await _asset(session, NOW, "just now")
        body = await today.today(session)
        assert [row["seq"] for row in body["built_today"]] == [second.seq, first.seq]
        assert body["built_today"][0]["name"] == "just now"
        assert body["built_today"][0]["status"] == "ok"

    async def test_the_week_runs_monday_to_sunday_of_the_pinned_day(
        self, session, slots
    ):
        dates = [slot["date"] for slot in (await today.today(session))["week"]]
        assert date.fromisoformat(min(dates)) >= date(2026, 8, 31)
        assert date.fromisoformat(max(dates)) <= date(2026, 9, 6)
        assert "2026-09-06" in dates
