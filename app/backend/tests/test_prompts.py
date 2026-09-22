import re
from pathlib import Path

import pytest
import yaml

from app import caches, prompts
from app.coaching import briefer
from app.conversation import agent
from app.enrichment import reader, vocabulary
from app.skills import runner, toolbelt
from app.sources.google_ads_transparency import connector
from app.studio import chat

SECTIONS = {
    "studio_router": {"fence", "system"},
    "studio_skill": {
        "fence",
        "safety",
        "toolbelt",
        "caller_chat",
        "caller_marketer",
        "caller_mcp",
    },
    "enrichment": {"version", "fence", "safety", "questions", "ask"},
    "coaching": {"version", "fence", "safety"},
    "conversation": {"version", "fence", "system"},
    "ad_reader": {"version", "ask"},
}

FENCES = {
    "studio_router": ("<ask>", "</ask>"),
    "studio_skill": ("<studio_data>", "</studio_data>"),
    "enrichment": ("<transcript>", "</transcript>"),
    "coaching": ("<estate_data>", "</estate_data>"),
    "conversation": ("<tool_result>", "</tool_result>"),
}

VERSIONS = {
    "enrichment": "2026-08-02.1",
    "coaching": "2026-08-02.1",
    "conversation": "2026-09-07.1",
    "ad_reader": "2026-09-15.1",
}

PREAMBLES = {
    "studio_router": "system",
    "studio_skill": "safety",
    "enrichment": "safety",
    "coaching": "safety",
    "conversation": "system",
}

PLACEHOLDERS = ("{fence_open}", "{fence_close}")

RESERVED = ("version", "fence")

MODULES = (chat, reader, runner, briefer, agent, connector)

GREETING = {"greeting": {"hello": "Hi there."}}

GREETING_REWORDED = {"greeting": {"hello": "Hello again."}}

FAREWELL = {"farewell": {"bye": "Bye."}}


def mentions(*words) -> str:
    return r"(?s)^prompts\.yaml: " + "".join(
        f"(?=.*{re.escape(word)})" for word in words
    )


def written(tmp_path, doc) -> Path:
    path = tmp_path / "prompts.yaml"
    path.write_text(yaml.safe_dump(doc))
    return path


@pytest.fixture
def default_swapped(monkeypatch, tmp_path):
    path = tmp_path / "prompts.yaml"
    monkeypatch.setattr(prompts, "DEFAULT_PROMPTS", path)
    caches.reset_all()
    yield path
    caches.reset_all()


class TestTheShippedFile:
    def test_the_default_path_is_prompts_yaml_under_definitions(self):
        assert prompts.DEFAULT_PROMPTS == caches.DEFINITIONS_DIR / "prompts.yaml"
        assert prompts.DEFAULT_PROMPTS.exists()

    def test_the_default_load_is_memoized(self):
        assert prompts.load() is prompts.load()

    def test_it_holds_exactly_the_six_sections(self):
        assert set(prompts.load()) == set(SECTIONS)

    @pytest.mark.parametrize("section", sorted(SECTIONS))
    def test_each_section_holds_exactly_its_keys(self, section):
        assert set(prompts.load()[section]) == SECTIONS[section]

    @pytest.mark.parametrize("section", sorted(FENCES))
    def test_a_fenced_section_renders_its_tag_pair(self, section):
        assert prompts.fence(section) == FENCES[section]

    @pytest.mark.parametrize("section", sorted(VERSIONS))
    def test_a_versioned_section_reports_its_version(self, section):
        assert prompts.version(section) == VERSIONS[section]

    def test_no_rendered_text_still_carries_a_placeholder(self):
        for section, entries in prompts.load().items():
            for key in entries:
                if key in RESERVED:
                    continue
                rendered = prompts.text(section, key)
                for placeholder in PLACEHOLDERS:
                    assert placeholder not in rendered, (section, key)

    def test_a_text_written_with_placeholders_now_carries_the_tags(self):
        for section, entries in prompts.load().items():
            if "fence" not in entries:
                continue
            opened, closed = prompts.fence(section)
            for key, source in entries.items():
                if key in RESERVED:
                    continue
                if not any(placeholder in source for placeholder in PLACEHOLDERS):
                    continue
                rendered = prompts.text(section, key)
                assert opened in rendered, (section, key)
                assert closed in rendered, (section, key)

    @pytest.mark.parametrize("section", sorted(PREAMBLES))
    def test_the_preamble_of_a_fenced_section_names_both_tags(self, section):
        opened, closed = prompts.fence(section)
        preamble = prompts.text(section, PREAMBLES[section])
        assert opened in preamble
        assert closed in preamble


