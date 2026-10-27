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
    {"role": "builder", "text": "Who sends them in?"},
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

    def answer(draft=None, reply=REPLY, questions=QUESTIONS):
        async def parse(**kwargs):
            calls.append(kwargs)
            parsed = kwargs["output_format"](
                reply=reply, questions=list(questions), draft=draft
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

    async def test_the_model_fills_only_a_reply_questions_and_a_draft(
        self, on, answered
    ):
        calls = answered()
        await chat.turn(MESSAGES)
        fields = set(calls[0]["output_format"].model_fields)
        assert fields == {"reply", "questions", "draft"}

    async def test_the_conversation_goes_in_order_with_each_speaker(self, on, answered):
        calls = answered()
        await chat.turn(MESSAGES)
        user = calls[0]["user"]
        lines = [f"{message['role']}: {message['text']}" for message in MESSAGES]
        assert all(line in user for line in lines)
        positions = [user.index(line) for line in lines]
        assert positions == sorted(positions)


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
            "draft": RECEIPTS,
            "problems": [],
        }

    async def test_an_invalid_draft_comes_back_with_the_app_error(self, on, answered):
        answered(draft=INVALID, questions=[])
        assert await chat.turn(MESSAGES) == {
            "reply": REPLY,
            "questions": [],
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
