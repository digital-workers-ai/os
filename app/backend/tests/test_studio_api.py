from datetime import date

import httpx
import pytest
import pytest_asyncio

from app.api import studio_api
from app.db import get_session
from app.main import app
from app.skills import runner
from tests.test_studio_factories import (
    NOW,
    agent_run,
    asset,
    claim,
    draft,
    evidence,
    fake_marketer,
    media_at,
    proposal,
    skill_run,
    slot_skip,
    store_file,
    studio_on,
    sync_run,
    tool_call,
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


async def test_today_answers_with_the_day_and_what_is_ready(api, session):
    await agent_run(session)
    made = await proposal(session)
    await asset(session, proposal_seq=made.seq)
    await skill_run(session, status="running", stage="render", proposal_seq=made.seq)
    body = (await api.get("/api/studio/today")).json()
    assert body["today"] == "2026-09-04"
    assert body["readiness"] == {
        "brand": True,
        "competitors": True,
        "calendar": True,
        "estate": False,
    }
    assert body["last_run"]["agent"] == "marketer"
    assert [row["seq"] for row in body["open"]] == [made.seq]
    assert [row["stage"] for row in body["building"]] == ["render"]
    assert [row["kind"] for row in body["built_today"]] == ["post"]
    assert body["skill_proposals"] == []
    assert [slot["name"] for slot in body["week"]]


async def test_today_notices_what_a_reactive_proposal_answered(api, session):
    made = await proposal(session, kind="ad", reactive=True, title="counter to vidora")
    body = (await api.get("/api/studio/today")).json()
    assert body["noticed"] == [{"text": "counter to vidora", "proposal_seq": made.seq}]


async def test_today_on_an_empty_estate_has_nothing_to_show(api, session):
    body = (await api.get("/api/studio/today")).json()
    assert (body["last_run"], body["open"], body["noticed"]) == (None, [], [])
    assert body["built_today"] == []


async def test_the_estate_is_ready_once_a_sync_has_landed_rows(api, session):
    await sync_run(session, "stripe", rows_written=4)
    body = (await api.get("/api/studio/today")).json()
    assert body["readiness"]["estate"] is True


async def test_the_calendar_answers_slots_and_their_cadence(api, session):
    await proposal(
        session, slot_date=date(2026, 9, 8), slot_name="linkedin_post", status="built"
    )
    body = (await api.get("/api/studio/calendar?from=2026-09-07&to=2026-09-13")).json()
    assert (body["from"], body["to"]) == ("2026-09-07", "2026-09-13")
    assert {slot["name"] for slot in body["slots"]} >= {"linkedin_post"}
    assert {entry["kind"] for entry in body["cadence"]} >= {"post"}


async def test_the_calendar_covers_at_most_a_year(api):
    body = (await api.get("/api/studio/calendar?from=2026-01-01&to=2030-01-01")).json()
    assert body["to"] == "2027-01-02"


async def test_filling_the_calendar_asks_the_marketer(api, monkeypatch):
    marketer = fake_marketer(monkeypatch)
    answer = await api.post("/api/studio/calendar/fill", json={"days": 14})
    assert answer.json() == {"agent_run": 9}
    assert marketer.calls == [14]


async def test_a_slot_can_be_skipped_twice_and_stays_skipped(api, session):
    for _ in range(2):
        answer = await api.post("/api/studio/slots/2026-09-08/linkedin_post/skip")
        assert answer.json() == {"ok": True}
    body = (await api.get("/api/studio/calendar?from=2026-09-07&to=2026-09-13")).json()
    assert [s["state"] for s in body["slots"] if s["date"] == "2026-09-08"] == [
        "skipped"
    ]


async def test_the_proposal_queue_answers_rows_and_counts(api, session):
    made = await proposal(session)
    await evidence(session, made.seq)
    await claim(session, made.seq)
    body = (await api.get("/api/studio/proposals?status=open&kind=post")).json()
    assert [row["seq"] for row in body["proposals"]] == [made.seq]
    assert body["counts"]["open"] == 1
    assert (await api.get("/api/studio/proposals?slot=linkedin_post")).json()[
        "proposals"
    ] == []


async def test_a_proposal_answers_its_drafts_and_evidence(api, session):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"Sales has one Acme")
    await draft(session, made.seq, path="post.md", size=18)
    body = (await api.get(f"/api/studio/proposals/{made.seq}")).json()
    assert body["drafts"][0]["text"] == "Sales has one Acme"
    assert (
        body["drafts"][0]["url"] == f"/api/studio/proposals/{made.seq}/drafts/post.md"
    )


async def test_a_proposal_nobody_opened_is_not_found(api):
    assert (await api.get("/api/studio/proposals/404")).status_code == 404


async def test_the_bytes_of_a_draft_come_back_as_the_file(api, session):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"Sales has one Acme")
    await draft(session, made.seq, path="post.md")
    answer = await api.get(f"/api/studio/proposals/{made.seq}/drafts/post.md")
    assert answer.content == b"Sales has one Acme"
    assert answer.headers["content-type"].startswith("text/markdown")


