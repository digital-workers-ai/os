from fastapi import HTTPException, Query, Request

from app.api.routers import coaching as router
from app.coaching import briefer
from app.config import settings
from app.db import async_session


@router.get("")
async def index():
    known = briefer.recipients()
    return {
        "enabled": settings.COACHING_ENABLED,
        "model": settings.COACHING_MODEL,
        "prompt_version": briefer.PROMPT_VERSION,
        "prompts_sha": briefer.prompts_sha()[:12],
        "roles": briefer.roles(),
        "recipients": {role: known.get(role, []) for role in briefer.roles()},
        "inferred": True,
        "note": "narration over measured numbers, not a measurement",
    }


@router.api_route(
    "/{role}",
    methods=["GET", "POST"],
    responses={404: {"description": "no briefing stored for this role"}},
)
async def briefing(role: str, request: Request):
    if request.method == "POST":
        async with async_session() as session:
            try:
                return {**await briefer.generate(session, role), "inferred": True}
            except briefer.CoachingError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    async with async_session() as session:
        stored = await briefer.latest(session, role)
    if stored is None:
        raise HTTPException(404, f"no briefing stored for {role!r}")
    return {**stored, "inferred": True}


@router.get("/{role}/history")
async def briefing_history(role: str, limit: int = Query(50, ge=1, le=200)):
    async with async_session() as session:
        briefings = await briefer.history(session, role, limit)
    return {"role": role, "briefings": briefings, "inferred": True}
