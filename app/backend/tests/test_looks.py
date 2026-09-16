import re
from pathlib import Path

import pytest
import yaml

from app import caches
from app.engine import looks

SHIPPED = Path(caches.DEFINITIONS_DIR) / "looks"

STAT = {
    "name": "stat-card",
    "medium": "image",
    "ratios": ["1:1", "4:5", "9:16", "16:9"],
    "slots": [
        {"name": "stat", "max": 6},
        {"name": "label", "max": 28},
        {"name": "support", "max": 96},
    ],
}
STAT_CONTENT = {
    "stat": "27",
    "label": "tools, one connector each",
    "support": "Every record kept as it arrived.",
}
CAROUSEL = {
    "name": "carousel",
    "medium": "carousel",
    "ratios": ["1:1", "4:5"],
    "slides": {"min": 3, "max": 10},
    "slots": {
        "cover": [{"name": "title", "max": 60}, {"name": "kicker", "max": 40}],
        "slide": [{"name": "title", "max": 40}, {"name": "body", "max": 160}],
        "closing": [{"name": "title", "max": 40}, {"name": "cta", "max": 40}],
    },
}
CAROUSEL_CONTENT = {
    "cover": {"title": "Where a number comes from", "kicker": "Three facts"},
    "slides": [{"title": f"Fact {n}", "body": "A body."} for n in (1, 2, 3)],
    "closing": {"title": "Open source", "cta": "Read the code"},
}

IMAGE_LOOKS = ("stat-card", "quote-card", "list-card")
SHIPPED_TEMPLATES = [
    *[(name, "card.html.j2") for name in IMAGE_LOOKS],
    *[("carousel", template) for template in looks.TEMPLATES["carousel"]],
]


def _write_look(root, manifest, content, layouts="┌┐\n"):
    folder = root / manifest["name"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "look.yaml").write_text(yaml.safe_dump(manifest, sort_keys=False))
    (folder / "content.yaml").write_text(yaml.safe_dump(content, sort_keys=False))
    (folder / "layouts.md").write_text(layouts)
    for template in looks.TEMPLATES[manifest["medium"]]:
        (folder / template).write_text("<html></html>\n")
    return folder


def _edit(root, name, mutate):
    path = root / name / "look.yaml"
    doc = yaml.safe_load(path.read_text())
    mutate(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False))


def _content(root, name, doc):
    (root / name / "content.yaml").write_text(yaml.safe_dump(doc, sort_keys=False))


def _without(base, *keys):
    return {k: v for k, v in base.items() if k not in keys}


@pytest.fixture
def root(tmp_path, monkeypatch):
    _write_look(tmp_path, STAT, STAT_CONTENT)
    _write_look(tmp_path, CAROUSEL, CAROUSEL_CONTENT)
    monkeypatch.setattr(looks, "DEFAULT_LOOKS", tmp_path)
    return tmp_path


class TestLooksRead:
    def test_names_lists_directories_sorted(self, root):
        (root / "notes.txt").write_text("x")
        assert looks.names() == ["carousel", "stat-card"]

    def test_load_returns_the_manifest(self, root):
        assert looks.load("stat-card") == STAT

    def test_load_refuses_an_unknown_look(self, root):
        with pytest.raises(looks.LookError, match="nope"):
            looks.load("nope")

    def test_read_adds_the_sample_and_the_layouts(self, root):
        assert looks.read("carousel") == {
            **CAROUSEL,
            "sample": CAROUSEL_CONTENT,
            "layouts": "┌┐\n",
        }

    @pytest.mark.parametrize(
        "ratio,size",
        [
            ("1:1", (1080, 1080)),
            ("4:5", (1080, 1350)),
            ("9:16", (1080, 1920)),
            ("16:9", (1920, 1080)),
        ],
    )
    def test_frame_gives_the_pixel_size(self, ratio, size):
        assert looks.frame(ratio) == size

    def test_frame_refuses_an_unknown_ratio(self):
        with pytest.raises(looks.LookError, match="3:2"):
            looks.frame("3:2")

    def test_limits_of_an_image_look(self, root):
        assert looks.limits("stat-card") == {"stat": 6, "label": 28, "support": 96}

    def test_limits_of_an_image_look_ignore_the_part(self, root):
        assert looks.limits("stat-card", "cover") == looks.limits("stat-card")

    @pytest.mark.parametrize(
        "part,expected",
        [
            ("cover", {"title": 60, "kicker": 40}),
            ("slide", {"title": 40, "body": 160}),
            ("closing", {"title": 40, "cta": 40}),
        ],
    )
    def test_limits_of_a_carousel_part(self, root, part, expected):
        assert looks.limits("carousel", part) == expected

    @pytest.mark.parametrize("part", [None, "middle"], ids=["absent", "unknown"])
    def test_limits_of_a_carousel_need_a_part(self, root, part):
        with pytest.raises(looks.LookError, match="cover"):
            looks.limits("carousel", part)

    def test_the_constants_match_the_contract(self):
        assert looks.MEDIA == ("image", "carousel")
        assert looks.FRAMES == {
            "1:1": (1080, 1080),
            "4:5": (1080, 1350),
            "9:16": (1080, 1920),
            "16:9": (1920, 1080),
        }
        assert looks.TEMPLATES == {
            "image": ("card.html.j2",),
            "carousel": ("cover.html.j2", "slide.html.j2", "closing.html.j2"),
        }


