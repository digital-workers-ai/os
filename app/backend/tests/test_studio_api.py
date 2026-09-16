import sys
import types
from datetime import UTC, date, datetime

import httpx
import pytest
import pytest_asyncio
import yaml
from sqlalchemy import select

from app import llm
from app.db import get_session
from app.engine import calendar as declared
from app.engine import looks
from app.main import app
from app.models import (
    AgentRun,
    Asset,
    AssetVersion,
    SkillRun,
    SlotSkip,
    StudioThread,
    StudioTurn,
)
from app.skills import catalog, runner
from app.studio import chat

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
SHA = "a" * 64
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
        "days": ["tue", "fri"],
        "time": "06:00",
        "look": "stat-card",
        "ratio": "1:1",
        "theme": "One thing a spreadsheet cannot do.",
    },
}
STAT = {
    "name": "stat-card",
    "medium": "image",
    "ratios": ["1:1", "4:5"],
    "slots": [{"name": "stat", "max": 6}],
}
POST = chat.Choice(
    skill="dw-post",
    look="stat-card",
    ratio="1:1",
    ask="A post on MRR",
    reply="Making a post on MRR.",
)
NONE = chat.Choice(skill="none", ask="hello", reply="Nothing to make here.")
SLOT_KEYS = {
    "date",
    "time",
    "name",
    "kind",
    "skill",
    "look",
    "ratio",
    "theme",
    "state",
    "asset_seq",
}


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def defs(tmp_path, monkeypatch):
    path = tmp_path / "calendar.yaml"
    path.write_text(yaml.safe_dump({"slots": SLOTS}, sort_keys=False))
    monkeypatch.setattr(declared, "DEFAULT_CALENDAR", path)
    skills = tmp_path / "skills"
    (skills / "dw-post").mkdir(parents=True)
    (skills / "dw-post" / "SKILL.md").write_text(
        "---\nname: dw-post\ndescription: Make one post.\nmakes: post\n---\n"
        "# Skill\n\n## Lessons\n"
    )
    root = tmp_path / "looks"
    (root / "stat-card").mkdir(parents=True)
    (root / "stat-card" / "look.yaml").write_text(yaml.safe_dump(STAT))
    monkeypatch.setattr(catalog, "SKILLS_DIR", skills)
    monkeypatch.setattr(looks, "DEFAULT_LOOKS", root)


