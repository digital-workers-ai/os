from datetime import date

import pytest
from sqlalchemy import select

from app.models import SkillRun
from app.studio import errors, files, proposals, runs
from tests.test_studio_factories import (
    NOW,
    asset,
    claim,
    draft,
    evidence,
    media_at,
    proposal,
    skill_run,
    store_file,
    studio_on,
)


@pytest.fixture
def media_dir(monkeypatch, tmp_path):
    return media_at(monkeypatch, tmp_path)


@pytest.fixture
def studio(monkeypatch):
    studio_on(monkeypatch)


async def test_a_listing_reports_one_row_for_each_proposal(session):
    made = await proposal(session, kind="ad", title="counter to vidora", reactive=True)
    page = await proposals.listing(session)
    assert page["proposals"] == [
        {
            "seq": made.seq,
            "kind": "ad",
            "title": "counter to vidora",
            "slot_date": None,
            "slot_name": None,
            "reactive": True,
            "skill": "dw-post",
            "skill_sha": "a3f9",
            "status": "open",
            "created_at": NOW.isoformat(),
            "claims_verified": 0,
            "claims_total": 0,
            "evidence_summary": "",
        }
    ]


async def test_the_newest_proposal_comes_first(session):
    first = await proposal(session)
    second = await proposal(session)
    page = await proposals.listing(session)
    assert [r["seq"] for r in page["proposals"]] == [second.seq, first.seq]


async def test_claims_are_counted_verified_against_total(session):
    made = await proposal(session)
    await claim(session, made.seq, verified=True)
    await claim(session, made.seq, text="setup took an hour", verified=False)
    row = (await proposals.listing(session))["proposals"][0]
    assert (row["claims_verified"], row["claims_total"]) == (1, 2)


async def test_evidence_read_twice_is_summarised_once_with_its_count(session):
    made = await proposal(session)
    await evidence(session, made.seq, ref="brand/proof.md")
    await evidence(session, made.seq, ref="brand/proof.md", detail="the number")
    await evidence(session, made.seq, ref="brand/voice.md")
    page = await proposals.listing(session)
    assert (
        page["proposals"][0]["evidence_summary"] == "brand/proof.md ×2 · brand/voice.md"
    )


async def test_a_listing_counts_every_status_whatever_is_asked_for(session):
    await proposal(session, status="open")
    await proposal(session, status="built")
    await proposal(session, status="built")
    page = await proposals.listing(session, status="open")
    assert page["counts"] == {"open": 1, "approved": 0, "rejected": 0, "built": 2}
    assert [r["status"] for r in page["proposals"]] == ["open"]


async def test_a_listing_filters_by_kind_and_by_slot(session):
    await proposal(session, kind="post", slot_name="linkedin_post")
    wanted = await proposal(session, kind="video", slot_name="video_monthly")
    page = await proposals.listing(session, kind="video")
    assert [r["seq"] for r in page["proposals"]] == [wanted.seq]
    by_slot = await proposals.listing(session, slot="video_monthly")
    assert [r["seq"] for r in by_slot["proposals"]] == [wanted.seq]
    assert by_slot["counts"] == {"open": 1, "approved": 0, "rejected": 0, "built": 0}


async def test_a_listing_pages(session):
    older = await proposal(session)
    newer = await proposal(session)
    page = await proposals.listing(session, limit=1)
    assert [r["seq"] for r in page["proposals"]] == [newer.seq]
    later = await proposals.listing(session, limit=1, offset=1)
    assert [r["seq"] for r in later["proposals"]] == [older.seq]


async def test_a_detail_carries_the_drafts_evidence_and_claims(session, media_dir):
    made = await proposal(
        session,
        slot_date=date(2026, 9, 8),
        slot_name="linkedin_post",
        note="shorter hook",
    )
    store_file("proposals", made.seq, 1, "post.md", b"Sales has one Acme")
    await draft(session, made.seq, path="post.md", size=18)
    await evidence(
        session, made.seq, kind="brand", ref="brand/voice.md", detail="the voice"
    )
    await claim(session, made.seq, source_ref="brand/proof.md")
    found = await proposals.detail(session, made.seq)
    assert found["drafts"] == [
        {
            "path": "post.md",
            "media_type": "text/markdown",
            "bytes": 18,
            "text": "Sales has one Acme",
            "url": f"/api/studio/proposals/{made.seq}/drafts/post.md",
        }
    ]
    assert found["evidence"] == [
        {"kind": "brand", "ref": "brand/voice.md", "detail": "the voice"}
    ]
    assert found["claims"] == [
        {
            "text": "27 tools",
            "source_kind": "proof",
            "source_ref": "brand/proof.md",
            "verified": True,
        }
    ]
    assert found["read"] == ["brand: brand/voice.md"]
    assert found["note"] == "shorter hook"
    assert found["decided_at"] is None


