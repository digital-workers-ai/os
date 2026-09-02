import json

import pytest
import yaml

from app import caches
from app.enrichment import vocabulary
from app.enrichment.vocabulary import VocabularyError
from tests import ground_truth


@pytest.fixture
def write(tmp_path):
    def _write(name, doc):
        path = tmp_path / name
        path.write_text(yaml.safe_dump(doc, sort_keys=False))
        return path

    return _write


MINIMAL = {
    "readings": {
        "sales_call": {
            "entity": "meeting",
            "input": "transcript",
            "fields": {
                "interest": {"type": "one_of", "labels": ["strong", "weak"]},
                "pain_points": {
                    "type": "many_of",
                    "labels": ["pricing", "manual_work"],
                },
            },
        }
    }
}


def a_reading(**overrides):
    body = {
        "entity": "meeting",
        "input": "transcript",
        "fields": {
            "pain_points": {"type": "many_of", "labels": ["pricing", "timeline"]}
        },
    }
    body.update(overrides)
    return {"readings": {"sales_call": body}}


class TestTheShippedFile:
    def test_the_committed_file_is_the_default(self):
        assert vocabulary.DEFAULT_ENRICHMENT_FILES == [
            caches.KNOWLEDGE_DIR / "enrichment.yaml"
        ]

    def test_it_loads_and_declares_the_sales_call_reading(self):
        readings = vocabulary.load()
        assert "sales_call" in readings
        reading = readings["sales_call"]
        assert reading.entity == "meeting"
        assert reading.input_attr == "transcript"

    def test_it_carries_the_three_questions_the_plan_names(self):
        fields = {f.name: f for f in vocabulary.load()["sales_call"].fields}
        assert set(fields) == {"interest", "pain_points", "timing"}
        assert fields["interest"].kind == "one_of"
        assert fields["pain_points"].kind == "many_of"
        assert fields["timing"].kind == "one_of"

    def test_its_labels_are_the_vocabulary_the_seed_world_plants(self):
        world = ground_truth.world()
        if world is None:
            pytest.skip("seed world not mounted at /adversarial")
        fields = {f.name: set(f.labels) for f in vocabulary.load()["sales_call"].fields}
        assert fields["interest"] == set(world.INTEREST_LEVELS)
        assert fields["pain_points"] == set(world.PAIN_POINTS)
        assert fields["timing"] == set(world.PURCHASE_TIMING)


