import pytest
import yaml

from app.engine import ontology as ont


def write(tmp_path, doc):
    path = tmp_path / "ontology.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


def a_doc(**overrides):
    doc = {
        "entities": {
            "company": {"attrs": {"domain": "string", "name": "string"}},
        },
    }
    doc.update(overrides)
    return doc


class TestTheFile:
    def test_a_top_level_that_is_not_a_mapping_is_refused(self, tmp_path):
        path = tmp_path / "ontology.yaml"
        path.write_text("- a\n- b\n")
        with pytest.raises(ont.OntologyError, match="top level must be a mapping"):
            ont.load(path)

    def test_a_file_with_no_entities_is_refused(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="non-empty mapping"):
            ont.load(write(tmp_path, {"entities": {}}))


class TestEntities:
    def test_an_entity_that_is_not_a_mapping_is_refused(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="must be a mapping"):
            ont.load(write(tmp_path, {"entities": {"company": "nope"}}))

    def test_an_entity_with_no_attrs_is_refused(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="declares no attrs"):
            ont.load(write(tmp_path, {"entities": {"company": {"attrs": {}}}}))

    def test_an_unknown_attr_type_lists_the_known_ones(self, tmp_path):
        doc = a_doc()
        doc["entities"]["company"]["attrs"]["domain"] = "colour"
        with pytest.raises(ont.OntologyError, match="is not one of"):
            ont.load(write(tmp_path, doc))


class TestBoot:
    def test_the_shipped_file_loads(self):
        assert ont.load() is not None

    def test_company_person_deal_are_present(self):
        loaded = ont.load()
        for entity in ("company", "person", "deal"):
            assert entity in loaded.entities

    def test_deal_currency_is_declared(self):
        loaded = ont.load()
        assert loaded.attr_type("deal", "currency") is not None