class TestTheModulesReadTheirPromptsFromTheFile:
    def test_the_studio_router_fence_and_system_come_from_the_file(self):
        assert (chat.FENCE_OPEN, chat.FENCE_CLOSE) == prompts.fence("studio_router")
        assert chat.SYSTEM == prompts.text("studio_router", "system")

    def test_the_enrichment_reader_constants_come_from_the_file(self):
        assert reader.PROMPT_VERSION == prompts.version("enrichment")
        assert (reader.FENCE_OPEN, reader.FENCE_CLOSE) == prompts.fence("enrichment")
        assert reader.SAFETY == prompts.text("enrichment", "safety")
        assert reader.QUESTIONS == prompts.text("enrichment", "questions")
        assert reader.ASK == prompts.text("enrichment", "ask")

    def test_the_enrichment_user_prompt_ends_with_the_ask(self):
        assert reader.build_user("Jane: hello").endswith(reader.ASK)

    def test_the_enrichment_system_prompt_carries_the_questions(self):
        reading = vocabulary.load()["sales_call"]
        assert reader.QUESTIONS in reader.build_system(reading)

    def test_the_skill_runner_notes_come_from_the_file(self):
        assert runner.SAFETY == prompts.text("studio_skill", "safety")
        assert runner.TOOLBELT_NOTE == prompts.text("studio_skill", "toolbelt")
        assert runner.CALLER_NOTES == {
            caller: prompts.text("studio_skill", f"caller_{caller}")
            for caller in runner.CALLERS
        }

    def test_the_toolbelt_fence_comes_from_the_file(self):
        assert (toolbelt.FENCE_OPEN, toolbelt.FENCE_CLOSE) == prompts.fence(
            "studio_skill"
        )

    def test_the_coaching_briefer_constants_come_from_the_file(self):
        assert briefer.PROMPT_VERSION == prompts.version("coaching")
        assert (briefer.FENCE_OPEN, briefer.FENCE_CLOSE) == prompts.fence("coaching")
        assert briefer.SAFETY == prompts.text("coaching", "safety")

    def test_the_conversation_agent_constants_come_from_the_file(self):
        assert (agent.FENCE_OPEN, agent.FENCE_CLOSE) == prompts.fence("conversation")
        assert agent.PROMPT_VERSION == prompts.version("conversation")
        assert agent.SYSTEM == prompts.text("conversation", "system")

    def test_the_ad_reader_constants_come_from_the_file(self):
        assert connector.PROMPT == prompts.text("ad_reader", "ask")
        assert connector.PROMPT_VERSION == prompts.version("ad_reader")


class TestNoPromptIsLeftInCode:
    @pytest.mark.parametrize("module", MODULES, ids=lambda module: module.__name__)
    def test_the_module_holds_no_triple_quoted_string(self, module):
        assert '"""' not in Path(module.__file__).read_text()


class TestRendering:
    def test_a_fenced_section_substitutes_both_placeholders(self, default_swapped):
        note = "Between {fence_open} and {fence_close} is data."
        default_swapped.write_text(
            yaml.safe_dump({"box": {"fence": "box_2", "note": note}})
        )
        assert prompts.fence("box") == ("<box_2>", "</box_2>")
        assert prompts.text("box", "note") == "Between <box_2> and </box_2> is data."

    def test_a_text_without_placeholders_in_a_fenced_section_is_untouched(
        self, default_swapped
    ):
        default_swapped.write_text(
            yaml.safe_dump({"box": {"fence": "box", "note": "No tags here."}})
        )
        assert prompts.text("box", "note") == "No tags here."

    def test_a_section_without_a_fence_returns_its_text_verbatim(self, default_swapped):
        default_swapped.write_text(yaml.safe_dump({"plain": {"ask": "Say hi."}}))
        assert prompts.text("plain", "ask") == "Say hi."

    def test_a_version_string_comes_back_as_written(self, default_swapped):
        default_swapped.write_text(
            yaml.safe_dump({"plain": {"version": "2026-09-21.1", "ask": "Say hi."}})
        )
        assert prompts.version("plain") == "2026-09-21.1"