class TestTheFileIsCheckedNotTrusted:
    def test_an_unknown_field_type_lists_the_known_ones(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"]["interest"]["type"] = "free_text"
        with pytest.raises(VocabularyError, match="is not one of"):
            vocabulary.load([write("e.yaml", doc)])

    def test_an_empty_label_set_is_a_build_error(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"]["interest"]["labels"] = []
        with pytest.raises(VocabularyError, match="no labels"):
            vocabulary.load([write("e.yaml", doc)])

    def test_a_duplicate_label_is_a_build_error(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"]["interest"]["labels"] = [
            "strong",
            "strong",
        ]
        with pytest.raises(VocabularyError, match="duplicate"):
            vocabulary.load([write("e.yaml", doc)])

    @pytest.mark.parametrize("label", ["Strong", "very strong", "strong!", "1st"])
    def test_a_label_that_is_not_snake_case_is_a_build_error(self, write, label):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"]["interest"]["labels"] = [label]
        with pytest.raises(VocabularyError, match="snake_case"):
            vocabulary.load([write("e.yaml", doc)])

    def test_a_reading_with_no_fields_is_a_build_error(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"] = {}
        with pytest.raises(VocabularyError, match="no fields"):
            vocabulary.load([write("e.yaml", doc)])


class TestTheFileItself:
    def test_a_top_level_that_is_not_a_mapping_is_named(self, tmp_path):
        path = tmp_path / "vocab.yaml"
        path.write_text("- just\n- a\n- list\n")
        with pytest.raises(VocabularyError, match="top level must be a mapping"):
            vocabulary.load([path])

    def test_a_file_with_no_readings_block_says_so(self, write):
        with pytest.raises(VocabularyError, match="no `readings:` block"):
            vocabulary.load([write("vocab.yaml", {"something_else": {}})])

    def test_a_readings_block_that_is_not_a_mapping_is_refused(self, write):
        with pytest.raises(VocabularyError, match="must be a mapping"):
            vocabulary.load([write("vocab.yaml", {"readings": ["sales_call"]})])

    def test_the_filename_is_in_the_message(self, write):
        path = write("tenant_vocab.yaml", {"readings": {"sales_call": "not a mapping"}})
        with pytest.raises(VocabularyError, match="tenant_vocab.yaml"):
            vocabulary.load([path])


class TestAReading:
    def test_a_reading_that_is_not_a_mapping_is_refused(self, write):
        path = write("vocab.yaml", {"readings": {"sales_call": "text"}})
        with pytest.raises(VocabularyError, match="must be a mapping"):
            vocabulary.load([path])

    def test_a_reading_name_must_be_snake_case(self, write):
        doc = a_reading()
        doc["readings"]["SalesCall"] = doc["readings"].pop("sales_call")
        with pytest.raises(VocabularyError, match="not snake_case"):
            vocabulary.load([write("vocab.yaml", doc)])

    def test_a_reading_must_name_an_entity(self, write):
        with pytest.raises(VocabularyError, match="names no entity"):
            vocabulary.load([write("vocab.yaml", a_reading(entity=""))])

    def test_a_reading_must_name_the_attr_holding_its_text(self, write):
        with pytest.raises(VocabularyError, match="names no input attr"):
            vocabulary.load([write("vocab.yaml", a_reading(input=""))])


class TestAField:
    def test_a_field_name_must_be_snake_case(self, write):
        fields = {"PainPoints": {"type": "many_of", "labels": ["pricing"]}}
        path = write("vocab.yaml", a_reading(fields=fields))
        with pytest.raises(VocabularyError, match="not snake_case"):
            vocabulary.load([path])

    def test_a_field_that_is_not_a_mapping_is_refused(self, write):
        path = write("vocab.yaml", a_reading(fields={"pain_points": ["pricing"]}))
        with pytest.raises(VocabularyError, match="must be a mapping"):
            vocabulary.load([path])


class TestLabels:
    def test_labels_may_be_a_plain_list(self, write):
        fields = {"pain_points": {"type": "many_of", "labels": ["pricing"]}}
        path = write("vocab.yaml", a_reading(fields=fields))
        reading = vocabulary.load([path])["sales_call"]
        assert reading.fields[0].glosses == (("pricing", ""),)

    def test_labels_may_be_a_label_to_meaning_mapping(self, write):
        path = write(
            "vocab.yaml",
            a_reading(
                fields={
                    "pain_points": {
                        "type": "many_of",
                        "labels": {"pricing": "cost is the blocker"},
                    }
                }
            ),
        )
        field = vocabulary.load([path])["sales_call"].fields[0]
        assert field.meaning("pricing") == "cost is the blocker"

    def test_an_unknown_label_glosses_to_empty_rather_than_raising(self, write):
        path = write("vocab.yaml", a_reading())
        field = vocabulary.load([path])["sales_call"].fields[0]
        assert field.meaning("never_defined") == ""

    def test_labels_of_the_wrong_shape_name_the_type_they_got(self, write):
        path = write(
            "vocab.yaml",
            a_reading(fields={"pain_points": {"type": "many_of", "labels": "pricing"}}),
        )
        with pytest.raises(VocabularyError, match="got str"):
            vocabulary.load([path])


class TestTheOverlayRuleThatDiffersFromMappings:
    def test_a_later_file_may_add_a_reading(self, write):
        base = write("base.yaml", MINIMAL)
        extra = write(
            "tenant.yaml",
            {
                "readings": {
                    "support_call": {
                        "entity": "meeting",
                        "input": "transcript",
                        "fields": {
                            "mood": {"type": "one_of", "labels": ["calm", "angry"]}
                        },
                    }
                }
            },
        )
        readings = vocabulary.load([base, extra])
        assert set(readings) == {"sales_call", "support_call"}

    def test_a_later_file_may_replace_a_readings_labels_outright(self, write):
        base = write("base.yaml", MINIMAL)
        tenant = write(
            "tenant.yaml",
            {
                "readings": {
                    "sales_call": {
                        "entity": "meeting",
                        "input": "transcript",
                        "fields": {
                            "interest": {
                                "type": "one_of",
                                "labels": ["hot", "warm", "cold"],
                            }
                        },
                    }
                }
            },
        )
        reading = vocabulary.load([base, tenant])["sales_call"]
        fields = {f.name: f for f in reading.fields}
        assert set(fields) == {"interest"}
        assert fields["interest"].labels == ("hot", "warm", "cold")
        assert reading.origin == "tenant.yaml"

    def test_replacing_is_whole_reading_not_a_field_merge(self, write):
        base = write("base.yaml", MINIMAL)
        tenant = write(
            "tenant.yaml",
            {
                "readings": {
                    "sales_call": {
                        "entity": "meeting",
                        "input": "transcript",
                        "fields": {"interest": {"type": "one_of", "labels": ["hot"]}},
                    }
                }
            },
        )
        reading = vocabulary.load([base, tenant])["sales_call"]
        assert [f.name for f in reading.fields] == ["interest"]


class TestTheDigest:
    def test_the_same_spec_digests_the_same_way_twice(self, write):
        a = vocabulary.load([write("a.yaml", MINIMAL)])["sales_call"]
        b = vocabulary.load([write("b.yaml", MINIMAL)])["sales_call"]
        assert a.sha == b.sha

    def test_changing_a_label_changes_the_digest(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        before = vocabulary.load([write("a.yaml", MINIMAL)])["sales_call"].sha
        doc["readings"]["sales_call"]["fields"]["interest"]["labels"] = ["hot"]
        after = vocabulary.load([write("b.yaml", doc)])["sales_call"].sha
        assert before != after

    def test_reordering_labels_changes_the_digest(self, write):
        doc = json.loads(json.dumps(MINIMAL))
        doc["readings"]["sales_call"]["fields"]["interest"]["labels"] = [
            "weak",
            "strong",
        ]
        assert (
            vocabulary.load([write("a.yaml", MINIMAL)])["sales_call"].sha
            != vocabulary.load([write("b.yaml", doc)])["sales_call"].sha
        )


class TestTheGeneratedModel:
    def test_a_one_of_field_is_a_single_finding_and_many_of_is_a_list(self, write):
        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        instance = model.model_validate(
            {
                "interest": {"label": "strong", "quote": "we want it"},
                "pain_points": [{"label": "pricing", "quote": "too dear"}],
            }
        )
        assert instance.interest.label.value == "strong"
        assert instance.pain_points[0].label.value == "pricing"

    def test_every_answer_is_forced_to_carry_a_quote(self, write):
        from pydantic import ValidationError

        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        with pytest.raises(ValidationError):
            model.model_validate({"interest": {"label": "strong"}, "pain_points": []})

    def test_a_label_outside_the_file_is_rejected(self, write):
        from pydantic import ValidationError

        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        with pytest.raises(ValidationError):
            model.model_validate(
                {
                    "interest": {"label": "lukewarm", "quote": "maybe"},
                    "pain_points": [],
                }
            )

    def test_an_extra_field_is_rejected(self, write):
        from pydantic import ValidationError

        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        with pytest.raises(ValidationError):
            model.model_validate(
                {
                    "interest": {"label": "strong", "quote": "we want it"},
                    "pain_points": [],
                    "mood": {"label": "calm", "quote": "so calm"},
                }
            )

    def test_many_of_accepts_the_empty_list(self, write):
        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        instance = model.model_validate(
            {"interest": {"label": "weak", "quote": "not now"}, "pain_points": []}
        )
        assert instance.pain_points == []

    def test_the_json_schema_the_api_receives_encodes_the_closed_set(self, write):
        model = vocabulary.model_for(
            vocabulary.load([write("e.yaml", MINIMAL)])["sales_call"]
        )
        blob = json.dumps(model.model_json_schema())
        for label in ("strong", "weak", "pricing", "manual_work"):
            assert f'"{label}"' in blob

    def test_two_readings_do_not_share_a_generated_enum(self, write):
        base = write("base.yaml", MINIMAL)
        other = write(
            "other.yaml",
            {
                "readings": {
                    "support_call": {
                        "entity": "meeting",
                        "input": "transcript",
                        "fields": {"interest": {"type": "one_of", "labels": ["hot"]}},
                    }
                }
            },
        )
        readings = vocabulary.load([base, other])
        sales = vocabulary.model_for(readings["sales_call"])
        support = vocabulary.model_for(readings["support_call"])
        assert "strong" in json.dumps(sales.model_json_schema())
        assert "strong" not in json.dumps(support.model_json_schema())


class TestCaching:
    def test_the_committed_vocabulary_is_cached_between_calls(self):
        vocabulary._reset()
        assert vocabulary.load() is vocabulary.load()

    def test_reset_drops_the_cache_and_the_generated_models(self):
        vocabulary._reset()
        first = vocabulary.load()
        vocabulary._reset()
        assert vocabulary.load() is not first

    def test_an_explicit_path_never_touches_the_cache(self, write):
        vocabulary._reset()
        committed = vocabulary.load()
        path = write("vocab.yaml", a_reading())
        assert vocabulary.load([path]) is not committed
        assert vocabulary.load() is committed

    def test_a_later_file_replaces_an_earlier_reading_outright(self, write):
        first = write("a.yaml", a_reading())
        fields = {"interest": {"type": "one_of", "labels": ["strong", "weak"]}}
        second = write("b.yaml", a_reading(fields=fields))
        reading = vocabulary.load([first, second])["sales_call"]
        assert [f.name for f in reading.fields] == ["interest"]
