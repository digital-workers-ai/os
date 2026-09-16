from datetime import date
from pathlib import Path

import pytest
import yaml

from app import caches
from app.engine import brand

SHIPPED = Path(caches.DEFINITIONS_DIR) / "brand"

CONTRACT_TOKENS = {
    "logo": "assets/logo.svg",
    "colors": {
        "ink": "#1A1A1A",
        "paper": "#FFFFFF",
        "wash": "#F5F3EB",
        "line": "#E0DCC1",
        "muted": "#807F74",
        "accent": "#FD4E00",
    },
    "fonts": {
        "sans": "assets/space-grotesk.woff2",
        "display": "assets/science-gothic-500.woff2",
    },
}

SVG = "<svg xmlns='http://www.w3.org/2000/svg'/>"


def _front(title):
    return f"---\ntitle: {title}\nupdated: 2026-09-15\n---\n"


def _write_brand(folder):
    folder.mkdir(parents=True)
    for name in brand.REQUIRED:
        body = f"# {name}\n\nOne line about {name}.\n"
        (folder / name).write_text(_front(name) + body)
    (folder / "tokens.yaml").write_text(yaml.safe_dump(CONTRACT_TOKENS))
    assets = folder / "assets"
    assets.mkdir()
    (assets / "logo.svg").write_text(SVG)
    (assets / "space-grotesk.woff2").write_bytes(b"wOF2sans")
    (assets / "science-gothic-500.woff2").write_bytes(b"wOF2display")
    return folder


def _tokens(folder, mutate):
    path = folder / "tokens.yaml"
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc))


@pytest.fixture
def folder(tmp_path, monkeypatch):
    folder = _write_brand(tmp_path / "brand")
    monkeypatch.setattr(brand, "DEFAULT_BRAND", folder)
    return folder


class TestTheBrandReads:
    def test_files_lists_the_seven_in_reading_order(self, folder):
        assert brand.files() == [
            "brand-brain.md",
            "voice.md",
            "pillars.md",
            "audiences.md",
            "objections.md",
            "language.md",
            "proof.md",
        ]

    def test_read_splits_front_matter_from_body(self, folder):
        front, body = brand.read("voice.md")
        assert front == {"title": "voice.md", "updated": date(2026, 9, 15)}
        assert body == "# voice.md\n\nOne line about voice.md.\n"

    def test_read_of_a_file_without_front_matter_is_all_body(self, folder):
        (folder / "voice.md").write_text("just words\n")
        assert brand.read("voice.md") == ({}, "just words\n")

    def test_read_of_empty_front_matter_is_an_empty_mapping(self, folder):
        (folder / "voice.md").write_text("---\n---\nwords\n")
        assert brand.read("voice.md") == ({}, "words\n")

    def test_read_refuses_a_name_that_is_not_a_brand_file(self, folder):
        with pytest.raises(brand.BrandError, match="tokens.yaml"):
            brand.read("tokens.yaml")

    def test_tokens_returns_the_mapping(self, folder):
        assert brand.tokens() == CONTRACT_TOKENS

    def test_assets_lists_files_by_name_with_type_and_size(self, folder):
        (folder / "assets" / "notes.txt").write_text("n")
        (folder / "assets" / ".hidden").write_text("h")
        (folder / "assets" / "nested").mkdir()
        assert brand.assets() == [
            {
                "name": "logo.svg",
                "path": "assets/logo.svg",
                "media_type": "image/svg+xml",
                "bytes": len(SVG),
            },
            {
                "name": "notes.txt",
                "path": "assets/notes.txt",
                "media_type": "application/octet-stream",
                "bytes": 1,
            },
            {
                "name": "science-gothic-500.woff2",
                "path": "assets/science-gothic-500.woff2",
                "media_type": "font/woff2",
                "bytes": 11,
            },
            {
                "name": "space-grotesk.woff2",
                "path": "assets/space-grotesk.woff2",
                "media_type": "font/woff2",
                "bytes": 8,
            },
        ]

    def test_asset_bytes_reads_a_listed_asset(self, folder):
        assert brand.asset_bytes("space-grotesk.woff2") == b"wOF2sans"

    def test_asset_bytes_refuses_a_name_that_is_not_listed(self, folder):
        with pytest.raises(brand.BrandError, match="tokens.yaml"):
            brand.asset_bytes("../tokens.yaml")