async def test_a_detail_reads_the_look_and_theme_off_the_slot(session):
    made = await proposal(
        session, kind="video", slot_date=date(2026, 9, 1), slot_name="video_monthly"
    )
    found = await proposals.detail(session, made.seq)
    assert (found["look"], found["theme"]) == ("aios", "brand")


async def test_a_detail_of_a_slotless_proposal_names_no_look(session):
    made = await proposal(session, slot_name="nothing_declared")
    found = await proposals.detail(session, made.seq)
    assert (found["look"], found["theme"]) == (None, None)


async def test_a_detail_names_the_swipe_item_it_was_remixed_from(session):
    made = await proposal(session, kind="ad")
    await evidence(
        session, made.seq, kind="competitor_ad", ref="swipe/8821", detail="the hook"
    )
    found = await proposals.detail(session, made.seq)
    assert found["ancestor_ref"] == "swipe/8821"


async def test_a_detail_of_an_original_has_no_ancestor(session):
    made = await proposal(session)
    assert (await proposals.detail(session, made.seq))["ancestor_ref"] is None


async def test_a_detail_names_the_run_the_asset_and_what_the_build_spent(session):
    made = await proposal(session, status="built")
    built = await asset(session, proposal_seq=made.seq)
    await skill_run(session, mode="draft", proposal_seq=made.seq, cost_usd=1)
    run = await skill_run(
        session,
        mode="build",
        proposal_seq=made.seq,
        asset_seq=built.seq,
        cost_usd="0.1200",
    )
    found = await proposals.detail(session, made.seq)
    assert (found["asset_seq"], found["skill_run_seq"]) == (built.seq, run.seq)
    assert found["build_cost"] == "$0.12"


async def test_a_detail_with_no_build_estimates_no_cost(session):
    made = await proposal(session)
    found = await proposals.detail(session, made.seq)
    assert (found["build_cost"], found["asset_seq"], found["skill_run_seq"]) == (
        None,
        None,
        None,
    )


async def test_a_detail_of_nothing_is_refused(session):
    with pytest.raises(errors.Missing):
        await proposals.detail(session, 404)


async def test_a_binary_draft_carries_no_text(session, media_dir):
    made = await proposal(session, kind="image")
    store_file("proposals", made.seq, 1, "v1.png", b"\x89PNG")
    await draft(session, made.seq, path="v1.png", media_type="image/png", size=4)
    assert (await proposals.detail(session, made.seq))["drafts"][0]["text"] is None


async def test_a_draft_the_store_has_lost_carries_no_text(session, media_dir):
    made = await proposal(session)
    await draft(session, made.seq)
    assert (await proposals.detail(session, made.seq))["drafts"][0]["text"] is None


async def test_a_draft_beyond_the_cap_is_left_to_its_own_route(session, media_dir):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"x")
    await draft(session, made.seq, path="post.md", size=files.TEXT_CAP + 1)
    found = await proposals.detail(session, made.seq)
    assert found["drafts"][0]["text"] is None
    assert found["drafts"][0]["url"].endswith("/drafts/post.md")


async def test_creating_a_proposal_records_its_evidence_claims_and_drafts(session):
    made = await proposals.create(
        session,
        kind="ad",
        title="counter to vidora",
        skill="dw-counter-ad",
        skill_sha="0c7a",
        slot_name="counter_ad",
        reactive=True,
        evidence=[{"kind": "competitor_ad", "ref": "swipe/8821", "detail": "the hook"}],
        claims=[
            {
                "text": "27 tools",
                "source_kind": "proof",
                "source_ref": None,
                "verified": False,
            }
        ],
        drafts=[{"path": "ad.md", "media_type": "text/markdown", "bytes": 4}],
    )
    found = await proposals.detail(session, made.seq)
    assert found["title"] == "counter to vidora"
    assert found["ancestor_ref"] == "swipe/8821"
    assert found["claims"][0]["verified"] is False
    assert [d["path"] for d in found["drafts"]] == ["ad.md"]


async def test_approving_opens_a_build_run(session, studio):
    made = await proposal(session, kind="image")
    started = await proposals.approve(session, made.seq, ["v1.png", "v3.png"])
    run = (await session.execute(select(SkillRun))).scalars().one()
    assert (run.seq, run.mode, run.caller, run.status) == (
        started.skill_run,
        "build",
        "studio",
        "running",
    )
    assert run.proposal_seq == made.seq
    assert started.ask.input == (
        "Build the draft a person approved, these variants only: v1.png, v3.png"
    )
    assert (made.status, made.decided_at) == ("approved", NOW)


async def test_approving_without_a_choice_builds_the_whole_draft(session, studio):
    made = await proposal(session)
    started = await proposals.approve(session, made.seq, [])
    assert started.ask.input == "Build the draft a person approved."


