import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
import yaml
from sqlalchemy import func, select

from app import store
from app.db import get_session
from app.engine import checks, links, mappings, metrics, ontology, rules, run, search
from app.engine.survivorship import FoldedFact
from app.main import app
from app.models import EngineRun, EntityFact, FactCurrent

SEEN = datetime(2026, 8, 1, tzinfo=UTC)
OLDER = datetime(2026, 7, 1, tzinfo=UTC)
NEWER = datetime(2026, 8, 20, tzinfo=UTC)
NOW = datetime(2026, 8, 2, tzinfo=UTC)

MONEY = frozenset({"mrr", "amount", "price", "spend", "budget"})

MRR = {
    "company": {
        "mrr": {
            "expression": "SUM(subscription.mrr)",
            "via": "belongs_to",
            "filter": {"status": "active"},
        }
    }
}
TICKETS = {
    "company": {"open_tickets": {"expression": "COUNT(ticket)", "via": "belongs_to"}}
}
LAST_MEETING = {
    "person": {
        "last_meeting_at": {
            "expression": "MAX(meeting.started_at)",
            "via": "attended_by",
        }
    }
}


def _derived():
    from app.engine import derived

    return derived


@pytest.fixture(scope="module")
def onto():
    return ontology.load()


def _yaml(tmp_path, doc):
    path = tmp_path / "derived.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def _specs(tmp_path, doc):
    return _derived().load(_yaml(tmp_path, doc))


def _problems(tmp_path, onto, doc):
    return "\n".join(_derived().check(onto, _yaml(tmp_path, doc)))


def _fact(canonical_id, entity_type, attr, value, value_num=None, observed_at=SEEN):
    return FoldedFact(
        canonical_id=canonical_id,
        entity_type=entity_type,
        attr=attr,
        value=str(value),
        value_num=value_num,
        source="stripe",
        entity_key=("stripe", entity_type, str(canonical_id)),
        raw_event_id=None,
        observed_at=observed_at,
        disagreements=0,
    )


def _edge(from_canonical, rel, to_canonical):
    return links.Edge(from_canonical, rel, to_canonical, "via:test")


def _by_attr(facts):
    return {(f.canonical_id, f.attr): f for f in facts}


class TestTheFile:
    def test_the_shipped_file_declares_the_three_facts(self):
        specs = _derived().load()
        assert set(specs["company"]) == {"mrr", "open_tickets"}
        assert "last_meeting_at" in specs["person"]

    def test_a_file_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "derived.yaml"
        path.write_text("- a\n")
        with pytest.raises(_derived().DerivedError):
            _derived().load(path)


