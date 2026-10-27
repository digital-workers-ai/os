import hashlib
import re

import pytest
import yaml

from app.caches import BACKEND_DIR
from app.skills import catalog

FRONT = {"name": "dw-sample", "description": "Write one post", "makes": "post"}
LESSONS = "## Lessons\n\nThe taste agent appends here, one line each.\n"
BODY = "# Skill: Post\n\n## Steps\n\n1. Read the brand.\n\n" + LESSONS
WORKFLOW = (
    "dw-ship",
    "dw-implement",
    "dw-operator",
    "dw-operator-build",
    "dw-add-tests",
    "dw-app",
)
SHIPPED = {
    "post": "dw-linkedin-post",
    "newsletter": "dw-newsletter",
    "blog": "dw-blog",
    "image": "dw-image",
    "carousel": "dw-carousel",
}


def _text(front=FRONT, body=BODY):
    return f"---\n{yaml.safe_dump(front, sort_keys=False)}---\n{body}"


def _front(**overrides):
    return {**FRONT, **overrides}


def _without(key):
    return {k: v for k, v in FRONT.items() if k != key}


def _lessons(section):
    return BODY.replace(LESSONS, "## Lessons\n" + section)


def _app_skill():
    text = (catalog.SKILLS_DIR / "dw-app" / "SKILL.md").read_text()
    return catalog._split("dw-app", text)


def _vocabulary_cells():
    lines = _app_skill()[1].splitlines()
    section = lines[lines.index("## Vocabulary") + 1 :]
    ends = [n for n, line in enumerate(section) if line.startswith("## ")]
    rows = [
        line for line in section[: ends[0] if ends else None] if line.startswith("|")
    ]
    return [row.split("|")[1].strip() for row in rows[2:]]


@pytest.fixture
def skills(tmp_path, monkeypatch):
    monkeypatch.setattr(catalog, "SKILLS_DIR", tmp_path)

    def write(name, text):
        (tmp_path / name).mkdir()
        path = tmp_path / name / "SKILL.md"
        path.write_text(text)
        return path

    return write


class TestNamesListsTheContentSkills:
    def test_directories_whose_front_matter_carries_makes_are_listed(self, skills):
        skills("dw-sample", _text())
        skills("dw-image", _text(_front(name="dw-image", makes="image")))
        assert catalog.names() == ["dw-image", "dw-sample"]

    def test_a_skill_without_makes_is_a_workflow_skill_and_stays_out(self, skills):
        skills("dw-ship", _text(_without("makes")))
        assert catalog.names() == []

    def test_a_directory_without_a_skill_file_stays_out(self, skills, tmp_path):
        (tmp_path / "dw-empty").mkdir()
        assert catalog.names() == []

    def test_a_file_beside_the_directories_stays_out(self, skills, tmp_path):
        (tmp_path / "dw-notes.md").write_text(_text())
        assert catalog.names() == []

    def test_a_directory_without_the_prefix_stays_out(self, skills):
        skills("post", _text(_front(name="post")))
        assert catalog.names() == []

    def test_a_skill_file_with_no_front_matter_stays_out(self, skills):
        skills("dw-sample", BODY)
        assert catalog.names() == []


class TestLoadReadsASkill:
    def test_a_skill_loads_its_name_description_makes_and_body(self, skills):
        skills("dw-sample", _text())
        skill = catalog.load("dw-sample")
        assert skill.name == "dw-sample"
        assert skill.description == "Write one post"
        assert skill.makes == "post"
        assert skill.body == BODY

    def test_the_body_starts_right_after_the_front_matter(self, skills):
        skills("dw-sample", _text())
        body = catalog.load("dw-sample").body
        assert body.startswith("# Skill: Post\n")
        assert "## Lessons" in body

    def test_the_sha_is_the_sha256_of_the_file(self, skills):
        path = skills("dw-sample", _text())
        expected = hashlib.sha256(path.read_bytes()).hexdigest()
        assert catalog.load("dw-sample").sha == expected

    def test_a_missing_description_reads_as_empty(self, skills):
        skills("dw-sample", _text(_without("description")))
        assert catalog.load("dw-sample").description == ""

    def test_the_kinds_are_the_five_content_kinds(self):
        assert catalog.KINDS == ("post", "newsletter", "blog", "image", "carousel")


class TestLoadRefusesAMalformedSkill:
    @pytest.mark.parametrize(
        "text,reason",
        [
            (BODY, "no front matter"),
            ("---\njust words\n---\n" + BODY, "no front matter"),
            ("---\nname: dw-sample\n" + BODY, "no front matter"),
            (_text(_without("name")), "no name"),
            (_text(_front(name="dw-other")), "'dw-other'"),
            (_text(_front(name="dw-other")), "not the directory"),
            (_text(_without("makes")), "no makes"),
            (_text(_front(makes="video")), "'video'"),
            (_text(_front(makes="video")), "carousel"),
            (_text(body=BODY.replace(LESSONS, "")), "## Lessons"),
        ],
    )
    def test_the_message_names_the_skill_and_the_problem(self, skills, text, reason):
        skills("dw-sample", text)
        with pytest.raises(catalog.SkillError) as e:
            catalog.load("dw-sample")
        assert "dw-sample" in str(e.value)
        assert reason in str(e.value)

    def test_a_skill_with_no_file_is_refused_by_name(self, skills):
        with pytest.raises(catalog.SkillError, match="dw-ghost"):
            catalog.load("dw-ghost")


