import uuid

import pytest
from sqlalchemy import func, select

from app import llm
from app.config import settings
from app.enrichment import reader, vocabulary
from app.enrichment import store as enrichment_store
from app.models import (
    CanonicalAlias,
    EnrichedFact,
    EnrichmentRun,
    EntityCanonical,
    FactCurrent,
)

TRANSCRIPT = (
    "Jane Smith (Elise): What's blocking you?\n"
    "Bruce Wayne: honestly the pricing is what stalls us internally."
)


@pytest.fixture
def reading():
    return vocabulary.load()["sales_call"]


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", True)


async def a_meeting(session, text=TRANSCRIPT, seq=1):
    canonical_id = uuid.uuid4()
    session.add(
        EntityCanonical(
            canonical_id=canonical_id,
            entity_type="meeting",
            anchor_key=f"zoom|meeting|test-{seq}",
            minted_seq=seq,
            member_count=1,
        )
    )
    session.add(
        FactCurrent(
            canonical_id=canonical_id,
            entity_type="meeting",
            attr="transcript",
            value=text,
            observed_at=func.now(),
        )
    )
    await session.commit()
    return canonical_id


def a_result(reading, text, *, labels=("pricing",)):
    findings = tuple(
        reader.Finding(
            field="pain_points",
            label=label,
            quote="honestly the pricing",
            quote_verified=reader.verify_quote("honestly the pricing", text),
        )
        for label in labels
    )
    return reader.ReadingResult(
        reading=reading.name,
        findings=findings,
        model="test-model",
        prompt_version=reader.PROMPT_VERSION,
        input_sha=reader.input_sha(text),
        vocabulary_sha=reading.sha,
    )


@pytest.fixture
def scripted_reader(monkeypatch, reading):
    def _install(*outcomes):
        queue = list(outcomes)

        async def fake_read_many(rd, texts, **kwargs):
            return [queue.pop(0) if queue else a_result(rd, text) for text in texts]

        monkeypatch.setattr(reader, "read_many", fake_read_many)

    return _install


class TestTheGate:
    async def test_the_layer_refuses_while_it_is_off(self, session, monkeypatch):
        monkeypatch.setattr(settings, "ENRICHMENT_ENABLED", False)
        with pytest.raises(
            enrichment_store.EnrichmentError, match="ENRICHMENT_ENABLED"
        ):
            await enrichment_store.enrich(session)

    async def test_an_unknown_reading_is_named(self, session, enabled):
        with pytest.raises(enrichment_store.EnrichmentError, match="no reading named"):
            await enrichment_store.enrich(session, reading_name="not_a_reading")

    async def test_a_second_concurrent_run_is_refused_not_queued(
        self, session, enabled, sessionmaker_for_test
    ):
        await a_meeting(session)
        async with sessionmaker_for_test() as holder:
            await holder.execute(
                select(func.pg_try_advisory_xact_lock(enrichment_store._LOCK_ID))
            )
            with pytest.raises(
                enrichment_store.EnrichmentError, match="already in progress"
            ):
                await enrichment_store.enrich(session)


class TestARun:
    async def test_an_empty_estate_is_a_run_that_read_nothing(
        self, session, enabled, scripted_reader
    ):
        scripted_reader()
        report = await enrichment_store.enrich(session)
        assert report["calls"] == 0 and report["rows"] == 0
        assert report["readings"]

    async def test_a_transcript_is_read_and_its_labels_stored(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session)
        scripted_reader(a_result(reading, TRANSCRIPT))
        report = await enrichment_store.enrich(session, reading_name="sales_call")
        assert report["readings"]["sales_call"]["read"] == 1
        assert report["rows"] >= 1
        stored = (await session.execute(select(EnrichedFact))).scalars().all()
        assert {f.value for f in stored} == {"pricing"}

    async def test_every_run_leaves_a_row_recording_what_produced_it(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session)
        scripted_reader(a_result(reading, TRANSCRIPT))
        await enrichment_store.enrich(session, reading_name="sales_call")
        runs = (await session.execute(select(EnrichmentRun))).scalars().all()
        assert len(runs) == 1
        assert runs[0].vocabulary_sha == reading.sha
        assert runs[0].prompt_version == reader.PROMPT_VERSION

    async def test_a_second_pass_re_reads_nothing(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session)
        scripted_reader(a_result(reading, TRANSCRIPT))
        await enrichment_store.enrich(session, reading_name="sales_call")
        scripted_reader()
        second = await enrichment_store.enrich(session, reading_name="sales_call")
        assert second["readings"]["sales_call"]["pending"] == 0

    async def test_force_re_reads_anyway(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session)
        scripted_reader(a_result(reading, TRANSCRIPT))
        await enrichment_store.enrich(session, reading_name="sales_call")
        scripted_reader(a_result(reading, TRANSCRIPT))
        second = await enrichment_store.enrich(
            session, reading_name="sales_call", force=True
        )
        assert second["readings"]["sales_call"]["read"] == 1


