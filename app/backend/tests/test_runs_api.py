import httpx
import pytest
import pytest_asyncio

from app import media
from app.config import settings
from app.db import get_session
from app.main import app
from app.models import (
    AgentRun,
    Asset,
    AssetFile,
    AssetVersion,
    SkillRun,
    SkillRunToolCall,
)

SHA = "a" * 64
RUN_KEYS = {
    "seq",
    "skill",
    "skill_sha",
    "caller",
    "asset_seq",
    "version",
    "stage",
    "status",
    "error",
    "model",
    "tokens_in",
    "tokens_out",
    "duration_ms",
    "started_at",
    "finished_at",
}
AGENT_RUN_KEYS = {
    "seq",
    "agent",
    "trigger",
    "read_detail",
    "made",
    "duration_ms",
    "ok",
    "error",
    "created_at",
}
FILE_KEYS = {"path", "media_type", "bytes", "url", "text"}


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


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))


async def _stored(session, row):
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _run(session, skill="dw-post", **overrides):
    fields = {"skill": skill, "skill_sha": SHA, "caller": "chat", "status": "ok"}
    return await _stored(session, SkillRun(**{**fields, **overrides}))


async def _agent_run(session, **overrides):
    fields = {
        "agent": "marketer",
        "trigger": "daily",
        "read_detail": "4 slots, 2 empty",
        "ok": True,
    }
    return await _stored(session, AgentRun(**{**fields, **overrides}))


async def _asset(session):
    asset = await _stored(
        session,
        Asset(name="Three numbers", kind="post", skill="dw-post", origin="chat"),
    )
    await _stored(session, AssetVersion(asset_seq=asset.seq, version=1, note="v1"))
    return asset


async def _file(session, asset, version, path, data):
    written = media.write(asset.seq, version, path, data)
    return await _stored(
        session, AssetFile(asset_seq=asset.seq, version=version, **written)
    )


class TestSkillRuns:
    async def test_no_runs_is_an_empty_list(self, api):
        assert (await api.get("/api/skill-runs")).json() == {"runs": []}

    async def test_runs_come_newest_first_with_the_row_keys(self, api, session):
        first = await _run(session)
        second = await _run(session, skill="dw-image")
        body = (await api.get("/api/skill-runs")).json()
        assert [row["seq"] for row in body["runs"]] == [second.seq, first.seq]
        for row in body["runs"]:
            assert set(row) == RUN_KEYS

    async def test_the_skill_filter_the_limit_and_the_offset_narrow_the_list(
        self, api, session
    ):
        for _ in range(3):
            await _run(session)
        await _run(session, skill="dw-image")
        by_skill = (await api.get("/api/skill-runs?skill=dw-post")).json()["runs"]
        assert [row["seq"] for row in by_skill] == [3, 2, 1]
        page = await api.get("/api/skill-runs?skill=dw-post&limit=1&offset=1")
        assert [row["seq"] for row in page.json()["runs"]] == [2]

    @pytest.mark.parametrize("query", ["limit=0", "limit=501", f"offset={2**63}"])
    async def test_out_of_range_paging_is_refused(self, api, query):
        assert (await api.get(f"/api/skill-runs?{query}")).status_code == 422


class TestSkillRun:
    async def test_an_unknown_run_is_a_404(self, api):
        response = await api.get("/api/skill-runs/404")
        assert response.status_code == 404
        assert "404" in response.json()["detail"]

    async def test_the_detail_adds_the_tool_calls_and_the_files_of_its_version(
        self, api, session
    ):
        asset = await _asset(session)
        await _file(session, asset, 1, "post.md", "# One\n")
        await _stored(session, AssetVersion(asset_seq=asset.seq, version=2, note="v2"))
        await _file(session, asset, 2, "post.md", "# Two\n")
        await _file(session, asset, 2, "image.png", b"\x89PNG")
        run = await _run(session, asset_seq=asset.seq, version=2)
        calls = [
            SkillRunToolCall(
                skill_run_seq=run.seq,
                tool="brand_read",
                ok=True,
                duration_ms=12,
                detail="voice.md",
            ),
            SkillRunToolCall(skill_run_seq=run.seq, tool="image_paint", ok=False),
        ]
        session.add_all(calls)
        await session.flush()
        body = (await api.get(f"/api/skill-runs/{run.seq}")).json()
        assert set(body) == RUN_KEYS | {"tool_calls", "files"}
        assert body["seq"] == run.seq
        assert [call["id"] for call in body["tool_calls"]] == sorted(
            str(call.id) for call in calls
        )
        assert sorted(
            (call["tool"], call["ok"], call["duration_ms"], call["detail"])
            for call in body["tool_calls"]
        ) == [("brand_read", True, 12, "voice.md"), ("image_paint", False, 0, None)]
        assert [(f["path"], f["text"]) for f in body["files"]] == [
            ("image.png", None),
            ("post.md", "# Two\n"),
        ]
        for file in body["files"]:
            assert set(file) == FILE_KEYS

    async def test_a_run_without_an_asset_has_no_files(self, api, session):
        run = await _run(session)
        body = (await api.get(f"/api/skill-runs/{run.seq}")).json()
        assert (body["tool_calls"], body["files"]) == ([], [])


class TestAgentRuns:
    async def test_no_runs_is_an_empty_list(self, api):
        assert (await api.get("/api/agent-runs")).json() == {"runs": []}

    async def test_runs_come_newest_first_with_the_row_keys(self, api, session):
        first = await _agent_run(session)
        second = await _agent_run(session, trigger="manual", ok=False, error="down")
        body = (await api.get("/api/agent-runs")).json()
        assert [row["seq"] for row in body["runs"]] == [second.seq, first.seq]
        assert body["runs"][0]["error"] == "down"
        for row in body["runs"]:
            assert set(row) == AGENT_RUN_KEYS

    async def test_the_limit_and_the_offset_page_the_list(self, api, session):
        for _ in range(3):
            await _agent_run(session)
        page = (await api.get("/api/agent-runs?limit=1&offset=1")).json()
        assert [row["seq"] for row in page["runs"]] == [2]

    @pytest.mark.parametrize("query", ["limit=0", "limit=501", f"offset={2**63}"])
    async def test_out_of_range_paging_is_refused(self, api, query):
        assert (await api.get(f"/api/agent-runs?{query}")).status_code == 422
