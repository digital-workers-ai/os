import shutil
from pathlib import Path

import pytest
import yaml

from app import caches
from app.engine import checks
from app.sources.google_sheets import connector as google_sheets_connector
from app.sources.hubspot import connector as hubspot_connector
from app.sources.salesforce import connector as salesforce_connector

KNOWLEDGE = Path(caches.BACKEND_DIR)
ALL_FILES = (
    "mappings.yaml",
    "ontology.yaml",
    "transforms.yaml",
    "metrics.yaml",
    "sources.yaml",
    "rules.yaml",
    "goals.yaml",
)


@pytest.fixture
def files(tmp_path):
    for name in ALL_FILES:
        shutil.copy(KNOWLEDGE / name, tmp_path / name)

    class Bundle:
        root = tmp_path

        def edit(self, name, mutate):
            path = tmp_path / name
            doc = yaml.safe_load(path.read_text())
            mutate(doc)
            path.write_text(yaml.safe_dump(doc, sort_keys=False))

        def problems(self):
            return checks.run(
                mapping_paths=[tmp_path / "mappings.yaml"],
                ontology_path=tmp_path / "ontology.yaml",
                transforms_path=tmp_path / "transforms.yaml",
                metrics_path=tmp_path / "metrics.yaml",
                sources_path=tmp_path / "sources.yaml",
                rules_path=tmp_path / "rules.yaml",
                goals_path=tmp_path / "goals.yaml",
            )

    return Bundle()


def _rel(doc, name, from_type):
    for entry in doc["relationships"]:
        if entry["rel"] == name and entry["from"] == from_type:
            return entry
    raise AssertionError(f"no {from_type} {name} relationship in the ontology")


class TestShippedFiles:
    def test_the_shipped_files_agree(self):
        assert checks.run() == []

    def test_the_copy_used_by_the_negative_tests_also_passes(self, files):
        assert files.problems() == []


