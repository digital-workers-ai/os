import httpx
import pytest
import pytest_asyncio

from app import media
from app.config import settings
from app.db import get_session
from app.main import app
from app.models import Asset, AssetFile, AssetVersion, SkillRun
from app.skills import runner

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
    return tmp_path


async def _stored(session, row):
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _asset(session, **overrides):
    fields = {
        "name": "Three numbers from the quarter",
        "kind": "post",
        "skill": "dw-post",
        "origin": "chat",
    }
    asset = await _stored(session, Asset(**{**fields, **overrides}))
    await _stored(session, AssetVersion(asset_seq=asset.seq, version=1, note="v1"))
    return asset


async def _file(session, asset, version, path, data):
    written = media.write(asset.seq, version, path, data)
    return await _stored(
        session, AssetFile(asset_seq=asset.seq, version=version, **written)
    )


@pytest.fixture
def runner_fakes(monkeypatch):
    asks, detached = [], []

    async def fake_open_run(session, ask):
        asks.append(ask)
        run = await _stored(
            session,
            SkillRun(
                skill=ask.skill,
                skill_sha=SHA,
                caller=ask.caller,
                asset_seq=ask.asset_seq,
                version=2,
                status="running",
            ),
        )
        return runner.Started(skill_run=run.seq, asset_seq=ask.asset_seq, version=2)

    async def fake_execute_detached(seq, ask):
        detached.append((seq, ask))

    monkeypatch.setattr(runner, "open_run", fake_open_run)
    monkeypatch.setattr(runner, "execute_detached", fake_execute_detached)
    return asks, detached


@pytest.fixture
def runner_refuses(monkeypatch, runner_fakes):
    async def refuse(session, ask):
        raise runner.SkillError("Studio is off")

    monkeypatch.setattr(runner, "open_run", refuse)
    return runner_fakes[1]


class TestList:
    async def test_an_empty_library_is_no_assets(self, api):
        assert (await api.get("/api/assets")).json() == {"assets": [], "total": 0}

    async def test_the_filters_reach_the_query(self, api, session):
        await _asset(session, name="Why churn fell", look="stat-card")
        await _asset(session, name="Churn chart", kind="image", look="stat-card")
        await _asset(session, name="Churn chart two", kind="image", origin="mcp")
        await _asset(
            session, name="Churn chart", kind="image", look="stat-card", origin="mcp"
        )
        response = await api.get(
            "/api/assets?kind=image&look=stat-card&origin=mcp&q=chart"
        )
        body = response.json()
        assert [row["name"] for row in body["assets"]] == ["Churn chart"]
        assert body["assets"][0]["seq"] == 4
        assert body["total"] == 1

    async def test_limit_and_offset_page_the_library(self, api, session):
        for n in range(3):
            await _asset(session, name=f"Asset {n}")
        body = (await api.get("/api/assets?limit=1&offset=1")).json()
        assert [row["name"] for row in body["assets"]] == ["Asset 1"]
        assert body["total"] == 3

    @pytest.mark.parametrize(
        "query", ["limit=0", "limit=501", "offset=-1", f"offset={2**63}"]
    )
    async def test_out_of_range_paging_is_refused(self, api, query):
        assert (await api.get(f"/api/assets?{query}")).status_code == 422

    async def test_the_largest_legal_offset_is_an_empty_page(self, api):
        response = await api.get(f"/api/assets?offset={2**63 - 1}")
        assert response.status_code == 200
        assert response.json()["assets"] == []


class TestDetail:
    async def test_an_unknown_asset_is_a_404(self, api):
        response = await api.get("/api/assets/404")
        assert response.status_code == 404
        assert "404" in response.json()["detail"]

    async def test_the_detail_is_served(self, api, session):
        asset = await _asset(session, feedback="Shorter")
        body = (await api.get(f"/api/assets/{asset.seq}")).json()
        assert body["seq"] == asset.seq
        assert [v["version"] for v in body["versions"]] == [1]
        assert body["feedback"] == "Shorter"
        assert body["skill_run_seq"] is None


class TestFiles:
    async def test_the_bytes_are_served_with_their_media_type(self, api, session):
        asset = await _asset(session)
        await _file(session, asset, 1, "slides/slide-01.png", b"\x89PNG")
        response = await api.get(
            f"/api/assets/{asset.seq}/versions/1/files/slides/slide-01.png"
        )
        assert response.status_code == 200
        assert response.content == b"\x89PNG"
        assert response.headers["content-type"] == "image/png"

    async def test_a_file_the_asset_does_not_have_is_a_404(self, api, session):
        asset = await _asset(session)
        response = await api.get(f"/api/assets/{asset.seq}/versions/1/files/post.md")
        assert response.status_code == 404
        assert "post.md" in response.json()["detail"]

    @pytest.mark.parametrize(
        "path", ["%2e%2e/%2e%2e/etc/passwd", "a/%2e%2e/b", "/etc/passwd"]
    )
    async def test_a_path_that_climbs_is_a_409(self, api, path):
        response = await api.get(f"/api/assets/1/versions/1/files/{path}")
        assert response.status_code == 409