async def test_a_draft_the_proposal_never_wrote_is_not_found(api, session):
    made = await proposal(session)
    assert (
        await api.get(f"/api/studio/proposals/{made.seq}/drafts/post.md")
    ).status_code == 404


async def test_a_draft_path_that_climbs_out_is_refused(api, session):
    made = await proposal(session)
    answer = await api.get(f"/api/studio/proposals/{made.seq}/drafts/%2E%2E/secret.md")
    assert answer.status_code == 409


async def test_editing_a_draft_answers_the_proposal_again(api, session):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"old")
    await draft(session, made.seq, path="post.md", size=3)
    answer = await api.put(
        f"/api/studio/proposals/{made.seq}/draft",
        json={"path": "post.md", "text": "a longer line"},
    )
    assert answer.json()["drafts"][0]["text"] == "a longer line"


async def test_editing_a_draft_of_nothing_is_not_found(api):
    answer = await api.put(
        "/api/studio/proposals/404/draft", json={"path": "post.md", "text": "x"}
    )
    assert answer.status_code == 404


async def test_approving_answers_the_run_it_started(api, session):
    made = await proposal(session)
    answer = await api.post(f"/api/studio/proposals/{made.seq}/approve")
    assert answer.json()["skill_run"] > 0
    assert api.started[0][1].mode == "build"


async def test_approving_only_some_variants_says_which(api, session):
    made = await proposal(session, kind="image")
    await api.post(
        f"/api/studio/proposals/{made.seq}/approve", json={"variants": ["v1.png"]}
    )
    assert "v1.png" in api.started[0][1].input


async def test_approving_nothing_is_not_found(api):
    assert (await api.post("/api/studio/proposals/404/approve")).status_code == 404


async def test_approving_twice_is_refused(api, session):
    made = await proposal(session, status="approved")
    assert (
        await api.post(f"/api/studio/proposals/{made.seq}/approve")
    ).status_code == 409


async def test_rejecting_answers_the_proposal_with_its_reason(api, session):
    made = await proposal(session)
    answer = await api.post(
        f"/api/studio/proposals/{made.seq}/reject", json={"reason": "off voice"}
    )
    assert answer.json()["reason"] == "off voice"
    assert (
        await api.post("/api/studio/proposals/404/reject", json={"reason": "x"})
    ).status_code == 404
    assert (
        await api.post(f"/api/studio/proposals/{made.seq}/reject", json={"reason": "x"})
    ).status_code == 409


async def test_a_redo_answers_the_draft_run_it_started(api, session):
    made = await proposal(session)
    answer = await api.post(
        f"/api/studio/proposals/{made.seq}/redo", json={"note": "shorter hook"}
    )
    assert answer.json()["skill_run"] > 0
    assert api.started[0][1].input == "shorter hook"


async def test_a_redo_of_nothing_is_not_found(api, session):
    assert (
        await api.post("/api/studio/proposals/404/redo", json={"note": "x"})
    ).status_code == 404
    made = await proposal(session, status="built")
    assert (
        await api.post(f"/api/studio/proposals/{made.seq}/redo", json={"note": "x"})
    ).status_code == 409


async def test_the_canvas_answers_nodes_edges_frames_and_a_layout(api, session):
    made = await proposal(session)
    await draft(session, made.seq, path="post.md")
    body = (await api.get("/api/studio/canvas?from=2026-09-01&to=2026-09-30")).json()
    assert [node["label"] for node in body["nodes"]] == ["post.md"]
    assert (body["edges"], body["frames"], body["layout"]) == ([], [], {})
    assert (await api.get("/api/studio/canvas?kind=video")).json()["nodes"] == []


async def test_a_saved_layout_comes_back_on_the_next_board(api, session):
    made = await proposal(session)
    await draft(session, made.seq, path="post.md")
    frames = [{"id": "frame:1", "label": "Q4", "nodes": [f"draft:{made.seq}:post.md"]}]
    answer = await api.put(
        "/api/studio/canvas/layout",
        json={
            "layout": {f"draft:{made.seq}:post.md": {"x": 4, "y": 8}},
            "frames": frames,
        },
    )
    assert answer.json() == {"ok": True}
    body = (await api.get("/api/studio/canvas")).json()
    assert body["layout"] == {f"draft:{made.seq}:post.md": {"x": 4.0, "y": 8.0}}
    assert body["frames"] == frames


async def test_a_layout_of_more_than_a_board_is_refused(api):
    layout = {
        f"node:{n}": {"x": 0, "y": 0} for n in range(studio_api.MAX_LAYOUT_NODES + 1)
    }
    answer = await api.put("/api/studio/canvas/layout", json={"layout": layout})
    assert answer.status_code == 422


async def test_too_many_frames_are_refused(api):
    frames = [
        {"id": f"f{n}", "label": "x", "nodes": []}
        for n in range(studio_api.MAX_FRAMES + 1)
    ]
    answer = await api.put(
        "/api/studio/canvas/layout", json={"layout": {}, "frames": frames}
    )
    assert answer.status_code == 422