class TestCheck:
    def test_the_shipped_file_has_no_problems(self, onto):
        assert _derived().check(onto) == []

    def test_an_unknown_target_entity_is_refused(self, tmp_path, onto):
        doc = {"galaxy": {"mrr": dict(MRR["company"]["mrr"])}}
        assert "derived galaxy.mrr: " in _problems(tmp_path, onto, doc)

    def test_an_unknown_source_entity_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": {**MRR["company"]["mrr"], "expression": "SUM(widget.mrr)"}
            }
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived company.mrr: " in text
        assert "widget" in text

    def test_a_via_that_walks_no_declared_edge_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": {
                    "expression": "SUM(order.amount)",
                    "via": "belongs_to",
                }
            }
        }
        assert "no declared edge order belongs_to company" in _problems(
            tmp_path, onto, doc
        )

    def test_a_source_attr_that_is_not_declared_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": {
                    **MRR["company"]["mrr"],
                    "expression": "SUM(subscription.takings)",
                }
            }
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived company.mrr: " in text
        assert "takings" in text

    def test_summing_a_string_attr_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": {
                    **MRR["company"]["mrr"],
                    "expression": "SUM(subscription.status)",
                }
            }
        }
        assert "SUM over a string attr" in _problems(tmp_path, onto, doc)

    def test_max_over_a_string_attr_is_a_category_error(self, tmp_path, onto):
        doc = {
            "person": {
                "last_meeting_at": {
                    "expression": "MAX(meeting.name)",
                    "via": "attended_by",
                }
            }
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived person.last_meeting_at: " in text
        assert "MAX over a string attr is a category error" in text

    def test_a_filter_attr_the_source_does_not_declare_is_refused(self, tmp_path, onto):
        doc = {
            "company": {"mrr": {**MRR["company"]["mrr"], "filter": {"state": "active"}}}
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived company.mrr: " in text
        assert "state" in text

    def test_a_derived_name_that_shadows_a_declared_attr_is_refused(
        self, tmp_path, onto
    ):
        doc = {
            "company": {
                "industry": {"expression": "COUNT(ticket)", "via": "belongs_to"}
            }
        }
        assert "shadows a declared attr of company" in _problems(tmp_path, onto, doc)

    def test_an_unknown_key_under_a_spec_is_refused(self, tmp_path, onto):
        doc = {"company": {"mrr": {**MRR["company"]["mrr"], "where": "status=active"}}}
        text = _problems(tmp_path, onto, doc)
        assert "unknown key" in text
        assert "where" in text

    def test_a_money_sum_onto_a_target_that_declares_currency_is_refused(
        self, tmp_path, onto
    ):
        doc = {
            "deal": {"billed": {"expression": "SUM(order.amount)", "via": "placed_by"}}
        }
        assert "shadows a declared attr of deal" in _problems(tmp_path, onto, doc)

    def test_a_second_money_sum_on_one_target_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": dict(MRR["company"]["mrr"]),
                "pipeline": {"expression": "SUM(deal.amount)", "via": "belongs_to"},
            }
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived company.pipeline: " in text
        assert "currency" in text
        assert "twice" in text

    def test_an_expression_the_grammar_cannot_parse_is_refused(self, tmp_path, onto):
        doc = {
            "company": {
                "mrr": {**MRR["company"]["mrr"], "expression": "everything we bill"}
            }
        }
        text = _problems(tmp_path, onto, doc)
        assert "derived company.mrr: " in text
        assert "everything we bill" in text


class TestABrokenFileIsReportedNotRaised:
    def test_a_spec_the_grammar_refuses_still_lets_the_checks_finish(self, tmp_path):
        path = _yaml(
            tmp_path,
            {"company": {"mrr": {**MRR["company"]["mrr"], "where": "status=active"}}},
        )
        problems = checks.run(derived_path=path)
        assert any("unknown key" in p and "where" in p for p in problems)

    def test_a_file_that_is_not_a_mapping_still_lets_the_checks_finish(self, tmp_path):
        path = tmp_path / "derived.yaml"
        path.write_text("- a\n")
        problems = checks.run(derived_path=path)
        assert any("top level must be a mapping" in p for p in problems)

    def test_attrs_of_falls_back_to_the_declared_attrs(self, tmp_path, onto):
        path = _yaml(
            tmp_path,
            {"company": {"mrr": {**MRR["company"]["mrr"], "where": "status=active"}}},
        )
        attrs = _derived().attrs_of(onto, path)("company")
        assert attrs == onto.entities["company"].attrs


class TestTypes:
    def test_sum_and_count_are_numbers(self):
        assert _derived().types_for("company") == {
            "mrr": "number",
            "open_tickets": "number",
            "currency": "string",
        }

    def test_max_takes_the_type_of_the_source_attr(self):
        assert _derived().types_for("person")["last_meeting_at"] == "date"

    def test_an_entity_with_no_derived_facts_has_no_types(self):
        assert _derived().types_for("deal") == {}

    def test_attrs_of_merges_declared_attrs_with_derived_types(self, onto):
        attrs_of = _derived().attrs_of(onto)
        company = attrs_of("company")
        assert company["industry"] == "string"
        assert company["mrr"] == "number"
        assert company["open_tickets"] == "number"

    def test_attrs_of_leaves_an_undecorated_entity_alone(self, onto):
        assert _derived().attrs_of(onto)("deal") == onto.entities["deal"].attrs


class TestCompute:
    def test_count_writes_zero_for_a_target_with_no_sources(self, tmp_path, onto):
        folded = [_fact("c1", "company", "domain", "acme.io")]
        facts, refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, [], MONEY
        )
        assert refused == []
        assert [(f.entity_type, f.attr, f.value_num) for f in facts] == [
            ("company", "open_tickets", 0)
        ]

    def test_a_count_is_written_the_way_the_pipeline_writes_a_number(
        self, tmp_path, onto
    ):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("t1", "ticket", "status", "open"),
        ]
        edges = [_edge("t1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "open_tickets")].value == "1.0"

    def test_count_counts_the_sources_that_point_at_the_target(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("t1", "ticket", "status", "open"),
            _fact("t2", "ticket", "status", "solved"),
        ]
        edges = [_edge("t1", "belongs_to", "c1"), _edge("t2", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "open_tickets")].value_num == 2

    def test_sum_writes_zero_when_no_kept_source_carries_the_attr(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "status", "active"),
        ]
        edges = [_edge("s1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "mrr")].value_num == 0

    def test_a_filter_keeps_only_the_matching_sources(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "100.0", 100.0),
            _fact("s1", "subscription", "status", "ACTIVE"),
            _fact("s1", "subscription", "currency", "usd"),
            _fact("s2", "subscription", "mrr", "900.0", 900.0),
            _fact("s2", "subscription", "status", "canceled"),
            _fact("s2", "subscription", "currency", "usd"),
        ]
        edges = [_edge("s1", "belongs_to", "c1"), _edge("s2", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "mrr")].value_num == 100.0

    def test_a_money_sum_carries_the_currency_of_its_sources(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "100.0", 100.0),
            _fact("s1", "subscription", "status", "active"),
            _fact("s1", "subscription", "currency", "usd"),
        ]
        edges = [_edge("s1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        currency = _by_attr(facts)[("c1", "currency")]
        assert (currency.value, currency.value_num) == ("usd", None)
        assert currency.observed_at == _by_attr(facts)[("c1", "mrr")].observed_at

    def test_a_company_with_no_sources_gets_a_zero_and_no_currency(
        self, tmp_path, onto
    ):
        folded = [_fact("c1", "company", "domain", "acme.io")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, [], MONEY
        )
        assert _by_attr(facts)[("c1", "mrr")].value_num == 0
        assert ("c1", "currency") not in _by_attr(facts)

    def test_two_currencies_under_one_company_refuse_the_sum(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "100.0", 100.0),
            _fact("s1", "subscription", "status", "active"),
            _fact("s1", "subscription", "currency", "usd"),
            _fact("s2", "subscription", "mrr", "200.0", 200.0),
            _fact("s2", "subscription", "status", "active"),
            _fact("s2", "subscription", "currency", "eur"),
        ]
        edges = [_edge("s1", "belongs_to", "c1"), _edge("s2", "belongs_to", "c1")]
        facts, refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        assert facts == []
        assert refused == [
            {
                "entity": "company",
                "attr": "mrr",
                "canonical_id": "c1",
                "reason": "mixed_currencies",
            }
        ]

    def test_max_over_dates_takes_the_latest(self, tmp_path, onto):
        folded = [
            _fact("p1", "person", "email", "a@acme.io"),
            _fact("m1", "meeting", "started_at", "2026-01-09T10:00:00Z"),
            _fact("m2", "meeting", "started_at", "2026-03-02T10:00:00Z"),
        ]
        edges = [_edge("m1", "attended_by", "p1"), _edge("m2", "attended_by", "p1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, LAST_MEETING), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("p1", "last_meeting_at")].value == (
            "2026-03-02T10:00:00Z"
        )

    def test_max_is_stamped_with_the_winning_facts_own_observation(
        self, tmp_path, onto
    ):
        folded = [
            _fact("p1", "person", "email", "a@acme.io"),
            _fact(
                "m1",
                "meeting",
                "started_at",
                "2026-01-09T10:00:00Z",
                observed_at=NEWER,
            ),
            _fact(
                "m2",
                "meeting",
                "started_at",
                "2026-03-02T10:00:00Z",
                observed_at=OLDER,
            ),
        ]
        edges = [_edge("m1", "attended_by", "p1"), _edge("m2", "attended_by", "p1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, LAST_MEETING), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("p1", "last_meeting_at")].observed_at == OLDER

    def test_max_writes_nothing_when_no_source_carries_the_attr(self, tmp_path, onto):
        folded = [
            _fact("p1", "person", "email", "a@acme.io"),
            _fact("m1", "meeting", "name", "Intro"),
        ]
        edges = [_edge("m1", "attended_by", "p1")]
        facts, refused = _derived().compute(
            _specs(tmp_path, LAST_MEETING), onto, folded, edges, MONEY
        )
        assert (facts, refused) == ([], [])

    def test_a_source_reached_by_another_rel_is_not_a_source(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("t1", "ticket", "status", "open"),
        ]
        edges = [_edge("t1", "raised_by", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "open_tickets")].value_num == 0

    def test_a_source_of_another_entity_type_is_not_a_source(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("d1", "deal", "status", "open"),
        ]
        edges = [_edge("d1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "open_tickets")].value_num == 0

    def test_a_derived_fact_names_no_member_and_no_raw_event(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "100.0", 100.0),
            _fact("s1", "subscription", "status", "active"),
            _fact("s1", "subscription", "currency", "usd"),
        ]
        edges = [_edge("s1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        fact = _by_attr(facts)[("c1", "mrr")]
        assert (fact.source or "") == ""
        assert (fact.entity_key, fact.raw_event_id, fact.disagreements) == (
            None,
            None,
            0,
        )
        assert isinstance(fact.value, str)
        assert fact.value_num == 100.0

    def test_observed_at_is_the_newest_contributing_fact(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io", observed_at=OLDER),
            _fact("s1", "subscription", "mrr", "100.0", 100.0, observed_at=OLDER),
            _fact("s1", "subscription", "status", "active", observed_at=OLDER),
            _fact("s1", "subscription", "currency", "usd", observed_at=OLDER),
            _fact("s2", "subscription", "mrr", "50.0", 50.0, observed_at=NEWER),
            _fact("s2", "subscription", "status", "active", observed_at=NEWER),
            _fact("s2", "subscription", "currency", "usd", observed_at=NEWER),
        ]
        edges = [_edge("s1", "belongs_to", "c1"), _edge("s2", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "mrr")].observed_at == NEWER

    def test_observed_at_falls_back_to_the_targets_newest_own_fact(
        self, tmp_path, onto
    ):
        folded = [
            _fact("c1", "company", "domain", "acme.io", observed_at=OLDER),
            _fact("c1", "company", "name", "Acme", observed_at=NEWER),
        ]
        facts, _refused = _derived().compute(
            _specs(tmp_path, TICKETS), onto, folded, [], MONEY
        )
        assert _by_attr(facts)[("c1", "open_tickets")].observed_at == NEWER

    def test_a_source_missing_a_filter_attr_is_dropped(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "100.0", 100.0),
            _fact("s1", "subscription", "currency", "usd"),
        ]
        edges = [_edge("s1", "belongs_to", "c1")]
        facts, _refused = _derived().compute(
            _specs(tmp_path, MRR), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "mrr")].value_num == 0

    def test_a_sum_over_a_label_that_is_not_money_ignores_currency(
        self, tmp_path, onto
    ):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("d1", "deal", "amount", "300.0", 300.0),
            _fact("d1", "deal", "currency", "usd"),
            _fact("d2", "deal", "amount", "400.0", 400.0),
            _fact("d2", "deal", "currency", "eur"),
        ]
        edges = [_edge("d1", "belongs_to", "c1"), _edge("d2", "belongs_to", "c1")]
        doc = {
            "company": {
                "pipeline": {"expression": "SUM(deal.amount)", "via": "belongs_to"}
            }
        }
        facts, refused = _derived().compute(
            _specs(tmp_path, doc), onto, folded, edges, frozenset()
        )
        assert refused == []
        assert _by_attr(facts)[("c1", "pipeline")].value_num == 700.0

    def test_max_over_numbers_takes_the_greatest(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("s1", "subscription", "mrr", "900.0", 900.0),
            _fact("s2", "subscription", "mrr", "1100.0", 1100.0),
        ]
        edges = [_edge("s1", "belongs_to", "c1"), _edge("s2", "belongs_to", "c1")]
        doc = {
            "company": {
                "top_mrr": {
                    "expression": "MAX(subscription.mrr)",
                    "via": "belongs_to",
                }
            }
        }
        facts, _refused = _derived().compute(
            _specs(tmp_path, doc), onto, folded, edges, MONEY
        )
        assert _by_attr(facts)[("c1", "top_mrr")].value_num == 1100.0

    def test_two_runs_over_the_same_input_agree(self, tmp_path, onto):
        folded = [
            _fact("c1", "company", "domain", "acme.io"),
            _fact("c2", "company", "domain", "beta.io"),
            _fact("t1", "ticket", "status", "open"),
            _fact("t2", "ticket", "status", "open"),
        ]
        edges = [_edge("t1", "belongs_to", "c1"), _edge("t2", "belongs_to", "c2")]
        specs = _specs(tmp_path, TICKETS)
        first = _derived().compute(specs, onto, folded, edges, MONEY)
        second = _derived().compute(specs, onto, folded, edges, MONEY)
        assert first == second


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


async def _seed_acme(session, canonical, link):
    company = await canonical("company", {"domain": "acme.io", "name": "Acme"})
    subscription = await canonical(
        "subscription", {"mrr": 1500, "currency": "usd", "status": "active"}
    )
    ticket = await canonical("ticket", {"status": "open", "subject": "Broken login"})
    await link(subscription, "belongs_to", company)
    await link(ticket, "belongs_to", company)

    folded = [
        _fact(company, "company", "domain", "acme.io"),
        _fact(company, "company", "name", "Acme"),
        _fact(subscription, "subscription", "mrr", "1500.0", 1500.0),
        _fact(subscription, "subscription", "currency", "usd"),
        _fact(subscription, "subscription", "status", "active"),
        _fact(ticket, "ticket", "status", "open"),
    ]
    edges = [
        _edge(subscription, "belongs_to", company),
        _edge(ticket, "belongs_to", company),
    ]
    await _write_derived(session, folded, edges)
    return company


async def _write_derived(session, folded, edges):
    facts, _refused = _derived().compute(
        _derived().load(), ontology.load(), folded, edges, MONEY
    )
    for fact in facts:
        session.add(
            FactCurrent(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"{fact.canonical_id}|{fact.attr}"),
                canonical_id=fact.canonical_id,
                entity_type=fact.entity_type,
                attr=fact.attr,
                value=fact.value,
                value_num=fact.value_num,
                entity_id=None,
                raw_event_id=None,
                observed_at=fact.observed_at,
                disagreements=0,
            )
        )
    await session.flush()


async def _seed_paying_company(session, canonical, link, name, currency):
    company = await canonical("company", {"domain": f"{name}.io", "name": name})
    subscription = await canonical(
        "subscription", {"mrr": 1000, "currency": currency, "status": "active"}
    )
    await link(subscription, "belongs_to", company)
    folded = [
        _fact(company, "company", "domain", f"{name}.io"),
        _fact(subscription, "subscription", "mrr", "1000.0", 1000.0),
        _fact(subscription, "subscription", "currency", currency),
        _fact(subscription, "subscription", "status", "active"),
    ]
    await _write_derived(session, folded, [_edge(subscription, "belongs_to", company)])
    return company


class TestConsumers:
    async def test_a_rule_over_two_derived_attrs_fires(self, session, canonical, link):
        acme = await _seed_acme(session, canonical, link)
        rule = rules.parse(
            "paying_company_with_open_tickets",
            {
                "entity": "company",
                "all": [
                    {"attr": "mrr", "gte": 1000},
                    {"attr": "open_tickets", "gte": 1},
                ],
            },
        )
        findings = await rules.evaluate(
            session, rules={"paying_company_with_open_tickets": rule}, now=NOW
        )
        assert [f.canonical_id for f in findings] == [acme]

    async def test_a_metric_averages_a_derived_attr(self, session, canonical, link):
        await _seed_acme(session, canonical, link)
        result = await metrics.evaluate_definitions(
            session, {"m": {"entity": "company", "expression": "AVG(mrr)"}}
        )
        assert result["m"]["value"] == 1500.0

    async def test_an_average_across_two_currencies_is_refused(
        self, session, canonical, link
    ):
        await _seed_paying_company(session, canonical, link, "acme", "usd")
        await _seed_paying_company(session, canonical, link, "globex", "eur")
        result = await metrics.evaluate_definitions(
            session, {"m": {"entity": "company", "expression": "AVG(mrr)"}}
        )
        assert result["m"]["value"] is None
        assert result["m"]["mixed_currencies"] == ["eur", "usd"]

    async def test_search_leaves_a_derived_number_unindexed(
        self, session, canonical, link
    ):
        acme = await _seed_acme(session, canonical, link)
        await search.index(session)
        results = (await search.query(session, "mrr"))["results"]
        assert not any(
            r["id"] == str(acme) and r["evidence"].startswith("mrr=") for r in results
        )
        by_name = (await search.query(session, "Acme"))["results"]
        assert any(r["id"] == str(acme) for r in by_name)

    async def test_the_entity_payload_marks_which_facts_are_derived(
        self, api, session, canonical, link
    ):
        acme = await _seed_acme(session, canonical, link)
        body = (await api.get(f"/api/entities/{acme}")).json()
        flags = {f["attr"]: f["derived"] for f in body["facts"]}
        assert flags["mrr"] is True
        assert flags["domain"] is False

    async def test_the_definitions_route_serves_the_derived_file(self, api):
        response = await api.get("/api/definitions/derived")
        assert response.status_code == 200
        body = response.json()
        assert set(body["derived"]["company"]) == {"mrr", "open_tickets"}
        mrr = body["derived"]["company"]["mrr"]
        assert set(mrr) == {
            "expression",
            "via",
            "filter",
            "description",
            "synonyms",
            "type",
        }
        assert mrr["type"] == "number"
        assert body["derived"]["person"]["last_meeting_at"]["type"] == "date"

    def test_provenance_walks_a_derived_attr_to_its_raw_fields(self):
        lineage = metrics.provenance(
            {"m": {"entity": "company", "expression": "AVG(mrr)"}}, mappings.load()
        )
        assert {
            "stripe.subscriptions._amount_monthly",
            "stripe.subscriptions.status",
        } <= set(lineage["m"]["raw_fields"])

    def test_the_build_checks_read_a_derived_path(self, tmp_path):
        path = _yaml(
            tmp_path,
            {
                "company": {
                    "industry": {"expression": "COUNT(ticket)", "via": "belongs_to"}
                }
            },
        )
        problems = checks.run(derived_path=path)
        assert any("shadows a declared attr of company" in p for p in problems)


async def _seed_a_linked_subscription(session):
    await store.save_raw(
        session,
        source="stripe",
        object_type="customers",
        source_id="cus_1",
        raw_payload={"id": "cus_1", "name": "Acme", "email": "billing@acme.io"},
    )
    await store.save_raw(
        session,
        source="stripe",
        object_type="subscriptions",
        source_id="sub_1",
        raw_payload={
            "id": "sub_1",
            "customer": "cus_1",
            "currency": "usd",
            "status": "active",
            "start_date": 1705386400,
            "items": {
                "data": [
                    {
                        "quantity": 1,
                        "price": {
                            "unit_amount": 150000,
                            "recurring": {"interval": "month", "interval_count": 1},
                        },
                    }
                ]
            },
        },
    )
    await session.commit()


async def _seed_a_second_currency(session):
    await store.save_raw(
        session,
        source="stripe",
        object_type="subscriptions",
        source_id="sub_2",
        raw_payload={
            "id": "sub_2",
            "customer": "cus_1",
            "currency": "eur",
            "status": "active",
            "start_date": 1705386400,
            "items": {
                "data": [
                    {
                        "quantity": 1,
                        "price": {
                            "unit_amount": 90000,
                            "recurring": {"interval": "month", "interval_count": 1},
                        },
                    }
                ]
            },
        },
    )
    await session.commit()


class TestTheRebuild:
    async def test_a_rebuild_writes_and_counts_the_derived_company_mrr(self, session):
        await _seed_a_linked_subscription(session)
        result = await run.rebuild(session, run_checks=False)

        derived_rows = (
            (
                await session.execute(
                    select(FactCurrent).where(
                        FactCurrent.entity_type == "company",
                        FactCurrent.attr == "mrr",
                        FactCurrent.entity_id.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(derived_rows) == 1
        assert derived_rows[0].value_num == 1500.0
        assert result["report"]["counts"]["derived/company.mrr"] == 1

        entity_facts = (
            await session.execute(select(func.count()).select_from(EntityFact))
        ).scalar_one()
        all_derived = (
            await session.execute(
                select(func.count())
                .select_from(FactCurrent)
                .where(FactCurrent.entity_id.is_(None))
            )
        ).scalar_one()
        written = (
            await session.execute(
                select(EngineRun.facts_written).order_by(EngineRun.seq.desc()).limit(1)
            )
        ).scalar_one()
        assert all_derived
        assert written == entity_facts + all_derived

    async def test_a_rebuild_reports_a_company_whose_currencies_disagree(self, session):
        await _seed_a_linked_subscription(session)
        await _seed_a_second_currency(session)
        result = await run.rebuild(session, run_checks=False)

        counts = result["report"]["counts"]
        assert counts["derived_refused/company.mrr/mixed_currencies"] == 1
        assert "derived/company.mrr" not in counts
        assert (
            await session.execute(
                select(func.count())
                .select_from(FactCurrent)
                .where(FactCurrent.entity_type == "company", FactCurrent.attr == "mrr")
            )
        ).scalar_one() == 0

    async def test_the_rebuild_hands_compute_the_folded_facts_and_the_edges(
        self, session, monkeypatch
    ):
        seen: dict = {}

        def spy(specs, onto, folded, edges, money):
            seen["folded"] = folded
            seen["edges"] = edges
            seen["money"] = money
            return [], []

        monkeypatch.setattr(run.derived, "compute", spy)
        await _seed_a_linked_subscription(session)
        await run.rebuild(session, run_checks=False)
        assert any(e.rel == "belongs_to" for e in seen["edges"])
        assert any(f.attr == "mrr" for f in seen["folded"])
        assert "mrr" in seen["money"]
