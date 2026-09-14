from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.models import (
    AgentRun,
    Asset,
    AssetFile,
    Proposal,
    ProposalClaim,
    ProposalDraft,
    ProposalEvidence,
    SkillRun,
    SkillRunToolCall,
    SlotSkip,
)

SLOT = date(2026, 9, 5)


async def a_proposal(session, **overrides):
    proposal = Proposal(
        kind="post",
        title="Why the pipeline stalls",
        slot_date=SLOT,
        slot_name="friday_post",
        skill="dw-post",
        skill_sha="a3f9",
        **overrides,
    )
    session.add(proposal)
    await session.flush()
    return proposal


async def an_asset(session, **overrides):
    asset = Asset(
        name="Why the pipeline stalls",
        kind="video",
        look="studio",
        origin="proposal",
        **overrides,
    )
    session.add(asset)
    await session.flush()
    return asset


async def a_skill_run(session, **overrides):
    run = SkillRun(
        skill="dw-post",
        skill_sha="a3f9",
        mode="draft",
        caller="marketer",
        status="running",
        **overrides,
    )
    session.add(run)
    await session.flush()
    return run


async def rows(session, model, order):
    result = await session.execute(select(model).order_by(order))
    return result.scalars().all()


class TestAProposalKeepsWhatItWasBuiltFrom:
    async def test_a_fresh_proposal_is_open_unreactive_and_undecided(self, session):
        proposal = await a_proposal(session)
        await session.refresh(proposal)
        assert proposal.seq == 1
        assert proposal.status == "open"
        assert proposal.reactive is False
        assert (proposal.decided_at, proposal.reason, proposal.note) == (
            None,
            None,
            None,
        )
        assert (proposal.slot_date, proposal.slot_name) == (SLOT, "friday_post")

    async def test_a_reactive_proposal_needs_no_slot(self, session):
        proposal = await a_proposal(
            session, slot_date=None, slot_name=None, reactive=True
        )
        await session.refresh(proposal)
        assert (proposal.slot_date, proposal.slot_name, proposal.reactive) == (
            None,
            None,
            True,
        )

    async def test_a_proposal_reads_back_with_its_evidence_claims_and_drafts(
        self, session
    ):
        proposal = await a_proposal(session)
        session.add_all(
            [
                ProposalEvidence(
                    proposal_seq=proposal.seq,
                    kind="brand",
                    ref="brand/voice.md",
                    detail="the sentences it is allowed to write",
                ),
                ProposalEvidence(
                    proposal_seq=proposal.seq,
                    kind="competitor_ad",
                    ref="swipe/8821",
                    detail="the hook it is answering",
                ),
                ProposalClaim(
                    proposal_seq=proposal.seq,
                    text="Reporting takes four hours a week.",
                    source_kind="proof",
                    source_ref="brand/proof.md",
                    verified=True,
                ),
                ProposalClaim(
                    proposal_seq=proposal.seq,
                    text="Nobody opens the dashboard.",
                    source_kind="transcript",
                    source_ref=None,
                    verified=False,
                ),
                ProposalDraft(
                    proposal_seq=proposal.seq,
                    path="proposals/1/post.md",
                    media_type="text/markdown",
                    bytes=412,
                ),
            ]
        )
        await session.flush()
        evidence = await rows(session, ProposalEvidence, ProposalEvidence.id)
        assert [(row.kind, row.ref) for row in evidence] == [
            ("brand", "brand/voice.md"),
            ("competitor_ad", "swipe/8821"),
        ]
        claims = await rows(session, ProposalClaim, ProposalClaim.id)
        assert [(row.source_kind, row.source_ref, row.verified) for row in claims] == [
            ("proof", "brand/proof.md", True),
            ("transcript", None, False),
        ]
        draft = (await rows(session, ProposalDraft, ProposalDraft.id))[0]
        assert (draft.proposal_seq, draft.media_type, draft.bytes) == (
            proposal.seq,
            "text/markdown",
            412,
        )

    async def test_deleting_a_proposal_takes_its_evidence_claims_and_drafts(
        self, session
    ):
        proposal = await a_proposal(session)
        session.add_all(
            [
                ProposalEvidence(
                    proposal_seq=proposal.seq,
                    kind="asset",
                    ref="assets/4",
                    detail="the post it follows",
                ),
                ProposalClaim(
                    proposal_seq=proposal.seq,
                    text="Reporting takes four hours a week.",
                    source_kind="proof",
                    source_ref="brand/proof.md",
                    verified=True,
                ),
                ProposalDraft(
                    proposal_seq=proposal.seq,
                    path="proposals/1/post.md",
                    media_type="text/markdown",
                    bytes=412,
                ),
            ]
        )
        await session.flush()
        await session.execute(delete(Proposal).where(Proposal.seq == proposal.seq))
        await session.flush()
        assert await rows(session, ProposalEvidence, ProposalEvidence.id) == []
        assert await rows(session, ProposalClaim, ProposalClaim.id) == []
        assert await rows(session, ProposalDraft, ProposalDraft.id) == []