class TestOneBadTranscriptCostsOneTranscript:
    async def test_a_read_error_is_counted_not_raised(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session, seq=1)
        await a_meeting(session, seq=2)
        scripted_reader(
            reader.ReadError("sales_call: model declined"),
            a_result(reading, TRANSCRIPT),
        )
        report = await enrichment_store.enrich(session, reading_name="sales_call")
        per = report["readings"]["sales_call"]
        assert per["failed"] == 1 and per["read"] == 1
        assert any("declined" in e for e in per["errors"])

    async def test_only_the_first_few_errors_are_kept(
        self, session, enabled, scripted_reader
    ):
        for seq in range(8):
            await a_meeting(session, seq=seq)
        scripted_reader(*[reader.ReadError(f"failure {n}") for n in range(8)])
        report = await enrichment_store.enrich(session, reading_name="sales_call")
        per = report["readings"]["sales_call"]
        assert per["failed"] == 8
        assert len(per["errors"]) == 5

    async def test_a_row_the_database_rejects_is_counted_not_raised(
        self, session, enabled, scripted_reader, monkeypatch, reading
    ):
        from sqlalchemy.exc import IntegrityError

        await a_meeting(session, seq=1)
        scripted_reader(a_result(reading, TRANSCRIPT))

        async def refuse(*args, **kwargs):
            raise IntegrityError("INSERT", {}, Exception("duplicate key"))

        monkeypatch.setattr(enrichment_store, "write", refuse)
        report = await enrichment_store.enrich(session, reading_name="sales_call")
        per = report["readings"]["sales_call"]
        assert per["failed"] == 1 and per["read"] == 0
        assert any("duplicate key" in e for e in per["errors"])

    async def test_a_failed_row_leaves_the_others_committed(
        self, session, enabled, scripted_reader, reading
    ):
        await a_meeting(session, seq=1)
        await a_meeting(session, seq=2)
        scripted_reader(reader.ReadError("nope"), a_result(reading, TRANSCRIPT))
        await enrichment_store.enrich(session, reading_name="sales_call")
        assert (
            await session.execute(select(func.count()).select_from(EnrichedFact))
        ).scalar_one() >= 1


class TestTheCap:
    async def test_the_run_stops_at_the_cap_and_says_so(
        self, session, enabled, scripted_reader, reading
    ):
        for seq in range(3):
            await a_meeting(session, seq=seq)
        scripted_reader(*[a_result(reading, TRANSCRIPT) for _ in range(3)])
        report = await enrichment_store.enrich(
            session, reading_name="sales_call", limit=1
        )
        per = report["readings"]["sales_call"]
        assert per["pending"] == 1
        assert per["truncated_at_cap"] is True

    async def test_the_default_cap_comes_from_settings(
        self, session, enabled, scripted_reader, monkeypatch, reading
    ):
        monkeypatch.setattr(settings, "ENRICHMENT_MAX_CALLS_PER_RUN", 1)
        for seq in range(2):
            await a_meeting(session, seq=seq)
        scripted_reader(*[a_result(reading, TRANSCRIPT) for _ in range(2)])
        report = await enrichment_store.enrich(session)
        assert report.get("truncated_at_cap") is True


