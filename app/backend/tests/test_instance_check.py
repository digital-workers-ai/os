import shutil
import sys
from pathlib import Path

import pytest
import yaml

from app.engine import spy
from tests import ground_truth
from tools import instance_check, seed_demo

WORLD = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "world"

pytestmark = pytest.mark.skipif(
    not (WORLD / "__init__.py").is_file(),
    reason="the mock is not mounted at ADVERSARIAL_ROOT",
)


def run(capsys, argv=()) -> tuple[dict, int]:
    code = instance_check.main(list(argv))
    lines = capsys.readouterr().out.splitlines()
    return dict(line.split(": ", 1) for line in lines), code


def rewrite_world(tmp_path, monkeypatch, mutate) -> None:
    data = yaml.safe_load((WORLD / "data.yaml").read_text())
    mutate(data)
    other = tmp_path / "world.yaml"
    other.write_text(yaml.safe_dump(data))
    monkeypatch.setenv("WORLD_DATA", str(other))
    monkeypatch.delitem(sys.modules, "seeds.world", raising=False)


class TestTheTemplateTree:
    def test_every_check_passes_with_one_line_each(self, capsys):
        report, code = run(capsys)
        assert report == {
            "definitions": "ok",
            "world": "ok",
            "fixtures": "ok",
            "studio": "ok",
            "names": "skipped (no --names file)",
        }
        assert code == 0

    def test_terms_nothing_carries_pass_the_name_scan(self, capsys, tmp_path):
        names = tmp_path / "names.txt"
        names.write_text("Nonesuch Corp\nnonesuch.example\n")
        report, code = run(capsys, ["--names", str(names)])
        assert report["names"] == "ok"
        assert code == 0

    def test_the_template_brand_is_found_where_it_lives(self, capsys, tmp_path):
        names = tmp_path / "names.txt"
        names.write_text("Pipedrive\n")
        report, code = run(capsys, ["--names", str(names)])
        assert report["names"].startswith("'Pipedrive' in ")
        assert "definitions/spy.yaml" in report["names"]
        assert "mock/world/data.yaml" in report["names"]
        assert code == 1


class TestTheNameScan:
    def test_words_match_whole_while_domains_and_emails_match_inside(
        self, capsys, tmp_path, monkeypatch
    ):
        tree = tmp_path / "tree"
        (tree / "brand").mkdir(parents=True)
        (tree / "brand" / "voice.md").write_text(
            "Pipedrive sells at www.pipedrive.com; write ana@pipedrive.com. "
            "A Pipedriver is not a Pipedrive."
        )
        (tree / "logo.svg").write_bytes(b"\x89PNG\x00\x01<text>PIPEDRIVE</text>")
        monkeypatch.setattr(instance_check, "SCANNED", [("definitions", tree)])
        names = tmp_path / "names.txt"
        names.write_text("pipe\n\nPIPEDRIVE\npipedrive.com\nana@pipedrive.com\ndrive\n")
        report, code = run(capsys, ["--names", str(names)])
        assert report["names"] == (
            "'PIPEDRIVE' in definitions/brand/voice.md, definitions/logo.svg; "
            "'pipedrive.com' in definitions/brand/voice.md; "
            "'ana@pipedrive.com' in definitions/brand/voice.md"
        )
        assert code == 1

    def test_a_root_the_tree_lacks_is_simply_not_scanned(
        self, capsys, tmp_path, monkeypatch
    ):
        monkeypatch.setattr(
            instance_check, "SCANNED", [("README.md", tmp_path / "README.md")]
        )
        names = tmp_path / "names.txt"
        names.write_text("Pipedrive\n")
        report, code = run(capsys, ["--names", str(names)])
        assert report["names"] == "ok"
        assert code == 0


