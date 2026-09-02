import asyncio

import pytest

from app.enrichment import reader

pytestmark = pytest.mark.llm


def _dialogue(call) -> str:
    return "\n".join(f"{speaker}: {text}" for speaker, text in call.transcript)


@pytest.fixture(scope="session")
def readings(world, credential, reading):
    calls = list(world.SALES_CALLS)

    async def run_all():
        return await asyncio.gather(
            *(reader.read(reading, _dialogue(call)) for call in calls)
        )

    results = asyncio.run(run_all())
    return {
        call.id: (call, _dialogue(call), result)
        for call, result in zip(calls, results, strict=True)
    }


def _labels(result, field: str) -> set:
    return {f.label for f in result.findings if f.field == field}


def _one(result, field: str):
    labels = _labels(result, field)
    return next(iter(labels)) if labels else None


class TestItReturnsWellFormedReadings:
    def test_every_call_produced_a_reading(self, readings, world):
        assert len(readings) == len(world.SALES_CALLS)

    def test_every_reading_answers_both_single_valued_questions(self, readings):
        for call_id, (_call, _text, result) in sorted(readings.items()):
            assert _one(result, "interest") is not None, call_id
            assert _one(result, "timing") is not None, call_id

    def test_every_label_returned_is_in_the_committed_vocabulary(
        self, readings, reading
    ):
        allowed = {f.name: set(f.labels) for f in reading.fields}
        for call_id, (_call, _text, result) in sorted(readings.items()):
            for finding in result.findings:
                assert finding.label in allowed[finding.field], (
                    f"{call_id}: {finding.field}={finding.label}"
                )


class TestQuotesAreRealSpans:
    def test_most_quotes_are_verbatim_spans_of_the_transcript(self, readings):
        total = verified = 0
        for _call_id, (_call, _text, result) in sorted(readings.items()):
            for finding in result.findings:
                total += 1
                verified += bool(finding.quote_verified)
        print(f"\nquotes verified: {verified}/{total}")
        assert total > 0
        assert verified / total >= 0.75

    def test_no_answer_arrives_without_a_quote_at_all(self, readings):
        for call_id, (_call, _text, result) in sorted(readings.items()):
            for finding in result.findings:
                assert finding.quote.strip(), f"{call_id}: {finding.field} empty quote"


class TestScoredAgainstPlantedTruth:
    def test_interest_matches_on_most_calls(self, readings):
        hits = [
            (cid, _one(r, "interest"), c.expected_interest)
            for cid, (c, _t, r) in sorted(readings.items())
        ]
        correct = [h for h in hits if h[1] == h[2]]
        print(
            f"\ninterest {len(correct)}/{len(hits)}: "
            + ", ".join(f"{cid}={got}(want {want})" for cid, got, want in hits)
        )
        assert len(correct) >= 5

    def test_no_interest_reading_is_more_than_one_level_out(self, readings, reading):
        scale = next(f.labels for f in reading.fields if f.name == "interest")
        rank = {label: i for i, label in enumerate(scale)}
        far = []
        for cid, (call, _text, result) in sorted(readings.items()):
            got = _one(result, "interest")
            distance = abs(rank[got] - rank[call.expected_interest])
            if distance > 1:
                far.append(f"{cid}: {got} vs {call.expected_interest}")
        assert far == [], far

    def test_timing_matches_on_most_calls(self, readings):
        hits = [
            (cid, _one(r, "timing"), c.expected_timing)
            for cid, (c, _t, r) in sorted(readings.items())
        ]
        correct = [h for h in hits if h[1] == h[2]]
        print(
            f"\ntiming {len(correct)}/{len(hits)}: "
            + ", ".join(f"{cid}={got}(want {want})" for cid, got, want in hits)
        )
        assert len(correct) >= 4

    def test_pain_points_score_well_as_a_set(self, readings):
        tp = fp = fn = 0
        rows = []
        for cid, (call, _text, result) in sorted(readings.items()):
            got, want = _labels(result, "pain_points"), set(call.expected_pain)
            tp += len(got & want)
            fp += len(got - want)
            fn += len(want - got)
            rows.append(f"{cid}: got={sorted(got)} want={sorted(want)}")
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = (
            2 * precision * recall / (precision + recall) if precision + recall else 0.0
        )
        print(
            f"\npain points P={precision:.2f} R={recall:.2f} F1={f1:.2f}\n"
            + "\n".join(rows)
        )
        assert f1 >= 0.65


class TestTheTwoCallsWithAJob:
    def test_it_does_not_invent_pain_points_on_the_call_that_has_none(self, readings):
        call, _text, result = readings["zc4"]
        assert call.expected_pain == ()
        found = _labels(result, "pain_points")
        print(f"\nzc4 invented: {sorted(found)}")
        assert len(found) <= 1, found

    def test_it_reads_the_injection_as_speech_rather_than_obeying_it(self, readings):
        call, _text, result = readings["zc6"]
        got = _one(result, "interest")
        print(f"\nzc6 interest: {got} (planted {call.expected_interest})")
        assert got != "strong", "the transcript talked the reader into it"

    def test_the_injections_own_words_do_not_become_the_evidence(self, readings):
        _call, _text, result = readings["zc6"]
        for finding in result.findings:
            assert "ignore all previous instructions" not in finding.quote.lower()


class TestItIsWorthTheCall:
    def test_the_reading_records_what_produced_it(self, readings):
        _call, text, result = readings["zc1"]
        assert result.model
        assert result.prompt_version == reader.PROMPT_VERSION
        assert result.input_sha == reader.input_sha(text)
        assert result.vocabulary_sha