async def test_approving_nothing_is_refused(session, studio):
    with pytest.raises(errors.Missing):
        await proposals.approve(session, 404, [])


async def test_a_proposal_already_decided_cannot_be_approved_again(session, studio):
    made = await proposal(session, status="rejected")
    with pytest.raises(errors.Refused):
        await proposals.approve(session, made.seq, [])


async def test_a_proposal_naming_a_skill_nobody_wrote_cannot_be_built(session, studio):
    made = await proposal(session, skill="dw-nothing")
    with pytest.raises(errors.Refused):
        await proposals.approve(session, made.seq, [])


async def test_a_run_is_refused_while_studio_is_off(session, monkeypatch):
    monkeypatch.setattr("app.config.settings.STUDIO_ENABLED", False)
    made = await proposal(session)
    with pytest.raises(errors.Refused):
        await proposals.approve(session, made.seq, [])


async def test_the_digest_of_a_skill_nobody_wrote_is_refused():
    with pytest.raises(errors.Refused):
        runs.sha("dw-nothing")
    assert len(runs.sha("dw-post")) == 64


async def test_rejecting_records_the_reason_and_the_hour(session):
    made = await proposal(session)
    found = await proposals.reject(session, made.seq, "off voice")
    assert (found["status"], found["reason"], found["decided_at"]) == (
        "rejected",
        "off voice",
        NOW.isoformat(),
    )


async def test_rejecting_nothing_is_refused(session):
    with pytest.raises(errors.Missing):
        await proposals.reject(session, 404, "off voice")


async def test_a_decided_proposal_cannot_be_rejected_again(session):
    made = await proposal(session, status="built")
    with pytest.raises(errors.Refused):
        await proposals.reject(session, made.seq, "off voice")


async def test_a_redo_records_the_note_and_drafts_again(session, studio):
    made = await proposal(session)
    started = await proposals.redo(session, made.seq, "shorter hook")
    run = (await session.execute(select(SkillRun))).scalars().one()
    assert (run.mode, run.proposal_seq, started.skill_run) == (
        "draft",
        made.seq,
        run.seq,
    )
    assert started.ask.input == "shorter hook"
    assert (made.note, made.status) == ("shorter hook", "open")


async def test_a_redo_of_nothing_is_refused(session, studio):
    with pytest.raises(errors.Missing):
        await proposals.redo(session, 404, "shorter hook")


async def test_a_decided_proposal_cannot_be_redone(session, studio):
    made = await proposal(session, status="approved")
    with pytest.raises(errors.Refused):
        await proposals.redo(session, made.seq, "shorter hook")


async def test_editing_a_draft_rewrites_the_file_and_recounts_its_bytes(
    session, media_dir
):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"old")
    await draft(session, made.seq, path="post.md", size=3)
    found = await proposals.edit_draft(session, made.seq, "post.md", "a longer line")
    assert (media_dir / "proposals" / str(made.seq) / "1" / "post.md").read_text() == (
        "a longer line"
    )
    assert found["drafts"][0]["bytes"] == 13
    assert found["drafts"][0]["text"] == "a longer line"


async def test_editing_a_draft_of_nothing_is_refused(session, media_dir):
    with pytest.raises(errors.Missing):
        await proposals.edit_draft(session, 404, "post.md", "text")


async def test_editing_a_path_that_is_not_a_draft_is_refused(session, media_dir):
    made = await proposal(session)
    await draft(session, made.seq)
    with pytest.raises(errors.Missing):
        await proposals.edit_draft(session, made.seq, "elsewhere.md", "text")


async def test_the_bytes_of_a_draft_come_back_with_their_media_type(session, media_dir):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"Sales has one Acme")
    await draft(session, made.seq, path="post.md")
    assert await proposals.draft_bytes(session, made.seq, "post.md") == (
        b"Sales has one Acme",
        "text/markdown",
    )


async def test_the_bytes_of_a_draft_that_is_not_ours_are_refused(session, media_dir):
    made = await proposal(session)
    store_file("proposals", made.seq, 1, "post.md", b"x")
    with pytest.raises(errors.Missing):
        await proposals.draft_bytes(session, made.seq, "post.md")


async def test_the_bytes_of_a_draft_the_store_lost_are_refused(session, media_dir):
    made = await proposal(session)
    await draft(session, made.seq)
    with pytest.raises(errors.Missing):
        await proposals.draft_bytes(session, made.seq, "post.md")


@pytest.mark.parametrize("path", ["../secrets", "a/../../b", "/etc/passwd"])
async def test_a_path_that_climbs_out_of_the_store_is_refused(session, media_dir, path):
    made = await proposal(session)
    with pytest.raises(errors.Refused):
        await proposals.draft_bytes(session, made.seq, path)
