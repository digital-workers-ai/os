import uuid

from fastapi import Body, HTTPException

from app.api.routers import conversation as router
from app.conversation import agent, store
from app.db import async_session


@router.post("/conversations")
async def create_conversation():
    async with async_session() as session:
        conversation_id = await store.create_conversation(session)
        await session.commit()
    return {"conversation_id": str(conversation_id)}


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
