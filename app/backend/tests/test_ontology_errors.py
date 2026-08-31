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


class TestIdentity:
    def test_identity_must_be_a_list(self, tmp_path):
        doc = a_doc()
        doc["entities"]["company"]["identity"] = "domain"
        with pytest.raises(ont.OntologyError, match="`identity:` must be a list"):
            ont.load(write(tmp_path, doc))

    def test_identity_may_only_name_attrs_the_entity_carries(self, tmp_path):
        doc = a_doc()
        doc["entities"]["company"]["identity"] = ["vat_number"]
        with pytest.raises(ont.OntologyError, match="is not a declared attr"):
            ont.load(write(tmp_path, doc))


class TestRelationships:
    def _with(self, tmp_path, *rels):
        doc = a_doc(relationships=list(rels))
        doc["entities"]["deal"] = {"attrs": {"amount": "number"}}
        return write(tmp_path, doc)

    def test_a_relationship_that_is_not_a_mapping_is_refused(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="must be a mapping"):
            ont.load(self._with(tmp_path, "deal belongs_to company"))

    def test_a_via_grounding_names_its_ref(self):
        rel = ont.Relationship(
            rel="belongs_to",
            from_type="deal",
            to_type="company",
            cardinality="many_to_one",
            via="account_ref",
        )
        assert rel.grounding == "via:account_ref"

    def test_a_match_grounding_names_its_attr(self):
        rel = ont.Relationship(
            rel="same_as",
            from_type="company",
            to_type="company",
            cardinality="one_to_one",
            match="domain",
        )
        assert rel.grounding == "match:domain"

    def test_a_relationship_missing_a_required_key_names_it(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="is missing"):
            ont.load(self._with(tmp_path, {"rel": "belongs_to", "from": "deal"}))

    def test_an_unknown_cardinality_lists_the_known_ones(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="is not one of"):
            ont.load(
                self._with(
                    tmp_path,
                    {
                        "rel": "belongs_to",
                        "from": "deal",
                        "to": "company",
                        "cardinality": "some_to_some",
                        "via": "account_ref",
                    },
                )
            )

    @pytest.mark.parametrize(
        "grounding",
        [
            {},
            {"via": "account_ref", "match": "domain"},
        ],
    )
    def test_a_relationship_needs_exactly_one_grounding(self, tmp_path, grounding):
        with pytest.raises(ont.OntologyError, match="exactly one grounding"):
            ont.load(
                self._with(
                    tmp_path,
                    {
                        "rel": "belongs_to",
                        "from": "deal",
                        "to": "company",
                        "cardinality": "many_to_one",
                        **grounding,
                    },
                )
            )

    def test_a_duplicate_relationship_is_refused(self, tmp_path):
        rel = {
            "rel": "belongs_to",
            "from": "deal",
            "to": "company",
            "cardinality": "many_to_one",
            "via": "account_ref",
        }
        with pytest.raises(ont.OntologyError, match="duplicate relationship"):
            ont.load(self._with(tmp_path, rel, dict(rel)))


class TestSourcePriority:
    def test_source_priority_must_be_a_list(self, tmp_path):
        with pytest.raises(ont.OntologyError, match="must be a list"):
            ont.load(write(tmp_path, a_doc(source_priority={"a": 1})))

    def test_an_unlisted_source_sorts_last_rather_than_undefined(self, tmp_path):
        loaded = ont.load(write(tmp_path, a_doc(source_priority=["hubspot", "stripe"])))
        assert loaded.priority_index("hubspot") == 0
        assert loaded.priority_index("stripe") == 1
        assert loaded.priority_index("never_heard_of_it") == 2


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
