import json

import httpx
import pytest
import yaml

from app import llm, prompts
from app.builder import chat, github
from app.config import settings
from app.engine import apps, ontology
from app.skills import catalog
from app.sources import client

REPLY = "A few questions before the draft."
QUESTIONS = ["Who sends receipts in?", "Which categories do you use?"]
MESSAGES = [
    {"role": "person", "text": "We snap receipts for fuel and meals."},
    {
        "role": "builder",
        "text": "Who sends them in?",
        "questions": [],
        "suggestions": [],
        "draft": None,
    },
    {"role": "person", "text": "Staff and finance."},
]
RECEIPTS = """\
title: Receipts
description: A photo of a paper receipt for something bought for the business.
input: photo
roles: [staff, finance]
lands_as: expense
fields:
  vendor: { type: text }
  date: { type: date }
  total: { type: money }
  tax: { type: money }
  category:
    type: one_of
    labels:
      fuel: Gas, diesel or charging for a vehicle
      meals: Food and drink, including with customers
      supplies: Consumables used up in the work
      tools: Equipment that lasts beyond the job
      travel: Parking, tolls, fares and lodging
      other: Anything none of the above fits
  items:
    type: list
    lands_as: expense_item
    fields:
      description: { type: text }
      amount: { type: money }
"""
INVALID = RECEIPTS.replace("vendor: { type: text }", "vendor: { type: paragraph }")
REVISED = RECEIPTS.replace(
    "vendor: { type: text }",
    "vendor: { type: text, description: The store or station when it is named }",
)
EXISTING = {
    "app": "receipts",
    "title": "Receipts",
    "reason": "Your drivers photograph every fuel stop.",
}
NEW_IDEA = {
    "app": None,
    "title": "Patient intake",
    "reason": "New patients give their history before the first visit.",
}
UNKNOWN = {
    "app": "dental_xrays",
    "title": "Dental x-rays",
    "reason": "Every x-ray is filed with its patient.",
}
LONG = [
    {"role": "person", "text": "We snap receipts for fuel and meals."},
    {
        "role": "builder",
        "text": REPLY,
        "questions": QUESTIONS,
        "suggestions": [NEW_IDEA],
        "draft": None,
    },
    {"role": "person", "text": "Who sends receipts in?\nStaff and finance."},
    {
        "role": "builder",
        "text": "Here is the draft.",
        "questions": [],
        "suggestions": [],
        "draft": RECEIPTS,
    },
    {"role": "person", "text": "Make the vendor optional."},
    {
        "role": "builder",
        "text": "The vendor may be left empty now.",
        "questions": [],
        "suggestions": [],
        "draft": REVISED,
    },
    {"role": "person", "text": "Add a field for the trip."},
]
NOT_YAML = "title: [Receipts\n"
NOT_A_MAPPING = "- receipts\n- invoices\n"
OFF = "the builder is off: set BUILDER_ENABLED"
REPOSITORY = "acme/widgets"
TITLE = "New app: Receipts"
BODY = "We snap receipts for fuel and meals."
PAGE = "https://github.com/acme/widgets/issues/7"
CREATED = {"number": 7, "html_url": PAGE, "labels": [{"name": "app"}]}


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "BUILDER_ENABLED", True)


@pytest.fixture
def answered(monkeypatch):
    calls = []

    def answer(draft=None, reply=REPLY, questions=QUESTIONS, suggestions=()):
        async def parse(**kwargs):
            calls.append(kwargs)
            parsed = kwargs["output_format"](
                reply=reply,
                questions=list(questions),
                suggestions=list(suggestions),
                draft=draft,
            )
            return parsed, "claude-opus-5-5"

        monkeypatch.setattr(llm, "parse", parse)
        return calls

    return answer


@pytest.fixture
def overloaded(monkeypatch):
    async def parse(**kwargs):
        raise llm.LLMError("overloaded")

    monkeypatch.setattr(llm, "parse", parse)


async def _instant(_seconds):
    return None


@pytest.fixture
def github_answers(monkeypatch):
    monkeypatch.setattr(settings, "GITHUB_REPOSITORY", REPOSITORY)
    monkeypatch.setattr(client, "_sleep", _instant)
    seen = []

    def install(answer):
        def handler(request):
            seen.append(request)
            if isinstance(answer, Exception):
                raise answer
            return answer

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        return seen

    return install


