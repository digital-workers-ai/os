from datetime import UTC, datetime, timedelta

from app.connectors import client, hubspot, registry
from sqlalchemy import func, select

from app import sync
from app.config import settings
from app.models import PullManifest, RawEvent, SyncRun


class TestObjectClass:
    def test_record_class_is_the_default(self):
        assert sync.object_class(hubspot, "companies") == "record"

    def test_an_undeclared_object_type_defaults_to_record(self):
        assert sync.object_class(hubspot, "charges") == "record"

    def test_a_module_declaring_nothing_still_answers(self):
        class Bare:
            pass

        assert sync.object_class(Bare, "anything") == "record"


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

    async def test_a_truncated_pull_refuses_to_write_a_manifest(
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
        assert "no manifest written" in detail
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


class TestAPullThatFoundNothingStillSaysSo:
    async def _run(self, sessionmaker_for_test, monkeypatch, pull, **attrs):
        module = type("M", (), {"pull": staticmethod(pull), **attrs})
        monkeypatch.setattr(registry, "discover", lambda: {"hubspot": module})
        return await sync.run_all(sessionmaker_for_test, ["hubspot"])

    async def test_an_empty_record_pull_writes_an_empty_manifest(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            return None

        await self._run(
            sessionmaker_for_test,
            monkeypatch,
            pull,
            OBJECT_CLASS={"companies": "record"},
        )

        rows = (await session.execute(select(PullManifest))).scalars().all()
        assert [r.object_type for r in rows] == ["companies"]
        assert rows[0].source_ids == []

    async def test_an_event_stream_still_writes_none(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            return None

        await self._run(
            sessionmaker_for_test,
            monkeypatch,
            pull,
            OBJECT_CLASS={"activities": "event"},
        )
        assert (
            await session.execute(select(func.count()).select_from(PullManifest))
        ).scalar_one() == 0

    async def test_a_truncated_pull_still_writes_nothing(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        async def pull(session, store):
            client.SourceClient("hubspot", "http://api").truncate("cap")

        await self._run(
            sessionmaker_for_test,
            monkeypatch,
            pull,
            OBJECT_CLASS={"companies": "record"},
        )
        assert (
            await session.execute(select(func.count()).select_from(PullManifest))
        ).scalar_one() == 0


class TestThePullManifestIsPrunedLikeEveryOtherLog:
    async def test_only_the_newest_manifests_survive(self, session, monkeypatch):
        monkeypatch.setattr(settings, "PULL_MANIFEST_RETENTION", 2)
        for n in range(5):
            session.add(
                PullManifest(
                    source="hubspot", object_type="companies", source_ids=[f"c{n}"]
                )
            )
        await session.flush()

        await sync.prune_pull_manifests(session)

        kept = (await session.execute(select(PullManifest))).scalars().all()
        assert [r.source_ids for r in kept] == [["c3"], ["c4"]]

    async def test_each_identity_keeps_its_own_history(self, session, monkeypatch):
        monkeypatch.setattr(settings, "PULL_MANIFEST_RETENTION", 1)
        for n in range(3):
            session.add(
                PullManifest(
                    source="hubspot", object_type="companies", source_ids=[f"c{n}"]
                )
            )
        session.add(
            PullManifest(source="stripe", object_type="customers", source_ids=["cus_1"])
        )
        await session.flush()

        await sync.prune_pull_manifests(session)

        kept = {
            (r.source, r.object_type): r.source_ids
            for r in (await session.execute(select(PullManifest))).scalars().all()
        }
        assert kept == {
            ("hubspot", "companies"): ["c2"],
            ("stripe", "customers"): ["cus_1"],
        }


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

        module = type(
            "M",
            (),
            {"pull": staticmethod(pull), "OBJECT_CLASS": {"companies": "record"}},
        )
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


class TestRetentionIsEnforcedNotJustDeclared:
    async def test_a_sync_run_past_the_window_is_pruned(self, session, monkeypatch):
        monkeypatch.setattr(settings, "SYNC_RUN_RETENTION_DAYS", 30)
        now = datetime.now(UTC)
        session.add(
            SyncRun(
                source="hubspot",
                ok=True,
                detail="older",
                started_at=now - timedelta(days=31),
            )
        )
        session.add(
            SyncRun(
                source="hubspot",
                ok=True,
                detail="inside",
                started_at=now - timedelta(days=29),
            )
        )
        await session.flush()

        await sync.prune_sync_runs(session)

        kept = (await session.execute(select(SyncRun))).scalars().all()
        assert [r.detail for r in kept] == ["inside"]
