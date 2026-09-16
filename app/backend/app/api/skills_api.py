from typing import Annotated

from fastapi import BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, StringConstraints
from sqlalchemy import func, select

from app.api.routers import skills as router
from app.db import get_session
from app.models import Asset, SkillRun
from app.skills import catalog, runner
from app.studio import rows

CALLER = "chat"
NOT_FOUND = {404: {"description": "no such skill"}}
CANNOT_RUN = {409: {"description": "the run cannot open"}}


class RunBody(BaseModel):
    input: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
    look: str | None = None
    ratio: str | None = None


def _skill(name) -> catalog.Skill:
    try:
        return catalog.load(name)
    except catalog.SkillError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def _row(skill, runs) -> dict:
    return {
        "name": skill.name,
        "description": skill.description,
        "makes": skill.makes,
        "runs": runs,
    }


@router.get("/skills")
async def list_skills(session=Depends(get_session)):
    counted = await session.execute(
        select(SkillRun.skill, func.count()).group_by(SkillRun.skill)
    )
    runs = dict(counted.all())
    return {
        "skills": [
            {**_row(skill, runs.get(skill.name, 0)), "lessons": len(skill.lessons)}
            for skill in map(catalog.load, catalog.names())
        ]
    }


@router.get("/skills/{name}", responses=NOT_FOUND)
async def get_skill(name: str, session=Depends(get_session)):
    skill = _skill(name)
    runs = await session.scalar(
        select(func.count()).select_from(SkillRun).where(SkillRun.skill == name)
    )
    return {
        **_row(skill, runs),
        "body": skill.body,
        "lessons": list(skill.lessons),
        "sha": skill.sha,
    }


@router.post("/skills/{name}/run", responses={**NOT_FOUND, **CANNOT_RUN})
async def run_skill(
    name: str,
    body: RunBody,
    background: BackgroundTasks,
    session=Depends(get_session),
):
    skill = _skill(name)
    ask = runner.Ask(
        skill=skill.name,
        caller=CALLER,
        input=body.input,
        look=body.look,
        ratio=body.ratio,
    )
    try:
        started = await runner.open_run(session, ask)
    except runner.SkillError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    run = await session.get(SkillRun, started.skill_run)
    asset = await session.get(Asset, started.asset_seq)
    [row] = await rows.asset_rows(session, [asset])
    await session.commit()
    background.add_task(runner.execute_detached, started.skill_run, ask)
    return {"skill_run": rows.skill_run_row(run), "asset": row}
