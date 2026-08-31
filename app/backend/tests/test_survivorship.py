from datetime import UTC, datetime

from app.engine import ontology, resolver
from app.engine import survivorship as s
from app.engine.pipeline import ProjectedEntity, ProjectedFact
from app.engine.report import SyncReport

ONTO = ontology.load()


def at(day, hour=0):
    return datetime(2026, day // 100, day % 100, hour, tzinfo=UTC)


def entity(source, source_id, facts, entity_type="company", object_type="companies"):
    built = {}
    for attr, (value, observed) in facts.items():
        built[attr] = ProjectedFact(
            attr=attr,
            value=value,
            value_num=float(value) if attr in ("mrr", "spend") and value else None,
            raw_event_id=f"raw-{source}-{attr}",
            observed_at=observed,
            observed_at_source="provider",
            seq=1,
        )
    return ProjectedEntity(
        source=source,
        entity_type=entity_type,
        source_id=source_id,
        object_type=object_type,
        first_seq=1,
        facts=built,
    )


def cluster(entities, entity_type="company"):
    anchor = sorted(e.anchor_key for e in entities)[0]
    c = resolver.Cluster(
        canonical_id=resolver.canonical_id_for(anchor),
        entity_type=entity_type,
        anchor_key=anchor,
        minted_order=1,
    )
    for e in entities:
        c.members[e.key] = "domain=acme.io"
        c.sources.add(e.source)
    return c


def fold(entities, entity_type="company"):
    projected = {e.key: e for e in entities}
    report = SyncReport()
    folded = s.fold([cluster(entities, entity_type)], projected, ONTO, report)
    return {f.attr: f for f in folded}, report


class TestRecency:
    def test_the_most_recent_observation_wins(self):
        result, _ = fold(
            [
                entity("hubspot", "hs_1", {"industry": ("Software", at(701))}),
                entity("stripe", "cus_1", {"industry": ("SaaS", at(715))}),
            ]
        )
        assert result["industry"].value == "SaaS"
        assert result["industry"].source == "stripe"

    def test_a_stale_backfill_landing_late_does_not_win(self):
        fresh = entity("hubspot", "hs_1", {"industry": ("Software", at(715))})
        stale = entity("stripe", "cus_1", {"industry": ("Manufacturing", at(101))})
        stale.facts["industry"].seq = 9999
        result, _ = fold([fresh, stale])
        assert result["industry"].value == "Software"

    def test_the_winning_value_traces_to_the_raw_event_that_won(self):
        result, _ = fold(
            [
                entity("hubspot", "hs_1", {"name": ("Acme Corp", at(701))}),
                entity("stripe", "cus_1", {"name": ("ACME Corporation", at(715))}),
            ]
        )
        assert result["name"].raw_event_id == "raw-stripe-name"


class TestPriorityTiebreak:
    def test_equal_observation_times_fall_to_declared_priority(self):
        result, _ = fold(
            [
                entity("stripe", "cus_1", {"name": ("ACME Corporation", at(701))}),
                entity("hubspot", "hs_1", {"name": ("Acme Corp", at(701))}),
            ]
        )
        assert result["name"].source == "hubspot"

    def test_an_unlisted_source_sorts_last_rather_than_undefined(self):
        result, _ = fold(
            [
                entity("stripe", "cus_1", {"name": ("From Stripe", at(701))}),
                entity("adroll", "ad_1", {"name": ("From AdRoll", at(701))}),
            ]
        )
        assert result["name"].source == "stripe"


class TestDisagreements:
    def test_disagreeing_sources_are_counted_per_attr(self):
        result, report = fold(
            [
                entity("hubspot", "hs_1", {"industry": ("Software", at(701))}),
                entity("stripe", "cus_1", {"industry": ("SaaS", at(715))}),
            ]
        )
        assert report.disagreements["company.industry"] == 1
        assert result["industry"].disagreements == 1

    def test_agreement_is_not_a_disagreement(self):
        _result, report = fold(
            [
                entity("hubspot", "hs_1", {"domain": ("acme.io", at(701))}),
                entity("stripe", "cus_1", {"domain": ("acme.io", at(715))}),
            ]
        )
        assert report.disagreements == {}


class TestClears:
    def test_the_freshest_observation_being_a_clear_empties_the_value(self):
        result, report = fold(
            [
                entity("hubspot", "hs_1", {"industry": ("Software", at(701))}),
                entity("stripe", "cus_1", {"industry": (None, at(715))}),
            ]
        )
        assert "industry" not in result
        assert report.counts["cleared_canonical/company/industry"] == 1

    def test_a_stale_clear_does_not_beat_a_fresh_value(self):
        result, _ = fold(
            [
                entity("hubspot", "hs_1", {"industry": (None, at(101))}),
                entity("stripe", "cus_1", {"industry": ("Software", at(715))}),
            ]
        )
        assert result["industry"].value == "Software"

    def test_a_clear_competes_like_any_other_observation(self):
        result, _ = fold(
            [
                entity("stripe", "cus_1", {"industry": (None, at(715))}),
                entity("hubspot", "hs_1", {"industry": ("Software", at(715))}),
            ]
        )
        assert result["industry"].value == "Software"


class TestDeterminism:
    def test_the_fold_does_not_depend_on_member_iteration_order(self):
        first = entity("hubspot", "hs_1", {"name": ("A", at(701))})
        second = entity("stripe", "cus_1", {"name": ("B", at(701))})
        third = entity("adroll", "ad_1", {"name": ("C", at(701))})
        one, _ = fold([first, second, third])
        two, _ = fold([third, second, first])
        assert one["name"].value == two["name"].value