class TestABrokenTree:
    def test_a_broken_definition_fails_the_definitions_check(
        self, capsys, tmp_path, monkeypatch
    ):
        doc = yaml.safe_load(spy.DEFAULT_SPY.read_text())
        doc["brand"]["domain"] = "Not A Host"
        broken = tmp_path / "spy.yaml"
        broken.write_text(yaml.safe_dump(doc))
        monkeypatch.setattr(spy, "DEFAULT_SPY", broken)
        report, code = run(capsys)
        assert "brand domain 'Not A Host'" in report["definitions"]
        assert report["fixtures"] == "ok"
        assert code == 1

    def test_a_world_without_a_competitor_fails_the_world_check(
        self, capsys, tmp_path, monkeypatch
    ):
        rewrite_world(tmp_path, monkeypatch, lambda d: d["spy"].update(competitors=[]))
        report, code = run(capsys)
        assert report["world"] == (
            "no competitor; "
            "spy.competitors differs between the world and definitions/spy.yaml"
        )
        assert code == 1

    def test_a_spy_brand_the_definitions_do_not_name_fails_the_world_check(
        self, capsys, tmp_path, monkeypatch
    ):
        rewrite_world(
            tmp_path, monkeypatch, lambda d: d["spy"]["brand"].update(name="Nonesuch")
        )
        report, code = run(capsys)
        assert report["world"] == (
            "spy.brand differs between the world and definitions/spy.yaml"
        )
        assert code == 1

    def test_competitors_and_queries_the_definitions_do_not_name_are_each_reported(
        self, capsys, tmp_path, monkeypatch
    ):
        def mutate(d):
            d["spy"]["competitors"].pop()
            d["spy"]["queries"].append("nonesuch crm")

        rewrite_world(tmp_path, monkeypatch, mutate)
        report, code = run(capsys)
        assert report["world"] == (
            "spy.competitors differs between the world and definitions/spy.yaml; "
            "spy.queries differs between the world and definitions/spy.yaml"
        )
        assert code == 1

    def test_a_world_file_that_will_not_load_is_reported_not_raised(
        self, capsys, tmp_path, monkeypatch
    ):
        rewrite_world(tmp_path, monkeypatch, lambda d: d.pop("people"))
        report, code = run(capsys)
        assert report["world"] == "seeds.world failed to load: KeyError: 'people'"
        assert code == 1

    def test_a_tree_without_the_mock_fails_the_world_check(self, capsys, monkeypatch):
        monkeypatch.setattr(instance_check.ground_truth, "world", lambda: None)
        report, code = run(capsys)
        assert report["world"] == (
            f"seeds.world is not importable from {ground_truth.ADVERSARIAL_ROOT}"
        )
        assert code == 1

    @pytest.fixture
    def fixtures(self, tmp_path, monkeypatch):
        copy = tmp_path / "mock"
        shutil.copytree(instance_check.MOCK_FIXTURES, copy)
        monkeypatch.setattr(instance_check, "MOCK_FIXTURES", copy)
        return copy

    def test_a_record_file_the_expectation_lists_must_exist(self, capsys, fixtures):
        (fixtures / "stripe" / "customers.json").unlink()
        report, code = run(capsys)
        assert report["fixtures"] == (
            "stripe: customers.json is listed in expected.json but missing"
        )
        assert code == 1

    def test_a_mapped_source_without_a_capture_is_named(self, capsys, fixtures):
        shutil.rmtree(fixtures / "stripe")
        report, code = run(capsys)
        assert report["fixtures"] == "stripe: no expected.json"
        assert code == 1

    @pytest.fixture
    def studio(self, tmp_path, monkeypatch):
        copy = tmp_path / "studio"
        shutil.copytree(seed_demo.STUDIO_FIXTURES, copy)
        monkeypatch.setattr(seed_demo, "STUDIO_FIXTURES", copy)
        return copy

    def test_a_manifest_size_that_disagrees_with_the_file_is_named(
        self, capsys, studio
    ):
        manifest = studio / "manifest.yaml"
        library = yaml.safe_load(manifest.read_text())
        library["assets"][0]["versions"][0]["files"][0]["bytes"] = 236
        manifest.write_text(yaml.safe_dump(library))
        report, code = run(capsys)
        assert report["studio"] == (
            "1-100-line-and-branch-coverage/1/build.md is 235 bytes, "
            "the manifest says 236"
        )
        assert code == 1

    def test_a_listed_file_that_is_absent_is_named(self, capsys, studio):
        gone = studio / "3-why-a-rebuild-never-touches-the-raw-store" / "1" / "post.md"
        gone.unlink()
        report, code = run(capsys)
        assert report["studio"] == (
            "3-why-a-rebuild-never-touches-the-raw-store/1/post.md is listed "
            "but missing"
        )
        assert code == 1
