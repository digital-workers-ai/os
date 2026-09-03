import uuid

from fastapi import Body, HTTPException, Query, Request

from app.api.routers import conversation as router
from app.caches import MAX_OFFSET
from app.conversation import agent, store
from app.db import async_session


@router.api_route("/conversations", methods=["GET", "POST"])
async def conversations(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0, le=MAX_OFFSET),
):
    async with async_session() as session:
        if request.method == "POST":
            conversation_id = await store.create_conversation(session)
            await session.commit()
            return {"conversation_id": str(conversation_id)}
        return {
            "conversations": await store.list_conversations(
                session, limit=limit, offset=offset
            )
        }


@router.get(
    "/conversations/{conversation_id}",
    responses={404: {"description": "no such conversation"}},
)
async def get_conversation(conversation_id: str):
    try:
        parsed = uuid.UUID(conversation_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="no such conversation") from None
    async with async_session() as session:
        if await store.get_conversation(session, parsed) is None:
            raise HTTPException(status_code=404, detail="no such conversation")
        return {
            "conversation_id": conversation_id,
            "turns": await store.conversation_turns(session, parsed),
        }


@router.post("")
async def run_turn(body: dict = Body(default={})):
    question = str(body.get("question") or "")
    conversation_id = body.get("conversation_id")
    if not conversation_id:
        raise HTTPException(status_code=422, detail="conversation_id is required")
    try:
        parsed = uuid.UUID(str(conversation_id))
    except ValueError:
        raise HTTPException(status_code=404, detail="no such conversation") from None
    async with async_session() as session:
        if await store.get_conversation(session, parsed) is None:
            raise HTTPException(status_code=404, detail="no such conversation")
        try:
            return await agent.run_turn(session, question, conversation_id=parsed)
        except agent.ConversationError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
