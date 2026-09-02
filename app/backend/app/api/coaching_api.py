from fastapi import HTTPException, Request

from app.api.routers import coaching as router
from app.coaching import briefer
from app.db import async_session


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
