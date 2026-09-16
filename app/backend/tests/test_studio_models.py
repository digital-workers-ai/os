from datetime import date

import pytest
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.models import (
    AgentRun,
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    SkillRun,
    SkillRunToolCall,
    SlotSkip,
    StudioThread,
    StudioTurn,
)

SLOT_DATE = date(2026, 9, 4)
SHA = "a" * 64


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
    return await _stored(session, Asset(**{**fields, **overrides}))


async def _skill_run(session, asset=None):
    return await _stored(
        session,
        SkillRun(
            skill="dw-post",
            skill_sha=SHA,
            caller="chat",
            asset_seq=None if asset is None else asset.seq,
            status="running",
        ),
    )


async def _thread(session):
    return await _stored(session, StudioThread(title="Monday post"))


async def _rows(session, model):
    return (await session.execute(select(model))).scalars().all()


class TestEveryTableTakesARowAndGivesItBack:
    async def test_asset(self, session):
        asset = await _asset(
            session,
            look="stat-card",
            ratio="1:1",
            origin="marketer",
            slot_date=SLOT_DATE,
            slot_name="linkedin_post",
            feedback="Shorter next time",
        )
        assert asset.seq == 1
        assert asset.kind == "post"
        assert asset.look == "stat-card"
        assert asset.slot_date == SLOT_DATE
        assert asset.feedback == "Shorter next time"
        assert asset.created_at.tzinfo is not None

    async def test_asset_defaults_leave_the_slot_and_look_empty(self, session):
        asset = await _asset(session)
        assert (asset.look, asset.ratio, asset.slot_date, asset.slot_name) == (
            None,
            None,
            None,
            None,
        )
        assert asset.feedback is None

    async def test_asset_version(self, session):
        asset = await _asset(session)
        version = await _stored(
            session,
            AssetVersion(asset_seq=asset.seq, version=1, note="first cut"),
        )
        assert version.id is not None
        assert version.note == "first cut"
        assert version.created_at.tzinfo is not None

    async def test_asset_file(self, session):
        asset = await _asset(session)
        file = await _stored(
            session,
            AssetFile(
                asset_seq=asset.seq,
                version=1,
                path="post.md",
                media_type="text/markdown",
                bytes=1200,
            ),
        )
        assert file.bytes == 1200
        assert file.created_at.tzinfo is not None

    async def test_asset_claim(self, session):
        asset = await _asset(session)
        claim = await _stored(
            session,
            AssetClaim(
                asset_seq=asset.seq,
                version=1,
                text="MRR is 17,147",
                source_kind="proof",
                source_ref="mrr",
                verified=True,
            ),
        )
        assert claim.verified is True
        assert claim.source_ref == "mrr"

    async def test_asset_claim_may_lack_a_source_ref(self, session):
        asset = await _asset(session)
        claim = await _stored(
            session,
            AssetClaim(
                asset_seq=asset.seq,
                version=1,
                text="Everyone loves it",
                source_kind="none",
                verified=False,
            ),
        )
        assert claim.source_ref is None

    async def test_asset_evidence(self, session):
        asset = await _asset(session)
        evidence = await _stored(
            session,
            AssetEvidence(
                asset_seq=asset.seq,
                version=1,
                kind="transcript",
                ref="mtg_20260830",
                detail="Bruce: the pricing is what stalls us",
            ),
        )
        assert evidence.kind == "transcript"
        assert evidence.ref == "mtg_20260830"

    async def test_skill_run_and_its_counters_start_at_zero(self, session):
        run = await _skill_run(session)
        assert run.seq == 1
        assert run.asset_seq is None
        assert (run.version, run.stage, run.error, run.model) == (
            None,
            None,
            None,
            None,
        )
        assert (run.tokens_in, run.tokens_out, run.duration_ms) == (0, 0, 0)
        assert run.started_at.tzinfo is not None
        assert run.finished_at is None

    async def test_skill_run_tool_call(self, session):
        run = await _skill_run(session)
        call = await _stored(
            session,
            SkillRunToolCall(skill_run_seq=run.seq, tool="brand_read", ok=True),
        )
        assert call.duration_ms == 0
        assert call.detail is None

    async def test_agent_run(self, session):
        run = await _stored(
            session,
            AgentRun(
                agent="marketer",
                trigger="daily",
                read_detail="4 slots, 2 empty",
                ok=True,
            ),
        )
        assert run.seq == 1
        assert (run.made, run.duration_ms, run.error) == (0, 0, None)
        assert run.created_at.tzinfo is not None

    async def test_slot_skip(self, session):
        skip = await _stored(
            session, SlotSkip(slot_date=SLOT_DATE, slot_name="linkedin_post")
        )
        assert skip.id is not None
        assert skip.created_at.tzinfo is not None

    async def test_studio_thread(self, session):
        thread = await _thread(session)
        assert thread.seq == 1
        assert thread.title == "Monday post"
        assert thread.created_at.tzinfo is not None

    async def test_studio_turn(self, session):
        thread = await _thread(session)
        run = await _skill_run(session)
        turn = await _stored(
            session,
            StudioTurn(
                thread_seq=thread.seq,
                role="studio",
                text="Here is the post.",
                skill_run_seq=run.seq,
            ),
        )
        assert turn.skill_run_seq == run.seq
        assert turn.created_at.tzinfo is not None

    async def test_studio_turn_may_carry_no_run(self, session):
        thread = await _thread(session)
        turn = await _stored(
            session, StudioTurn(thread_seq=thread.seq, role="person", text="Hi")
        )
        assert turn.skill_run_seq is None