class TestCheckNamesWhatIsWrong:
    def test_two_clean_looks_pass(self, root):
        assert looks.check(root) == []
        assert looks.check() == []

    def test_a_missing_directory_is_one_problem(self, tmp_path):
        problems = looks.check(tmp_path / "nowhere")
        assert len(problems) == 1, problems
        assert "looks/" in problems[0]
        assert "not a directory" in problems[0]

    def test_an_empty_directory_passes(self, tmp_path):
        assert looks.check(tmp_path) == []

    def test_a_file_beside_the_looks_is_not_a_look(self, root):
        (root / "README.md").write_text("x")
        assert looks.check(root) == []

    def test_a_look_without_a_manifest(self, root):
        (root / "bare").mkdir()
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/bare/look.yaml" in problems[0]
        assert "missing" in problems[0]

    def test_a_manifest_that_is_not_a_mapping(self, root):
        (root / "stat-card" / "look.yaml").write_text("- a\n")
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/look.yaml" in problems[0]
        assert "mapping" in problems[0]

    def test_a_manifest_that_does_not_parse(self, root):
        (root / "stat-card" / "look.yaml").write_text("slots: [\n")
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/look.yaml" in problems[0]
        assert "does not parse" in problems[0]

    def test_a_manifest_naming_another_look(self, root):
        _edit(root, "stat-card", lambda d: d.update({"name": "big-number"}))
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "'big-number'" in problems[0]
        assert "'stat-card'" in problems[0]

    def test_an_unknown_medium_is_its_only_problem(self, root):
        _edit(root, "stat-card", lambda d: d.update({"medium": "video", "ratios": []}))
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/look.yaml" in problems[0]
        assert "medium 'video'" in problems[0]

    @pytest.mark.parametrize(
        "mutate,reason",
        [
            (lambda d: d.update({"ratios": "1:1"}), "ratios must be"),
            (lambda d: d.update({"ratios": []}), "ratios must be"),
            (lambda d: d.update({"ratios": ["1:1", "3:2"]}), "ratio '3:2'"),
            (lambda d: d.update({"slots": {}}), "slots must be a non-empty list"),
            (lambda d: d.update({"slots": []}), "slots must be a non-empty list"),
            (lambda d: d.update({"slots": ["stat"]}), "string `name`"),
            (lambda d: d.update({"slots": [{"max": 6}]}), "string `name`"),
            (lambda d: d.update({"slots": [{"name": 7, "max": 6}]}), "string `name`"),
            (lambda d: d.update({"slots": [{"name": "stat"}]}), "max None"),
            (lambda d: d.update({"slots": [{"name": "stat", "max": 0}]}), "max 0"),
            (
                lambda d: d.update({"slots": [{"name": "stat", "max": True}]}),
                "max True",
            ),
            (lambda d: d.update({"slots": [{"name": "stat", "max": "6"}]}), "max '6'"),
        ],
        ids=[
            "ratios_not_a_list",
            "ratios_empty",
            "ratio_unknown",
            "slots_a_mapping",
            "slots_empty",
            "slot_a_string",
            "slot_without_name",
            "slot_name_not_a_string",
            "slot_without_max",
            "slot_max_zero",
            "slot_max_a_bool",
            "slot_max_a_string",
        ],
    )
    def test_a_malformed_image_manifest_is_named(self, root, mutate, reason):
        _edit(root, "stat-card", mutate)
        problems = looks.check(root)
        assert problems
        assert all("looks/stat-card/look.yaml" in p for p in problems), problems
        assert any(reason in p for p in problems), problems

    @pytest.mark.parametrize(
        "mutate,reason",
        [
            (lambda d: d.update({"slots": []}), "slots must be a mapping"),
            (lambda d: d["slots"].pop("closing"), "slots.closing"),
            (lambda d: d["slots"].update({"closing": []}), "slots.closing"),
            (lambda d: d["slots"].update({"outro": []}), "slots.outro"),
            (lambda d: d.pop("slides"), "slides must be a mapping"),
            (lambda d: d.update({"slides": [3, 10]}), "slides must be a mapping"),
            (lambda d: d.update({"slides": {"min": 0, "max": 10}}), "slides min 0"),
            (lambda d: d.update({"slides": {"min": 4, "max": 3}}), "slides min 4"),
            (lambda d: d.update({"slides": {"min": "3", "max": 10}}), "slides min '3'"),
            (lambda d: d.update({"slides": {"min": 3}}), "max None"),
            (lambda d: d.update({"slides": {"min": True, "max": 10}}), "min True"),
        ],
        ids=[
            "slots_a_list",
            "part_missing",
            "part_empty",
            "part_unknown",
            "slides_absent",
            "slides_a_list",
            "slides_min_zero",
            "slides_min_past_max",
            "slides_min_a_string",
            "slides_max_absent",
            "slides_min_a_bool",
        ],
    )
    def test_a_malformed_carousel_manifest_is_named(self, root, mutate, reason):
        _edit(root, "carousel", mutate)
        problems = looks.check(root)
        assert problems
        assert all("looks/carousel/look.yaml" in p for p in problems), problems
        assert any(reason in p for p in problems), problems

    @pytest.mark.parametrize(
        "look,template",
        [
            ("stat-card", "card.html.j2"),
            ("carousel", "cover.html.j2"),
            ("carousel", "slide.html.j2"),
            ("carousel", "closing.html.j2"),
        ],
    )
    def test_a_missing_template_is_named(self, root, look, template):
        (root / look / template).unlink()
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert f"looks/{look}/{template}" in problems[0]
        assert "missing" in problems[0]

    def test_a_missing_layouts_file_is_named(self, root):
        (root / "stat-card" / "layouts.md").unlink()
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/layouts.md" in problems[0]
        assert "missing" in problems[0]

    def test_a_missing_sample(self, root):
        (root / "stat-card" / "content.yaml").unlink()
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/content.yaml" in problems[0]
        assert "missing" in problems[0]

    def test_a_sample_that_is_not_a_mapping(self, root):
        (root / "stat-card" / "content.yaml").write_text("- a\n")
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/content.yaml" in problems[0]
        assert "mapping" in problems[0]

    def test_a_sample_that_does_not_parse(self, root):
        (root / "stat-card" / "content.yaml").write_text("stat: [\n")
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/content.yaml" in problems[0]
        assert "does not parse" in problems[0]

    @pytest.mark.parametrize(
        "content,reason",
        [
            ({**STAT_CONTENT, "stat": ""}, "slot 'stat' must be non-empty text"),
            ({**STAT_CONTENT, "stat": "   "}, "slot 'stat' must be non-empty text"),
            ({**STAT_CONTENT, "stat": 27}, "slot 'stat' must be non-empty text"),
            (_without(STAT_CONTENT, "label"), "slot 'label' must be non-empty text"),
            (
                {**STAT_CONTENT, "stat": "1234567"},
                "slot 'stat' runs 7 chars, past its max of 6",
            ),
        ],
        ids=["empty", "blank", "a_number", "absent", "too_long"],
    )
    def test_a_sample_outside_its_slots_is_named(self, root, content, reason):
        _content(root, "stat-card", content)
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/stat-card/content.yaml" in problems[0]
        assert reason in problems[0]

    def test_a_sample_exactly_at_its_max_passes(self, root):
        _content(root, "stat-card", {**STAT_CONTENT, "stat": "123456"})
        assert looks.check(root) == []

    def test_a_malformed_manifest_leaves_the_sample_unjudged(self, root):
        _edit(root, "stat-card", lambda d: d.update({"slots": [{"name": "stat"}]}))
        _content(root, "stat-card", {"stat": "1234567"})
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "look.yaml" in problems[0]

    @pytest.mark.parametrize(
        "mutate,reason",
        [
            (lambda d: d.pop("cover"), "cover must be a mapping"),
            (lambda d: d.update({"cover": {"title": "x"}}), "cover slot 'kicker'"),
            (
                lambda d: d.update({"cover": {"title": "x" * 61, "kicker": "k"}}),
                "cover slot 'title' runs 61",
            ),
            (lambda d: d.pop("slides"), "slides must be a list of 3 to 10"),
            (
                lambda d: d.update({"slides": d["slides"][:2]}),
                "slides must be a list of 3 to 10",
            ),
            (
                lambda d: d.update(
                    {"slides": [{"title": f"Fact {n}", "body": "b"} for n in range(11)]}
                ),
                "slides must be a list of 3 to 10",
            ),
            (lambda d: d["slides"].__setitem__(1, "text"), "slide 2 must be a mapping"),
            (
                lambda d: d["slides"][1].update({"body": "b" * 161}),
                "slide 2 slot 'body' runs 161",
            ),
            (lambda d: d.update({"closing": []}), "closing must be a mapping"),
            (lambda d: d["closing"].pop("cta"), "closing slot 'cta'"),
        ],
        ids=[
            "cover_absent",
            "cover_slot_absent",
            "cover_slot_too_long",
            "slides_absent",
            "too_few_slides",
            "too_many_slides",
            "slide_not_a_mapping",
            "slide_slot_too_long",
            "closing_a_list",
            "closing_slot_absent",
        ],
    )
    def test_a_carousel_sample_outside_its_slots_is_named(self, root, mutate, reason):
        doc = yaml.safe_load((root / "carousel" / "content.yaml").read_text())
        mutate(doc)
        _content(root, "carousel", doc)
        problems = looks.check(root)
        assert len(problems) == 1, problems
        assert "looks/carousel/content.yaml" in problems[0]
        assert reason in problems[0]

    def test_a_carousel_at_its_slide_bounds_passes(self, root):
        doc = yaml.safe_load((root / "carousel" / "content.yaml").read_text())
        doc["slides"] = [{"title": f"Fact {n}", "body": "b"} for n in range(10)]
        _content(root, "carousel", doc)
        assert looks.check(root) == []

    def test_every_problem_in_a_look_is_reported(self, root):
        _edit(root, "stat-card", lambda d: d.update({"ratios": ["3:2"]}))
        (root / "stat-card" / "card.html.j2").unlink()
        assert len(looks.check(root)) == 2

    def test_problems_come_in_directory_order(self, root):
        (root / "carousel" / "cover.html.j2").unlink()
        (root / "stat-card" / "card.html.j2").unlink()
        problems = looks.check(root)
        assert len(problems) == 2, problems
        assert "carousel" in problems[0]
        assert "stat-card" in problems[1]


