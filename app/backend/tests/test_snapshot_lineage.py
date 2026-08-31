from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.engine import metrics
from app.models import MetricSnapshot


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


class TestHistoryReturnsTheNewestPoints:
    async def test_a_limit_keeps_the_newest_points(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=3)
        assert [p["value"] for p in series["points"]] == [3.0, 4.0, 5.0]

    async def test_the_points_are_still_oldest_first_within_the_window(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=3)
        values = [p["value"] for p in series["points"]]
        assert values == sorted(values)

    async def test_a_series_shorter_than_the_limit_is_returned_whole(self, session):
        await _points(session, "mrr", 2)
        series = await metrics.history(session, "mrr", limit=500)
        assert [p["value"] for p in series["points"]] == [0.0, 1.0]

    async def test_a_trend_goal_sees_the_window_advance(self, session):
        await _points(session, "mrr", 6)
        series = await metrics.history(session, "mrr", limit=2)
        assert [p["value"] for p in series["points"]][-1] == 5.0


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
