import pytest
from sqlalchemy import select

from app.config import settings
from app.conversation import agent, store
from app.models import ConversationTurn
from tests.test_conversation_loop import Reply, ScriptedModel, Text, ToolUse


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "CONVERSATION_ENABLED", True)


class TestAnswersLandOnTheirThread:
    async def test_an_answer_is_stored_and_replayed_as_history(self, session, enabled):
        conversation_id = await store.create_conversation(session)
        model = ScriptedModel(Reply([Text("MRR is 0.")]))
        result = await agent.run_turn(
            session,
            "what is mrr?",
            conversation_id=conversation_id,
            model_client=model,
        )
        assert result["conversation_id"] == str(conversation_id)
        assert await store.load_history(session, conversation_id) == [
            {"role": "user", "content": "what is mrr?"},
            {"role": "assistant", "content": "MRR is 0."},
        ]

    async def test_a_second_turn_sees_the_stored_first_exchange(self, session, enabled):
        conversation_id = await store.create_conversation(session)
        model = ScriptedModel(Reply([Text("first.")]), Reply([Text("second.")]))
        await agent.run_turn(
            session, "first?", conversation_id=conversation_id, model_client=model
        )
        await agent.run_turn(
            session, "second?", conversation_id=conversation_id, model_client=model
        )
        assert model.sent[1]["messages"] == [
            {"role": "user", "content": "first?"},
            {"role": "assistant", "content": "first."},
            {"role": "user", "content": "second?"},
        ]

    async def test_an_exhausted_turn_is_persisted_with_its_receipts(
        self, session, enabled, monkeypatch
    ):
        monkeypatch.setattr(settings, "CONVERSATION_MAX_TURNS", 2)
        conversation_id = await store.create_conversation(session)
        model = ScriptedModel(*[Reply([ToolUse("entity_counts")]) for _ in range(2)])
        result = await agent.run_turn(
            session, "q", conversation_id=conversation_id, model_client=model
        )
        assert result["exhausted"] is True
        assert result["conversation_id"] == str(conversation_id)
        row = (await session.execute(select(ConversationTurn))).scalars().one()
        assert row.exhausted is True
        assert row.loop_turns == 2
        assert row.receipts == [{"tool": "entity_counts", "input": {}}] * 2