class TestEachCheckFires:
    def test_a_label_not_declared_in_the_ontology(self, files):
        files.edit(
            "mappings.yaml",
            lambda d: d["company"].update(
                {"hubspot.companies.properties.city": "city"}
            ),
        )
        assert any("not declared as an attr" in p for p in files.problems())

    def test_an_attr_no_mapping_line_fills(self, files):
        files.edit(
            "ontology.yaml",
            lambda d: d["entities"]["company"]["attrs"].update({"headcount": "number"}),
        )
        assert any("no mapping line produces it" in p for p in files.problems())

    def test_one_label_two_meanings(self, files):
        def mutate(doc):
            doc["entities"]["campaign"]["attrs"]["name"] = "number"

        files.edit("ontology.yaml", mutate)
        assert any("same label must mean the same thing" in p for p in files.problems())

    def test_a_source_prefix_with_no_connector(self, files):
        files.edit(
            "mappings.yaml",
            lambda d: d["company"].update({"netsuite.customers.domain": "domain"}),
        )
        assert any("matches no connector" in p for p in files.problems())

    def test_a_transform_that_is_not_in_the_registry(self, files):
        files.edit(
            "transforms.yaml", lambda d: d.update({"domain": "normalise_domain"})
        )
        assert any("not in the registry" in p for p in files.problems())

    def test_a_transform_whose_type_contradicts_the_ontology(self, files):
        files.edit(
            "transforms.yaml", lambda d: d.update({"industry": "normalize_money"})
        )
        assert any("ontology declares it string" in p for p in files.problems())

    def test_a_relationship_pointing_at_an_undeclared_entity(self, files):
        files.edit(
            "ontology.yaml",
            lambda d: _rel(d, "belongs_to", "subscription").update(
                {"to": "organisation"}
            ),
        )
        assert any("is not a declared entity" in p for p in files.problems())

    def test_a_via_that_names_no_declared_label(self, files):
        files.edit(
            "ontology.yaml",
            lambda d: _rel(d, "belongs_to", "subscription").update(
                {"via": "organization_ref"}
            ),
        )
        assert any(
            "via 'organization_ref' is not an attr" in p for p in files.problems()
        )

    def test_a_match_that_the_target_does_not_carry(self, files):
        files.edit(
            "ontology.yaml",
            lambda d: _rel(d, "performed_by", "event").update({"match": "occurred_at"}),
        )
        assert any(
            "match 'occurred_at' is not an attr of person" in p
            for p in files.problems()
        )

    def test_an_identity_attr_with_no_transform(self, files):
        files.edit("transforms.yaml", lambda d: d.pop("domain"))
        assert any("merge evidence must be normalized" in p for p in files.problems())

    def test_a_metric_over_an_undeclared_entity(self, files):
        files.edit(
            "metrics.yaml",
            lambda d: d.update(
                {"bogus": {"entity": "invoice", "expression": "COUNT(entity)"}}
            ),
        )
        assert any("is not declared in the ontology" in p for p in files.problems())

    def test_a_metric_aggregating_an_attr_the_entity_lacks(self, files):
        files.edit(
            "metrics.yaml",
            lambda d: d.update(
                {"bogus": {"entity": "campaign", "expression": "SUM(mrr)"}}
            ),
        )
        assert any("not an attr of campaign" in p for p in files.problems())

    def test_a_metric_summing_a_string(self, files):
        files.edit(
            "metrics.yaml",
            lambda d: d.update(
                {"bogus": {"entity": "company", "expression": "SUM(industry)"}}
            ),
        )
        assert any("category error" in p for p in files.problems())

    def test_a_metric_filtering_on_an_attr_the_entity_lacks(self, files):
        files.edit(
            "metrics.yaml",
            lambda d: d.update(
                {
                    "bogus": {
                        "entity": "campaign",
                        "expression": "COUNT(entity)",
                        "filter": {"industry": "Software"},
                    }
                }
            ),
        )
        assert any("filters on 'industry'" in p for p in files.problems())

    def test_a_hook_field_from_a_source_with_no_hook(self, files):
        files.edit(
            "mappings.yaml",
            lambda d: d["event"].update(
                {"customerio.activities._computed": "event_name"}
            ),
        )
        assert any("customerio" in p and "extract" in p for p in files.problems())

    def test_a_connector_with_no_status_row(self, files):
        files.edit("sources.yaml", lambda d: d["sources"].pop("zendesk"))
        assert any("has no status row" in p for p in files.problems())

    def test_a_mapped_source_still_marked_unmapped(self, files):
        files.edit(
            "sources.yaml",
            lambda d: d["sources"].update({"stripe": {"status": "unmapped"}}),
        )
        assert any(
            "marked unmapped but has mapping lines" in p for p in files.problems()
        )

    def test_an_unmapped_source_claiming_validation(self, files):
        files.edit(
            "mappings.yaml",
            lambda d: [
                section.pop(key)
                for section in d.values()
                for key in [k for k in section if k.startswith("segment.")]
            ],
        )
        assert any("has no mapping lines" in p for p in files.problems())


class TestAccountCurrencyExemption:
    def test_a_money_mapping_source_must_declare_or_map_its_currency(
        self, files, monkeypatch
    ):
        monkeypatch.setattr(hubspot_connector, "ACCOUNT_CURRENCY", None)
        assert any("hubspot" in p and "ACCOUNT_CURRENCY" in p for p in files.problems())

    def test_an_unmapped_currency_attr_is_exempt_only_while_a_connector_declares_it(
        self, files, monkeypatch
    ):
        assert not any("deal.currency" in p for p in files.problems())
        for module in (
            hubspot_connector,
            salesforce_connector,
            google_sheets_connector,
        ):
            monkeypatch.setattr(module, "ACCOUNT_CURRENCY", None)
        assert any(
            "deal.currency" in p and "no mapping line produces it" in p
            for p in files.problems()
        )


class TestValidationLabels:
    def test_nothing_ships_on_by_default_until_it_is_provider_validated(self):
        status = checks.load_source_status()
        for source in checks.enabled_sources():
            assert status[source]["status"] == "provider-validated", source

    def test_the_pilot_sources_are_labelled_mock_validated(self):
        status = checks.load_source_status()
        for source in ("hubspot", "salesforce", "stripe", "customerio", "google_ads"):
            assert status[source]["status"] == "mock-validated"

    def test_a_provider_validated_source_is_enabled(self, monkeypatch):
        monkeypatch.setattr(
            checks,
            "load_source_status",
            lambda path=None: {
                "zoom": {"status": "provider-validated"},
                "stripe": {"status": "provider-validated"},
                "hubspot": {"status": "mock-validated"},
            },
        )
        assert checks.enabled_sources() == ["stripe", "zoom"]
