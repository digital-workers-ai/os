import shutil
from pathlib import Path

import pytest
import yaml

from app import caches
from app.engine import checks

DEFINITIONS = Path(caches.DEFINITIONS_DIR)
ALL_FILES = (
    "mappings.yaml",
    "ontology.yaml",
    "transforms.yaml",
    "metrics.yaml",
    "rules.yaml",
    "goals.yaml",
)


@pytest.fixture
def files(tmp_path):
    for name in ALL_FILES:
        shutil.copy(DEFINITIONS / name, tmp_path / name)

    class Bundle:
        root = tmp_path

        def write(self, name, text):
            (tmp_path / name).write_text(text)

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
                rules_path=tmp_path / "rules.yaml",
                goals_path=tmp_path / "goals.yaml",
            )

    return Bundle()


class TestAFileThatWillNotParse:
    def test_an_unparseable_mapping_file_stops_everything_at_once(self, files):
        files.write("mappings.yaml", "mappings:\n  - not a mapping line\n")
        assert len(files.problems()) == 1

    def test_an_unparseable_ontology_stops_everything_at_once(self, files):
        files.write("ontology.yaml", "entities: []\n")
        assert len(files.problems()) == 1

    def test_a_transforms_file_that_is_not_a_mapping_stops_everything_at_once(
        self, files
    ):
        files.write("transforms.yaml", "- a\n- b\n")
        problems = files.problems()
        assert len(problems) == 1
        assert "top level must be a mapping" in problems[0]

    def test_a_broken_metrics_file_is_reported_and_the_run_continues(self, files):
        files.write("metrics.yaml", "metrics:\n  bad: [not, a, mapping]\n")
        assert any("metric" in p for p in files.problems())

    def test_unparseable_yaml_in_rules_is_reported_and_the_run_continues(self, files):
        files.write("rules.yaml", "rules: [unclosed\n")
        problems = files.problems()
        assert any("rules.yaml" in p for p in problems)
        assert len(problems) >= 1

    def test_unparseable_yaml_in_goals_is_reported_and_the_run_continues(self, files):
        files.write("goals.yaml", "goals: {unclosed\n")
        assert any("goals.yaml" in p for p in files.problems())

    def test_a_rule_with_no_entity_is_still_caught_by_the_checks(self, files):
        files.write("rules.yaml", "rules:\n  bad: 42\n")
        assert files.problems()

    def test_the_error_carries_every_problem_it_found(self):
        error = checks.BuildCheckError(["first", "second"])
        assert error.problems == ["first", "second"]
        assert str(error).startswith("build checks failed:")
        assert "first" in str(error) and "second" in str(error)


class TestMappingsAgainstTheOntology:
    def test_a_mapping_for_an_entity_the_ontology_does_not_declare(self, files):
        def mutate(doc):
            doc["entities"].pop("ticket")

        files.edit("ontology.yaml", mutate)
        assert any(
            "'ticket' is not declared in ontology.yaml" in p for p in files.problems()
        )

    def test_an_identity_attr_that_is_not_a_declared_attr(self, files):
        def mutate(doc):
            doc["entities"]["company"]["attrs"].pop("domain")

        files.edit("ontology.yaml", mutate)
        assert any("domain" in p for p in files.problems())

    def test_a_transform_naming_a_label_no_entity_declares(self, files):
        def mutate(doc):
            doc["never_declared_anywhere"] = "normalize_text"

        files.edit("transforms.yaml", mutate)
        assert any("orphan transform entry never runs" in p for p in files.problems())


class TestGoalChecks:
    def test_a_goal_that_is_not_a_mapping_is_refused(self):
        problems = checks.check_goals(
            {"grow_mrr": "not a mapping"}, metric_defs={"mrr": {}}
        )
        assert any("must be a mapping" in p for p in problems)

    def test_a_goal_missing_a_required_key_names_it(self):
        problems = checks.check_goals(
            {"grow_mrr": {"metric": "mrr"}}, metric_defs={"mrr": {}}
        )
        assert any("is missing" in p for p in problems)

    def test_a_goal_naming_a_metric_that_was_renamed_is_refused(self):
        problems = checks.check_goals(
            {
                "grow_mrr": {
                    "metric": "monthly_revenue",
                    "strategy": "at_least",
                    "target": 1,
                    "label": "Grow MRR",
                }
            },
            metric_defs={"mrr": {}},
        )
        assert any("monthly_revenue" in p for p in problems)

    def test_no_goals_at_all_is_not_a_problem(self):
        assert checks.check_goals({}, metric_defs={}) == []
        assert checks.check_goals(None, metric_defs={}) == []
