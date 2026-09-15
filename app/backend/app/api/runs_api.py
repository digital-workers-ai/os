from fastapi import Depends, HTTPException, Query
from sqlalchemy import select

from app.api.routers import runs as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.models import AgentRun, SkillRun, SkillRunToolCall
from app.studio import assets, proposals
from app.studio.today import agent_run_row, skill_run_row


def _stages(run):
    if run.stage is None:
        return []
    return [
        {
            "name": run.stage,
            "state": "running" if run.status == "running" else "done",
            "detail": run.error,
        }
    ]


async def _files(session, run):
    if run.asset_seq is not None:
        return await assets.version_files(session, run.asset_seq)
    if run.proposal_seq is not None:
        return await proposals.draft_files(session, run.proposal_seq)
    return []


@router.get("/skill-runs")
async def list_skill_runs(
    limit: int = Query(50, ge=1, le=500),
    skill: str | None = None,
    mode: str | None = None,
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(SkillRun).order_by(SkillRun.seq.desc())
    if skill:
        query = query.where(SkillRun.skill == skill)
    if mode:
        query = query.where(SkillRun.mode == mode)
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    return {"runs": [skill_run_row(row) for row in rows]}


@router.get("/skill-runs/{seq}", responses={404: {"description": "no such skill run"}})
async def read_skill_run(seq: int, session=Depends(get_session)):
    run = await session.get(SkillRun, seq)
    if run is None:
        raise HTTPException(404, f"no skill run {seq}")
    calls = (
        (
            await session.execute(
                select(SkillRunToolCall)
                .where(SkillRunToolCall.skill_run_seq == seq)
                .order_by(SkillRunToolCall.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        **skill_run_row(run),
        "skill_sha": run.skill_sha,
        "stages": _stages(run),
        "tool_calls": [
            {
                "tool": call.tool,
                "ok": call.ok,
                "duration_ms": call.duration_ms,
                "detail": call.detail,
            }
            for call in calls
        ],
        "files": await _files(session, run),
    }


@router.get("/agent-runs/{seq}", responses={404: {"description": "no such agent run"}})
async def read_agent_run(seq: int, session=Depends(get_session)):
    run = await session.get(AgentRun, seq)
    if run is None:
        raise HTTPException(404, f"no agent run {seq}")
    return agent_run_row(run)


@router.get("/agent-runs")
async def list_agent_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    rows = (
        (
            await session.execute(
                select(AgentRun)
                .order_by(AgentRun.seq.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        .scalars()
        .all()
    )
    return {"runs": [agent_run_row(row) for row in rows]}