def _refusal(draft):
    with pytest.raises(apps.AppError) as caught:
        apps.parse("draft", yaml.safe_load(draft))
    return str(caught.value)


def _skill_body():
    text = (catalog.SKILLS_DIR / "dw-app" / "SKILL.md").read_text()
    _front, body = text.split("\n---\n", 1)
    return body.strip()


async def _system(answered):
    calls = answered()
    await chat.turn(MESSAGES)
    return calls[0]["system"]


async def _sent(answered, messages=LONG):
    calls = answered()
    await chat.turn(messages)
    return calls[0]["messages"]


def _app_yaml(name):
    return (apps.APPS_DIR / name / "app.yaml").read_text()


class TestTurnAsksTheModel:
    async def test_one_parse_call_answers_a_turn(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES)
        assert len(calls) == 1

    async def test_the_model_is_the_custom_model(self, on, answered, monkeypatch):
        monkeypatch.setattr(settings, "CUSTOM_MODEL", "claude-test-model")
        calls = answered()
        await chat.turn(MESSAGES)
        assert calls[0]["model"] == "claude-test-model"

    async def test_the_answer_may_run_to_the_custom_max_tokens(
        self, on, answered, monkeypatch
    ):
        monkeypatch.setattr(settings, "CUSTOM_MAX_TOKENS", 1234)
        calls = answered()
        await chat.turn(MESSAGES)
        assert calls[0]["max_tokens"] == 1234

    async def test_the_refusal_fallback_is_on(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES)
        assert calls[0]["fallback"] is True

    async def test_a_client_override_reaches_the_model(self, on, answered):
        calls = answered()
        stand_in = object()
        await chat.turn(MESSAGES, client_override=stand_in)
        assert calls[0]["client_override"] is stand_in

    async def test_the_model_fills_only_a_reply_questions_suggestions_and_a_draft(
        self, on, answered
    ):
        calls = answered()
        await chat.turn(MESSAGES)
        fields = set(calls[0]["output_format"].model_fields)
        assert fields == {"reply", "questions", "suggestions", "draft"}

    async def test_a_suggestion_is_an_app_a_title_and_a_reason(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES)
        suggestion = calls[0]["output_format"].model_fields["suggestions"].annotation
        [shape] = suggestion.__args__
        assert set(shape.model_fields) == {"app", "title", "reason"}

    async def test_the_conversation_goes_in_order_with_each_speaker(self, on, answered):
        sent = await _sent(answered, MESSAGES)
        assert [message["role"] for message in sent] == ["user", "assistant", "user"]
        assert [sent[0]["content"], sent[2]["content"]] == [
            MESSAGES[0]["text"],
            MESSAGES[2]["text"],
        ]


class TestTheSystemPrompt:
    async def test_it_holds_the_dw_app_skill_body(self, on, answered):
        assert _skill_body() in await _system(answered)

    async def test_it_leaves_out_the_skill_front_matter(self, on, answered):
        assert "user-invocable: true" not in await _system(answered)

    async def test_it_holds_the_app_builder_turn_prompt(self, on, answered):
        assert prompts.text("app_builder", "turn") in await _system(answered)

    async def test_it_names_every_existing_app(self, on, answered):
        system = await _system(answered)
        names = apps.names()
        assert names
        assert [name for name in names if name not in system] == []

    async def test_it_names_every_ontology_entity(self, on, answered):
        system = await _system(answered)
        entities = list(ontology.load().entities)
        assert entities
        assert [name for name in entities if name not in system] == []