class TestDeletesCascade:
    async def test_an_asset_takes_its_versions_files_claims_and_evidence(self, session):
        asset = await _asset(session)
        kept = await _asset(session)
        for seq in (asset.seq, kept.seq):
            session.add(AssetVersion(asset_seq=seq, version=1, note="first"))
            session.add(
                AssetFile(
                    asset_seq=seq,
                    version=1,
                    path="post.md",
                    media_type="text/markdown",
                    bytes=1,
                )
            )
            session.add(
                AssetClaim(
                    asset_seq=seq,
                    version=1,
                    text="x",
                    source_kind="proof",
                    verified=True,
                )
            )
            session.add(
                AssetEvidence(
                    asset_seq=seq,
                    version=1,
                    kind="proof",
                    ref="mrr",
                    detail="the figure it quotes",
                )
            )
        await session.flush()

        await session.execute(delete(Asset).where(Asset.seq == asset.seq))

        for model in (AssetVersion, AssetFile, AssetClaim, AssetEvidence):
            assert [row.asset_seq for row in await _rows(session, model)] == [kept.seq]

    async def test_an_asset_leaves_its_runs_with_no_asset(self, session):
        asset = await _asset(session)
        run = await _skill_run(session, asset)
        await session.execute(delete(Asset).where(Asset.seq == asset.seq))
        await session.refresh(run)
        assert run.asset_seq is None

    async def test_a_skill_run_takes_its_tool_calls(self, session):
        run = await _skill_run(session)
        kept = await _skill_run(session)
        for seq in (run.seq, kept.seq):
            session.add(SkillRunToolCall(skill_run_seq=seq, tool="brand_read", ok=True))
        await session.flush()
        await session.execute(delete(SkillRun).where(SkillRun.seq == run.seq))
        calls = await _rows(session, SkillRunToolCall)
        assert [call.skill_run_seq for call in calls] == [kept.seq]

    async def test_a_skill_run_leaves_its_turn_with_no_run(self, session):
        thread = await _thread(session)
        run = await _skill_run(session)
        turn = await _stored(
            session,
            StudioTurn(
                thread_seq=thread.seq, role="studio", text="x", skill_run_seq=run.seq
            ),
        )
        await session.execute(delete(SkillRun).where(SkillRun.seq == run.seq))
        await session.refresh(turn)
        assert turn.skill_run_seq is None

    async def test_a_thread_takes_its_turns(self, session):
        thread = await _thread(session)
        kept = await _thread(session)
        for seq in (thread.seq, kept.seq):
            session.add(StudioTurn(thread_seq=seq, role="person", text="Hi"))
        await session.flush()
        await session.execute(
            delete(StudioThread).where(StudioThread.seq == thread.seq)
        )
        turns = await _rows(session, StudioTurn)
        assert [turn.thread_seq for turn in turns] == [kept.seq]


class TestUniqueConstraintsHold:
    async def test_one_version_number_per_asset(self, session):
        asset = await _asset(session)
        session.add(AssetVersion(asset_seq=asset.seq, version=1, note="first"))
        await session.flush()
        session.add(AssetVersion(asset_seq=asset.seq, version=1, note="again"))
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_one_path_per_version(self, session):
        asset = await _asset(session)
        for _ in range(2):
            session.add(
                AssetFile(
                    asset_seq=asset.seq,
                    version=1,
                    path="post.md",
                    media_type="text/markdown",
                    bytes=1,
                )
            )
        with pytest.raises(IntegrityError):
            await session.flush()

    async def test_the_same_path_may_recur_in_another_version(self, session):
        asset = await _asset(session)
        for version in (1, 2):
            session.add(
                AssetFile(
                    asset_seq=asset.seq,
                    version=version,
                    path="post.md",
                    media_type="text/markdown",
                    bytes=1,
                )
            )
        await session.flush()
        assert len(await _rows(session, AssetFile)) == 2

    async def test_one_skip_per_slot_and_day(self, session):
        for _ in range(2):
            session.add(SlotSkip(slot_date=SLOT_DATE, slot_name="linkedin_post"))
        with pytest.raises(IntegrityError):
            await session.flush()
