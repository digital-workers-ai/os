import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select, update

from app.config import settings
from app.models import ConversationThread, ConversationTurn


async def create_conversation(session) -> uuid.UUID:
    row = ConversationThread()
    session.add(row)
    await session.flush()
    await prune_conversations(session)
    return row.id


async def prune_conversations(session) -> None:
    keep = (
        (
            await session.execute(
                select(ConversationThread.seq)
                .order_by(ConversationThread.seq.desc())
                .limit(settings.CONVERSATION_THREAD_RETENTION)
            )
        )
        .scalars()
        .all()
    )
    await session.execute(
        delete(ConversationThread).where(ConversationThread.seq < min(keep))
    )


async def get_conversation(
    session, conversation_id: uuid.UUID
) -> ConversationThread | None:
    return (
        (
            await session.execute(
                select(ConversationThread).where(
                    ConversationThread.id == conversation_id
                )
            )
        )
        .scalars()
        .first()
    )


async def load_history(session, conversation_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(ConversationTurn)
                .where(ConversationTurn.thread_id == conversation_id)
                .order_by(ConversationTurn.seq.desc())
                .limit(settings.CONVERSATION_MAX_HISTORY_TURNS)
            )
        )
        .scalars()
        .all()
    )
    history: list[dict] = []
    for row in reversed(rows):
        history.append({"role": "user", "content": row.question})
        history.append({"role": "assistant", "content": row.answer})
    return history


async def conversation_turns(session, conversation_id: uuid.UUID) -> list[dict]:
    rows = (
        (
            await session.execute(
                select(ConversationTurn)
                .where(ConversationTurn.thread_id == conversation_id)
                .order_by(ConversationTurn.seq)
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "question": row.question,
            "answer": row.answer,
            "created_at": row.created_at.isoformat(),
        }
        for row in rows
    ]


async def append_turn(
    session, conversation_id: uuid.UUID, question: str, result: dict
) -> None:
    session.add(
        ConversationTurn(
            thread_id=conversation_id,
            question=question,
            answer=result["answer"],
            receipts=result["receipts"],
            model=result["model"],
            prompt_version=result["prompt_version"],
            loop_turns=result["turns"],
            exhausted=bool(result.get("exhausted")),
        )
    )
    await session.execute(
        update(ConversationThread)
        .where(ConversationThread.id == conversation_id)
        .values(updated_at=datetime.now(UTC))
    )
    await session.flush()
