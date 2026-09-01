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


def resolve(records, **kwargs):
    report = SyncReport()
    return r.resolve(records, ONTO, report, **kwargs), report


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

    def test_an_oversized_bucket_is_quarantined_whole(self):
        records = [rec(f"s{i}", f"id_{i}", i, domain="shared.io") for i in range(1, 8)]
        result, report = resolve(records, bucket_cap=5)
        assert len(result["clusters"]) == 7
        assert report.oversized[0]["kind"] == "identity_bucket"
        assert report.oversized[0]["records"] == 7

    def test_under_the_cap_still_merges(self):
        records = [rec(f"s{i}", f"id_{i}", i, domain="shared.io") for i in range(1, 5)]
        result, _ = resolve(records, bucket_cap=5)
        assert len(result["clusters"]) == 1

    def test_a_value_repeated_inside_one_source_identifies_a_group(self):
        result, report = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("hubspot", "hs_2", 2, domain="acme.io"),
                rec("stripe", "cus_1", 3, domain="acme.io"),
            ]
        )
        assert len(result["clusters"]) == 3
        entry = next(
            o for o in report.oversized if o["kind"] == "shared_across_records"
        )
        assert entry["records"] == 3 and entry["sources"] == 2

    def test_one_record_per_source_still_guards_multi_attr_identity(self):
        onto2 = ontology.Ontology(
            entities={
                "company": ontology.EntitySpec(
                    "company",
                    {"domain": "string", "vendor_ref": "string"},
                    ("domain", "vendor_ref"),
                )
            },
            relationships=(),
            source_priority=(),
        )
        report = SyncReport()
        result = r.resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("hubspot", "hs_2", 2, vendor_ref="V-9"),
                rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9"),
            ],
            onto2,
            report,
        )
        assert len(result["clusters"]) == 2
        assert any(o["kind"] == "one_record_per_source" for o in report.oversized)


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


class TestGuardFiveTenantScopedNamespaces:
    def person(self, source, source_id, order, **identity):
        return rec(source, source_id, order, entity_type="person", **identity)

    def colliding_counters(self, count: int):
        records = []
        for index in range(count):
            records.append(
                self.person(
                    "zendesk",
                    f"z{index}",
                    index * 2,
                    email=f"person{index}@acme.io",
                    external_ref=str(index + 1),
                )
            )
            records.append(
                self.person(
                    "intercom",
                    f"i{index}",
                    index * 2 + 1,
                    email=f"other{index}@globex.io",
                    external_ref=str(index + 1),
                )
            )
        return records

    def test_two_tools_numbering_their_own_rows_do_not_merge_strangers(self):
        records = self.colliding_counters(20)
        result, _ = resolve(records)
        assert len(result["clusters"]) == 40

    def test_the_refusal_is_on_the_report_rather_than_silent(self):
        _result, report = resolve(self.colliding_counters(20))
        reasons = {entry["kind"] for entry in report.as_dict()["oversized"]}
        assert "namespace_not_shared" in reasons
        assert "namespace_not_shared_merge" in reasons

    def test_the_report_names_both_tools_and_shows_its_working(self):
        _result, report = resolve(self.colliding_counters(20))
        verdict = next(
            e
            for e in report.as_dict()["oversized"]
            if e["kind"] == "namespace_not_shared"
        )
        assert verdict["sources"] == ["intercom", "zendesk"]
        assert verdict["contradicted"] == 20
        assert verdict["corroborated"] == 0
        assert "numbering its own rows" in verdict["detail"]

    def test_a_genuinely_shared_key_still_merges_across_the_estate(self):
        records = []
        for index in range(20):
            key = f"user_{index}@acme"
            records.append(
                self.person(
                    "zendesk",
                    f"z{index}",
                    index * 2,
                    email=f"person{index}@acme.io",
                    external_ref=key,
                )
            )
            records.append(
                self.person(
                    "intercom",
                    f"i{index}",
                    index * 2 + 1,
                    email=f"person{index}@acme.io",
                    external_ref=key,
                )
            )
        result, _ = resolve(records)
        assert len(result["clusters"]) == 20

    def test_a_changed_email_rides_through_a_namespace_that_corroborates(self):
        records = []
        for index in range(20):
            key = f"user_{index}@acme"
            left = f"person{index}@acme.io"
            right = "renamed@acme.io" if index == 7 else left
            records.append(
                self.person(
                    "zendesk", f"z{index}", index * 2, email=left, external_ref=key
                )
            )
            records.append(
                self.person(
                    "intercom",
                    f"i{index}",
                    index * 2 + 1,
                    email=right,
                    external_ref=key,
                )
            )
        result, _ = resolve(records)
        assert len(result["clusters"]) == 20

    def test_one_corroborated_value_survives_a_split_namespace(self):
        records = self.colliding_counters(19)
        records.append(
            self.person(
                "zendesk", "zx", 100, email="real@acme.io", external_ref="shared_key"
            )
        )
        records.append(
            self.person(
                "intercom", "ix", 101, email="real@acme.io", external_ref="shared_key"
            )
        )
        result, report = resolve(records)
        assert len(result["clusters"]) == 39
        assert report.as_dict()["counts"].get(
            "namespace_value_witnessed/person/external_ref"
        )

    def test_a_globally_scoped_attr_is_never_second_guessed(self):
        result, _ = resolve(
            [
                self.person("zendesk", "z1", 1, email="jane@acme.io", external_ref="1"),
                self.person(
                    "intercom", "i1", 2, email="jane@acme.io", external_ref="2"
                ),
            ]
        )
        assert len(result["clusters"]) == 1

    def test_no_second_identity_attr_is_reported_rather_than_assumed(self):
        _result, report = resolve(
            [
                self.person("zendesk", "z1", 1, external_ref="1"),
                self.person("intercom", "i1", 2, external_ref="1"),
            ]
        )
        counts = report.as_dict()["counts"]
        assert any(
            k.startswith("identity_unwitnessed/person/external_ref") for k in counts
        )


