import uuid

from sqlalchemy import select

from app.config import settings
from app.conversation import store
from app.models import ConversationThread, ConversationTurn


class TestConversationRetention:
    async def test_only_the_newest_conversations_survive(self, session, monkeypatch):
        monkeypatch.setattr(settings, "CONVERSATION_THREAD_RETENTION", 2)
        ids = [await store.create_conversation(session) for _ in range(3)]
        await session.flush()
        kept = (await session.execute(select(ConversationThread))).scalars().all()
        assert {row.id for row in kept} == {ids[1], ids[2]}

    async def test_pruning_drops_the_turns_with_their_thread(
        self, session, monkeypatch
    ):
        monkeypatch.setattr(settings, "CONVERSATION_THREAD_RETENTION", 1)
        first = await store.create_conversation(session)
        await store.append_turn(
            session,
            first,
            "old?",
            {
                "answer": "old.",
                "receipts": [],
                "turns": 1,
                "model": "claude-test",
                "prompt_version": "2026-08-02.1",
            },
        )
        await store.create_conversation(session)
        await session.flush()
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
