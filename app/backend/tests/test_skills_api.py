import hashlib

import httpx
import pytest
import pytest_asyncio
import yaml

from app.db import get_session
from app.main import app
from app.models import Asset, AssetVersion, SkillRun
from app.skills import catalog, runner

SHA = "a" * 64
BODY = (
    "# Skill: Post\n\n## Steps\n\n1. Read the brand.\n\n"
    "## Lessons\n\n- Shorter.\n- Fewer numbers.\n"
)
NO_LESSONS = "# Skill: Image\n\n## Lessons\n"
ROW_KEYS = {
    "seq",
    "name",
    "kind",
    "skill",
    "look",
    "ratio",
    "origin",
    "slot_date",
    "slot_name",
    "status",
    "version",
    "preview",
    "created_at",
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
def skills(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "SKILLS_DIR", tmp_path)

    def write(name, makes, body=BODY):
        front = {"name": name, "description": f"Make one {makes}", "makes": makes}
        text = f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n{body}"
        (tmp_path / name).mkdir()
        (tmp_path / name / "SKILL.md").write_text(text)
        return text

    return write


async def _stored(session, row):
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _run(session, skill, caller="chat"):
    return await _stored(
        session, SkillRun(skill=skill, skill_sha=SHA, caller=caller, status="ok")
    )


@pytest.fixture
def runner_fakes(monkeypatch):
    asks, detached = [], []

    async def fake_open_run(session, ask):
        asks.append(ask)
        asset = await _stored(
            session,
            Asset(
                name=ask.input.splitlines()[0],
                kind=catalog.load(ask.skill).makes,
                skill=ask.skill,
                look=ask.look,
                ratio=ask.ratio,
                origin=ask.caller,
            ),
        )
        await _stored(
            session, AssetVersion(asset_seq=asset.seq, version=1, note=ask.input)
        )
        run = await _stored(
            session,
            SkillRun(
                skill=ask.skill,
                skill_sha=SHA,
                caller=ask.caller,
                asset_seq=asset.seq,
                version=1,
                status="running",
            ),
        )
        return runner.Started(skill_run=run.seq, asset_seq=asset.seq, version=1)

    async def fake_execute_detached(seq, ask):
        detached.append((seq, ask))

    monkeypatch.setattr(runner, "open_run", fake_open_run)
    monkeypatch.setattr(runner, "execute_detached", fake_execute_detached)
    return asks, detached


class TestList:
    async def test_an_empty_catalog_is_no_skills(self, api, skills):
        assert (await api.get("/api/skills")).json() == {"skills": []}

    async def test_every_row_counts_its_runs_and_its_lessons(
        self, api, session, skills
    ):
        skills("dw-linkedin-post", "post")
        skills("dw-image", "image", body=NO_LESSONS)
        await _run(session, "dw-linkedin-post")
        await _run(session, "dw-linkedin-post", caller="mcp")
        await _run(session, "dw-gone")
        assert (await api.get("/api/skills")).json() == {
            "skills": [
                {
                    "name": "dw-image",
                    "description": "Make one image",
                    "makes": "image",
                    "runs": 0,
                    "lessons": 0,
                },
                {
                    "name": "dw-linkedin-post",
                    "description": "Make one post",
                    "makes": "post",
                    "runs": 2,
                    "lessons": 2,
                },
            ]
        }

    async def test_the_runs_are_counted_in_one_query(
        self, api, session, skills, count_queries
    ):
        skills("dw-linkedin-post", "post")
        skills("dw-image", "image", body=NO_LESSONS)
        await _run(session, "dw-linkedin-post")
        with count_queries() as counter:
            body = (await api.get("/api/skills")).json()
        assert [row["runs"] for row in body["skills"]] == [0, 1]
        assert counter.total == 1


class TestDetail:
    async def test_the_detail_adds_the_body_the_lessons_and_the_sha(
        self, api, session, skills
    ):
        text = skills("dw-linkedin-post", "post")
        await _run(session, "dw-linkedin-post")
        await _run(session, "dw-image")
        assert (await api.get("/api/skills/dw-linkedin-post")).json() == {
            "name": "dw-linkedin-post",
            "description": "Make one post",
            "makes": "post",
            "runs": 1,
            "body": BODY,
            "lessons": ["Shorter.", "Fewer numbers."],
            "sha": hashlib.sha256(text.encode()).hexdigest(),
        }

    async def test_an_unknown_skill_is_a_404(self, api, skills):
        response = await api.get("/api/skills/dw-nope")
        assert response.status_code == 404
        assert "dw-nope" in response.json()["detail"]


class TestRun:
    async def test_a_run_opens_for_chat_and_executes_after_the_reply(
        self, api, skills, runner_fakes, sessionmaker_for_test
    ):
        skills("dw-linkedin-post", "post")
        asks, detached = runner_fakes
        response = await api.post(
            "/api/skills/dw-linkedin-post/run",
            json={"input": "Why churn fell\nand what changed", "look": "stat-card"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"skill_run", "asset"}
        assert set(body["asset"]) == ROW_KEYS
        assert body["asset"]["name"] == "Why churn fell"
        assert body["asset"]["seq"] == body["skill_run"]["asset_seq"]
        assert (body["asset"]["status"], body["asset"]["version"]) == ("running", 1)
        assert body["skill_run"]["status"] == "running"
        [ask] = asks
        assert (ask.skill, ask.caller, ask.input) == (
            "dw-linkedin-post",
            "chat",
            "Why churn fell\nand what changed",
        )
        assert (ask.look, ask.ratio, ask.asset_seq) == ("stat-card", None, None)
        assert detached == [(body["skill_run"]["seq"], ask)]
        async with sessionmaker_for_test() as fresh:
            assert await fresh.get(SkillRun, body["skill_run"]["seq"]) is not None

    async def test_the_ratio_travels_with_the_ask(self, api, skills, runner_fakes):
        skills("dw-image", "image", body=NO_LESSONS)
        response = await api.post(
            "/api/skills/dw-image/run", json={"input": "A chart", "ratio": "4:5"}
        )
        assert response.status_code == 200
        assert runner_fakes[0][0].ratio == "4:5"

    async def test_an_unknown_skill_is_a_404_and_opens_nothing(
        self, api, skills, runner_fakes
    ):
        response = await api.post("/api/skills/dw-nope/run", json={"input": "x"})
        assert response.status_code == 404
        assert "dw-nope" in response.json()["detail"]
        assert runner_fakes == ([], [])

    async def test_a_refusal_from_the_runner_is_a_409_with_its_message(
        self, api, skills, runner_fakes, monkeypatch
    ):
        skills("dw-linkedin-post", "post")

        async def refuse(session, ask):
            raise runner.SkillError("Studio is off")

        monkeypatch.setattr(runner, "open_run", refuse)
        response = await api.post(
            "/api/skills/dw-linkedin-post/run", json={"input": "x"}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Studio is off"
        assert runner_fakes[1] == []

    async def test_a_body_without_input_is_a_422(self, api, skills, runner_fakes):
        skills("dw-linkedin-post", "post")
        response = await api.post("/api/skills/dw-linkedin-post/run", json={})
        assert response.status_code == 422
        assert runner_fakes == ([], [])
