import pytest

from app.skills import catalog

ASSET_SKILL = """---
name: dw-thing
description: One thing, made once and said once.
---

# Skill: Thing

One thing. `thing.md` is the text.

## Modes

**draft** is the marketer's daily run. **build** runs after approval.
**chat** is an ask over MCP.

## Steps

1. Settle the one idea.

## Rules

- One idea.

## Lessons

The taste agent appends here, one line each.

- Never lead with a statistic. The number lands after the reader is
  already in the sentence (#209, 2026-09-12).
- One quote a post, verbatim (#198, 2026-09-05).
"""

WORKFLOW_SKILL = """---
name: dw-chore
description: A workflow skill a person invokes, not one Studio runs.
---

# Chore

## Steps

1. Do the chore.
"""


@pytest.fixture
def skills(tmp_path, monkeypatch):
    def write(name, text):
        directory = tmp_path / name
        directory.mkdir(exist_ok=True)
        (directory / "SKILL.md").write_text(text)
        return directory

    monkeypatch.setattr(catalog, "SKILLS_DIR", tmp_path)
    write("dw-thing", ASSET_SKILL)
    return write


class TestDiscovery:
    def test_a_skill_with_modes_is_one_studio_runs(self, skills):
        assert catalog.names() == ["dw-thing"]

    def test_a_workflow_skill_without_modes_is_not_listed(self, skills):
        skills("dw-chore", WORKFLOW_SKILL)
        assert catalog.names() == ["dw-thing"]

    def test_a_directory_without_a_skill_file_is_not_listed(self, skills, tmp_path):
        (tmp_path / "dw-empty").mkdir()
        assert catalog.names() == ["dw-thing"]

    def test_a_directory_that_is_not_ours_is_not_listed(self, skills):
        skills("other-thing", ASSET_SKILL)
        assert catalog.names() == ["dw-thing"]

    def test_no_skills_directory_lists_nothing(self, monkeypatch, tmp_path):
        monkeypatch.setattr(catalog, "SKILLS_DIR", tmp_path / "nowhere")
        assert catalog.names() == []


class TestWhatASkillIs:
    def test_the_front_matter_gives_the_description(self, skills):
        assert catalog.load("dw-thing").description == (
            "One thing, made once and said once."
        )

    def test_the_body_is_everything_but_the_front_matter_and_lessons(self, skills):
        body = catalog.load("dw-thing").body
        assert body.startswith("# Skill: Thing")
        assert "## Rules" in body
        assert "Lessons" not in body
        assert "#209" not in body

    def test_lessons_are_one_line_each_however_they_wrap(self, skills):
        assert catalog.lessons("dw-thing") == (
            "Never lead with a statistic. The number lands after the reader is "
            "already in the sentence (#209, 2026-09-12).",
            "One quote a post, verbatim (#198, 2026-09-05).",
        )

    def test_the_modes_are_read_from_the_modes_section(self, skills):
        assert catalog.load("dw-thing").modes == ("draft", "build", "chat")

    def test_the_sha_is_over_the_whole_file(self, skills):
        before = catalog.sha("dw-thing")
        skills("dw-thing", ASSET_SKILL.replace("One idea.", "Two ideas."))
        assert len(before) == 64
        assert catalog.sha("dw-thing") != before


class TestWhatItRefuses:
    def test_a_skill_that_is_not_there_is_refused(self, skills):
        with pytest.raises(catalog.SkillError, match="no skill named"):
            catalog.load("dw-missing")

    def test_a_workflow_skill_is_not_loadable_by_name(self, skills):
        skills("dw-chore", WORKFLOW_SKILL)
        with pytest.raises(catalog.SkillError, match="no skill named"):
            catalog.load("dw-chore")

    def test_a_name_that_could_climb_out_of_the_directory_is_refused(self, skills):
        with pytest.raises(catalog.SkillError, match="no skill named"):
            catalog.load("../../definitions/brand/proof")

    def test_a_skill_with_no_front_matter_is_refused(self, skills):
        skills("dw-bare", ASSET_SKILL.split("---\n", 2)[2])
        with pytest.raises(catalog.SkillError, match="front matter"):
            catalog.load("dw-bare")

    def test_a_skill_with_no_lessons_section_is_refused(self, skills):
        skills("dw-mute", ASSET_SKILL.split("## Lessons")[0])
        with pytest.raises(catalog.SkillError, match="Lessons"):
            catalog.load("dw-mute")

    def test_a_skill_whose_modes_are_only_prose_names_none(self, skills):
        skills(
            "dw-vague",
            ASSET_SKILL.replace("**draft**", "draft")
            .replace("**build**", "build")
            .replace("**chat**", "chat"),
        )
        assert catalog.load("dw-vague").modes == ()


class TestTheSkillsInThisRepo:
    def test_studio_runs_the_seven_asset_skills(self):
        assert catalog.names() == [
            "dw-blog",
            "dw-counter-ad",
            "dw-image",
            "dw-newsletter",
            "dw-post",
            "dw-remix",
            "dw-video",
        ]

    @pytest.mark.parametrize("name", catalog.names())
    def test_every_skill_carries_modes_lessons_and_a_sha(self, name):
        skill = catalog.load(name)
        assert skill.modes == ("draft", "build", "chat")
        assert skill.lessons
        assert skill.description
        assert len(skill.sha) == 64
