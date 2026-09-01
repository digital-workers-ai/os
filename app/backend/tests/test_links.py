from datetime import UTC, datetime

from app.engine import links, ontology, resolver
from app.engine.pipeline import ProjectedEntity, ProjectedFact
from app.engine.report import SyncReport
from app.engine.survivorship import FoldedFact

ONTO = ontology.load()
NOW = datetime(2026, 8, 1, tzinfo=UTC)


def record(source, entity_type, source_id, **facts):
    built = {
        attr: ProjectedFact(
            attr=attr,
            value=value,
            value_num=None,
            raw_event_id="raw",
            observed_at=NOW,
            observed_at_source="provider",
            seq=1,
        )
        for attr, value in facts.items()
    }
    return ProjectedEntity(
        source=source,
        entity_type=entity_type,
        source_id=source_id,
        object_type="o",
        first_seq=1,
        facts=built,
    )


def canonical(entity):
    return resolver.canonical_id_for(entity.anchor_key)


def folded_of(entities):
    out = []
    for e in entities:
        for attr, fact in e.facts.items():
            out.append(
                FoldedFact(
                    canonical_id=canonical(e),
                    entity_type=e.entity_type,
                    attr=attr,
                    value=fact.value,
                    value_num=None,
                    source=e.source,
                    entity_key=e.key,
                    raw_event_id="raw",
                    observed_at=NOW,
                    disagreements=0,
                )
            )
    return out


def build(entities, of_record=None, folded=None):
    projected = {e.key: e for e in entities}
    of_record = of_record or {e.key: canonical(e) for e in entities}
    report = SyncReport()
    edges = links.build(
        ONTO,
        projected=projected,
        of_record=of_record,
        folded=folded if folded is not None else folded_of(entities),
        report=report,
    )
    return edges, report


class TestViaEdges:
    def test_a_ref_joins_to_the_targets_structural_id(self):
        company = record("stripe", "company", "cus_123", domain="acme.io")
        sub = record("stripe", "subscription", "sub_9", customer_ref="cus_123")
        edges, report = build([company, sub])
        assert len(edges) == 1
        assert edges[0].rel == "belongs_to"
        assert edges[0].from_canonical == canonical(sub)
        assert edges[0].to_canonical == canonical(company)
        assert edges[0].grounding == "via:customer_ref"
        rate = report.match_rates["subscription belongs_to company"]
        assert rate["match_rate"] == 1.0

    def test_provider_ids_never_cross_sources(self):
        company = record("hubspot", "company", "cus_123", domain="acme.io")
        sub = record("stripe", "subscription", "sub_9", customer_ref="cus_123")
        edges, report = build([company, sub])
        assert edges == []
        assert report.dangling_refs["subscription belongs_to company"] == 1

    def test_a_ref_pointing_at_nothing_is_counted_as_dangling(self):
        sub = record("stripe", "subscription", "sub_9", customer_ref="cus_missing")
        edges, report = build([sub])
        assert edges == []
        assert report.dangling_refs["subscription belongs_to company"] == 1

    def test_the_edge_lands_on_the_canonical_company_not_the_stripe_row(self):
        stripe_co = record("stripe", "company", "cus_123", domain="acme.io")
        crm_co = record(
            "hubspot", "company", "hs_1", domain="acme.io", industry="Software"
        )
        sub = record("stripe", "subscription", "sub_9", customer_ref="cus_123")
        merged = resolver.canonical_id_for(crm_co.anchor_key)
        of_record = {
            stripe_co.key: merged,
            crm_co.key: merged,
            sub.key: canonical(sub),
        }
        edges, _ = build([stripe_co, crm_co, sub], of_record=of_record)
        assert [e.to_canonical for e in edges] == [merged]


class TestViaCardinality:
    def test_a_subject_reaching_two_different_companies_is_quarantined(self):
        acme = record("stripe", "company", "cus_1", domain="acme.io")
        globex = record("hubspot", "company", "cus_2", domain="globex.com")
        left = record("stripe", "subscription", "sub_a", customer_ref="cus_1")
        right = record("hubspot", "subscription", "sub_b", customer_ref="cus_2")
        merged_subject = canonical(left)
        of_record = {
            acme.key: canonical(acme),
            globex.key: canonical(globex),
            left.key: merged_subject,
            right.key: merged_subject,
        }
        edges, report = build([acme, globex, left, right], of_record=of_record)
        assert [e for e in edges if e.rel == "belongs_to"] == []
        assert any("expected 1" in q["detail"] for q in report.quarantines)

    def test_one_target_is_left_alone(self):
        company = record("stripe", "company", "cus_1", domain="acme.io")
        one = record("stripe", "subscription", "s1", customer_ref="cus_1")
        two = record("hubspot", "subscription", "s2", customer_ref="cus_1")
        edges, report = build([company, one, two])
        assert len(edges) == 1
        assert report.quarantines == []