class TestLessonsParse:
    def test_a_heading_with_no_bullets_is_an_empty_list(self, skills):
        skills("dw-sample", _text())
        assert catalog.load("dw-sample").lessons == ()

    def test_each_bullet_is_one_lesson(self, skills):
        section = "- Say the number first.\n- Cut the second idea.\n"
        skills("dw-sample", _text(body=_lessons(section)))
        assert catalog.load("dw-sample").lessons == (
            "Say the number first.",
            "Cut the second idea.",
        )

    def test_a_line_indented_by_two_spaces_joins_the_previous_lesson(self, skills):
        section = (
            "- Say the number first,\n  before the claim.\n- Cut the second idea.\n"
        )
        skills("dw-sample", _text(body=_lessons(section)))
        assert catalog.load("dw-sample").lessons == (
            "Say the number first, before the claim.",
            "Cut the second idea.",
        )

    def test_an_indented_line_before_any_bullet_is_not_a_lesson(self, skills):
        section = "  stray words\n- Say the number first.\n"
        skills("dw-sample", _text(body=_lessons(section)))
        assert catalog.load("dw-sample").lessons == ("Say the number first.",)

    def test_a_plain_sentence_under_the_heading_is_not_a_lesson(self, skills):
        section = "The taste agent appends here.\n\n- Say the number first.\n"
        skills("dw-sample", _text(body=_lessons(section)))
        assert catalog.load("dw-sample").lessons == ("Say the number first.",)

    def test_bullets_after_the_next_heading_are_not_lessons(self, skills):
        section = "- Say the number first.\n\n## Notes\n\n- Not a lesson.\n"
        skills("dw-sample", _text(body=_lessons(section)))
        assert catalog.load("dw-sample").lessons == ("Say the number first.",)

    def test_bullets_before_the_heading_are_not_lessons(self, skills):
        body = "# Skill: Post\n\n## Rules\n\n- A rule.\n\n" + LESSONS
        skills("dw-sample", _text(body=body))
        assert catalog.load("dw-sample").lessons == ()


class TestForKindFindsTheSkill:
    def test_the_skill_that_makes_the_kind_is_named(self, skills):
        skills("dw-sample", _text())
        skills("dw-image", _text(_front(name="dw-image", makes="image")))
        assert catalog.for_kind("image") == "dw-image"
        assert catalog.for_kind("post") == "dw-sample"

    def test_a_kind_no_skill_makes_is_refused(self, skills):
        skills("dw-sample", _text())
        with pytest.raises(catalog.SkillError, match="video"):
            catalog.for_kind("video")


class TestTheShippedSkills:
    def test_the_skills_dir_is_the_mounted_skills_directory(self):
        assert catalog.SKILLS_DIR == BACKEND_DIR / ".claude" / "skills"

    def test_a_skill_ships_for_every_kind(self):
        assert tuple(SHIPPED) == catalog.KINDS

    @pytest.mark.parametrize("kind,name", SHIPPED.items())
    def test_each_shipped_skill_loads_and_makes_its_kind(self, kind, name):
        skill = catalog.load(name)
        assert skill.name == name
        assert skill.makes == kind
        assert skill.description
        assert skill.body.startswith("# Skill: ")
        assert catalog.for_kind(kind) == name

    def test_the_five_are_listed_and_the_workflow_skills_are_not(self):
        listed = catalog.names()
        assert set(SHIPPED.values()) <= set(listed)
        for name in WORKFLOW:
            assert (catalog.SKILLS_DIR / name / "SKILL.md").is_file()
            assert name not in listed


class TestTheAppSkill:
    def test_its_front_matter_names_it_dw_app(self):
        assert _app_skill()[0]["name"] == "dw-app"

    def test_a_person_can_invoke_it(self):
        assert _app_skill()[0]["user-invocable"] is True

    def test_it_makes_no_content_so_studio_never_lists_it(self):
        assert "makes" not in _app_skill()[0]

    def test_it_describes_itself(self):
        assert _app_skill()[0]["description"]

    def test_it_hints_at_its_argument(self):
        assert _app_skill()[0]["argument-hint"]

    def test_every_vocabulary_row_starts_with_one_backticked_name(self):
        cells = _vocabulary_cells()
        assert cells
        assert [cell for cell in cells if not re.fullmatch(r"`[a-z_]+`", cell)] == []

    def test_the_vocabulary_names_exactly_what_the_apps_check_accepts(self):
        from app.engine import apps

        named = {
            cell.strip("`") for cell in _vocabulary_cells() if cell.startswith("`")
        }
        assert named == set(apps.KEYS) | set(apps.INPUTS) | set(apps.FIELD_TYPES)