async def test_the_studio_sources_name_the_competitor_connectors(api, session):
    await sync_run(session, "meta_ad_library", ok=False, detail="rate-limited")
    body = (await api.get("/api/studio/sources")).json()
    watched = {row["source"]: row for row in body["competitor_sources"]}
    assert watched["meta_ad_library"]["ok"] is False
    assert watched["meta_ad_library"]["error"] == "rate-limited"
    assert watched["meta_ad_library"]["detail"]
    assert body["estate_sources"] > 0


async def test_a_connector_that_never_ran_reports_no_sync(api):
    body = (await api.get("/api/studio/sources")).json()
    watched = {row["source"]: row for row in body["competitor_sources"]}
    assert watched["meta_ad_library"]["last_sync"] is None
    assert watched["meta_ad_library"]["error"] is None


async def test_the_brand_files_answer_with_what_read_them(api, session):
    run = await skill_run(session, skill="dw-post")
    await tool_call(session, run.seq, tool="brand.read", detail="voice")
    await tool_call(session, run.seq, tool="brand.read", detail="voice")
    await tool_call(session, run.seq, tool="looks.read", detail="aios")
    body = (await api.get("/api/brand")).json()
    voice = next(row for row in body["files"] if row["name"] == "voice")
    assert (voice["title"], voice["reads"], voice["used_by"]) == (
        "Voice",
        2,
        ["dw-post"],
    )
    assert voice["pending_pr"] is False
    assert voice["updated"]


async def test_a_brand_file_answers_its_body(api):
    body = (await api.get("/api/brand/voice")).json()
    assert body["name"] == "voice"
    assert body["body"].strip()
    assert (await api.get("/api/brand/nothing")).status_code == 404


async def test_the_skill_runs_answer_newest_first(api, session):
    first = await skill_run(session, skill="dw-post", mode="draft")
    second = await skill_run(session, skill="dw-video", mode="build")
    body = (await api.get("/api/skill-runs")).json()
    assert [row["seq"] for row in body["runs"]] == [second.seq, first.seq]
    narrowed = (await api.get("/api/skill-runs?skill=dw-video&mode=build")).json()
    assert [row["seq"] for row in narrowed["runs"]] == [second.seq]
    assert narrowed["runs"][0]["tokens_in"] == 0


async def test_a_skill_run_answers_its_stage_tools_and_files(api, session):
    made = await proposal(session)
    await draft(session, made.seq, path="post.md")
    run = await skill_run(
        session, status="running", stage="render", proposal_seq=made.seq
    )
    await tool_call(session, run.seq, tool="image.render", ok=False, detail="down")
    body = (await api.get(f"/api/skill-runs/{run.seq}")).json()
    assert body["stages"] == [{"name": "render", "state": "running", "detail": None}]
    assert body["tool_calls"] == [
        {"tool": "image.render", "ok": False, "duration_ms": 3, "detail": "down"}
    ]
    assert [file["path"] for file in body["files"]] == ["post.md"]
    assert body["skill_sha"] == "a3f9"


async def test_a_skill_run_that_built_an_asset_answers_its_files(api, session):
    built = await asset(session)
    run = await skill_run(session, mode="build", asset_seq=built.seq, stage="done")
    body = (await api.get(f"/api/skill-runs/{run.seq}")).json()
    assert body["files"] == []
    assert body["stages"][0]["state"] == "done"


async def test_a_skill_run_with_no_work_behind_it_answers_no_files(api, session):
    run = await skill_run(session, mode="chat", caller="mcp")
    body = (await api.get(f"/api/skill-runs/{run.seq}")).json()
    assert (body["files"], body["stages"]) == ([], [])
    assert (await api.get("/api/skill-runs/404")).status_code == 404


async def test_the_agent_runs_answer_newest_first(api, session):
    first = await agent_run(session)
    second = await agent_run(session, agent="taste", trigger="nightly")
    body = (await api.get("/api/agent-runs?limit=1")).json()
    assert [row["seq"] for row in body["runs"]] == [second.seq]
    one = (await api.get(f"/api/agent-runs/{first.seq}")).json()
    assert one["read_detail"] == "four brand files, nine ads"
    assert one["created_at"] == NOW.isoformat()
    assert (await api.get("/api/agent-runs/404")).status_code == 404


async def test_a_skipped_slot_is_recorded_once_for_that_day(api, session):
    await slot_skip(session, date(2026, 9, 11), "linkedin_post")
    body = (await api.get("/api/studio/calendar?from=2026-09-07&to=2026-09-13")).json()
    assert [s["state"] for s in body["slots"] if s["date"] == "2026-09-11"] == [
        "skipped"
    ]


@pytest.mark.parametrize(
    "path",
    [
        "/api/studio/proposals?limit=0",
        "/api/studio/calendar?from=nonsense&to=2026-09-13",
        "/api/skill-runs?limit=9999",
    ],
)
async def test_an_argument_nobody_meant_is_refused_rather_than_broken(api, path):
    assert (await api.get(path)).status_code == 422
