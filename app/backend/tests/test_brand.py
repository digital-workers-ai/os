from datetime import date

import pytest

from app.engine import brand

FRONT_MATTER = "---\ntitle: A brand file\nupdated: 2026-09-14\n---\n"

BODY = "\nWe say the useful thing first.\n"

MAX_LINES = 120


def _brand_dir(root, names=None, body=BODY, front=FRONT_MATTER):
    directory = root / "brand"
    directory.mkdir(exist_ok=True)
    for name in brand.REQUIRED if names is None else names:
        (directory / f"{name}.md").write_text(f"{front}{body}")
    return directory


class TestTheShippedFiles:
    def test_the_shipped_directory_has_no_problems(self):
        assert brand.check() == []

    def test_the_seven_files_are_the_ones_the_brand_is_made_of(self):
        assert brand.files() == sorted(brand.REQUIRED)

    @pytest.mark.parametrize("name", brand.REQUIRED)
    def test_each_file_opens_with_a_title_and_a_date(self, name):
        front, _body = brand.read(name)
        assert front["title"]
        assert front["updated"]

    @pytest.mark.parametrize("name", brand.REQUIRED)
    def test_each_file_says_something(self, name):
        _front, body = brand.read(name)
        assert body.strip()

    @pytest.mark.parametrize("name", brand.REQUIRED)
    def test_each_file_stays_short_enough_to_be_read(self, name):
        _front, body = brand.read(name)
        assert len(body.splitlines()) < MAX_LINES

    def test_proof_says_where_every_fact_comes_from(self):
        _front, body = brand.read("proof")
        assert "definitions/" in body
        assert body.lower().count("source") >= 1


class TestReadingOneFile:
    def test_the_front_matter_comes_back_apart_from_the_body(self, tmp_path):
        directory = _brand_dir(tmp_path)
        front, body = brand.read("voice", directory)
        assert front == {"title": "A brand file", "updated": date(2026, 9, 14)}
        assert body == BODY

    def test_files_lists_the_directory_by_name(self, tmp_path):
        directory = _brand_dir(tmp_path, names=("voice", "proof"))
        assert brand.files(directory) == ["proof", "voice"]


class TestTheDirectoryIsChecked:
    def test_a_complete_directory_has_no_problems(self, tmp_path):
        assert brand.check(_brand_dir(tmp_path)) == []

    def test_a_directory_that_is_not_there_is_one_problem(self, tmp_path):
        problems = brand.check(tmp_path / "brand")
        assert len(problems) == 1, problems
        assert "brand" in problems[0]

    @pytest.mark.parametrize("missing", ["brand-brain", "proof"])
    def test_a_missing_file_is_named(self, tmp_path, missing):
        names = [name for name in brand.REQUIRED if name != missing]
        problems = brand.check(_brand_dir(tmp_path, names=names))
        assert any(missing in p for p in problems), problems

    def test_a_file_nobody_declared_is_named(self, tmp_path):
        directory = _brand_dir(tmp_path)
        (directory / "notes.md").write_text(f"{FRONT_MATTER}{BODY}")
        problems = brand.check(directory)
        assert any("notes" in p for p in problems), problems

    def test_a_file_with_no_front_matter_is_named(self, tmp_path):
        directory = _brand_dir(tmp_path)
        (directory / "voice.md").write_text("Just a body.\n")
        problems = brand.check(directory)
        assert any("voice" in p and "front matter" in p for p in problems), problems

    def test_an_empty_front_matter_block_counts_as_none(self, tmp_path):
        directory = _brand_dir(tmp_path)
        (directory / "voice.md").write_text("---\n---\nJust a body.\n")
        problems = brand.check(directory)
        assert any("voice" in p and "front matter" in p for p in problems), problems

    def test_a_file_with_no_body_is_named(self, tmp_path):
        directory = _brand_dir(tmp_path)
        (directory / "proof.md").write_text(f"{FRONT_MATTER}   \n")
        problems = brand.check(directory)
        assert any("proof" in p and "body" in p for p in problems), problems
