from fastapi import Depends, HTTPException
from sqlalchemy import func, select

from app.api.routers import brand as router
from app.db import get_session
from app.engine import brand as spec
from app.models import SkillRun, SkillRunToolCall

BRAND_READ = "brand.read"


async def _reads(session):
    return (
        await session.execute(
            select(SkillRun.skill, SkillRunToolCall.detail, func.count())
            .select_from(SkillRunToolCall)
            .join(SkillRun, SkillRun.seq == SkillRunToolCall.skill_run_seq)
            .where(SkillRunToolCall.tool == BRAND_READ)
            .group_by(SkillRun.skill, SkillRunToolCall.detail)
        )
    ).all()


def _read_by(name, rows):
    matched = [
        (skill, count) for skill, detail, count in rows if name in (detail or "")
    ]
    return sorted({skill for skill, _count in matched}), sum(
        count for _skill, count in matched
    )


def _file(name, rows):
    front, _body = spec.read(name)
    used_by, reads = _read_by(name, rows)
    return {
        "name": name,
        "title": str(front.get("title", name)),
        "updated": str(front.get("updated", "")),
        "used_by": used_by,
        "reads": reads,
    }


@router.get("/brand")
async def list_brand(session=Depends(get_session)):
    rows = await _reads(session)
    return {
        "files": [{**_file(name, rows), "pending_pr": False} for name in spec.files()]
    }


@router.get("/brand/{name}", responses={404: {"description": "no such brand file"}})
async def read_brand(name: str, session=Depends(get_session)):
    if name not in spec.files():
        raise HTTPException(404, f"no brand file {name!r}")
    _front, body = spec.read(name)
    return {**_file(name, await _reads(session)), "body": body}