class TestEdit:
    async def test_an_edit_opens_a_run_commits_it_and_executes_it_after_the_reply(
        self, api, session, runner_fakes, sessionmaker_for_test
    ):
        asks, detached = runner_fakes
        asset = await _asset(session, look="stat-card", ratio="1:1")
        response = await api.post(
            f"/api/assets/{asset.seq}/edit", json={"text": "Shorter"}
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"skill_run", "version"}
        assert body["version"] == 2
        assert set(body["skill_run"]) == RUN_KEYS
        assert body["skill_run"]["status"] == "running"
        assert body["skill_run"]["asset_seq"] == asset.seq
        assert [ask.input for ask in asks] == ["Shorter"]
        assert (asks[0].look, asks[0].ratio, asks[0].caller) == (
            "stat-card",
            "1:1",
            "chat",
        )
        assert detached == [(body["skill_run"]["seq"], asks[0])]
        async with sessionmaker_for_test() as fresh:
            assert await fresh.get(SkillRun, body["skill_run"]["seq"]) is not None

    async def test_an_unknown_asset_is_a_404(self, api, runner_fakes):
        response = await api.post("/api/assets/404/edit", json={"text": "Shorter"})
        assert response.status_code == 404
        assert runner_fakes[1] == []

    async def test_a_refusal_from_the_runner_is_a_409_with_its_message(
        self, api, session, runner_refuses
    ):
        asset = await _asset(session)
        response = await api.post(
            f"/api/assets/{asset.seq}/edit", json={"text": "Shorter"}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Studio is off"
        assert runner_refuses == []

    async def test_a_body_without_text_is_a_422(self, api, session, runner_fakes):
        asset = await _asset(session)
        response = await api.post(f"/api/assets/{asset.seq}/edit", json={})
        assert response.status_code == 422
        assert runner_fakes[0] == []


class TestResize:
    async def test_a_resize_opens_a_run_at_the_new_ratio(
        self, api, session, runner_fakes
    ):
        asks, detached = runner_fakes
        asset = await _asset(session, look="stat-card", ratio="1:1")
        response = await api.post(
            f"/api/assets/{asset.seq}/resize", json={"ratio": "9:16"}
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"skill_run", "version"}
        assert body["version"] == 2
        assert (asks[0].input, asks[0].ratio) == ("Remake this at 9:16", "9:16")
        assert detached == [(body["skill_run"]["seq"], asks[0])]

    async def test_an_unknown_asset_is_a_404(self, api, runner_fakes):
        response = await api.post("/api/assets/404/resize", json={"ratio": "9:16"})
        assert response.status_code == 404

    async def test_a_ratio_outside_the_frames_is_a_409(
        self, api, session, runner_fakes
    ):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        response = await api.post(
            f"/api/assets/{asset.seq}/resize", json={"ratio": "3:2"}
        )
        assert response.status_code == 409
        assert "3:2" in response.json()["detail"]
        assert runner_fakes[1] == []

    async def test_a_refusal_from_the_runner_is_a_409(
        self, api, session, runner_refuses
    ):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        response = await api.post(
            f"/api/assets/{asset.seq}/resize", json={"ratio": "9:16"}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Studio is off"

    async def test_a_body_without_a_ratio_is_a_422(self, api, session, runner_fakes):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        response = await api.post(f"/api/assets/{asset.seq}/resize", json={})
        assert response.status_code == 422


class TestFeedback:
    async def test_feedback_is_stored_and_the_detail_comes_back(
        self, api, session, sessionmaker_for_test
    ):
        asset = await _asset(session)
        response = await api.post(
            f"/api/assets/{asset.seq}/feedback", json={"text": "Shorter next time"}
        )
        assert response.status_code == 200
        body = response.json()
        assert body["feedback"] == "Shorter next time"
        assert [v["version"] for v in body["versions"]] == [1]
        async with sessionmaker_for_test() as fresh:
            stored = await fresh.get(Asset, asset.seq)
            assert stored.feedback == "Shorter next time"

    async def test_an_unknown_asset_is_a_404(self, api):
        response = await api.post("/api/assets/404/feedback", json={"text": "x"})
        assert response.status_code == 404

    async def test_a_body_without_text_is_a_422(self, api, session):
        asset = await _asset(session)
        response = await api.post(f"/api/assets/{asset.seq}/feedback", json={})
        assert response.status_code == 422
