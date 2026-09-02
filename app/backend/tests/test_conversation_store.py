import uuid

from sqlalchemy import delete, select

from app.conversation import store
from app.models import ConversationThread, ConversationTurn


class TestThreadsAreNeverDeleted:
    async def test_every_created_thread_survives(self, session):
        ids = [await store.create_conversation(session) for _ in range(3)]
        await session.flush()
        kept = (await session.execute(select(ConversationThread))).scalars().all()
        assert {row.id for row in kept} == set(ids)

    async def test_schema_cascades_turns_on_direct_thread_delete(self, session):
        thread_id = await store.create_conversation(session)
        await store.append_turn(
            session,
            thread_id,
            "old?",
            {
                "answer": "old.",
                "receipts": [],
                "turns": 1,
                "model": "claude-test",
                "prompt_version": "2026-08-02.1",
            },
        )
        await session.execute(
            delete(ConversationThread).where(ConversationThread.id == thread_id)
        )
        turns = (await session.execute(select(ConversationTurn))).scalars().all()
        assert turns == []


class TestStoredHistory:
    async def test_prior_turns_are_replayed_for_the_model(self, session):
        conversation_id = await store.create_conversation(session)
        await store.append_turn(
            session,
            conversation_id,
            "first?",
            {
                "answer": "first.",
                "receipts": [],
                "turns": 1,
                "model": "claude-test",
                "prompt_version": "2026-08-02.1",
            },
        )
        history = await store.load_history(session, conversation_id)
        assert history == [
            {"role": "user", "content": "first?"},
            {"role": "assistant", "content": "first."},
        ]

    async def test_an_unknown_conversation_is_not_found(self, session):
        assert await store.get_conversation(session, uuid.uuid4()) is None
