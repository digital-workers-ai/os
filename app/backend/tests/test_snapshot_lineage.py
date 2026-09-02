import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.engine import metrics
from app.enrichment import vocabulary
from app.models import EnrichedFact, EntityCanonical, FactCurrent, MetricSnapshot

SEEN = datetime(2026, 8, 1, tzinfo=UTC)


@pytest.fixture
def reading():
    return vocabulary.load()["sales_call"]


async def _read_meeting(
    session,
    seq,
    reading,
    label="strong",
    *,
    vocab=None,
    prompt="p1",
    model="test-model",
):
    canonical_id = uuid.uuid4()
    session.add(
        EntityCanonical(
            canonical_id=canonical_id,
            entity_type="meeting",
            anchor_key=f"zoom|meeting|s{seq}",
            minted_seq=seq,
            member_count=1,
        )
    )
    session.add(
        FactCurrent(
            canonical_id=canonical_id,
            entity_type="meeting",
            attr="transcript",
            value=f"call {seq}",
            observed_at=SEEN,
        )
    )
    session.add(
        EnrichedFact(
            canonical_id=canonical_id,
            entity_type="meeting",
            reading=reading.name,
            attr="interest",
            value=label,
            quote="…",
            quote_verified=True,
            input_sha=f"sha{seq}",
            vocabulary_sha=vocab or reading.sha,
            model=model,
            prompt_version=prompt,
        )
    )
    return canonical_id


async def _points(session, metric, count):
    base = datetime(2026, 1, 1, tzinfo=UTC)
    for n in range(count):
        session.add(
            MetricSnapshot(
                metric=metric,
                value=float(n),
                entities=1,
                recorded_at=base + timedelta(days=n),
            )
        )
    await session.flush()


def _values(series):
    return [p["value"] for run in series["runs"] for p in run["points"]]


class TestWhatASnapshotRecords:
    async def test_an_inferred_snapshot_stores_the_vocabulary_that_produced_it(
        self, session, reading
    ):
        await _read_meeting(session, 1, reading)
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(
                        MetricSnapshot.metric == "strong_interest_share"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.vocabulary_sha == reading.sha
        assert row.inferred is True

    async def test_it_stores_the_model_and_prompt_that_produced_it(
        self, session, reading
    ):
        await _read_meeting(session, 1, reading, prompt="p1", model="test-model")
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(
                        MetricSnapshot.metric == "strong_interest_share"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.produced_by == "test-model@p1"

    async def test_a_canonical_snapshot_carries_no_lineage_and_is_not_inferred(
        self, session, reading
    ):
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(MetricSnapshot.metric == "mrr")
                )
            )
            .scalars()
            .first()
        )
        assert row is not None
        assert row.inferred is False
        assert row.vocabulary_sha is None
        assert row.produced_by is None

    async def test_a_metric_read_under_two_prompts_records_both(self, session, reading):
        await _read_meeting(session, 1, reading, prompt="p1")
        await _read_meeting(session, 2, reading, prompt="p2")
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(
                        MetricSnapshot.metric == "strong_interest_share"
                    )
                )
            )
            .scalars()
            .one()
        )
        assert row.produced_by == "test-model@p1, test-model@p2"


class TestHistoryReturnsTheNewestPoints:
    async def test_a_limit_keeps_the_newest_points(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=3)
        assert _values(series) == [3.0, 4.0, 5.0]

    async def test_the_points_are_still_oldest_first_within_the_window(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=3)
        assert _values(series) == sorted(_values(series))

    async def test_a_series_shorter_than_the_limit_is_returned_whole(self, session):
        await _points(session, "mrr", 2)
        series = await metrics.history(session, "mrr", limit=500)
        assert _values(series) == [0.0, 1.0]

    async def test_a_trend_goal_sees_the_window_advance(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=2)
        assert _values(series)[-1] == 5.0


