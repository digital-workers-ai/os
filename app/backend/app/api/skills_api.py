import statistics

from fastapi import BackgroundTasks, Body, HTTPException
from sqlalchemy import func, select

from app.api.routers import skills as router
from app.db import async_session
from app.models import Proposal, SkillRun
from app.skills import catalog, runner

DECIDED = ("approved", "built", "rejected")

APPROVED = ("approved", "built")


async def _runs(session) -> dict:
    return dict(
        (
            await session.execute(
                select(SkillRun.skill, func.count()).group_by(SkillRun.skill)
            )
        ).all()
    )


async def _approvals(session) -> dict:
    rows = (
        await session.execute(
            select(Proposal.skill, Proposal.status, func.count())
            .where(Proposal.status.in_(DECIDED))
            .group_by(Proposal.skill, Proposal.status)
        )
    ).all()
    counts: dict = {}
    for skill, status, total in rows:
        decided, approved = counts.get(skill, (0, 0))
        counts[skill] = (
            decided + total,
            approved + (total if status in APPROVED else 0),
        )
    return {
        skill: round(approved / decided, 2)
        for skill, (decided, approved) in counts.items()
    }


async def _edits(session) -> dict:
    rows = (
        await session.execute(
            select(Proposal.skill, SkillRun.proposal_seq, func.count())
            .join(SkillRun, SkillRun.proposal_seq == Proposal.seq)
            .where(Proposal.status.in_(APPROVED), SkillRun.mode == "draft")
            .group_by(Proposal.skill, SkillRun.proposal_seq)
        )
    ).all()
    drafted: dict = {}
    for skill, _proposal, drafts in rows:
        drafted.setdefault(skill, []).append(drafts - 1)
    return {skill: statistics.median(edits) for skill, edits in drafted.items()}


async def _spend(session) -> dict:
    rows = (
        await session.execute(
            select(SkillRun.skill, func.avg(SkillRun.cost_usd))
            .where(SkillRun.mode == "build", SkillRun.status == "ok")
            .group_by(SkillRun.skill)
        )
    ).all()
    return {skill: float(spent) for skill, spent in rows if spent}


async def _stats() -> dict:
    async with async_session() as session:
        return {
            "runs": await _runs(session),
            "approvals": await _approvals(session),
            "edits": await _edits(session),
            "spend": await _spend(session),
        }


def _row(skill, stats: dict) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "modes": list(skill.modes),
        "runs": stats["runs"].get(skill.name, 0),
        "approval_rate": stats["approvals"].get(skill.name),
        "median_edits": stats["edits"].get(skill.name),
        "cost_per_build": stats["spend"].get(skill.name),
        "proposed_lesson": None,
    }


@router.get("/skills")
async def skills():
    stats = await _stats()
    return {"skills": [_row(catalog.load(name), stats) for name in catalog.names()]}


@router.get("/skills/{name}", responses={404: {"description": "no such skill"}})
async def skill(name: str):
    try:
        loaded = catalog.load(name)
    except catalog.SkillError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **_row(loaded, await _stats()),
        "body": loaded.body,
        "lessons": list(loaded.lessons),
        "sha": loaded.sha,
    }


@router.post(
    "/skills/{name}/run",
    responses={
        404: {"description": "no such skill"},
        409: {"description": "the run was refused before it started"},
    },
)
async def start_run(name: str, background: BackgroundTasks, body: dict = Body({})):
    if name not in catalog.names():
        raise HTTPException(
            status_code=404,
            detail=f"no skill named {name!r} — Studio runs {catalog.names()}",
        )
    ask = runner.Ask(
        skill=name,
        mode=str(body.get("mode") or ""),
        caller="studio",
        input=str(body.get("input") or ""),
        look=body.get("look"),
        slot=body.get("slot"),
    )
    async with async_session() as session:
        try:
            seq = await runner.open_run(session, ask)
        except runner.SkillError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    background.add_task(runner.execute_detached, seq, ask)
    return {"skill_run": seq}