class TestTheAnswer:
    async def test_with_no_draft_the_reply_and_questions_come_back_alone(
        self, on, answered
    ):
        answered()
        assert await chat.turn(MESSAGES) == {
            "reply": REPLY,
            "questions": QUESTIONS,
            "suggestions": [],
            "draft": None,
            "problems": [],
        }

    async def test_a_blank_draft_counts_as_no_draft(self, on, answered):
        answered(draft="  \n")
        result = await chat.turn(MESSAGES)
        assert (result["draft"], result["problems"]) == (None, [])

    async def test_a_valid_draft_comes_back_with_no_problems(self, on, answered):
        answered(draft=RECEIPTS, questions=[])
        assert await chat.turn(MESSAGES) == {
            "reply": REPLY,
            "questions": [],
            "suggestions": [],
            "draft": RECEIPTS,
            "problems": [],
        }

    async def test_an_invalid_draft_comes_back_with_the_app_error(self, on, answered):
        answered(draft=INVALID, questions=[])
        assert await chat.turn(MESSAGES) == {
            "reply": REPLY,
            "questions": [],
            "suggestions": [],
            "draft": INVALID,
            "problems": [_refusal(INVALID)],
        }

    async def test_a_draft_that_is_not_yaml_is_one_problem_naming_yaml(
        self, on, answered
    ):
        answered(draft=NOT_YAML)
        [problem] = (await chat.turn(MESSAGES))["problems"]
        assert problem.startswith("the draft is not YAML: ")

    async def test_a_draft_that_is_not_a_mapping_is_one_problem(self, on, answered):
        answered(draft=NOT_A_MAPPING)
        result = await chat.turn(MESSAGES)
        assert result["problems"] == ["the draft is not a mapping"]


class TestTheConversation:
    async def test_it_goes_as_messages_not_as_one_user_string(self, on, answered):
        calls = answered()
        await chat.turn(LONG)
        assert "user" not in calls[0]
        assert len(calls[0]["messages"]) == len(LONG)

    async def test_every_turn_alternates_person_as_user_and_builder_as_assistant(
        self, on, answered
    ):
        sent = await _sent(answered)
        assert [message["role"] for message in sent] == [
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
            "assistant",
            "user",
        ]

    async def test_each_person_message_goes_as_its_text_in_order(self, on, answered):
        sent = await _sent(answered)
        assert [message["content"] for message in sent[::2]] == [
            message["text"] for message in LONG[::2]
        ]

    async def test_each_builder_message_goes_as_its_whole_answer(self, on, answered):
        sent = await _sent(answered)
        assert [json.loads(message["content"]) for message in sent[1::2]] == [
            {
                "reply": message["text"],
                "questions": message["questions"],
                "suggestions": message["suggestions"],
                "draft": message["draft"],
                "problems": [],
            }
            for message in LONG[1::2]
        ]

    async def test_a_builder_drafts_problems_go_back_with_it(self, on, answered):
        broken = {**LONG[3], "draft": INVALID}
        sent = await _sent(answered, [*LONG[:3], broken, LONG[4]])
        assert json.loads(sent[3]["content"])["problems"] == [_refusal(INVALID)]

    async def test_the_builders_drafts_go_back_to_the_model_latest_last(
        self, on, answered
    ):
        sent = await _sent(answered)
        drafts = [json.loads(message["content"])["draft"] for message in sent[1::2]]
        assert drafts == [None, RECEIPTS, REVISED]

    async def test_the_last_message_is_the_persons_latest_words(self, on, answered):
        sent = await _sent(answered)
        assert sent[-1] == {"role": "user", "content": "Add a field for the trip."}


class TestSuggestions:
    async def test_suggestions_come_back_in_order(self, on, answered):
        assert EXISTING["app"] in apps.names()
        answered(suggestions=[NEW_IDEA, EXISTING], questions=[])
        result = await chat.turn(MESSAGES)
        assert result["suggestions"] == [NEW_IDEA, EXISTING]

    async def test_a_suggestion_naming_an_app_not_here_is_dropped(self, on, answered):
        assert UNKNOWN["app"] not in apps.names()
        answered(suggestions=[UNKNOWN, EXISTING, NEW_IDEA], questions=[])
        result = await chat.turn(MESSAGES)
        assert result["suggestions"] == [EXISTING, NEW_IDEA]

    async def test_no_suggestions_come_back_as_an_empty_list(self, on, answered):
        answered(draft=RECEIPTS, questions=[])
        assert (await chat.turn(MESSAGES))["suggestions"] == []