class TestASnapshotOfNothingIsNotAZero:
    async def _snapshot(self, session):
        written = await metrics.record_snapshots(session)
        await session.commit()
        return written

    async def test_a_metric_over_nothing_stores_no_value(self, session):
        await self._snapshot(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(MetricSnapshot.metric == "mrr")
                )
            )
            .scalars()
            .one()
        )
        assert row.entities == 0
        assert row.value is None

    async def test_the_run_still_records_itself(self, session):
        assert await self._snapshot(session) > 0

    async def test_a_real_measurement_is_still_stored(self, session, canonical):
        await canonical(
            "subscription", {"mrr": "100", "status": "active", "currency": "usd"}
        )
        await session.commit()
        await self._snapshot(session)
        row = (
            (
                await session.execute(
                    select(MetricSnapshot).where(MetricSnapshot.metric == "mrr")
                )
            )
            .scalars()
            .one()
        )
        assert row.value == 100.0 and row.entities == 1


class TestTheSeriesSplits:
    async def test_a_series_under_one_vocabulary_is_one_run(self, session, reading):
        await _read_meeting(session, 1, reading)
        await session.commit()
        await metrics.record_snapshots(session)
        await metrics.record_snapshots(session)
        history = await metrics.history(session, "strong_interest_share")
        assert len(history["runs"]) == 1
        assert len(history["runs"][0]["points"]) == 2
        assert history["comparable"] is True

    async def test_a_vocabulary_change_starts_a_new_run(self, session, reading):
        first = await _read_meeting(session, 1, reading)
        await session.commit()
        await metrics.record_snapshots(session)

        row = (
            (
                await session.execute(
                    select(EnrichedFact).where(EnrichedFact.canonical_id == first)
                )
            )
            .scalars()
            .one()
        )
        row.vocabulary_sha = "a-replaced-vocabulary"
        await session.commit()
        await metrics.record_snapshots(session)

        history = await metrics.history(session, "strong_interest_share")
        assert len(history["runs"]) == 2
        assert history["comparable"] is False

    async def test_a_prompt_change_also_starts_a_new_run(self, session, reading):
        first = await _read_meeting(session, 1, reading, prompt="p1")
        await session.commit()
        await metrics.record_snapshots(session)

        row = (
            (
                await session.execute(
                    select(EnrichedFact).where(EnrichedFact.canonical_id == first)
                )
            )
            .scalars()
            .one()
        )
        row.prompt_version = "p2"
        await session.commit()
        await metrics.record_snapshots(session)

        history = await metrics.history(session, "strong_interest_share")
        assert len(history["runs"]) == 2

    async def test_each_run_says_what_produced_it(self, session, reading):
        first = await _read_meeting(session, 1, reading, prompt="p1")
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(EnrichedFact).where(EnrichedFact.canonical_id == first)
                )
            )
            .scalars()
            .one()
        )
        row.prompt_version = "p2"
        await session.commit()
        await metrics.record_snapshots(session)

        history = await metrics.history(session, "strong_interest_share")
        assert [r["produced_by"] for r in history["runs"]] == [
            "test-model@p1",
            "test-model@p2",
        ]

    async def test_a_canonical_series_is_always_one_comparable_run(
        self, session, reading
    ):
        await session.commit()
        await metrics.record_snapshots(session)
        await metrics.record_snapshots(session)
        history = await metrics.history(session, "mrr")
        assert len(history["runs"]) == 1
        assert history["comparable"] is True

    async def test_the_break_is_visible_without_reading_every_point(
        self, session, reading
    ):
        first = await _read_meeting(session, 1, reading)
        await session.commit()
        await metrics.record_snapshots(session)
        row = (
            (
                await session.execute(
                    select(EnrichedFact).where(EnrichedFact.canonical_id == first)
                )
            )
            .scalars()
            .one()
        )
        row.vocabulary_sha = "replaced"
        await session.commit()
        await metrics.record_snapshots(session)

        history = await metrics.history(session, "strong_interest_share")
        assert history["comparable"] is False
        assert history["breaks"] == 1