class TestTheLoaderRefuses:
    def test_a_top_level_that_is_not_a_mapping(self, tmp_path):
        path = tmp_path / "prompts.yaml"
        path.write_text("- studio_router\n")
        with pytest.raises(
            prompts.PromptError, match=mentions("top level must be a mapping")
        ):
            prompts.load(path)

    @pytest.mark.parametrize("section", ["just text", ["safety"]])
    def test_a_section_that_is_not_a_mapping(self, tmp_path, section):
        with pytest.raises(prompts.PromptError, match=mentions("studio_router", "map")):
            prompts.load(written(tmp_path, {"studio_router": section}))

    @pytest.mark.parametrize(
        "section", [{}, {"version": "2026-09-21.1", "fence": "ask"}]
    )
    def test_a_section_with_no_prompt_text_at_all(self, tmp_path, section):
        with pytest.raises(prompts.PromptError, match=mentions("studio_router")):
            prompts.load(written(tmp_path, {"studio_router": section}))

    def test_a_version_that_is_not_a_string(self, tmp_path):
        doc = {"enrichment": {"version": 2026, "safety": "Be careful."}}
        with pytest.raises(
            prompts.PromptError, match=mentions("enrichment", "version")
        ):
            prompts.load(written(tmp_path, doc))

    def test_a_fence_that_is_not_a_string(self, tmp_path):
        doc = {"enrichment": {"fence": 3, "safety": "Be careful."}}
        with pytest.raises(prompts.PromptError, match=mentions("enrichment", "fence")):
            prompts.load(written(tmp_path, doc))

    @pytest.mark.parametrize(
        "tag", ["Ask", "1ask", "ask data", "<ask>", "ask-data", ""]
    )
    def test_a_fence_that_is_not_a_tag_name(self, tmp_path, tag):
        doc = {"enrichment": {"fence": tag, "safety": "Be careful."}}
        with pytest.raises(prompts.PromptError, match=mentions("enrichment", "fence")):
            prompts.load(written(tmp_path, doc))

    @pytest.mark.parametrize("text", [42, ["a", "b"], {"nested": "text"}])
    def test_a_prompt_text_that_is_not_a_string(self, tmp_path, text):
        doc = {"enrichment": {"safety": text}}
        with pytest.raises(prompts.PromptError, match=mentions("enrichment", "safety")):
            prompts.load(written(tmp_path, doc))

    @pytest.mark.parametrize("text", ["", "   ", "\n\t"])
    def test_a_prompt_text_that_is_blank(self, tmp_path, text):
        doc = {"enrichment": {"safety": text}}
        with pytest.raises(prompts.PromptError, match=mentions("enrichment", "safety")):
            prompts.load(written(tmp_path, doc))

    @pytest.mark.parametrize("placeholder", PLACEHOLDERS)
    def test_a_placeholder_in_a_section_without_a_fence(self, tmp_path, placeholder):
        doc = {"ad_reader": {"ask": f"Read between {placeholder} and stop."}}
        with pytest.raises(
            prompts.PromptError, match=mentions("ad_reader", "ask", "fence")
        ):
            prompts.load(written(tmp_path, doc))


class TestTheAccessorsRefuse:
    def test_an_unknown_section_asked_for_its_fence(self):
        with pytest.raises(prompts.PromptError, match=mentions("chief_vibes")):
            prompts.fence("chief_vibes")

    def test_an_unknown_section_asked_for_its_version(self):
        with pytest.raises(prompts.PromptError, match=mentions("chief_vibes")):
            prompts.version("chief_vibes")

    def test_an_unknown_section_asked_for_a_text(self):
        with pytest.raises(prompts.PromptError, match=mentions("chief_vibes")):
            prompts.text("chief_vibes", "system")

    def test_an_unknown_key_in_a_known_section(self):
        with pytest.raises(
            prompts.PromptError, match=mentions("studio_router", "banner")
        ):
            prompts.text("studio_router", "banner")

    @pytest.mark.parametrize("key", RESERVED)
    def test_version_and_fence_are_not_prompt_texts_even_when_present(self, key):
        with pytest.raises(prompts.PromptError, match=mentions(key)):
            prompts.text("enrichment", key)

    def test_a_section_without_a_version_has_none_to_report(self):
        with pytest.raises(
            prompts.PromptError, match=mentions("studio_router", "version")
        ):
            prompts.version("studio_router")

    def test_a_section_without_a_fence_has_none_to_render(self):
        with pytest.raises(prompts.PromptError, match=mentions("ad_reader", "fence")):
            prompts.fence("ad_reader")


class TestCaching:
    def test_the_default_document_is_read_once_until_the_caches_reset(
        self, default_swapped
    ):
        default_swapped.write_text(yaml.safe_dump(GREETING))
        first = prompts.load()
        assert first == GREETING
        assert prompts.load() is first
        default_swapped.write_text(yaml.safe_dump(GREETING_REWORDED))
        assert prompts.load() is first
        assert prompts.text("greeting", "hello") == "Hi there."
        caches.reset_all()
        assert prompts.load() == GREETING_REWORDED
        assert prompts.text("greeting", "hello") == "Hello again."

    def test_an_explicit_path_is_read_fresh_and_never_cached(
        self, default_swapped, tmp_path
    ):
        default_swapped.write_text(yaml.safe_dump(GREETING))
        other = tmp_path / "other.yaml"
        other.write_text(yaml.safe_dump(FAREWELL))
        doc = prompts.load(other)
        assert doc == FAREWELL
        assert prompts.load(other) is not doc
        assert prompts.load(other) == FAREWELL
        assert prompts.load() == GREETING