class TestReconciliation:
    async def test_a_reading_under_a_merged_id_moves_to_the_survivor(
        self, session, enabled, reading
    ):
        survivor = await a_meeting(session, seq=1)
        retired = uuid.uuid4()
        session.add(
            EnrichedFact(
                canonical_id=retired,
                entity_type="meeting",
                reading=reading.name,
                attr="pain_points",
                value="pricing",
                quote="q",
                quote_verified=True,
                input_sha="a" * 64,
                vocabulary_sha=reading.sha,
                model="m",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=survivor, reason="merged")
        )
        await session.commit()

        moved = await enrichment_store.reconcile(session, reading)
        assert moved == 1
        row = (await session.execute(select(EnrichedFact))).scalars().one()
        assert row.canonical_id == survivor

    async def test_a_clashing_reading_is_dropped_rather_than_duplicated(
        self, session, enabled, reading
    ):
        survivor = await a_meeting(session, seq=1)
        retired = uuid.uuid4()
        for owner in (survivor, retired):
            session.add(
                EnrichedFact(
                    canonical_id=owner,
                    entity_type="meeting",
                    reading=reading.name,
                    attr="pain_points",
                    value="pricing",
                    quote="q",
                    quote_verified=True,
                    input_sha="a" * 64,
                    vocabulary_sha=reading.sha,
                    model="m",
                    prompt_version=reader.PROMPT_VERSION,
                )
            )
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=survivor, reason="merged")
        )
        await session.commit()

        await enrichment_store.reconcile(session, reading)
        rows = (await session.execute(select(EnrichedFact))).scalars().all()
        assert len(rows) == 1

    async def test_an_orphan_with_no_alias_is_kept_and_not_counted(
        self, session, reading
    ):
        session.add(
            EnrichedFact(
                canonical_id=uuid.uuid4(),
                entity_type="meeting",
                reading=reading.name,
                attr="pain_points",
                value="pricing",
                quote="q",
                quote_verified=True,
                input_sha="a" * 64,
                vocabulary_sha=reading.sha,
                model="m",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        await session.commit()
        assert await enrichment_store.reconcile(session, reading) == 0
        assert (
            await session.execute(select(func.count()).select_from(EnrichedFact))
        ).scalar_one() == 1

    async def test_nothing_stored_is_nothing_to_reconcile(self, session, reading):
        assert await enrichment_store.reconcile(session, reading) == 0

    async def test_an_alias_cycle_terminates_rather_than_hanging(self, session):
        first, second = uuid.uuid4(), uuid.uuid4()
        session.add(
            CanonicalAlias(alias_id=first, canonical_id=second, reason="merged")
        )
        session.add(
            CanonicalAlias(alias_id=second, canonical_id=first, reason="merged")
        )
        await session.commit()
        assert await enrichment_store.resolve_alias(session, first) in (first, second)

    async def test_an_id_with_no_alias_resolves_to_itself(self, session):
        lone = uuid.uuid4()
        assert await enrichment_store.resolve_alias(session, lone) == lone


class TestReadOne:
    async def test_empty_text_is_refused_before_any_model_call(self, reading):
        with pytest.raises(reader.ReadError, match="nothing to read"):
            await reader.read(reading, "   ")

    async def test_a_wire_error_becomes_a_read_error_naming_the_reading(
        self, reading, monkeypatch
    ):
        async def boom(**kwargs):
            raise llm.LLMError("upstream down")

        monkeypatch.setattr(llm, "parse", boom)
        with pytest.raises(reader.ReadError, match="sales_call: upstream down"):
            await reader.read(reading, TRANSCRIPT)

    async def test_a_reading_records_the_model_that_answered(
        self, reading, monkeypatch
    ):
        class Parsed:
            pain_points = interest = None

        async def fake_parse(**kwargs):
            return Parsed(), "claude-actual"

        monkeypatch.setattr(llm, "parse", fake_parse)
        result = await reader.read(reading, TRANSCRIPT)
        assert result.model == "claude-actual"
        assert result.vocabulary_sha == reading.sha
        assert result.input_sha == reader.input_sha(TRANSCRIPT)


class TestOneUnexpectedFailureDoesNotDiscardThePaidBatch:
    async def test_an_unexpected_error_costs_one_read_not_the_batch(
        self, reading, monkeypatch
    ):
        calls = {"n": 0}

        async def flaky(rd, text, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise ValueError("1 validation error for SalesCallReading")
            return a_result(rd, text)

        monkeypatch.setattr(reader, "read", flaky)
        results = await reader.read_many(reading, ["a", "b", "c"])

        assert len(results) == 3
        assert isinstance(results[1], reader.ReadError)
        assert all(
            isinstance(r, reader.ReadingResult) for r in (results[0], results[2])
        )

    async def test_the_surviving_reads_are_still_written(
        self, session, enabled, monkeypatch, reading
    ):
        await a_meeting(session, seq=1)
        await a_meeting(session, seq=2)
        calls = {"n": 0}

        async def flaky(rd, texts, **kwargs):
            out = []
            for text in texts:
                calls["n"] += 1
                out.append(
                    ValueError("boom") if calls["n"] == 1 else a_result(rd, text)
                )
            return [
                reader.ReadError(str(o)) if isinstance(o, ValueError) else o
                for o in out
            ]

        monkeypatch.setattr(reader, "read_many", flaky)
        report = await enrichment_store.enrich(session, reading_name="sales_call")
        assert report["readings"]["sales_call"]["read"] == 1
        assert report["readings"]["sales_call"]["failed"] == 1

    async def test_a_schema_failure_from_the_sdk_becomes_a_read_error(
        self, reading, monkeypatch
    ):
        async def bad_parse(**kwargs):
            raise ValueError("1 validation error for SalesCallReading")

        monkeypatch.setattr(llm, "parse", bad_parse)
        with pytest.raises(reader.ReadError):
            await reader.read(reading, TRANSCRIPT)


class TestReadMany:
    async def test_one_declined_transcript_does_not_abandon_the_rest(
        self, reading, monkeypatch
    ):
        calls = {"n": 0}

        async def flaky(rd, text, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                raise reader.ReadError("declined")
            return a_result(rd, text)

        monkeypatch.setattr(reader, "read", flaky)
        results = await reader.read_many(reading, ["a", "b", "c"])
        assert len(results) == 3
        assert isinstance(results[0], reader.ReadError)
        assert all(isinstance(r, reader.ReadingResult) for r in results[1:])

    async def test_results_come_back_in_the_order_they_went_in(
        self, reading, monkeypatch
    ):
        async def echo(rd, text, **kwargs):
            return a_result(rd, text, labels=(text,))

        monkeypatch.setattr(reader, "read", echo)
        results = await reader.read_many(reading, ["one", "two", "three"])
        assert [r.findings[0].label for r in results] == ["one", "two", "three"]

    async def test_nothing_to_read_is_an_empty_list(self, reading):
        assert await reader.read_many(reading, []) == []
