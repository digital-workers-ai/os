import json
from datetime import UTC, datetime

import pytest

from app.studio import canvas
from tests.test_studio_factories import (
    NOW,
    asset,
    asset_file,
    draft,
    evidence,
    media_at,
    proposal,
    skill_run,
)

EARLIER = datetime(2026, 8, 20, 9, tzinfo=UTC)


@pytest.fixture
def media_dir(monkeypatch, tmp_path):
    return media_at(monkeypatch, tmp_path)


async def test_the_drafts_of_a_proposal_are_nodes_in_its_own_group(session, media_dir):
    made = await proposal(session, slot_name="linkedin_post")
    await draft(session, made.seq, path="post.md")
    board = await canvas.graph(session)
    assert board["nodes"] == [
        {
            "id": f"draft:{made.seq}:post.md",
            "group": f"#{made.seq} linkedin_post",
            "date": "2026-09-04",
            "kind": "document",
            "skill": "dw-post",
            "label": "post.md",
            "media_type": "text/markdown",
            "url": f"/api/studio/proposals/{made.seq}/drafts/post.md",
            "asset_seq": None,
            "proposal_seq": made.seq,
        }
    ]
    assert board["frames"] == []


async def test_a_proposal_with_no_slot_is_grouped_by_what_it_makes(session, media_dir):
    made = await proposal(session, kind="ad")
    await draft(session, made.seq)
    board = await canvas.graph(session)
    assert board["nodes"][0]["group"] == f"#{made.seq} ad"


async def test_the_files_of_an_asset_join_the_group_of_its_proposal(session, media_dir):
    made = await proposal(session, slot_name="linkedin_post")
    built = await asset(session, proposal_seq=made.seq)
    await asset_file(session, built.seq, path="post.md")
    board = await canvas.graph(session)
    assert board["nodes"][0] == {
        "id": f"file:{built.seq}:1:post.md",
        "group": f"#{made.seq} linkedin_post",
        "date": "2026-09-04",
        "kind": "document",
        "skill": None,
        "label": "post.md",
        "media_type": "text/markdown",
        "url": f"/api/assets/{built.seq}/files/post.md",
        "asset_seq": built.seq,
        "proposal_seq": made.seq,
    }


async def test_an_asset_from_a_chat_is_grouped_by_the_skill_that_ran(
    session, media_dir
):
    built = await asset(session, origin="chat", kind="image")
    await asset_file(session, built.seq, path="hero.png", media_type="image/png")
    await skill_run(
        session, skill="dw-image", mode="chat", caller="mcp", asset_seq=built.seq
    )
    board = await canvas.graph(session)
    assert board["nodes"][0]["group"] == "chat · dw-image"
    assert board["nodes"][0]["kind"] == "image"


async def test_an_asset_nothing_ran_is_grouped_by_the_chat_that_asked(
    session, media_dir
):
    built = await asset(session, origin="chat")
    await asset_file(session, built.seq)
    board = await canvas.graph(session)
    assert board["nodes"][0]["group"] == "chat"


async def test_the_media_type_decides_what_a_node_is(session, media_dir):
    built = await asset(session)
    await asset_file(session, built.seq, path="a.mp4", media_type="video/mp4")
    await asset_file(session, built.seq, path="b.html", media_type="text/html")
    await asset_file(session, built.seq, path="c.png", media_type="image/png")
    await asset_file(session, built.seq, path="d.md", media_type="text/markdown")
    board = await canvas.graph(session)
    assert {n["label"]: n["kind"] for n in board["nodes"]} == {
        "a.mp4": "video",
        "b.html": "html",
        "c.png": "image",
        "d.md": "document",
    }


async def test_the_swipe_item_a_remix_came_from_is_a_node_ahead_of_the_draft(
    session, media_dir
):
    made = await proposal(session, kind="ad", slot_name="counter_ad")
    await evidence(
        session, made.seq, kind="competitor_ad", ref="swipe/8821", detail="the hook"
    )
    await draft(session, made.seq, path="ad.md")
    board = await canvas.graph(session)
    ancestor = f"ancestor:#{made.seq} counter_ad:swipe/8821"
    assert [n["id"] for n in board["nodes"]] == [
        ancestor,
        f"draft:{made.seq}:ad.md",
    ]
    assert board["nodes"][0] == {
        "id": ancestor,
        "group": f"#{made.seq} counter_ad",
        "date": "2026-09-04",
        "kind": "ancestor",
        "skill": "dw-post",
        "label": "swipe/8821",
        "media_type": "",
        "url": None,
        "asset_seq": None,
        "proposal_seq": made.seq,
    }
    assert board["edges"] == [
        {"from": ancestor, "to": f"draft:{made.seq}:ad.md", "rel": "ancestor"}
    ]


