import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from app.conversation import store
from app.models import ConversationThread, ConversationTurn
from tests.conftest import NOW

SEEN = datetime(2026, 8, 1, tzinfo=UTC)

TURN = {
    "answer": "MRR is 0.",
    "receipts": [],
    "turns": 1,
    "model": "claude-test",
    "prompt_version": "2026-08-02.1",
}


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

    async def test_a_recorded_turn_stamps_the_thread_with_the_app_clock(self, session):
        conversation_id = await store.create_conversation(session)
        await store.append_turn(session, conversation_id, "what is mrr?", TURN)
        thread = await store.get_conversation(session, conversation_id)
        await session.refresh(thread)
        assert thread.updated_at == NOW


class TestListing:
    async def test_nothing_is_listed_before_any_thread_exists(self, session):
        assert await store.list_conversations(session, limit=50, offset=0) == []

    async def test_a_thread_with_a_new_turn_moves_to_the_front(self, session):
        older = await store.create_conversation(session)
        newer = await store.create_conversation(session)
        await store.append_turn(session, older, "what is mrr?", TURN)
        listed = await store.list_conversations(session, limit=50, offset=0)
        assert [row["conversation_id"] for row in listed] == [str(older), str(newer)]

    async def test_paging_walks_newest_first_without_repeating(self, session):
        stamped = [
            ConversationThread(updated_at=SEEN + timedelta(days=n)) for n in range(3)
        ]
        session.add_all(stamped)
        await session.flush()
        first = await store.list_conversations(session, limit=2, offset=0)
        second = await store.list_conversations(session, limit=2, offset=2)
        assert [row["conversation_id"] for row in first + second] == [
            str(stamped[2].id),
            str(stamped[1].id),
            str(stamped[0].id),
        ]
        assert first[0]["updated_at"] == (SEEN + timedelta(days=2)).isoformat()
