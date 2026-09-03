import pytest

from app.engine.report import SyncReport


class TestClean:
    def test_a_report_with_nothing_refused_is_clean(self):
        assert SyncReport().clean() is True

    def test_one_refusal_is_enough_to_stop_it_being_clean(self):
        report = SyncReport()
        report.skip("amount", "hubspot", "not_a_number")
        assert report.clean() is False

    def test_observations_that_are_not_refusals_leave_it_clean(self):
        report = SyncReport()
        report.clear("amount", "hubspot")
        report.dangling("company_contact")
        report.no_identity("company", "hubspot")
        report.disagree("company", "name", 2)
        assert report.clean() is True

    @pytest.mark.parametrize(
        "spoil",
        [
            lambda r: r.skip("amount", "hubspot", "not_a_number"),
            lambda r: r.declare_path("company", "name"),
            lambda r: r.quarantine("company_contact", "c1", "two winners"),
            lambda r: r.oversize("payload", {"bytes": 99}),
            lambda r: r.record_skip("hubspot", "companies", "no_id"),
        ],
    )
    def test_each_refusal_kind_makes_it_dirty(self, spoil):
        report = SyncReport()
        spoil(report)
        assert report.clean() is False


class TestRecording:
    def test_a_skip_is_keyed_label_source_reason(self):
        report = SyncReport()
        report.skip("amount", "hubspot", "not_a_number")
        report.skip("amount", "hubspot", "not_a_number")
        assert report.as_dict()["skips"] == {"amount/hubspot/not_a_number": 2}

    def test_a_clear_is_keyed_label_source(self):
        report = SyncReport()
        report.clear("amount", "hubspot")
        assert report.as_dict()["clears"] == {"amount/hubspot": 1}

    def test_a_record_skip_is_keyed_source_object_type_reason(self):
        report = SyncReport()
        report.record_skip("hubspot", "companies", "no_id")
        assert report.as_dict()["records_skipped"] == {"hubspot/companies/no_id": 1}

    def test_a_dangling_ref_is_keyed_by_rel(self):
        report = SyncReport()
        report.dangling("company_contact")
        assert report.as_dict()["dangling_refs"] == {"company_contact": 1}

    def test_a_missing_identity_is_keyed_entity_type_source(self):
        report = SyncReport()
        report.no_identity("company", "hubspot")
        assert report.as_dict()["identity_less"] == {"company/hubspot": 1}

    def test_a_disagreement_adds_n_under_entity_dot_attr(self):
        report = SyncReport()
        report.disagree("company", "name", 3)
        assert report.as_dict()["disagreements"] == {"company.name": 3}

    def test_a_count_accumulates_under_its_key(self):
        report = SyncReport()
        report.count("records", 2)
        report.count("records")
        assert report.as_dict()["counts"] == {"records": 3}

    def test_a_quarantine_stores_the_subject_under_record(self):
        report = SyncReport()
        report.quarantine("company_contact", "c1", "two winners")
        assert report.as_dict()["quarantines"] == [
            {"rel": "company_contact", "record": "c1", "detail": "two winners"}
        ]

    def test_an_oversize_splats_its_detail_into_the_entry(self):
        report = SyncReport()
        report.oversize("payload", {"bytes": 99, "source_id": "c1"})
        assert report.as_dict()["oversized"] == [
            {"kind": "payload", "bytes": 99, "source_id": "c1"}
        ]


class TestRates:
    def test_a_rate_is_rounded_to_three_places(self):
        report = SyncReport()
        report.rate("company_contact", 3, 2, 5)
        assert report.as_dict()["match_rates"]["company_contact"] == {
            "candidates": 3,
            "matched": 2,
            "edges": 5,
            "match_rate": 0.667,
        }

    def test_zero_candidates_gives_none_not_zero(self):
        report = SyncReport()
        report.rate("company_contact", 0, 0, 0)
        assert report.as_dict()["match_rates"]["company_contact"]["match_rate"] is None


class TestDeadPaths:
    def test_declared_but_never_hit_paths_come_back_sorted(self):
        report = SyncReport()
        report.declare_path("deal", "amount")
        report.declare_path("company", "name")
        assert report.dead_paths() == ["company:name", "deal:amount"]

    def test_a_hit_path_is_not_dead(self):
        report = SyncReport()
        report.declare_path("company", "name")
        report.declare_path("company", "domain")
        report.hit_path("company", "name")
        assert report.dead_paths() == ["company:domain"]

    def test_all_paths_hit_means_no_dead_paths(self):
        report = SyncReport()
        report.declare_path("company", "name")
        report.hit_path("company", "name")
        assert report.dead_paths() == []


class TestTotals:
    def test_totals_has_nine_integer_keys_without_counts_or_rates(self):
        report = SyncReport()
        totals = report.totals()
        assert set(totals) == {
            "skips",
            "clears",
            "dead_paths",
            "quarantines",
            "dangling_refs",
            "identity_less",
            "oversized",
            "disagreements",
            "records_skipped",
        }
        assert all(isinstance(v, int) for v in totals.values())

    def test_list_shaped_facts_total_as_lengths(self):
        report = SyncReport()
        report.quarantine("r", "s", "d")
        report.quarantine("r", "s2", "d")
        report.oversize("payload", {"bytes": 1})
        report.declare_path("company", "name")
        totals = report.totals()
        assert totals["quarantines"] == 2
        assert totals["oversized"] == 1
        assert totals["dead_paths"] == 1


class TestAsDict:
    def test_it_has_twelve_keys(self):
        assert set(SyncReport().as_dict()) == {
            "totals",
            "counts",
            "skips",
            "records_skipped",
            "clears",
            "dead_paths",
            "quarantines",
            "dangling_refs",
            "identity_less",
            "oversized",
            "disagreements",
            "match_rates",
        }

    def test_counter_dicts_come_back_sorted_by_key(self):
        report = SyncReport()
        report.skip("b", "s", "r")
        report.skip("a", "s", "r")
        report.count("z")
        report.count("a")
        as_dict = report.as_dict()
        assert list(as_dict["skips"]) == ["a/s/r", "b/s/r"]
        assert list(as_dict["counts"]) == ["a", "z"]

    @pytest.mark.parametrize("key", ["quarantines", "oversized"])
    def test_unbounded_lists_are_sliced_to_two_hundred(self, key):
        report = SyncReport()
        for index in range(201):
            report.quarantine("r", f"s{index}", "d")
            report.oversize("payload", {"index": index})
        assert len(report.as_dict()[key]) == 200
        assert len(getattr(report, key)) == 201
