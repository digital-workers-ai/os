from decimal import Decimal

import httpx
import pytest
import pytest_asyncio

from app.api import skills_api
from app.config import settings
from app.main import app
from app.models import Proposal, SkillRun
from app.skills import catalog

SKILL = """---
name: dw-post
description: One post, said once.
---

# Skill: Post

One LinkedIn post.

## Modes

**draft** is the daily run. **build** runs after approval. **chat** is MCP.

## Lessons

- Never lead with a statistic (#209, 2026-09-12).
"""


@pytest.fixture
def studio(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STUDIO_ENABLED", True)
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "media"))
    skills = tmp_path / "skills"
    (skills / "dw-post").mkdir(parents=True)
    (skills / "dw-post" / "SKILL.md").write_text(SKILL)
    monkeypatch.setattr(catalog, "SKILLS_DIR", skills)
    return skills


@pytest.fixture
def started(monkeypatch):
    calls = []

    async def record(seq, ask, **kwargs):
        calls.append((seq, ask))

    monkeypatch.setattr(skills_api.runner, "execute_detached", record)
    return calls


@pytest_asyncio.fixture
async def api(session, sessionmaker_for_test, monkeypatch, studio):
    monkeypatch.setattr(skills_api, "async_session", sessionmaker_for_test)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client


async def a_proposal(session, status, drafts=0, skill="dw-post"):
    row = Proposal(
        kind="post",
        title="A post",
        skill=skill,
        skill_sha="a" * 64,
        status=status,
    )
    session.add(row)
    await session.flush()
    for _ in range(drafts):
        session.add(
            SkillRun(
                skill=skill,
                skill_sha="a" * 64,
                mode="draft",
                caller="marketer",
                proposal_seq=row.seq,
                status="ok",
            )
        )
    await session.flush()
    return row


class TestTheSkillList:
    async def test_every_skill_is_listed_with_its_modes(self, api):
        body = (await api.get("/api/skills")).json()
        assert body["skills"] == [
            {
                "name": "dw-post",
                "description": "One post, said once.",
                "modes": ["draft", "build", "chat"],
                "runs": 0,
                "approval_rate": None,
                "median_edits": None,
                "cost_per_build": None,
                "proposed_lesson": None,
            }
        ]

    async def test_runs_approvals_and_edits_are_counted(self, api, session):
        await a_proposal(session, "built", drafts=3)
        await a_proposal(session, "approved", drafts=1)
        await a_proposal(session, "rejected", drafts=1)
        await session.commit()
        row = (await api.get("/api/skills")).json()["skills"][0]
        assert row["runs"] == 5
        assert row["approval_rate"] == 0.67
        assert row["median_edits"] == 1.0

    async def test_a_build_that_cost_nothing_reports_no_cost(self, api, session):
        session.add(
            SkillRun(
                skill="dw-post",
                skill_sha="a" * 64,
                mode="build",
                caller="studio",
                status="ok",
            )
        )
        await session.commit()
        assert (await api.get("/api/skills")).json()["skills"][0][
            "cost_per_build"
        ] is None

    async def test_a_build_that_cost_something_reports_the_average(self, api, session):
        for spend in (Decimal("0.20"), Decimal("0.40")):
            session.add(
                SkillRun(
                    skill="dw-post",
                    skill_sha="a" * 64,
                    mode="build",
                    caller="studio",
                    status="ok",
                    cost_usd=spend,
                )
            )
        await session.commit()
        assert (await api.get("/api/skills")).json()["skills"][0][
            "cost_per_build"
        ] == 0.3


class TestOneSkill:
    async def test_a_skill_carries_its_body_lessons_and_sha(self, api):
        body = (await api.get("/api/skills/dw-post")).json()
        assert body["body"].startswith("# Skill: Post")
        assert body["lessons"] == ["Never lead with a statistic (#209, 2026-09-12)."]
        assert body["sha"] == catalog.sha("dw-post")
        assert body["runs"] == 0

    async def test_a_skill_that_is_not_there_is_not_found(self, api):
        response = await api.get("/api/skills/dw-nothing")
        assert response.status_code == 404
        assert "no skill named" in response.json()["detail"]


class TestStartingARun:
    async def test_a_run_answers_with_its_seq_and_works_in_the_background(
        self, api, session, started
    ):
        response = await api.post(
            "/api/skills/dw-post/run",
            json={
                "mode": "draft",
                "input": "an idea",
                "look": "soda",
                "slot": "friday",
            },
        )
        assert response.status_code == 200
        seq = response.json()["skill_run"]
        row = await session.get(SkillRun, seq)
        assert (row.status, row.mode, row.caller) == ("running", "draft", "studio")
        assert started == [
            (
                seq,
                skills_api.runner.Ask(
                    skill="dw-post",
                    mode="draft",
                    caller="studio",
                    input="an idea",
                    look="soda",
                    slot="friday",
                ),
            )
        ]

    async def test_a_run_of_a_skill_that_is_not_there_is_not_found(self, api, started):
        response = await api.post(
            "/api/skills/dw-nothing/run", json={"mode": "draft", "input": "x"}
        )
        assert response.status_code == 404
        assert started == []

    async def test_a_mode_that_is_not_ours_is_refused(self, api, started):
        response = await api.post(
            "/api/skills/dw-post/run", json={"mode": "publish", "input": "x"}
        )
        assert response.status_code == 409
        assert "mode" in response.json()["detail"]
        assert started == []

    async def test_a_run_refuses_while_studio_is_off(self, api, monkeypatch, started):
        monkeypatch.setattr(settings, "STUDIO_ENABLED", False)
        response = await api.post(
            "/api/skills/dw-post/run", json={"mode": "draft", "input": "x"}
        )
        assert response.status_code == 409
        assert "STUDIO_ENABLED" in response.json()["detail"]
        assert started == []
