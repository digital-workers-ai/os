from fastapi import Depends, HTTPException, Query
from sqlalchemy import select

from app.api.routers import runs as router
from app.caches import MAX_OFFSET
from app.db import get_session
from app.models import AgentRun, AssetFile, SkillRun, SkillRunToolCall
from app.studio import rows

NOT_FOUND = {404: {"description": "no such run"}}


async def _newest_first(session, query, model, limit, offset) -> list:
    page = query.order_by(model.seq.desc()).limit(limit).offset(offset)
    return (await session.execute(page)).scalars().all()


def _tool_call_row(call) -> dict:
    return {
        "id": str(call.id),
        "tool": call.tool,
        "ok": call.ok,
        "duration_ms": call.duration_ms,
        "detail": call.detail,
    }


@router.get("/skill-runs")
async def list_skill_runs(
    limit: int = Query(50, ge=1, le=500),
    skill: str | None = None,
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    query = select(SkillRun)
    if skill:
        query = query.where(SkillRun.skill == skill)
    runs = await _newest_first(session, query, SkillRun, limit, offset)
    return {"runs": [rows.skill_run_row(run) for run in runs]}


@router.get("/skill-runs/{seq}", responses=NOT_FOUND)
async def get_skill_run(seq: int, session=Depends(get_session)):
    run = await session.get(SkillRun, seq)
    if run is None:
        raise HTTPException(status_code=404, detail=f"no skill run {seq}")
    calls = await session.execute(
        select(SkillRunToolCall)
        .where(SkillRunToolCall.skill_run_seq == seq)
        .order_by(SkillRunToolCall.id)
    )
    files = await session.execute(
        select(AssetFile)
        .where(AssetFile.asset_seq == run.asset_seq, AssetFile.version == run.version)
        .order_by(AssetFile.path)
    )
    return {
        **rows.skill_run_row(run),
        "tool_calls": [_tool_call_row(call) for call in calls.scalars()],
        "files": [
            rows.file_row(run.asset_seq, run.version, file) for file in files.scalars()
        ],
    }


@router.get("/agent-runs")
async def list_agent_runs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
    session=Depends(get_session),
):
    runs = await _newest_first(session, select(AgentRun), AgentRun, limit, offset)
    return {"runs": [rows.agent_run_row(run) for run in runs]}