class TestSubjectsThatCannotJoin:
    def test_a_subject_with_no_ref_fact_is_not_a_candidate(self):
        company = record("stripe", "company", "cus_1", domain="acme.io")
        sub = record("stripe", "subscription", "s1")
        edges, report = build([company, sub])
        assert edges == []
        rate = report.match_rates["subscription belongs_to company"]
        assert rate["candidates"] == 0

    def test_a_target_missing_from_the_resolution_is_dangling(self):
        company = record("stripe", "company", "cus_1", domain="acme.io")
        sub = record("stripe", "subscription", "s1", customer_ref="cus_1")
        edges, report = build([company, sub], of_record={sub.key: canonical(sub)})
        assert edges == []
        assert report.dangling_refs["subscription belongs_to company"] == 1


class TestUnboundedCardinality:
    def test_a_one_to_many_rel_skips_the_fanout_check(self):
        rel = ontology.Relationship(
            rel="covers",
            from_type="subscription",
            to_type="company",
            cardinality="one_to_many",
            via="customer_ref",
        )
        onto = ontology.Ontology(entities={}, relationships=(rel,), source_priority=())
        company = record("stripe", "company", "cus_1", domain="acme.io")
        sub = record("stripe", "subscription", "s1", customer_ref="cus_1")
        projected = {e.key: e for e in (company, sub)}
        of_record = {e.key: canonical(e) for e in (company, sub)}
        report = SyncReport()
        edges = links.build(
            onto, projected=projected, of_record=of_record, folded=[], report=report
        )
        assert len(edges) == 1
        assert report.quarantines == []


class TestMatchEdges:
    def test_a_shared_normalized_value_joins(self):
        person = record("hubspot", "person", "p1", email="jane@acme.io")
        event = record(
            "customerio", "event", "del_1", email="jane@acme.io", event_name="opened"
        )
        edges, _ = build([person, event])
        assert [e.rel for e in edges] == ["performed_by"]
        assert edges[0].from_canonical == canonical(event)
        assert edges[0].to_canonical == canonical(person)
        assert edges[0].grounding == "match:email"

    def test_it_resolves_against_canonical_entities_so_expected_one_is_true(self):
        hs = record("hubspot", "person", "p1", email="jane@acme.io")
        stripe = record("stripe", "person", "cus_1", email="jane@acme.io")
        event = record("customerio", "event", "del_1", email="jane@acme.io")
        merged = resolver.canonical_id_for(hs.anchor_key)
        of_record = {hs.key: merged, stripe.key: merged, event.key: canonical(event)}
        folded = [
            FoldedFact(
                canonical_id=merged,
                entity_type="person",
                attr="email",
                value="jane@acme.io",
                value_num=None,
                source="hubspot",
                entity_key=hs.key,
                raw_event_id="raw",
                observed_at=NOW,
                disagreements=0,
            ),
            FoldedFact(
                canonical_id=canonical(event),
                entity_type="event",
                attr="email",
                value="jane@acme.io",
                value_num=None,
                source="customerio",
                entity_key=event.key,
                raw_event_id="raw",
                observed_at=NOW,
                disagreements=0,
            ),
        ]
        edges, report = build([hs, stripe, event], of_record=of_record, folded=folded)
        assert len(edges) == 1
        assert report.quarantines == []

    def test_an_unmerged_duplicate_is_a_cardinality_violation_and_gets_no_link(self):
        one = record("hubspot", "person", "p1", email="jane@acme.io")
        two = record("stripe", "person", "cus_1", email="jane@acme.io")
        event = record("customerio", "event", "del_1", email="jane@acme.io")
        edges, report = build([one, two, event])
        assert edges == []
        assert len(report.quarantines) == 1
        assert "expected 1" in report.quarantines[0]["detail"]

    def test_an_event_whose_email_matches_nobody_is_dangling(self):
        event = record("customerio", "event", "del_1", email="ghost@acme.io")
        edges, report = build([event])
        assert edges == []
        assert report.dangling_refs["event performed_by person"] == 1


class TestReporting:
    def test_match_rates_report_candidates_and_matches(self):
        company = record("stripe", "company", "cus_1", domain="acme.io")
        good = record("stripe", "subscription", "s1", customer_ref="cus_1")
        bad = record("stripe", "subscription", "s2", customer_ref="cus_missing")
        _edges, report = build([company, good, bad])
        rate = report.match_rates["subscription belongs_to company"]
        assert (rate["candidates"], rate["matched"], rate["match_rate"]) == (2, 1, 0.5)

    def test_edges_are_deterministic_in_order(self):
        entities = [
            record("stripe", "company", f"cus_{i}", domain=f"a{i}.io") for i in range(3)
        ]
        entities += [
            record("stripe", "subscription", f"s{i}", customer_ref=f"cus_{i}")
            for i in range(3)
        ]
        first, _ = build(entities)
        second, _ = build(list(reversed(entities)))
        assert [(e.from_canonical, e.rel, e.to_canonical) for e in first] == [
            (e.from_canonical, e.rel, e.to_canonical) for e in second
        ]
