from datetime import UTC, datetime

from app.engine import ontology, resolver
from app.engine import survivorship as s
from app.engine.pipeline import ProjectedEntity, ProjectedFact
from app.engine.report import SyncReport

ONTO = ontology.load()


def at(day, hour=0):
    return datetime(2026, 8, day, hour, tzinfo=UTC)


def entity(source, source_id, facts, entity_type="company"):
    built = {
        attr: ProjectedFact(
            attr=attr,
            value=value,
            value_num=None,
            raw_event_id=f"raw-{source}-{attr}",
            observed_at=observed,
            observed_at_source="provider",
            seq=1,
        )
        for attr, (value, observed) in facts.items()
    }
    return ProjectedEntity(
        source=source,
        entity_type=entity_type,
        source_id=source_id,
        object_type="companies",
        first_seq=1,
        facts=built,
    )


def fold(entities):
    projected = {e.key: e for e in entities}
    anchor = sorted(e.anchor_key for e in entities)[0]
    cluster = resolver.Cluster(
        canonical_id=resolver.canonical_id_for(anchor),
        entity_type="company",
        anchor_key=anchor,
        minted_order=1,
    )
    for e in entities:
        cluster.members[e.key] = "domain=acme.io"
        cluster.sources.add(e.source)
    report = SyncReport()
    folded = s.fold([cluster], projected, ONTO, report)
    return {f.attr: f for f in folded}, report


class TestTheWinnersLineage:
    def test_the_winning_source_is_recorded_not_the_first_seen(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("Old", at(1))}),
                entity("stripe", "s1", {"name": ("New", at(9))}),
            ]
        )
        assert result["name"].value == "New"
        assert result["name"].source == "stripe"

    def test_the_winning_records_key_travels_with_the_value(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("Old", at(1))}),
                entity("stripe", "s1", {"name": ("New", at(9))}),
            ]
        )
        assert result["name"].entity_key == ("stripe", "company", "s1")

    def test_the_raw_event_behind_the_winner_is_carried(self):
        result, _ = fold([entity("stripe", "s1", {"name": ("New", at(9))})])
        assert result["name"].raw_event_id == "raw-stripe-name"

    def test_the_observation_time_is_the_winners_not_the_folds(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("Old", at(1))}),
                entity("stripe", "s1", {"name": ("New", at(9))}),
            ]
        )
        assert result["name"].observed_at == at(9)

    def test_the_canonical_id_and_type_come_from_the_cluster(self):
        result, _ = fold([entity("stripe", "s1", {"name": ("N", at(1))})])
        assert result["name"].entity_type == "company"
        assert result["name"].canonical_id is not None


class TestDisagreementCounting:
    def test_one_agreed_value_is_no_disagreement(self):
        result, report = fold(
            [
                entity("hubspot", "c1", {"name": ("Acme", at(1))}),
                entity("stripe", "s1", {"name": ("Acme", at(2))}),
            ]
        )
        assert result["name"].disagreements == 0
        assert report.totals()["disagreements"] == 0

    def test_two_different_values_is_one_disagreement(self):
        result, report = fold(
            [
                entity("hubspot", "c1", {"name": ("Acme", at(1))}),
                entity("stripe", "s1", {"name": ("Acme Inc", at(2))}),
            ]
        )
        assert result["name"].disagreements == 1
        assert report.totals()["disagreements"] == 1

    def test_three_different_values_is_two_disagreements(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("A", at(1))}),
                entity("stripe", "s1", {"name": ("B", at(2))}),
                entity("zendesk", "z1", {"name": ("C", at(3))}),
            ]
        )
        assert result["name"].disagreements == 2

    def test_a_cleared_value_is_not_counted_as_a_disagreeing_one(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("Acme", at(1))}),
                entity("stripe", "s1", {"name": (None, at(2))}),
            ]
        )
        assert "name" not in result

    def test_a_disagreement_count_is_never_negative(self):
        result, _ = fold([entity("hubspot", "c1", {"name": ("A", at(1))})])
        assert result["name"].disagreements == 0


class TestClearing:
    def test_the_freshest_observation_wins_even_when_it_is_empty(self):
        result, report = fold(
            [
                entity("hubspot", "c1", {"name": ("Acme", at(1))}),
                entity("stripe", "s1", {"name": (None, at(9))}),
            ]
        )
        assert "name" not in result
        assert any("cleared_canonical" in k for k in report.as_dict()["counts"])

    def test_an_older_clear_does_not_overrule_a_newer_value(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": (None, at(1))}),
                entity("stripe", "s1", {"name": ("Acme", at(9))}),
            ]
        )
        assert result["name"].value == "Acme"


class TestTiebreaks:
    def test_source_priority_breaks_a_tie_on_time(self):
        result, _ = fold(
            [
                entity("stripe", "s1", {"name": ("From Stripe", at(5))}),
                entity("hubspot", "c1", {"name": ("From HubSpot", at(5))}),
            ]
        )
        winners = {"hubspot", "stripe"}
        assert result["name"].source in winners
        ranked = min(winners, key=ONTO.priority_index)
        assert result["name"].source == ranked

    def test_the_same_source_and_time_falls_back_to_a_stable_id_order(self):
        first, second = (
            entity("hubspot", "c1", {"name": ("One", at(5))}),
            entity("hubspot", "c2", {"name": ("Two", at(5))}),
        )
        result, _ = fold([first, second])
        again, _ = fold([second, first])
        assert result["name"].value == again["name"].value

    def test_recency_outranks_source_priority(self):
        result, _ = fold(
            [
                entity("hubspot", "c1", {"name": ("Older, higher rank", at(1))}),
                entity("stripe", "s1", {"name": ("Newer", at(9))}),
            ]
        )
        assert result["name"].value == "Newer"


class TestAttributesAreFoldedIndependently:
    def test_different_attrs_may_have_different_winners(self):
        result, _ = fold(
            [
                entity(
                    "hubspot",
                    "c1",
                    {"name": ("From HubSpot", at(9)), "industry": ("Old", at(1))},
                ),
                entity(
                    "stripe",
                    "s1",
                    {"name": ("Old", at(1)), "industry": ("From Stripe", at(9))},
                ),
            ]
        )
        assert result["name"].source == "hubspot"
        assert result["industry"].source == "stripe"

    def test_every_observed_attr_appears_in_the_fold(self):
        result, _ = fold(
            [
                entity(
                    "hubspot",
                    "c1",
                    {
                        "name": ("A", at(1)),
                        "industry": ("B", at(1)),
                        "domain": ("acme.io", at(1)),
                    },
                ),
            ]
        )
        assert set(result) == {"name", "industry", "domain"}

    def test_an_entity_missing_from_the_projection_is_skipped(self):
        live = entity("stripe", "s1", {"name": ("Acme", at(1))})
        anchor = live.anchor_key
        cluster = resolver.Cluster(
            canonical_id=resolver.canonical_id_for(anchor),
            entity_type="company",
            anchor_key=anchor,
            minted_order=1,
        )
        cluster.members[live.key] = "domain=acme.io"
        cluster.members[("ghost", "company", "g1")] = "domain=acme.io"
        folded = s.fold([cluster], {live.key: live}, ONTO, SyncReport())
        assert {f.value for f in folded} == {"Acme"}