class TestGuardThreeIsGlobalOnPurpose:
    def test_a_repeated_value_is_refused_for_every_source(self):
        result, report = resolve(
            [
                rec("stripe", "cus_1", 1, domain="acme.io"),
                rec("stripe", "cus_2", 2, domain="acme.io"),
                rec("hubspot", "hs_1", 3, domain="acme.io"),
                rec("salesforce", "sf_1", 4, domain="acme.io"),
            ]
        )
        assert len(result["clusters"]) == 4
        assert any(o["kind"] == "shared_across_records" for o in report.oversized)

    def test_the_refusal_names_the_source_that_repeated_it(self):
        _result, report = resolve(
            [
                rec("stripe", "cus_1", 1, domain="acme.io"),
                rec("stripe", "cus_2", 2, domain="acme.io"),
            ]
        )
        entry = next(
            o for o in report.oversized if o["kind"] == "shared_across_records"
        )
        assert "stripe" in entry["detail"]

    def test_a_clean_estate_still_merges(self):
        result, report = resolve(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("salesforce", "sf_1", 2, domain="acme.io"),
                rec("stripe", "cus_1", 3, domain="acme.io"),
            ]
        )
        assert len(result["clusters"]) == 1
        assert report.oversized == []


class TestGuardFiveDoesNotFailOpenOnASparseEstate:
    def person(self, source, source_id, order, **identity):
        return rec(source, source_id, order, entity_type="person", **identity)

    def _sparse_estate(self, count):
        records = []
        for index in range(count):
            records.append(
                self.person(
                    "zendesk",
                    f"z{index}",
                    index * 2,
                    email=f"person{index}@acme.io",
                    external_ref=str(index + 1),
                )
            )
            records.append(
                self.person(
                    "intercom", f"i{index}", index * 2 + 1, external_ref=str(index + 1)
                )
            )
        return records

    def test_an_uncorroborated_namespace_does_not_merge(self):
        result, _report = resolve(self._sparse_estate(20))
        assert len(result["clusters"]) == 40, "strangers merged on a bare counter"

    def test_the_refusal_is_on_the_report(self):
        _result, report = resolve(self._sparse_estate(20))
        kinds = {e["kind"] for e in report.as_dict()["oversized"]}
        assert "namespace_unwitnessed" in kinds

    def test_a_corroborated_namespace_still_merges(self):
        records = self._sparse_estate(19)
        records.append(
            self.person(
                "zendesk", "zx", 100, email="real@acme.io", external_ref="shared"
            )
        )
        records.append(
            self.person(
                "intercom", "ix", 101, email="real@acme.io", external_ref="shared"
            )
        )
        result, _report = resolve(records)
        assert len(result["clusters"]) == 20

    def test_a_globally_scoped_attr_is_untouched(self):
        result, _report = resolve(
            [
                self.person("zendesk", "z1", 1, email="jane@acme.io"),
                self.person("intercom", "i1", 2, email="jane@acme.io"),
            ]
        )
        assert len(result["clusters"]) == 1


