import pytest

from app.engine import ontology
from app.engine import resolver as r
from app.engine.report import SyncReport

ONTO = ontology.load()


def rec(source, source_id, order, entity_type="company", **identity):
    return r.Record(
        source=source,
        entity_type=entity_type,
        source_id=source_id,
        order=order,
        identity=identity,
    )


def resolve(records):
    report = SyncReport()
    return r.resolve(records, ONTO, report), report


class TestExactMatch:
    def test_three_tools_one_company(self):
        result, _ = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("stripe", "cus_1", 2, domain="acme.io"),
                rec("zendesk", "zd_1", 3, domain="acme.io"),
            ]
        )
        assert len(result["clusters"]) == 1
        assert len(result["clusters"][0].members) == 3

    def test_different_domains_stay_apart(self):
        result, _ = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("hubspot", "hs_2", 2, domain="globex.com"),
            ]
        )
        assert len(result["clusters"]) == 2

    def test_an_entity_with_no_identity_list_is_never_merged(self):
        result, _ = resolve(
            [
                rec("stripe", "deal_1", 1, entity_type="deal"),
                rec("stripe", "deal_2", 2, entity_type="deal"),
            ]
        )
        assert len(result["clusters"]) == 2
        assert all(
            list(c.members.values()) == ["singleton"] for c in result["clusters"]
        )

    def test_names_are_never_evidence(self):
        result, _ = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io", name="Acme"),
                rec("stripe", "cus_1", 2, domain="acme-eu.io", name="Acme"),
            ]
        )
        assert len(result["clusters"]) == 2

    def test_evidence_is_recorded_not_just_the_edge(self):
        result, _ = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("stripe", "cus_1", 2, domain="acme.io"),
            ]
        )
        assert set(result["clusters"][0].members.values()) == {"domain=acme.io"}


class TestGuards:
    def test_null_identity_values_are_never_evidence(self):
        result, report = resolve(
            [
                rec("hubspot", "hs_1", 1),
                rec("stripe", "cus_1", 2),
            ]
        )
        assert len(result["clusters"]) == 2
        assert report.identity_less["company/hubspot"] == 1
        assert report.identity_less["company/stripe"] == 1

    def test_free_mail_domains_do_not_merge_four_hundred_strangers(self):
        result, report = resolve(
            [rec("stripe", f"cus_{i}", i, domain="gmail.com") for i in range(1, 6)]
        )
        assert len(result["clusters"]) == 5
        assert report.counts["identity_blocked/company/domain/free_mail_domain"] == 5

    def test_the_blocklists_flip_side_is_counted(self):
        _result, report = resolve([rec("stripe", "cus_1", 1, domain="gmail.com")])
        assert report.identity_less["company/stripe"] == 1

    def test_placeholder_values_are_blocked(self):
        result, report = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="n/a"),
                rec("stripe", "cus_1", 2, domain="n/a"),
            ]
        )
        assert len(result["clusters"]) == 2
        assert report.counts["identity_blocked/company/domain/placeholder"] == 2

    def test_test_mailboxes_are_blocked_on_person(self):
        result, report = resolve(
            [
                r.Record("hubspot", "person", "p1", 1, {"email": "test@acme.io"}),
                r.Record("stripe", "person", "p2", 2, {"email": "test@acme.io"}),
            ]
        )
        assert len(result["clusters"]) == 2
        assert any("placeholder_mailbox" in k for k in report.counts)

    def test_a_free_mail_address_still_identifies_a_person(self):
        result, _ = resolve(
            [
                r.Record("hubspot", "person", "p1", 1, {"email": "rich@gmail.com"}),
                r.Record("stripe", "person", "p2", 2, {"email": "rich@gmail.com"}),
            ]
        )
        assert len(result["clusters"]) == 1


class TestCanonicalIds:
    def test_the_id_is_uuid5_of_the_anchor_member(self):
        result, _ = resolve([rec("hubspot", "hs_1", 1, domain="acme.io")])
        assert result["clusters"][0].canonical_id == r.canonical_id_for(
            "hubspot|company|hs_1"
        )

    def test_ids_are_identical_across_runs(self):
        records = [
            rec("hubspot", "hs_1", 1, domain="acme.io"),
            rec("stripe", "cus_1", 2, domain="acme.io"),
        ]
        first, _ = resolve(records)
        second, _ = resolve(list(reversed(records)))
        assert [c.canonical_id for c in first["clusters"]] == [
            c.canonical_id for c in second["clusters"]
        ]

    def test_the_anchor_does_not_move_when_a_new_source_sorts_first(self):
        first, _ = resolve([rec("hubspot", "hs_1", 1, domain="acme.io")])
        second, _ = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("adroll", "ad_1", 2, domain="acme.io"),
            ]
        )
        assert first["clusters"][0].canonical_id == second["clusters"][0].canonical_id

    def test_an_identity_value_changing_does_not_rename_the_entity(self):
        before, _ = resolve([rec("hubspot", "hs_1", 1, domain="acme.io")])
        after, _ = resolve([rec("hubspot", "hs_1", 1, domain="acme-corp.io")])
        assert before["clusters"][0].canonical_id == after["clusters"][0].canonical_id


class TestDeterminism:
    def test_mint_order_comes_from_the_log_not_from_input_order(self):
        records = [
            rec("stripe", "cus_1", 5, domain="a.io"),
            rec("hubspot", "hs_1", 2, domain="b.io"),
            rec("zendesk", "zd_1", 9, domain="c.io"),
        ]
        first, _ = resolve(records)
        second, _ = resolve(sorted(records, key=lambda x: x.source_id, reverse=True))
        assert (
            [c.anchor_key for c in first["clusters"]]
            == [c.anchor_key for c in second["clusters"]]
            == [
                "hubspot|company|hs_1",
                "stripe|company|cus_1",
                "zendesk|company|zd_1",
            ]
        )


class TestBlocklistUnit:
    @pytest.mark.parametrize(
        "attr,value,expected",
        [
            ("domain", "gmail.com", "free_mail_domain"),
            ("domain", "acme.io", None),
            ("domain", "", "empty"),
            ("email", "n/a", "placeholder"),
            ("email", "noreply@acme.io", "placeholder_mailbox"),
            ("email", "jane@gmail.com", None),
            ("domain", "jane@gmail.com", "free_mail_domain"),
        ],
    )
    def test_reasons(self, attr, value, expected):
        assert r.is_blocked(attr, value) == expected