class TestAnAssetKeepsEveryVersionOfItsFiles:
    async def test_two_versions_of_one_path_live_side_by_side(self, session):
        asset = await an_asset(session)
        session.add_all(
            [
                AssetFile(
                    asset_seq=asset.seq,
                    version=1,
                    path="assets/1/out.mp4",
                    media_type="video/mp4",
                    bytes=1024,
                ),
                AssetFile(
                    asset_seq=asset.seq,
                    version=2,
                    path="assets/1/out.mp4",
                    media_type="video/mp4",
                    bytes=2048,
                    note="the hook was too slow",
                ),
            ]
        )
        await session.flush()
        files = await rows(session, AssetFile, AssetFile.version)
        assert [(row.version, row.bytes, row.note) for row in files] == [
            (1, 1024, None),
            (2, 2048, "the hook was too slow"),
        ]

    async def test_the_same_path_at_the_same_version_twice_is_refused(self, session):
        asset = await an_asset(session)
        session.add_all(
            [
                AssetFile(
                    asset_seq=asset.seq,
                    version=1,
                    path="assets/1/out.mp4",
                    media_type="video/mp4",
                    bytes=1024,
                ),
                AssetFile(
                    asset_seq=asset.seq,
                    version=1,
                    path="assets/1/out.mp4",
                    media_type="video/mp4",
                    bytes=1024,
                ),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()

    async def test_a_remix_records_the_swipe_item_it_descends_from(self, session):
        asset = await an_asset(session, origin="chat", ancestor_ref="swipe/8821")
        await session.refresh(asset)
        assert (asset.origin, asset.ancestor_ref, asset.proposal_seq) == (
            "chat",
            "swipe/8821",
            None,
        )

    async def test_deleting_an_asset_takes_its_files(self, session):
        asset = await an_asset(session)
        session.add(
            AssetFile(
                asset_seq=asset.seq,
                version=1,
                path="assets/1/out.mp4",
                media_type="video/mp4",
                bytes=1024,
            )
        )
        await session.flush()
        await session.execute(delete(Asset).where(Asset.seq == asset.seq))
        await session.flush()
        assert await rows(session, AssetFile, AssetFile.id) == []

    async def test_an_asset_outlives_the_proposal_that_proposed_it(self, session):
        proposal = await a_proposal(session)
        asset = await an_asset(session, proposal_seq=proposal.seq)
        await session.execute(delete(Proposal).where(Proposal.seq == proposal.seq))
        await session.flush()
        await session.refresh(asset)
        assert asset.proposal_seq is None


class TestASkillRunRecordsWhatItDid:
    async def test_a_started_run_has_no_cost_no_duration_and_no_finish(self, session):
        run = await a_skill_run(session)
        await session.refresh(run)
        assert (run.seq, run.status, run.duration_ms) == (1, "running", 0)
        assert run.cost_usd == Decimal("0")
        assert (run.finished_at, run.error, run.stage) == (None, None, None)
        assert (run.proposal_seq, run.asset_seq) == (None, None)

    async def test_a_run_lists_its_tool_calls_in_the_order_they_happened(self, session):
        run = await a_skill_run(session)
        for tool, ok in (
            ("brand.read", True),
            ("swipe.search", True),
            ("image.render", False),
        ):
            session.add(
                SkillRunToolCall(
                    skill_run_seq=run.seq, tool=tool, ok=ok, duration_ms=12
                )
            )
            await session.flush()
        calls = await rows(session, SkillRunToolCall, SkillRunToolCall.id)
        assert [(row.tool, row.ok) for row in calls] == [
            ("brand.read", True),
            ("swipe.search", True),
            ("image.render", False),
        ]
        assert [row.detail for row in calls] == [None, None, None]

    async def test_a_finished_run_keeps_its_cost_and_its_error(self, session):
        run = await a_skill_run(
            session,
            mode="build",
            caller="studio",
            status="failed",
            stage="render",
            error="RuntimeError: the renderer is down",
            duration_ms=8100,
            cost_usd=Decimal("1.2345"),
        )
        await session.refresh(run)
        assert run.cost_usd == Decimal("1.2345")
        assert (run.status, run.stage, run.duration_ms) == ("failed", "render", 8100)
        assert run.error == "RuntimeError: the renderer is down"

    async def test_deleting_a_run_takes_its_tool_calls(self, session):
        run = await a_skill_run(session)
        session.add(
            SkillRunToolCall(
                skill_run_seq=run.seq, tool="brand.read", ok=True, duration_ms=12
            )
        )
        await session.flush()
        await session.execute(delete(SkillRun).where(SkillRun.seq == run.seq))
        await session.flush()
        assert await rows(session, SkillRunToolCall, SkillRunToolCall.id) == []


class TestAnAgentRunRecordsWhatItRead:
    async def test_a_daily_marketer_run_reads_back_its_count_and_its_cost(
        self, session
    ):
        run = AgentRun(
            agent="marketer",
            trigger="daily",
            read_detail="four brand files, nine swipe items, three empty slots",
            proposed=3,
            duration_ms=8100,
            cost_usd=Decimal("0.4212"),
            ok=True,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        assert (run.seq, run.agent, run.proposed, run.ok, run.error) == (
            1,
            "marketer",
            3,
            True,
            None,
        )
        assert run.cost_usd == Decimal("0.4212")

    async def test_a_taste_run_that_failed_keeps_why(self, session):
        run = AgentRun(
            agent="taste",
            trigger="manual",
            read_detail="eleven rejections",
            proposed=0,
            ok=False,
            error="APIError: the model is down",
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)
        assert (run.agent, run.proposed, run.duration_ms, run.ok) == (
            "taste",
            0,
            0,
            False,
        )
        assert run.cost_usd == Decimal("0")
        assert run.error == "APIError: the model is down"


class TestASkippedSlotIsRecordedOnce:
    async def test_a_skipped_slot_reads_back(self, session):
        skip = SlotSkip(slot_date=SLOT, slot_name="friday_post")
        session.add(skip)
        await session.flush()
        await session.refresh(skip)
        assert (skip.slot_date, skip.slot_name) == (SLOT, "friday_post")

    async def test_two_names_on_one_day_are_two_skips(self, session):
        session.add_all(
            [
                SlotSkip(slot_date=SLOT, slot_name="friday_post"),
                SlotSkip(slot_date=SLOT, slot_name="friday_image"),
            ]
        )
        await session.flush()
        assert len(await rows(session, SlotSkip, SlotSkip.id)) == 2

    async def test_the_same_slot_skipped_twice_is_refused(self, session):
        session.add_all(
            [
                SlotSkip(slot_date=SLOT, slot_name="friday_post"),
                SlotSkip(slot_date=SLOT, slot_name="friday_post"),
            ]
        )
        with pytest.raises(IntegrityError):
            await session.flush()
        await session.rollback()


class TestTheStudioSettingsShipTheirDefaults:
    def test_studio_is_off_and_names_its_two_models_and_its_media_directory(self):
        defaults = {
            name: field.default for name, field in Settings.model_fields.items()
        }
        assert defaults["STUDIO_ENABLED"] is False
        assert defaults["MARKETER_MODEL"] == "claude-opus-5"
        assert defaults["SKILL_MODEL"] == "claude-sonnet-5"
        assert defaults["MEDIA_DIR"] == "/media"