class TestMergeHistory:
    ONTO2 = ontology.Ontology(
        entities={
            "company": ontology.EntitySpec(
                "company",
                {"domain": "string", "vendor_ref": "string"},
                ("domain", "vendor_ref"),
            )
        },
        relationships=(),
        source_priority=("hubspot", "stripe"),
    )

    def fold(self, records):
        report = SyncReport()
        return r.resolve(records, self.ONTO2, report), report

    def test_the_earlier_minted_id_survives_a_fold(self):
        first = rec("hubspot", "hs_1", 1, domain="acme.io")
        second = rec("stripe", "cus_1", 2, vendor_ref="V-9")
        bridge = rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9")
        result, _ = self.fold([first, second, bridge])
        assert len(result["clusters"]) == 1
        survivor = result["clusters"][0]
        assert survivor.canonical_id == r.canonical_id_for("hubspot|company|hs_1")

    def test_the_folded_id_retires_into_merge_history_as_an_alias(self):
        result, _ = self.fold(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("stripe", "cus_1", 2, vendor_ref="V-9"),
                rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9"),
            ]
        )
        retired = r.canonical_id_for("stripe|company|cus_1")
        assert result["aliases"] == {
            retired: r.canonical_id_for("hubspot|company|hs_1")
        }

    def test_the_survivors_id_is_not_recomputed_from_the_new_membership(self):
        result, _ = self.fold(
            [
                rec("stripe", "cus_1", 1, domain="acme.io"),
                rec("adroll", "ad_1", 2, vendor_ref="V-9"),
                rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9"),
            ]
        )
        assert result["clusters"][0].canonical_id == r.canonical_id_for(
            "stripe|company|cus_1"
        )

    def test_a_fold_that_would_break_the_source_bound_is_refused(self):
        result, report = self.fold(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("hubspot", "hs_2", 2, vendor_ref="V-9"),
                rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9"),
            ]
        )
        assert len(result["clusters"]) == 2
        assert any(o["kind"] == "one_record_per_source" for o in report.oversized)

    def test_every_record_still_maps_to_a_live_cluster_after_a_fold(self):
        result, _ = self.fold(
            [
                rec("hubspot", "hs_1", 1, domain="acme.io"),
                rec("stripe", "cus_1", 2, vendor_ref="V-9"),
                rec("zendesk", "zd_1", 3, domain="acme.io", vendor_ref="V-9"),
            ]
        )
        live = {c.canonical_id for c in result["clusters"]}
        assert set(result["of_record"].values()) == live
        assert len(result["of_record"]) == 3


class TestTheAttrIndexGoesStaleAndIsRepairedOnRead:
    def _chain(self):
        return [
            rec("hubspot", "p1", 1, entity_type="person", email="jo@acme.io"),
            rec("stripe", "p2", 2, entity_type="person", external_ref="EXT-1"),
            rec(
                "zendesk",
                "p3",
                3,
                entity_type="person",
                email="jo@acme.io",
                external_ref="EXT-1",
            ),
        ]

    def test_a_lookup_through_a_merged_away_entry_finds_the_survivor(self):
        result, _ = resolve(
            self._chain()
            + [
                rec(
                    "intercom",
                    "p4",
                    4,
                    entity_type="person",
                    email="jo@acme.io",
                    external_ref="EXT-1",
                )
            ]
        )
        assert len(result["clusters"]) == 1
        assert len(result["clusters"][0].members) == 4

    def test_every_of_record_value_still_names_a_live_cluster(self):
        result, _ = resolve(self._chain())
        live = {c.canonical_id for c in result["clusters"]}
        assert set(result["of_record"].values()) <= live
        assert len(result["of_record"]) == 3


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
