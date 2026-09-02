import uuid

import pytest
from sqlalchemy import func, select

from app.engine import run
from app.enrichment import reader, vocabulary
from app.enrichment import store as enrichment_store
from app.models import CanonicalAlias, EnrichedFact, EntityCanonical, FactCurrent

TRANSCRIPT = (
    "Jane Smith (Elise): What's blocking you?\n"
    "Bruce Wayne: honestly the pricing is what stalls us internally."
)


@pytest.fixture
def reading():
    return vocabulary.load()["sales_call"]


def result_for(reading, text, *, interest="strong", pain=("pricing",)):
    findings = [
        reader.Finding(
            field="interest",
            label=interest,
            quote="the pricing is what stalls us",
            quote_verified=reader.verify_quote("the pricing is what stalls us", text),
        )
    ]
    findings += [
        reader.Finding(
            field="pain_points",
            label=label,
            quote="honestly the pricing",
            quote_verified=reader.verify_quote("honestly the pricing", text),
        )
        for label in pain
    ]
    return reader.ReadingResult(
        reading=reading.name,
        findings=tuple(findings),
        model="test-model",
        prompt_version=reader.PROMPT_VERSION,
        input_sha=reader.input_sha(text),
        vocabulary_sha=reading.sha,
    )


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


class TestWhatGetsRead:
    async def test_an_entity_with_a_transcript_is_a_candidate(self, session, reading):
        canonical_id = await a_meeting(session)
        found = await enrichment_store.candidates(session, reading)
        assert [cid for cid, _text in found] == [canonical_id]

    async def test_an_entity_already_read_is_skipped(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        assert await enrichment_store.candidates(session, reading) == []

    async def test_a_changed_transcript_is_read_again(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        row = (
            await session.execute(
                select(FactCurrent).where(FactCurrent.canonical_id == canonical_id)
            )
        ).scalar_one()
        row.value = TRANSCRIPT + "\nBruce: one more thing — support is slow."
        await session.commit()
        assert len(await enrichment_store.candidates(session, reading)) == 1

    async def test_a_replaced_vocabulary_makes_every_reading_stale(
        self, session, reading
    ):
        canonical_id = await a_meeting(session)
        stale = result_for(reading, TRANSCRIPT)
        await enrichment_store.write(
            session,
            canonical_id,
            reading,
            reader.ReadingResult(
                **{**stale.__dict__, "vocabulary_sha": "a-retired-vocabulary"}
            ),
        )
        await session.commit()
        assert len(await enrichment_store.candidates(session, reading)) == 1

    async def test_an_entity_with_an_empty_transcript_is_never_read(
        self, session, reading
    ):
        await a_meeting(session, text="   ")
        assert await enrichment_store.candidates(session, reading) == []

    async def test_force_reads_everything_again(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        assert len(await enrichment_store.candidates(session, reading, force=True)) == 1

    async def test_the_limit_bounds_the_bill(self, session, reading):
        for i in range(5):
            await a_meeting(session, seq=i + 1)
        assert len(await enrichment_store.candidates(session, reading, limit=2)) == 2


class TestEveryEligibleEntityIsEventuallyOffered:
    async def _estate(self, session, reading, *, total, already_read):
        made = []
        for n in range(total):
            canonical_id = uuid.uuid4()
            session.add(
                EntityCanonical(
                    canonical_id=canonical_id,
                    entity_type="meeting",
                    anchor_key=f"zoom|meeting|m{n:04d}",
                    minted_seq=n,
                    member_count=1,
                )
            )
            session.add(
                FactCurrent(
                    canonical_id=canonical_id,
                    entity_type="meeting",
                    attr="transcript",
                    value=f"call {n}",
                    observed_at=func.now(),
                )
            )
            made.append((n, canonical_id))
        for n, canonical_id in made[:already_read]:
            session.add(
                EnrichedFact(
                    canonical_id=canonical_id,
                    entity_type="meeting",
                    reading=reading.name,
                    attr="interest",
                    value="strong",
                    quote="q",
                    quote_verified=True,
                    input_sha=reader.input_sha(f"call {n}"),
                    vocabulary_sha=reading.sha,
                    model="m",
                    prompt_version=reader.PROMPT_VERSION,
                )
            )
        await session.commit()
        return made

    async def test_entities_past_the_first_page_are_still_offered(
        self, session, reading
    ):
        await self._estate(session, reading, total=250, already_read=200)
        pending = await enrichment_store.candidates(session, reading)
        assert len(pending) == 50

    async def test_the_ones_offered_are_the_unread_ones(self, session, reading):
        made = await self._estate(session, reading, total=250, already_read=200)
        pending = await enrichment_store.candidates(session, reading)
        assert {cid for cid, _text in pending} == {c for _n, c in made[200:]}

    async def test_a_limit_still_bounds_the_bill(self, session, reading):
        await self._estate(session, reading, total=250, already_read=200)
        assert len(await enrichment_store.candidates(session, reading, limit=10)) == 10

    async def test_a_fully_read_estate_offers_nothing(self, session, reading):
        await self._estate(session, reading, total=250, already_read=250)
        assert await enrichment_store.candidates(session, reading) == []


class TestWhatGetsWritten:
    async def test_one_row_per_label(self, session, reading):
        canonical_id = await a_meeting(session)
        written = await enrichment_store.write(
            session,
            canonical_id,
            reading,
            result_for(reading, TRANSCRIPT, pain=("pricing", "manual_work")),
        )
        await session.commit()
        assert written == 3
        rows = (await session.execute(select(EnrichedFact))).scalars().all()
        assert {(r.attr, r.value) for r in rows} == {
            ("interest", "strong"),
            ("pain_points", "pricing"),
            ("pain_points", "manual_work"),
        }

    async def test_every_row_records_what_produced_it(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        row = (await session.execute(select(EnrichedFact))).scalars().first()
        assert row.model == "test-model"
        assert row.prompt_version == reader.PROMPT_VERSION
        assert row.vocabulary_sha == reading.sha
        assert row.input_sha == reader.input_sha(TRANSCRIPT)

    async def test_the_verification_verdict_is_stored_per_row(self, session, reading):
        canonical_id = await a_meeting(session)
        result = reader.ReadingResult(
            reading=reading.name,
            model="test-model",
            prompt_version=reader.PROMPT_VERSION,
            input_sha=reader.input_sha(TRANSCRIPT),
            vocabulary_sha=reading.sha,
            findings=(
                reader.Finding("interest", "strong", "honestly the pricing", True),
                reader.Finding("pain_points", "pricing", "composed", False),
            ),
        )
        await enrichment_store.write(session, canonical_id, reading, result)
        await session.commit()
        verdicts = {
            r.value: r.quote_verified
            for r in (await session.execute(select(EnrichedFact))).scalars().all()
        }
        assert verdicts == {"strong": True, "pricing": False}

    async def test_a_re_read_replaces_rather_than_accumulates(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session,
            canonical_id,
            reading,
            result_for(reading, TRANSCRIPT, interest="strong", pain=("pricing",)),
        )
        await session.commit()
        await enrichment_store.write(
            session,
            canonical_id,
            reading,
            result_for(reading, TRANSCRIPT, interest="weak", pain=("manual_work",)),
        )
        await session.commit()
        rows = (await session.execute(select(EnrichedFact))).scalars().all()
        assert {(r.attr, r.value) for r in rows} == {
            ("interest", "weak"),
            ("pain_points", "manual_work"),
        }

    async def test_reading_it_back_marks_it_inferred(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        facts = await enrichment_store.for_entity(session, canonical_id)
        assert {f["value"] for f in facts} == {"strong", "pricing"}
        assert all(f["model"] == "test-model" for f in facts)


class TestAnOrphanedReadingIsKeptRatherThanDestroyed:
    async def _orphan(self, session, reading):
        session.add(
            EnrichedFact(
                canonical_id=uuid.uuid4(),
                entity_type="meeting",
                reading=reading.name,
                attr="interest",
                value="strong",
                quote="q",
                quote_verified=True,
                input_sha="x",
                vocabulary_sha=reading.sha,
                model="test-model",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        await session.commit()

    async def test_an_orphan_survives_reconciliation(self, session, reading):
        await self._orphan(session, reading)
        await enrichment_store.reconcile(session, reading)
        assert (
            await session.execute(select(func.count()).select_from(EnrichedFact))
        ).scalar_one() == 1

    async def test_an_orphan_does_not_inflate_coverage(self, session, reading):
        read_one = await a_meeting(session, seq=1)
        await enrichment_store.write(
            session, read_one, reading, result_for(reading, TRANSCRIPT)
        )
        await self._orphan(session, reading)

        coverage = await enrichment_store.coverage(session, reading)
        assert coverage["read_under_current_vocabulary"] == 1

    async def test_a_merged_away_reading_still_folds_onto_the_survivor(
        self, session, reading
    ):
        survivor = await a_meeting(session, seq=1)
        retired = uuid.uuid4()
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=survivor, reason="merged")
        )
        session.add(
            EnrichedFact(
                canonical_id=retired,
                entity_type="meeting",
                reading=reading.name,
                attr="interest",
                value="strong",
                quote="q",
                quote_verified=True,
                input_sha="x",
                vocabulary_sha=reading.sha,
                model="test-model",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        await session.commit()

        assert await enrichment_store.reconcile(session, reading) == 1
        row = (await session.execute(select(EnrichedFact))).scalars().one()
        assert row.canonical_id == survivor


class TestTheInvariantThatMattersMost:
    async def test_a_rebuild_does_not_delete_a_reading(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()

        await run.rebuild(session, run_checks=False)

        surviving = (
            await session.execute(select(func.count()).select_from(EnrichedFact))
        ).scalar_one()
        assert surviving == 2

    async def test_the_reading_survives_even_when_its_entity_does_not(
        self, session, reading
    ):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        await run.rebuild(session, run_checks=False)
        rows = await enrichment_store.for_entity(session, canonical_id)
        assert len(rows) == 2


class TestDefectsFoundInReview:
    async def test_a_reading_under_a_merged_id_folds_onto_the_survivor(
        self, session, reading
    ):
        survivor = await a_meeting(session, seq=1)
        retired = uuid.uuid4()
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=survivor, reason="merged")
        )
        session.add(
            EnrichedFact(
                canonical_id=retired,
                entity_type="meeting",
                reading=reading.name,
                attr="interest",
                value="strong",
                quote="q",
                quote_verified=True,
                input_sha="x",
                vocabulary_sha=reading.sha,
                model="test-model",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        await session.commit()

        moved = await enrichment_store.reconcile(session, reading)

        assert moved == 1
        rows = (await session.execute(select(EnrichedFact))).scalars().all()
        assert [r.canonical_id for r in rows] == [survivor]

    async def test_a_reading_whose_entity_vanished_entirely_is_kept(
        self, session, reading
    ):
        session.add(
            EnrichedFact(
                canonical_id=uuid.uuid4(),
                entity_type="meeting",
                reading=reading.name,
                attr="interest",
                value="strong",
                quote="q",
                quote_verified=True,
                input_sha="x",
                vocabulary_sha=reading.sha,
                model="test-model",
                prompt_version=reader.PROMPT_VERSION,
            )
        )
        await session.commit()
        assert await enrichment_store.reconcile(session, reading) == 0
        assert (
            await session.execute(select(func.count()).select_from(EnrichedFact))
        ).scalar_one() == 1

    async def test_two_readings_may_share_a_field_name(self, session, reading):
        canonical_id = await a_meeting(session)
        await enrichment_store.write(
            session, canonical_id, reading, result_for(reading, TRANSCRIPT)
        )
        other = vocabulary.Reading(
            name="support_call",
            entity="meeting",
            input_attr="transcript",
            description="",
            fields=reading.fields,
            origin="test",
            sha="other-sha",
        )
        await enrichment_store.write(
            session, canonical_id, other, result_for(other, TRANSCRIPT)
        )
        await session.commit()
        rows = (await session.execute(select(EnrichedFact))).scalars().all()
        assert {(r.reading, r.attr, r.value) for r in rows} == {
            ("sales_call", "interest", "strong"),
            ("sales_call", "pain_points", "pricing"),
            ("support_call", "interest", "strong"),
            ("support_call", "pain_points", "pricing"),
        }

    async def test_reading_back_a_merged_id_still_answers(self, session, reading):
        survivor = await a_meeting(session)
        retired = uuid.uuid4()
        session.add(
            CanonicalAlias(alias_id=retired, canonical_id=survivor, reason="merged")
        )
        await enrichment_store.write(
            session, survivor, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()
        assert len(await enrichment_store.for_entity(session, retired)) == 2

    async def test_a_zero_limit_reads_nothing(self, session, reading):
        await a_meeting(session)
        assert await enrichment_store.candidates(session, reading, limit=0) == []

    async def test_coverage_separates_never_read_from_nothing_found(
        self, session, reading
    ):
        read_one = await a_meeting(session, seq=1)
        await a_meeting(session, text="a different transcript entirely", seq=2)
        await enrichment_store.write(
            session, read_one, reading, result_for(reading, TRANSCRIPT)
        )
        await session.commit()

        coverage = await enrichment_store.coverage(session, reading)
        assert coverage["eligible"] == 2
        assert coverage["read_under_current_vocabulary"] == 1
        assert coverage["never_read"] == 1

    async def test_a_retired_vocabulary_is_counted_apart_not_mixed_in(
        self, session, reading
    ):
        canonical_id = await a_meeting(session)
        stale = result_for(reading, TRANSCRIPT)
        await enrichment_store.write(
            session,
            canonical_id,
            reading,
            reader.ReadingResult(
                **{**stale.__dict__, "vocabulary_sha": "a-retired-vocabulary"}
            ),
        )
        await session.commit()
        coverage = await enrichment_store.coverage(session, reading)
        assert coverage["read_under_current_vocabulary"] == 0
        assert coverage["read_under_a_retired_vocabulary"] == 1