class TestCheckNamesWhatIsWrong:
    def test_a_clean_directory_passes(self, folder):
        assert brand.check(folder) == []

    def test_the_default_path_is_the_brand_directory(self, folder):
        assert brand.check() == []

    def test_a_missing_directory_is_one_problem(self, tmp_path):
        problems = brand.check(tmp_path / "nowhere")
        assert len(problems) == 1, problems
        assert "brand/" in problems[0]
        assert "not a directory" in problems[0]

    def test_a_missing_file(self, folder):
        (folder / "proof.md").unlink()
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/proof.md" in problems[0]
        assert "missing" in problems[0]

    def test_an_extra_markdown_file(self, folder):
        (folder / "tone.md").write_text("x\n")
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tone.md" in problems[0]
        assert "not one of" in problems[0]

    @pytest.mark.parametrize(
        "text,reason",
        [
            ("---\nupdated: 2026-09-15\n---\nbody\n", "missing `title`"),
            ("---\ntitle: Voice\n---\nbody\n", "missing `updated`"),
            ("---\ntitle: Voice\nupdated:\n---\nbody\n", "missing `updated`"),
            ("# Voice\n\nbody\n", "missing `title`"),
            ("---\n- a\n---\nbody\n", "must be a mapping"),
            ("---\ntitle: [\n---\nbody\n", "does not parse"),
            ("---\ntitle: Voice\nupdated: 2026-09-15\n---\n\n", "no body"),
        ],
        ids=[
            "no_title",
            "no_updated",
            "blank_updated",
            "no_front_matter",
            "front_matter_a_list",
            "front_matter_unparsable",
            "empty_body",
        ],
    )
    def test_a_malformed_brand_file_is_named(self, folder, text, reason):
        (folder / "voice.md").write_text(text)
        problems = brand.check(folder)
        assert problems
        assert all("brand/voice.md" in p for p in problems), problems
        assert any(reason in p for p in problems), problems

    def test_a_file_without_front_matter_lacks_both_keys(self, folder):
        (folder / "voice.md").write_text("# Voice\n\nbody\n")
        assert len(brand.check(folder)) == 2

    def test_tokens_missing(self, folder):
        (folder / "tokens.yaml").unlink()
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tokens.yaml" in problems[0]
        assert "missing" in problems[0]

    def test_tokens_that_are_not_a_mapping(self, folder):
        (folder / "tokens.yaml").write_text("- a\n")
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tokens.yaml" in problems[0]
        assert "mapping" in problems[0]

    def test_tokens_that_do_not_parse(self, folder):
        (folder / "tokens.yaml").write_text("colors: [\n")
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tokens.yaml" in problems[0]
        assert "does not parse" in problems[0]

    @pytest.mark.parametrize(
        "value",
        ["#FFF", "FFFFFF", "#GGGGGG", "#1A1A1A1", 123, None],
        ids=["short", "no_hash", "not_hex", "too_long", "a_number", "absent"],
    )
    def test_a_colour_that_is_not_rrggbb(self, folder, value):
        _tokens(folder, lambda d: d["colors"].update({"accent": value}))
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tokens.yaml" in problems[0]
        assert "colors.accent" in problems[0]
        assert "#RRGGBB" in problems[0]

    def test_a_lowercase_colour_passes(self, folder):
        _tokens(folder, lambda d: d["colors"].update({"ink": "#1a1a1a"}))
        assert brand.check(folder) == []

    def test_colors_that_are_not_a_mapping(self, folder):
        _tokens(folder, lambda d: d.update({"colors": ["#1A1A1A"]}))
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "colors must be a mapping" in problems[0]

    @pytest.mark.parametrize(
        "mutate,label,reason",
        [
            (lambda d: d.pop("logo"), "logo", "under assets/"),
            (lambda d: d.update({"logo": "logo.svg"}), "logo", "under assets/"),
            (lambda d: d.update({"logo": "assets/../tokens.yaml"}), "logo", "assets/"),
            (lambda d: d.update({"logo": "assets/mark.svg"}), "logo", "not a file"),
            (lambda d: d["fonts"].pop("sans"), "fonts.sans", "under assets/"),
            (
                lambda d: d["fonts"].update({"display": "assets/nope.woff2"}),
                "fonts.display",
                "not a file",
            ),
        ],
        ids=[
            "logo_absent",
            "logo_outside_assets",
            "logo_climbing_out",
            "logo_not_a_file",
            "sans_absent",
            "display_not_a_file",
        ],
    )
    def test_an_asset_that_points_nowhere(self, folder, mutate, label, reason):
        _tokens(folder, mutate)
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "brand/tokens.yaml" in problems[0]
        assert label in problems[0]
        assert reason in problems[0]

    def test_fonts_that_are_not_a_mapping(self, folder):
        _tokens(folder, lambda d: d.update({"fonts": "assets/space-grotesk.woff2"}))
        problems = brand.check(folder)
        assert len(problems) == 1, problems
        assert "fonts must be a mapping" in problems[0]

    def test_every_problem_is_reported_together(self, folder):
        (folder / "proof.md").unlink()
        (folder / "tone.md").write_text("x\n")
        _tokens(folder, lambda d: d.pop("logo"))
        assert len(brand.check(folder)) == 3


class TestTheShippedBrand:
    def test_it_passes_check(self):
        assert brand.check() == []

    def test_tokens_are_exactly_the_contract(self):
        assert brand.tokens() == CONTRACT_TOKENS

    def test_assets_are_the_logo_and_the_two_fonts(self):
        assets = brand.assets()
        assert [a["name"] for a in assets] == [
            "logo.svg",
            "science-gothic-500.woff2",
            "space-grotesk.woff2",
        ]
        assert all(a["bytes"] > 0 for a in assets)

    @pytest.mark.parametrize("name", brand.REQUIRED)
    def test_each_file_stays_under_seventy_lines(self, name):
        assert len((SHIPPED / name).read_text().splitlines()) < 70

    @pytest.mark.parametrize("name", brand.REQUIRED)
    def test_each_file_is_dated_the_day_it_was_written(self, name):
        front, body = brand.read(name)
        assert front["title"]
        assert front["updated"] == date(2026, 9, 15)
        assert body.strip()

    def test_the_logo_is_a_standalone_svg_of_paths(self):
        svg = brand.asset_bytes("logo.svg").decode()
        assert svg.startswith("<svg ")
        assert "<path" in svg
        assert "<text" not in svg
        assert "<!--" not in svg