async def test_an_asset_remixed_in_a_chat_keeps_its_ancestor(session, media_dir):
    built = await asset(session, origin="chat", ancestor_ref="swipe/8821")
    await asset_file(session, built.seq, path="ad.mp4", media_type="video/mp4")
    board = await canvas.graph(session)
    assert [n["kind"] for n in board["nodes"]] == ["ancestor", "video"]
    assert board["edges"] == [
        {
            "from": "ancestor:chat:swipe/8821",
            "to": f"file:{built.seq}:1:ad.mp4",
            "rel": "ancestor",
        }
    ]


async def test_a_draft_edges_to_the_asset_it_was_built_into(session, media_dir):
    made = await proposal(session, status="built", slot_name="linkedin_post")
    built = await asset(session, proposal_seq=made.seq)
    await draft(session, made.seq, path="post.md")
    await asset_file(session, built.seq, path="post.md")
    board = await canvas.graph(session)
    assert board["edges"] == [
        {
            "from": f"draft:{made.seq}:post.md",
            "to": f"file:{built.seq}:1:post.md",
            "rel": "draft",
        }
    ]


async def test_each_rebuild_edges_from_the_version_before_it(session, media_dir):
    built = await asset(session)
    await asset_file(session, built.seq, version=1, path="v1.md")
    await asset_file(session, built.seq, version=2, path="v2.md", note="shorter")
    board = await canvas.graph(session)
    assert board["edges"] == [
        {
            "from": f"file:{built.seq}:1:v1.md",
            "to": f"file:{built.seq}:2:v2.md",
            "rel": "build",
        }
    ]


async def test_only_what_falls_in_the_range_is_on_the_board(session, media_dir):
    old = await proposal(session, created_at=EARLIER)
    await draft(session, old.seq, path="old.md")
    new = await proposal(session)
    await draft(session, new.seq, path="new.md")
    board = await canvas.graph(session, frm="2026-09-01", to="2026-09-30")
    assert [n["label"] for n in board["nodes"]] == ["new.md"]
    assert [n["label"] for n in (await canvas.graph(session))["nodes"]] == [
        "old.md",
        "new.md",
    ]


async def test_the_board_narrows_by_node_kind_and_by_skill(session, media_dir):
    made = await proposal(session, skill="dw-post")
    await draft(session, made.seq, path="a.md")
    await draft(session, made.seq, path="b.png", media_type="image/png")
    other = await proposal(session, skill="dw-video")
    await draft(session, other.seq, path="c.md")
    assert [
        n["label"] for n in (await canvas.graph(session, kind="image"))["nodes"]
    ] == ["b.png"]
    assert [
        n["label"] for n in (await canvas.graph(session, skill="dw-video"))["nodes"]
    ] == ["c.md"]


async def test_an_edge_with_an_end_off_the_board_is_dropped(session, media_dir):
    made = await proposal(session, status="built")
    built = await asset(session, proposal_seq=made.seq)
    await draft(session, made.seq, path="post.md")
    await asset_file(session, built.seq, path="post.png", media_type="image/png")
    board = await canvas.graph(session, kind="image")
    assert [n["label"] for n in board["nodes"]] == ["post.png"]
    assert board["edges"] == []


async def test_an_empty_board_is_empty(session, media_dir):
    assert await canvas.graph(session) == {
        "nodes": [],
        "edges": [],
        "frames": [],
        "layout": {},
    }


async def test_the_saved_layout_and_frames_come_back_with_the_board(session, media_dir):
    frames = [{"id": "frame:1", "label": "Q4 launch", "nodes": ["draft:1"]}]
    canvas.save_layout({"draft:1": {"x": 4, "y": 8}}, frames)
    board = await canvas.graph(session)
    assert (board["layout"], board["frames"]) == ({"draft:1": {"x": 4, "y": 8}}, frames)


@pytest.mark.parametrize("written", ["not json", "[1, 2]"])
async def test_a_layout_the_store_cannot_read_is_no_layout(session, media_dir, written):
    (media_dir / "studio").mkdir(parents=True)
    (media_dir / "studio" / canvas.LAYOUT).write_text(written)
    board = await canvas.graph(session)
    assert (board["layout"], board["frames"]) == ({}, [])


async def test_saving_a_layout_writes_it_and_the_frames_to_the_store(media_dir):
    frames = [{"id": "frame:1", "label": "Q4 launch", "nodes": ["draft:1"]}]
    canvas.save_layout({"draft:1": {"x": 4, "y": 8}}, frames)
    assert json.loads((media_dir / "studio" / canvas.LAYOUT).read_text()) == {
        "layout": {"draft:1": {"x": 4, "y": 8}},
        "frames": frames,
    }


async def test_a_layout_written_is_read_back(media_dir):
    canvas.save_layout({"draft:1": {"x": 4, "y": 8}}, [])
    assert canvas.saved() == ({"draft:1": {"x": 4, "y": 8}}, [])


async def test_the_dates_a_node_carries_are_its_own(session, media_dir):
    built = await asset(session, created_at=EARLIER)
    await asset_file(session, built.seq, created_at=NOW)
    board = await canvas.graph(session)
    assert board["nodes"][0]["date"] == "2026-09-04"