@pytest.fixture
def fake_runner(monkeypatch):
    seen = {"asks": [], "executed": []}

    async def open_run(session, ask):
        seen["asks"].append(ask)
        asset = Asset(
            name=ask.input,
            kind="post",
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

    async def execute_detached(seq, ask):
        seen["executed"].append((seq, ask))

    monkeypatch.setattr(runner, "open_run", open_run)
    monkeypatch.setattr(runner, "execute_detached", execute_detached)
    return seen


@pytest.fixture
def studio_off(monkeypatch):
    async def refuse(session, ask):
        raise runner.SkillError("Studio is off")

    monkeypatch.setattr(runner, "open_run", refuse)


@pytest.fixture
def routed(monkeypatch):
    def choose(choice):
        async def parse(**kwargs):
            return choice, "claude-actual"

        monkeypatch.setattr(llm, "parse", parse)

    return choose


@pytest.fixture
def marketer(monkeypatch):
    calls = []

    async def fill(session, days, trigger):
        calls.append((days, trigger))
        run = AgentRun(
            agent="marketer",
            trigger=trigger,
            read_detail=f"{days} days",
            ok=True,
            created_at=NOW,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        return run

    module = types.ModuleType("app.agents.marketer")
    module.fill = fill
    package = types.ModuleType("app.agents")
    package.marketer = module
    monkeypatch.setitem(sys.modules, "app.agents", package)
    monkeypatch.setitem(sys.modules, "app.agents.marketer", module)
    return calls


async def _fresh_rows(sessionmaker_for_test, model):
    async with sessionmaker_for_test() as fresh:
        return (await fresh.execute(select(model))).scalars().all()


class TestCalendar:
    async def test_expands_the_range_with_its_cadence(self, api, defs):
        response = await api.get("/api/studio/calendar?from=2026-09-01&to=2026-09-07")
        body = response.json()
        assert (body["from"], body["to"]) == ("2026-09-01", "2026-09-07")
        assert [slot["date"] for slot in body["slots"]] == [
            "2026-09-01",
            "2026-09-04",
            "2026-09-07",
        ]
        assert set(body["slots"][0]) == SLOT_KEYS
        assert body["cadence"] == [
            {"kind": "post", "done": 0, "planned": 2},
            {"kind": "newsletter", "done": 0, "planned": 1},
        ]

    async def test_to_is_capped_a_year_past_from(self, api, defs):
        response = await api.get("/api/studio/calendar?from=2026-01-01&to=2030-01-01")
        assert response.json()["to"] == "2027-01-02"

    async def test_a_year_at_the_end_of_time_does_not_overflow(self, api, defs):
        response = await api.get("/api/studio/calendar?from=9999-12-01&to=9999-12-31")
        assert response.status_code == 200
        assert response.json()["to"] == "9999-12-31"

    @pytest.mark.parametrize(
        "query", ["", "from=2026-09-01", "to=2026-09-01", "from=x&to=2026-09-01"]
    )
    async def test_both_dates_are_required(self, api, defs, query):
        assert (await api.get(f"/api/studio/calendar?{query}")).status_code == 422


class TestFill:
    async def test_runs_the_marketer_by_hand_and_returns_its_run(
        self, api, marketer, sessionmaker_for_test
    ):
        response = await api.post("/api/studio/calendar/fill", json={"days": 7})
        assert response.status_code == 200
        body = response.json()["agent_run"]
        assert body["trigger"] == "manual"
        assert body["read_detail"] == "7 days"
        assert marketer == [(7, "manual")]
        assert len(await _fresh_rows(sessionmaker_for_test, AgentRun)) == 1

    async def test_days_default_to_fourteen(self, api, marketer):
        await api.post("/api/studio/calendar/fill", json={})
        assert marketer == [(14, "manual")]

    @pytest.mark.parametrize("days", [0, 91, "seven", None])
    async def test_days_are_one_to_ninety(self, api, marketer, days):
        response = await api.post("/api/studio/calendar/fill", json={"days": days})
        assert response.status_code == 422
        assert marketer == []


class TestSkip:
    async def test_skips_a_slot_and_commits(self, api, defs, sessionmaker_for_test):
        response = await api.post("/api/studio/slots/2026-09-04/linkedin_post/skip")
        assert response.json() == {"ok": True}
        [row] = await _fresh_rows(sessionmaker_for_test, SlotSkip)
        assert (row.slot_date, row.slot_name) == (date(2026, 9, 4), "linkedin_post")

    async def test_an_unknown_slot_is_a_404(self, api, defs):
        response = await api.post("/api/studio/slots/2026-09-04/nope/skip")
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    async def test_a_day_that_is_not_a_date_is_a_422(self, api, defs):
        response = await api.post("/api/studio/slots/friday/linkedin_post/skip")
        assert response.status_code == 422


class TestRunSlot:
    async def test_opens_the_run_answers_and_executes_behind(
        self, api, defs, fake_runner, sessionmaker_for_test
    ):
        response = await api.post("/api/studio/slots/2026-09-04/linkedin_post/run")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"skill_run", "asset"}
        assert body["skill_run"]["status"] == "running"
        assert body["asset"]["slot_name"] == "linkedin_post"
        assert body["asset"]["slot_date"] == "2026-09-04"
        assert (body["asset"]["status"], body["asset"]["version"]) == ("running", 1)
        assert body["asset"]["preview"] is None
        [ask] = fake_runner["asks"]
        assert fake_runner["executed"] == [(body["skill_run"]["seq"], ask)]
        assert len(await _fresh_rows(sessionmaker_for_test, SkillRun)) == 1

    async def test_an_unknown_slot_is_a_404(self, api, defs, fake_runner):
        response = await api.post("/api/studio/slots/2026-09-04/nope/run")
        assert response.status_code == 404
        assert fake_runner["executed"] == []

    async def test_a_wrong_day_is_a_409(self, api, defs, fake_runner):
        response = await api.post("/api/studio/slots/2026-09-03/linkedin_post/run")
        assert response.status_code == 409
        assert "2026-09-03" in response.json()["detail"]

    async def test_a_built_slot_is_a_409(self, api, defs, fake_runner):
        await api.post("/api/studio/slots/2026-09-04/linkedin_post/run")
        response = await api.post("/api/studio/slots/2026-09-04/linkedin_post/run")
        assert response.status_code == 409
        assert len(fake_runner["executed"]) == 1

    async def test_studio_off_is_a_409_with_the_runners_words(
        self, api, defs, studio_off
    ):
        response = await api.post("/api/studio/slots/2026-09-04/linkedin_post/run")
        assert response.status_code == 409
        assert response.json()["detail"] == "Studio is off"


class TestCanvas:
    async def test_lists_nodes_in_the_range_and_kind(self, api, session):
        for kind in ("post", "blog"):
            session.add(
                Asset(
                    name=kind,
                    kind=kind,
                    skill=f"dw-{kind}",
                    origin="chat",
                    created_at=NOW,
                )
            )
        await session.flush()
        body = (await api.get("/api/studio/canvas")).json()
        assert [node["kind"] for node in body["nodes"]] == ["blog", "post"]
        narrowed = await api.get(
            "/api/studio/canvas?from=2026-09-04&to=2026-09-04&kind=blog"
        )
        assert [node["kind"] for node in narrowed.json()["nodes"]] == ["blog"]
        empty = await api.get("/api/studio/canvas?to=2026-09-03")
        assert empty.json() == {"nodes": []}


class TestThreads:
    async def test_creates_lists_and_reads_a_thread(self, api, sessionmaker_for_test):
        created = (await api.post("/api/studio/threads")).json()["thread"]
        assert set(created) == {"seq", "title", "created_at"}
        assert created["title"] == "New thread"
        assert len(await _fresh_rows(sessionmaker_for_test, StudioThread)) == 1
        listed = (await api.get("/api/studio/threads")).json()
        assert listed == {"threads": [created]}
        read = (await api.get(f"/api/studio/threads/{created['seq']}")).json()
        assert read == {"seq": created["seq"], "title": "New thread", "turns": []}

    async def test_a_missing_thread_is_a_404(self, api):
        assert (await api.get("/api/studio/threads/9")).status_code == 404
        response = await api.post("/api/studio/threads/9", json={"text": "hi"})
        assert response.status_code == 404


class TestTurn:
    async def test_a_skill_turn_answers_with_the_run_and_executes_behind(
        self, api, defs, routed, fake_runner, sessionmaker_for_test
    ):
        routed(POST)
        seq = (await api.post("/api/studio/threads")).json()["thread"]["seq"]
        response = await api.post(
            f"/api/studio/threads/{seq}", json={"text": "Post about MRR"}
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"turn", "reply", "skill_run", "asset"}
        assert (body["turn"]["role"], body["turn"]["text"]) == (
            "person",
            "Post about MRR",
        )
        assert body["reply"]["text"] == "Making a post on MRR."
        assert body["reply"]["skill_run"] == body["skill_run"]
        assert body["skill_run"]["status"] == "running"
        assert body["asset"]["name"] == "A post on MRR"
        assert body["asset"]["status"] == "running"
        [ask] = fake_runner["asks"]
        assert fake_runner["executed"] == [(body["skill_run"]["seq"], ask)]
        assert len(await _fresh_rows(sessionmaker_for_test, StudioTurn)) == 2
        [thread] = await _fresh_rows(sessionmaker_for_test, StudioThread)
        assert thread.title == "Post about MRR"

    async def test_a_none_turn_answers_without_a_run(
        self, api, defs, routed, fake_runner
    ):
        routed(NONE)
        seq = (await api.post("/api/studio/threads")).json()["thread"]["seq"]
        body = (
            await api.post(f"/api/studio/threads/{seq}", json={"text": "hello"})
        ).json()
        assert (body["skill_run"], body["asset"]) == (None, None)
        assert body["reply"]["text"] == "Nothing to make here."
        assert fake_runner["executed"] == []

    async def test_studio_off_answers_with_the_refusal_and_no_run(
        self, api, defs, routed, studio_off
    ):
        routed(POST)
        seq = (await api.post("/api/studio/threads")).json()["thread"]["seq"]
        body = (
            await api.post(f"/api/studio/threads/{seq}", json={"text": "Post"})
        ).json()
        assert (body["skill_run"], body["asset"]) == (None, None)
        assert body["reply"]["text"] == "Studio is off"

    @pytest.mark.parametrize("body", [{}, {"text": ""}, {"text": "   \n"}, {"text": 3}])
    async def test_blank_text_is_a_422(self, api, defs, routed, fake_runner, body):
        routed(POST)
        seq = (await api.post("/api/studio/threads")).json()["thread"]["seq"]
        response = await api.post(f"/api/studio/threads/{seq}", json=body)
        assert response.status_code == 422
        assert fake_runner["asks"] == []
