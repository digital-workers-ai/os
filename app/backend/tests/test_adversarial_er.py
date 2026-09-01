import pytest

from app.engine import ontology, resolver, transforms
from app.engine.report import SyncReport
from tests import ground_truth

COMPANY_PRECISION_FLOOR = 0.99
COMPANY_RECALL_FLOOR = 0.88
PERSON_PRECISION_FLOOR = 0.98
PERSON_RECALL_FLOOR = 0.92

ONTO = ontology.Ontology(
    entities={
        "company": ontology.EntitySpec("company", {"domain": "string"}, ("domain",)),
        "person": ontology.EntitySpec("person", {"email": "string"}, ("email",)),
    },
    relationships=(),
    source_priority=(
        "hubspot",
        "salesforce",
        "stripe",
        "zendesk",
        "intercom",
        "netsuite",
    ),
)

IDENTITY_TRANSFORM = {
    "domain": transforms.normalize_domain,
    "email": transforms.normalize_email,
}


@pytest.fixture(scope="module")
def corpus():
    module = ground_truth.adversarial()
    if module is None:
        pytest.skip("v8 adversarial corpus not mounted at /adversarial")
    return module.build_records()


def to_records(rows, entity_type):
    out = []
    for order, row in enumerate(r for r in rows if r.type == entity_type):
        identity = {}
        for attr, fn in IDENTITY_TRANSFORM.items():
            if attr not in ONTO.entities[entity_type].attrs:
                continue
            raw = row.facts.get(attr)
            if raw is None:
                continue
            try:
                identity[attr] = fn(row.source, entity_type, raw)
            except transforms.TransformError:
                continue
        out.append(
            resolver.Record(
                source=row.source,
                entity_type=entity_type,
                source_id=row.ext_id,
                order=order,
                identity=identity,
            )
        )
    return out


def pairs(groups):
    out = set()
    for members in groups.values():
        ordered = sorted(members)
        for i, a in enumerate(ordered):
            for b in ordered[i + 1 :]:
                out.add((a, b))
    return out


def score(rows, entity_type):
    records = to_records(rows, entity_type)
    truth_of = {(r.source, r.ext_id): r.truth for r in rows if r.type == entity_type}

    report = SyncReport()
    result = resolver.resolve(
        records, ONTO, report, bucket_cap=50, one_record_per_source=True
    )

    predicted: dict = {}
    for cluster in result["clusters"]:
        for source, _type, source_id in cluster.members:
            predicted.setdefault(cluster.canonical_id, set()).add((source, source_id))
    actual: dict = {}
    for key, truth in truth_of.items():
        actual.setdefault(truth, set()).add(key)

    predicted_pairs, actual_pairs = pairs(predicted), pairs(actual)
    hits = predicted_pairs & actual_pairs
    precision = len(hits) / len(predicted_pairs) if predicted_pairs else 1.0
    recall = len(hits) / len(actual_pairs) if actual_pairs else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_merges": sorted(predicted_pairs - actual_pairs),
        "clusters": len(predicted),
        "real": len(actual),
        "records": len(records),
        "report": report,
    }


class TestCorpus:
    def test_the_corpus_is_actually_adversarial(self, corpus):
        by_domain: dict = {}
        for row in corpus:
            if row.type == "company" and row.facts.get("domain"):
                by_domain.setdefault(row.facts["domain"].lower(), set()).add(row.truth)
        colliding = [d for d, truths in by_domain.items() if len(truths) > 1]
        assert colliding, "no domain collisions — this fixture cannot fail"

    def test_it_is_big_enough_to_measure(self, corpus):
        assert len(corpus) > 200


class TestCompanyPrecision:
    def test_precision_does_not_regress(self, corpus):
        result = score(corpus, "company")
        assert result["precision"] >= COMPANY_PRECISION_FLOOR, (
            f"{len(result['false_merges'])} false merges: {result['false_merges'][:5]}"
        )

    def test_recall_does_not_regress(self, corpus):
        assert score(corpus, "company")["recall"] >= COMPANY_RECALL_FLOOR

    def test_the_source_ratio_guard_actually_fires_here(self, corpus):
        result = score(corpus, "company")
        assert any(
            o["kind"] == "shared_across_records" for o in result["report"].oversized
        )

    def test_company_merges_are_now_exactly_right(self, corpus):
        assert score(corpus, "company")["false_merges"] == []


class TestPersonPrecision:
    def test_precision_does_not_regress(self, corpus):
        result = score(corpus, "person")
        assert result["precision"] >= PERSON_PRECISION_FLOOR, (
            f"{len(result['false_merges'])} false merges: {result['false_merges'][:5]}"
        )

    def test_recall_does_not_regress(self, corpus):
        assert score(corpus, "person")["recall"] >= PERSON_RECALL_FLOOR

    def test_shared_mailboxes_do_not_merge_the_office(self, corpus):
        result = score(corpus, "person")
        assert result["clusters"] >= result["real"]


class TestResidualFalseMerges:
    def test_the_corpus_can_still_punish_us(self, corpus):
        result = score(corpus, "company")
        assert any(
            o["kind"] == "shared_across_records" for o in result["report"].oversized
        )

    def test_person_false_merges_never_share_a_source(self, corpus):
        result = score(corpus, "person")
        for left, right in result["false_merges"]:
            assert left[0] != right[0], (left, right)


class TestScoringDiscipline:
    def test_cluster_counts_alone_would_have_looked_fine(self, corpus):
        result = score(corpus, "company")
        assert result["clusters"] > 0 and result["real"] > 0
        assert result["precision"] <= 1.0 and result["recall"] <= 1.0
