import importlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app import sync
from app.config import settings
from app.models import RawEvent, SyncRun
from app.sources import client, registry
from tests.conftest import NOW


class TestSyncIsolation:
    async def test_one_source_failing_is_recorded_rather_than_raised(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def explode(session, store):
            raise RuntimeError("provider is down")

        module = type("M", (), {"pull": staticmethod(explode)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})

        result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
        assert result["failed"] == 1 and result["ok"] == 0
        assert "provider is down" in result["results"][0]["detail"]

    async def test_a_truncated_pull_reports_the_reason(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull_and_truncate(session, store):
            source_client = client.SourceClient("hubspot", "http://api")
            source_client._truncate("page cap reached")
            return None

        module = type("M", (), {"pull": staticmethod(pull_and_truncate)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})

        result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
        detail = result["results"][0]["detail"] or ""
        assert "page cap reached" in detail
        assert result["results"][0]["truncated"] is True

    async def test_notes_from_a_pull_reach_the_stored_detail(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull_with_notes(session, store):
            return {"missing_id": 3}

        module = type("M", (), {"pull": staticmethod(pull_with_notes)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})

        result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
        assert "missing_id=3" in result["results"][0]["detail"]
        assert result["ok"] == 1

    async def test_a_run_is_stamped_from_the_app_clock(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            return None

        module = type("M", (), {"pull": staticmethod(pull)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})

        await sync.run_all(sessionmaker_for_test, ["hubspot"])

        row = (await session.execute(select(SyncRun))).scalar_one()
        assert row.started_at == NOW


class TestOneUnstorableRecordCostsOneRecord:
    async def _run(self, sessionmaker_for_test, monkeypatch, pull):
        module = type("M", (), {"pull": staticmethod(pull)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})
        return await sync.run_all(sessionmaker_for_test, ["hubspot"])

    async def test_the_good_rows_around_it_still_commit(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c1",
                raw_payload={"name": "Good One"},
            )
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c2",
                raw_payload={"name": "Bad\x00Row"},
            )
            await store(
                session,
                source="hubspot",
                object_type="deals",
                source_id="d1",
                raw_payload={"name": "Good Two"},
            )

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)

        stored = (
            await session.execute(select(func.count()).select_from(RawEvent))
        ).scalar_one()
        assert stored == 2, "the whole source rolled back over one record"
        assert result["ok"] == 1

    async def test_the_refusal_is_reported_rather_than_swallowed(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c2",
                raw_payload={"name": "Bad\x00Row"},
            )

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)
        detail = result["results"][0]["detail"] or ""
        assert "refused" in detail
        assert "c2" in detail

    async def test_an_over_long_source_id_is_refused_the_same_way(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="x" * 5000,
                raw_payload={"name": "Too Long"},
            )
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="ok",
                raw_payload={"name": "Fine"},
            )

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)
        stored = (
            await session.execute(select(func.count()).select_from(RawEvent))
        ).scalar_one()
        assert stored == 1
        assert result["ok"] == 1

    async def test_the_detail_names_a_few_and_then_says_how_many(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            for index in range(9):
                await store(
                    session,
                    source="hubspot",
                    object_type="companies",
                    source_id=f"bad{index}",
                    raw_payload={"name": "Bad\x00Row"},
                )

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)
        detail = result["results"][0]["detail"] or ""
        assert "9 record(s) refused" in detail, detail
        assert detail.count("companies/bad") == 5, detail
        assert "companies/bad5" not in detail

    async def test_a_payload_that_is_not_an_object_is_refused_not_diagnosed(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            for payload in (["not", "an", "object"], ["a", "different", "list"]):
                await store(
                    session,
                    source="hubspot",
                    object_type="companies",
                    source_id="c1",
                    raw_payload=payload,
                )

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)
        detail = result["results"][0]["detail"] or ""
        assert result["ok"] == 1, "one source's bad shape is not an outage"
        assert (
            await session.execute(select(func.count()).select_from(RawEvent))
        ).scalar_one() == 0
        assert "2 record(s) refused" in detail, detail
        assert "must be a dict" in detail
        assert "collision" not in detail

    async def test_a_real_failure_still_fails_the_source(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            raise RuntimeError("provider is down")

        result = await self._run(sessionmaker_for_test, monkeypatch, pull)
        assert result["failed"] == 1


class TestReportedCountsMatchWhatSurvived:
    async def test_a_rolled_back_pull_reports_no_rows_written(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c1",
                raw_payload={"name": "Acme"},
            )
            raise RuntimeError("provider dropped the connection")

        module = type("M", (), {"pull": staticmethod(pull)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})

        result = await sync.run_all(sessionmaker_for_test, ["hubspot"])

        stored = (
            await session.execute(select(func.count()).select_from(RawEvent))
        ).scalar_one()
        assert stored == 0
        assert result["results"][0]["rows_written"] == 0
        assert result["results"][0]["ok"] is False

    async def test_a_successful_pull_still_reports_its_rows(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            await store(
                session,
                source="hubspot",
                object_type="companies",
                source_id="c1",
                raw_payload={"name": "Acme"},
            )

        module = type("M", (), {"pull": staticmethod(pull)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})
        result = await sync.run_all(sessionmaker_for_test, ["hubspot"])
        assert result["results"][0]["rows_written"] == 1


class TestTwoRecordsSharingAnIdAreNotSilentlyOne:
    async def _pull_with(self, sessionmaker_for_test, monkeypatch, records):
        async def pull(session, store):
            for source_id, payload in records:
                await store(
                    session,
                    source="hubspot",
                    object_type="companies",
                    source_id=source_id,
                    raw_payload=payload,
                )

        module = type("M", (), {"pull": staticmethod(pull)})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})
        return await sync.run_all(sessionmaker_for_test, ["hubspot"])

    async def test_a_collision_within_one_pull_is_counted(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        result = await self._pull_with(
            sessionmaker_for_test,
            monkeypatch,
            [("D-1", {"name": "Acme"}), ("D-1", {"name": "Globex"})],
        )
        assert result["results"][0]["rows_colliding"] == 1

    async def test_the_collision_names_the_id_in_the_detail(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        result = await self._pull_with(
            sessionmaker_for_test,
            monkeypatch,
            [("D-1", {"name": "Acme"}), ("D-1", {"name": "Globex"})],
        )
        detail = result["results"][0]["detail"] or ""
        assert "D-1" in detail and "collision" in detail.lower()

    async def test_distinct_ids_are_not_a_collision(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        result = await self._pull_with(
            sessionmaker_for_test,
            monkeypatch,
            [("D-1", {"name": "Acme"}), ("D-2", {"name": "Globex"})],
        )
        assert result["results"][0]["rows_colliding"] == 0
        assert "collision" not in (result["results"][0]["detail"] or "").lower()

    async def test_an_identical_repeat_is_not_a_collision(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        result = await self._pull_with(
            sessionmaker_for_test,
            monkeypatch,
            [("D-1", {"name": "Acme"}), ("D-1", {"name": "Acme"})],
        )
        assert result["results"][0]["rows_colliding"] == 0

    async def test_the_examples_stop_at_five_and_the_count_does_not(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        records = []
        for index in range(7):
            records.append((f"D-{index}", {"name": "first"}))
            records.append((f"D-{index}", {"name": "second"}))

        result = await self._pull_with(sessionmaker_for_test, monkeypatch, records)
        detail = result["results"][0]["detail"] or ""
        assert result["results"][0]["rows_colliding"] == 7
        assert "7 id collision(s)" in detail, detail
        assert detail.count("companies/D-") == 5, detail
        assert "companies/D-5" not in detail


def _zoom():
    return importlib.import_module("app.sources.zoom")


class TestZoomMeetingUuidEscaping:
    def test_a_slash_in_a_uuid_is_double_encoded(self):
        assert _zoom().participants_path("/ajXKmvfGQxa9d6bF0Q==") == (
            "/v2/past_meetings/%252FajXKmvfGQxa9d6bF0Q%253D%253D/participants"
        )

    def test_a_double_slash_inside_a_uuid_is_double_encoded(self):
        path = _zoom().participants_path("abc//def==")
        assert "%252F%252F" in path

    def test_an_ordinary_uuid_is_encoded_once(self):
        assert _zoom().participants_path("aDYbmzoNQGGJfSJTMHwCoQ==") == (
            "/v2/past_meetings/aDYbmzoNQGGJfSJTMHwCoQ%3D%3D/participants"
        )

    def test_a_plus_is_escaped(self):
        assert "+" not in _zoom().participants_path("ab+cd==")

    def test_the_uuid_is_never_interpolated_raw(self):
        for uuid in ("/a/b==", "x//y==", "plain=="):
            path = _zoom().participants_path(uuid)
            assert path.startswith("/v2/past_meetings/")
            assert path.endswith("/participants")
            assert path.count("/") == 4, path


class TestTheSourceSwitchGatesSyncing:
    def _recording(self, monkeypatch) -> list[str]:
        synced: list[str] = []

        async def fake_run_connector(source, sessionmaker):
            synced.append(source)
            return {"source": source, "ok": True, "rows_written": 0}

        monkeypatch.setattr(sync, "run_connector", fake_run_connector)
        return synced

    async def test_a_source_with_no_setting_row_is_enabled(self, session):
        assert await sync.disabled_sources(session) == set()

    async def test_syncing_everything_skips_a_disabled_source(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        synced = self._recording(monkeypatch)
        await sync.set_enabled(session, "hubspot", False)
        await session.commit()
        result = await sync.run_all(sessionmaker_for_test)
        assert synced == sorted(set(registry.discover()) - {"hubspot"})
        assert result["ok"] == len(synced)

    async def test_naming_a_disabled_source_raises(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        synced = self._recording(monkeypatch)
        await sync.set_enabled(session, "hubspot", False)
        await session.commit()
        with pytest.raises(sync.SourceDisabled, match="source 'hubspot' is disabled"):
            await sync.run_all(sessionmaker_for_test, ["hubspot"])
        assert synced == []

    async def test_re_enabling_lets_it_sync_again(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        synced = self._recording(monkeypatch)
        off = await sync.set_enabled(session, "hubspot", False)
        await session.commit()
        monkeypatch.setattr(settings, "CLOCK_PINNED_AT", NOW + timedelta(minutes=1))
        on = await sync.set_enabled(session, "hubspot", True)
        await session.commit()
        assert set(on) == {"source", "enabled", "updated_at"}
        assert on["source"] == "hubspot" and on["enabled"] is True
        assert off["updated_at"] == NOW.isoformat()
        assert on["updated_at"] == (NOW + timedelta(minutes=1)).isoformat()
        assert await sync.disabled_sources(session) == set()
        await sync.run_all(sessionmaker_for_test, ["hubspot"])
        assert synced == ["hubspot"]


class TestStatusAnswersThreeDifferentQuestions:
    NOW = datetime(2026, 8, 30, 12, 0, tzinfo=UTC)

    def _run(self, *, ok, rows_written=0, detail=None, minutes_ago=0):
        return SyncRun(
            source="hubspot",
            ok=ok,
            rows_written=rows_written,
            detail=detail,
            started_at=self.NOW - timedelta(minutes=minutes_ago),
        )

    async def _status_row(self, session, source="hubspot"):
        rows = await sync.status(session)
        return next(r for r in rows if r["source"] == source)

    async def test_a_failed_run_bumps_the_attempt_but_not_the_success(self, session):
        session.add(self._run(ok=False, detail="provider is down"))
        await session.flush()
        row = await self._status_row(session)
        assert row["last_attempt"] is not None
        assert row["last_success"] is None
        assert row["last_new_data"] is None

    async def test_an_ok_run_with_no_rows_is_a_success_without_new_data(self, session):
        session.add(self._run(ok=True, rows_written=0))
        await session.flush()
        row = await self._status_row(session)
        assert row["last_success"] == row["last_attempt"]
        assert row["last_new_data"] is None

    async def test_attempts_counts_every_run_regardless_of_outcome(self, session):
        session.add(self._run(ok=False, minutes_ago=30))
        session.add(self._run(ok=True, rows_written=5, minutes_ago=20))
        session.add(self._run(ok=True, rows_written=0, minutes_ago=10))
        await session.flush()
        row = await self._status_row(session)
        assert row["attempts"] == 3
        assert row["last_attempt"] == (self.NOW - timedelta(minutes=10)).isoformat()
        assert row["last_success"] == (self.NOW - timedelta(minutes=10)).isoformat()
        assert row["last_new_data"] == (self.NOW - timedelta(minutes=20)).isoformat()

    async def test_the_detail_is_the_newest_runs_not_an_earlier_ones(self, session):
        session.add(self._run(ok=False, detail="older failure", minutes_ago=60))
        session.add(self._run(ok=True, detail="newest note", minutes_ago=5))
        await session.flush()
        row = await self._status_row(session)
        assert row["detail"] == "newest note"

    async def test_a_never_synced_source_still_appears(self, session):
        rows = await sync.status(session)
        assert [r["source"] for r in rows] == sorted(registry.discover())
        assert len(rows) == 27
        stripe_row = next(r for r in rows if r["source"] == "stripe")
        assert stripe_row == {
            "source": "stripe",
            "last_attempt": None,
            "last_success": None,
            "last_new_data": None,
            "attempts": 0,
            "detail": None,
        }


class TestRetentionIsEnforcedNotJustDeclared:
    async def test_a_sync_run_past_the_window_is_pruned(self, session, monkeypatch):
        monkeypatch.setattr(settings, "SYNC_RUN_RETENTION_DAYS", 30)
        session.add(
            SyncRun(
                source="hubspot",
                ok=True,
                detail="older",
                started_at=NOW - timedelta(days=31),
            )
        )
        session.add(
            SyncRun(
                source="hubspot",
                ok=True,
                detail="inside",
                started_at=NOW - timedelta(days=29),
            )
        )
        await session.flush()

        await sync.prune_sync_runs(session)

        kept = (await session.execute(select(SyncRun))).scalars().all()
        assert [r.detail for r in kept] == ["inside"]