class TestTheShippedLooks:
    def test_they_pass_check(self):
        assert looks.check() == []

    def test_the_four_contract_looks_exist(self):
        assert looks.names() == ["carousel", "list-card", "quote-card", "stat-card"]

    @pytest.mark.parametrize("name", IMAGE_LOOKS)
    def test_image_looks_carry_every_ratio(self, name):
        assert looks.load(name)["medium"] == "image"
        assert looks.load(name)["ratios"] == ["1:1", "4:5", "9:16", "16:9"]

    def test_the_carousel_carries_the_two_portrait_ratios(self):
        manifest = looks.load("carousel")
        assert manifest["medium"] == "carousel"
        assert manifest["ratios"] == ["1:1", "4:5"]
        assert manifest["slides"] == {"min": 3, "max": 10}

    @pytest.mark.parametrize(
        "name,limits",
        [
            ("stat-card", {"stat": 6, "label": 28, "support": 96}),
            ("quote-card", {"quote": 140, "who": 40}),
            ("list-card", {"title": 40, "item1": 60, "item2": 60, "item3": 60}),
        ],
    )
    def test_image_slot_limits_match_the_contract(self, name, limits):
        assert looks.limits(name) == limits

    def test_carousel_slot_limits_match_the_contract(self):
        assert looks.limits("carousel", "cover") == {"title": 60, "kicker": 40}
        assert looks.limits("carousel", "slide") == {"title": 40, "body": 160}
        assert looks.limits("carousel", "closing") == {"title": 40, "cta": 40}

    @pytest.mark.parametrize("name", [*IMAGE_LOOKS, "carousel"])
    def test_read_carries_a_sample_and_ascii_frames(self, name):
        doc = looks.read(name)
        assert doc["sample"]
        assert "┌" in doc["layouts"]
        assert len([line for line in doc["layouts"].splitlines() if "┌" in line]) >= 2

    @pytest.mark.parametrize("name,template", SHIPPED_TEMPLATES)
    def test_every_template_reads_the_brand_never_a_literal(self, name, template):
        text = (SHIPPED / name / template).read_text()
        assert text.startswith("<!doctype html>")
        assert "tokens.colors." in text
        assert not re.search(r"#[0-9A-Fa-f]{6}\b", text)
        assert "{{ logo }}" in text
        assert "fonts.sans" in text
        assert "fonts.display" in text
        assert "picture" in text
        assert "{{ width }}" in text
        assert "{{ height }}" in text

    @pytest.mark.parametrize("template", looks.TEMPLATES["carousel"])
    def test_carousel_templates_number_their_pages(self, template):
        text = (SHIPPED / "carousel" / template).read_text()
        assert "page" in text
        assert "pages" in text