class TestChangingAnApp:
    async def test_the_model_sees_the_app_to_change_as_it_is_now(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES, changing="receipts")
        heading = "## The app to change: receipts"
        assert f"{heading}\n\n{_app_yaml('receipts')}" in calls[0]["system"]

    async def test_the_rest_of_the_system_prompt_stays_as_it_is(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES)
        await chat.turn(MESSAGES, changing="receipts")
        plain, changed = calls[0]["system"], calls[1]["system"]
        assert changed.startswith(plain)

    async def test_a_new_app_shows_no_app_to_change(self, on, answered):
        assert "## The app to change" not in await _system(answered)

    def test_the_app_yaml_is_the_apps_file_as_written(self):
        assert chat.app_yaml("receipts") == _app_yaml("receipts")

    def test_an_app_not_here_is_missing_naming_it(self):
        with pytest.raises(chat.Missing, match="no app named 'dental_xrays'"):
            chat.app_yaml("dental_xrays")

    def test_a_name_reaching_outside_the_apps_is_missing(self):
        with pytest.raises(chat.Missing):
            chat.app_yaml("../prompts.yaml")

    def test_missing_is_a_lookup_error(self):
        assert issubclass(chat.Missing, LookupError)


class TestTurnRefusals:
    async def test_the_builder_off_is_a_builder_error_naming_the_flag(self, answered):
        answered()
        with pytest.raises(chat.BuilderError) as caught:
            await chat.turn(MESSAGES)
        assert str(caught.value) == OFF

    async def test_the_builder_off_asks_the_model_nothing(self, answered):
        calls = answered()
        with pytest.raises(chat.BuilderError):
            await chat.turn(MESSAGES)
        assert calls == []

    async def test_a_model_failure_is_a_builder_error_with_its_message(
        self, on, overloaded
    ):
        with pytest.raises(chat.BuilderError) as caught:
            await chat.turn(MESSAGES)
        assert str(caught.value) == "overloaded"

    def test_builder_error_is_a_runtime_error(self):
        assert issubclass(chat.BuilderError, RuntimeError)


class TestFileIssue:
    async def test_posts_to_the_repositorys_issues_on_the_github_stand_in(
        self, github_answers
    ):
        seen = github_answers(httpx.Response(201, json=CREATED))
        await github.file_issue(TITLE, BODY)
        [request] = seen
        assert request.method == "POST"
        assert request.url.path == f"/repos/{REPOSITORY}/issues"

    async def test_sends_the_github_stand_in_credentials(self, github_answers):
        seen = github_answers(httpx.Response(201, json=CREATED))
        await github.file_issue(TITLE, BODY)
        [request] = seen
        assert request.headers["authorization"] == "Bearer mock_github_token"
        assert request.headers["accept"] == "application/vnd.github+json"

    async def test_sends_the_title_the_body_and_the_app_label(self, github_answers):
        seen = github_answers(httpx.Response(201, json=CREATED))
        await github.file_issue(TITLE, BODY)
        [request] = seen
        assert json.loads(request.content) == {
            "title": TITLE,
            "body": BODY,
            "labels": ["app"],
        }

    async def test_labels_given_replace_the_app_label(self, github_answers):
        seen = github_answers(httpx.Response(201, json=CREATED))
        await github.file_issue(TITLE, BODY, labels=("app", "urgent"))
        [request] = seen
        assert json.loads(request.content)["labels"] == ["app", "urgent"]

    async def test_answers_with_the_issue_number_and_its_page(self, github_answers):
        github_answers(httpx.Response(201, json=CREATED))
        assert await github.file_issue(TITLE, BODY) == {"number": 7, "url": PAGE}

    async def test_a_refused_issue_is_a_github_error_naming_the_status(
        self, github_answers
    ):
        github_answers(httpx.Response(422, json={"message": "Validation Failed"}))
        with pytest.raises(github.GitHubError, match="422"):
            await github.file_issue(TITLE, BODY)

    async def test_an_unreachable_github_is_a_github_error(self, github_answers):
        github_answers(httpx.ConnectError("connection refused"))
        with pytest.raises(github.GitHubError):
            await github.file_issue(TITLE, BODY)

    def test_github_error_is_a_runtime_error(self):
        assert issubclass(github.GitHubError, RuntimeError)
