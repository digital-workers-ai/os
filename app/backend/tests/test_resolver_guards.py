import pytest

from app.engine import ontology
from app.engine.report import SyncReport
from app.engine.resolver import Record, resolve


@pytest.fixture
def onto():
    return ontology.load()


def person(source, source_id, order, **identity):
    return Record(
        source=source,
        entity_type="person",
        source_id=source_id,
        order=order,
        identity=identity,
    )


def company(source, source_id, order, **identity):
    return Record(
        source=source,
        entity_type="company",
        source_id=source_id,
        order=order,
        identity=identity,
    )


class TestOneValueTwiceFromOneSource:
    def test_a_domain_two_hubspot_records_share_is_quarantined(self, onto):
        report = SyncReport()
        result = resolve(
            [
                company("hubspot", "c1", 1, domain="acme.io"),
                company("hubspot", "c2", 2, domain="acme.io"),
            ],
            onto,
            report,
        )
        assert len(set(result["of_record"].values())) == 2
        assert report.totals()["oversized"] >= 1
        assert "shared_across_records" in str(report.as_dict())

    def test_a_domain_two_different_tools_share_still_merges(self, onto):
        report = SyncReport()
        result = resolve(
            [
                company("hubspot", "c1", 1, domain="acme.io"),
                company("salesforce", "a1", 2, domain="acme.io"),
            ],
            onto,
            report,
        )
        assert len(set(result["of_record"].values())) == 1


class TestOneRecordPerSource:
    def _estate(self):
        return [
            person("hubspot", "p1", 1, email="a@acme.io"),
            person("salesforce", "s1", 2, email="a@acme.io", external_ref="X1"),
            person("hubspot", "p2", 3, external_ref="X1"),
            person("hubspot", "p4", 4, email="d@acme.io", external_ref="X9"),
            person("salesforce", "s4", 5, email="d@acme.io", external_ref="X9"),
        ]

    def test_a_source_rejoining_on_another_attr_is_refused(self, onto):
        report = SyncReport()
        result = resolve(self._estate(), onto, report)
        assert len(set(result["of_record"].values())) == 3
        assert "one_record_per_source" in str(report.as_dict())

    def test_the_refused_record_still_gets_a_cluster_of_its_own(self, onto):
        report = SyncReport()
        result = resolve(self._estate(), onto, report)
        assert len(result["of_record"]) == 5

    def test_the_guard_can_be_switched_off(self, onto):
        report = SyncReport()
        result = resolve(self._estate(), onto, report, one_record_per_source=False)
        assert len(set(result["of_record"].values())) == 2


class TestMergeHistory:
    def test_a_retired_id_resolves_to_the_survivor(self, onto):
        report = SyncReport()
        result = resolve(
            [
                person("hubspot", "p1", 1, email="a@acme.io"),
                person("salesforce", "s1", 2, email="a@acme.io", external_ref="X1"),
                person("stripe", "st1", 3, external_ref="X1"),
            ],
            onto,
            report,
        )
        for alias, survivor in result["aliases"].items():
            assert alias != survivor

    def test_an_alias_chain_is_flattened_rather_than_left_to_hop(self, onto):
        report = SyncReport()
        result = resolve(
            [
                person("hubspot", "p1", 1, email="a@acme.io"),
                person("stripe", "st1", 2, external_ref="X1"),
                person("salesforce", "s1", 3, email="a@acme.io", external_ref="X1"),
                person("zendesk", "z1", 4, email="a@acme.io"),
            ],
            onto,
            report,
        )
        survivors = set(result["aliases"].values())
        assert not (survivors & set(result["aliases"]))

    def test_every_record_lands_in_exactly_one_cluster(self, onto):
        report = SyncReport()
        records = [
            company("hubspot", f"c{n}", n, domain=f"c{n}.io") for n in range(1, 6)
        ]
        result = resolve(records, onto, report)
        assert len(result["of_record"]) == len(records)


class TestFoldedClustersStayReachable:
    def _chain(self):
        return [
            person("hubspot", "p1", 1, email="a@acme.io"),
            person("stripe", "p2", 2, email="b@acme.io"),
            person("zendesk", "p3", 3, external_ref="X1"),
            person("intercom", "p4", 4, email="b@acme.io", external_ref="X1"),
            person("klaviyo", "p5", 5, email="a@acme.io", external_ref="X1"),
        ]

    def test_evidence_pointing_at_a_folded_cluster_resolves_to_the_survivor(self, onto):
        report = SyncReport()
        result = resolve(self._chain(), onto, report)
        assert len(result["of_record"]) == 5
        assert set(result["of_record"].values())

    def test_an_alias_is_rewritten_when_its_target_is_itself_folded(self, onto):
        report = SyncReport()
        result = resolve(self._chain(), onto, report)
        assert not (set(result["aliases"].values()) & set(result["aliases"]))
