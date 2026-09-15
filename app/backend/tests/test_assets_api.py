import httpx
import pytest_asyncio

from app.db import get_session
from app.main import app
from app.skills import runner
from tests.test_studio_factories import (
    asset,
    asset_file,
    claim,
    evidence,
    media_at,
    proposal,
    skill_run,
    store_file,
    studio_on,
)


@pytest_asyncio.fixture
async def api(session, monkeypatch, tmp_path):
    started: list = []

    async def detached(seq, ask, **kwargs):
        started.append((seq, ask))

    async def override():
        yield session

    monkeypatch.setattr(runner, "execute_detached", detached)
    media_at(monkeypatch, tmp_path)
    studio_on(monkeypatch)
    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        client.started = started
        yield client
    app.dependency_overrides.clear()


async def test_the_library_answers_a_row_for_each_asset(api, session):
    made = await proposal(session)
    built = await asset(session, proposal_seq=made.seq, look="aios")
    await asset_file(session, built.seq, path="hero.png", media_type="image/png")
    await skill_run(session, mode="build", asset_seq=built.seq, skill="dw-image")
    body = (await api.get("/api/assets")).json()
    assert body["total"] == 1
    assert body["assets"] == [
        {
            "seq": built.seq,
            "name": "three-tools",
            "kind": "post",
            "skill": "dw-image",
            "look": "aios",
            "made_by": None,
            "origin": "proposal",
            "proposal_seq": made.seq,
            "status": "built",
            "created_at": "2026-09-04T12:00:00+00:00",
            "preview": f"/api/assets/{built.seq}/files/hero.png",
        }
    ]


async def test_an_asset_from_a_chat_names_the_tool_that_made_it(api, session):
    built = await asset(session, origin="chat", kind="image")
    await skill_run(
        session, mode="chat", caller="mcp", asset_seq=built.seq, skill="dw-counter-ad"
    )
    body = (await api.get("/api/assets")).json()
    assert body["assets"][0]["made_by"] == "dw.counter_ad"


async def test_an_asset_still_building_says_so(api, session):
    built = await asset(session)
    await skill_run(session, mode="build", asset_seq=built.seq, status="running")
    body = (await api.get("/api/assets")).json()
    assert body["assets"][0]["status"] == "building"
    assert body["assets"][0]["preview"] is None


async def test_the_library_narrows_by_kind_look_origin_skill_and_name(api, session):
    wanted = await asset(
        session, name="six-tools", kind="video", look="aios", origin="chat"
    )
    await skill_run(session, mode="chat", asset_seq=wanted.seq, skill="dw-video")
    await asset(session, name="three-tools", kind="post")
    for query in (
        "kind=video",
        "look=aios",
        "origin=chat",
        "q=six",
        "skill=dw-video",
    ):
        body = (await api.get(f"/api/assets?{query}")).json()
        assert [row["seq"] for row in body["assets"]] == [wanted.seq], query
        assert body["total"] == 1


async def test_the_library_pages(api, session):
    await asset(session)
    newer = await asset(session)
    body = (await api.get("/api/assets?limit=1")).json()
    assert [row["seq"] for row in body["assets"]] == [newer.seq]
    assert body["total"] == 2


async def test_an_asset_answers_its_versions_lineage_and_feedback(api, session):
    made = await proposal(session)
    await evidence(session, made.seq, kind="brand", ref="brand/voice.md")
    await claim(session, made.seq)
    built = await asset(session, proposal_seq=made.seq, ancestor_ref="swipe/8821")
    store_file("assets", built.seq, 1, "post.md", b"first")
    store_file("assets", built.seq, 2, "post.md", b"second")
    await asset_file(session, built.seq, version=1, path="post.md", size=5)
    await asset_file(
        session, built.seq, version=2, path="post.md", size=6, note="shorter"
    )
    run = await skill_run(session, mode="build", asset_seq=built.seq)
    body = (await api.get(f"/api/assets/{built.seq}")).json()
    assert [version["version"] for version in body["versions"]] == [2, 1]
    assert body["versions"][0]["note"] == "shorter"
    assert body["versions"][0]["files"][0]["text"] == "second"
    assert body["versions"][1]["files"][0]["text"] == "first"
    assert body["read"] == ["brand: brand/voice.md"]
    assert body["claims"][0]["text"] == "27 tools"
    assert (body["skill"], body["skill_run_seq"], body["feedback"]) == (
        "dw-post",
        run.seq,
        None,
    )
    assert body["ancestor_ref"] == "swipe/8821"


async def test_an_asset_nobody_built_is_not_found(api):
    assert (await api.get("/api/assets/404")).status_code == 404


async def test_the_bytes_of_an_asset_file_come_back_with_their_type(api, session):
    built = await asset(session)
    store_file("assets", built.seq, 1, "hero.png", b"\x89PNG")
    await asset_file(
        session, built.seq, path="hero.png", media_type="image/png", size=4
    )
    answer = await api.get(f"/api/assets/{built.seq}/files/hero.png")
    assert answer.content == b"\x89PNG"
    assert answer.headers["content-type"] == "image/png"


async def test_a_file_the_asset_never_held_is_not_found(api, session):
    built = await asset(session)
    assert (await api.get(f"/api/assets/{built.seq}/files/hero.png")).status_code == 404


async def test_a_file_the_store_lost_is_not_found(api, session):
    built = await asset(session)
    await asset_file(session, built.seq, path="hero.png", media_type="image/png")
    assert (await api.get(f"/api/assets/{built.seq}/files/hero.png")).status_code == 404


async def test_a_file_path_that_climbs_out_is_refused(api, session):
    built = await asset(session)
    answer = await api.get(f"/api/assets/{built.seq}/files/%2E%2E/secret.png")
    assert answer.status_code == 409


async def test_a_rebuild_starts_a_build_run_with_the_note(api, session):
    built = await asset(session)
    await skill_run(session, mode="build", asset_seq=built.seq, skill="dw-post")
    answer = await api.post(
        f"/api/assets/{built.seq}/rebuild", json={"note": "shorter first line"}
    )
    assert answer.json()["skill_run"] > 0
    assert api.started[0][1].input == "shorter first line"
    assert api.started[0][1].asset_seq == built.seq


async def test_a_rebuild_of_something_nothing_ever_built_is_refused(api, session):
    built = await asset(session)
    answer = await api.post(f"/api/assets/{built.seq}/rebuild", json={"note": "again"})
    assert answer.status_code == 409


async def test_a_rebuild_of_nothing_is_not_found(api):
    assert (
        await api.post("/api/assets/404/rebuild", json={"note": "x"})
    ).status_code == 404


async def test_feedback_is_kept_and_answered_with_the_asset(api, session):
    built = await asset(session)
    answer = await api.post(
        f"/api/assets/{built.seq}/feedback", json={"text": "good; the quote carried it"}
    )
    assert answer.json()["feedback"] == "good; the quote carried it"
    assert (await api.get(f"/api/assets/{built.seq}")).json()["feedback"] == (
        "good; the quote carried it"
    )


async def test_feedback_on_nothing_is_not_found(api):
    assert (
        await api.post("/api/assets/404/feedback", json={"text": "x"})
    ).status_code == 404
