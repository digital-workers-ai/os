import base64
import re

import httpx
import pytest
import pytest_asyncio
import yaml

from app import llm
from app.builder import github
from app.config import settings
from app.custom import reader
from app.engine import apps
from app.main import app

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
BAD_DRAFTS = [INVALID, NOT_YAML, NOT_A_MAPPING]
OFF = "the builder is off: set BUILDER_ENABLED"
JPEG = b"\xff\xd8\xff\xe0 a synthetic receipt"
DATA = base64.b64encode(JPEG).decode()
SAMPLE = {"name": "receipt.jpg", "media_type": "image/jpeg", "data": DATA}
TEXT = "Harbor Fuel, diesel, 48.20"
READING = {"fields": {"vendor": "Harbor Fuel", "total": 48.2}, "missing": ["tax"]}
DESCRIPTION = "We snap receipts for fuel and meals and want them sorted."
ANSWERS = ["Staff and finance send them in.", "Fuel, meals, supplies and travel."]
SUBMIT = {"description": DESCRIPTION, "answers": ANSWERS, "draft": RECEIPTS}
ISSUE = {"number": 7, "url": "https://github.com/acme/widgets/issues/7"}
GITHUB_DOWN = "[github] HTTP 503 from https://api.github.com/repos/acme/widgets/issues"
BAD_TURNS = [
    {},
    {"messages": []},
    {"messages": "hello"},
    {"messages": [{"role": "admin", "text": "hello"}]},
    {"messages": [{"text": "hello"}]},
    {"messages": [{"role": "person"}]},
    {"messages": [{"role": "person", "text": ""}]},
    {"messages": [{"role": "person", "text": "  \n"}]},
    {"messages": [{"role": "person", "text": 3}]},
]
BAD_TRIES = [
    {},
    {"draft": 3},
    {"draft": RECEIPTS, "files": "receipt.jpg"},
    {"draft": RECEIPTS, "files": [{"name": "receipt.jpg", "media_type": "image/jpeg"}]},
    {"draft": RECEIPTS, "files": [{"name": "receipt.jpg", "data": DATA}]},
    {"draft": RECEIPTS, "files": [{**SAMPLE, "data": "abc"}]},
    {"draft": RECEIPTS, "text": 3},
]
BAD_SUBMITS = [
    {},
    {"answers": ANSWERS, "draft": RECEIPTS},
    {"description": DESCRIPTION, "answers": ANSWERS},
    {"description": 3, "answers": ANSWERS, "draft": RECEIPTS},
    {"description": DESCRIPTION, "answers": "fuel", "draft": RECEIPTS},
    {"description": DESCRIPTION, "answers": [3], "draft": RECEIPTS},
    {"description": DESCRIPTION, "answers": ANSWERS, "draft": 3},
]


@pytest_asyncio.fixture
async def api():
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client


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


@pytest.fixture
def read(monkeypatch):
    calls = []

    async def fake(definition, *, files, text, **kwargs):
        calls.append({"app": definition, "files": files, "text": text})
        return READING

    monkeypatch.setattr(reader, "read", fake)
    return calls


@pytest.fixture
def reading_off(monkeypatch):
    async def fake(definition, *, files, text, **kwargs):
        raise reader.ReadError("reading is off: set CUSTOM_ENABLED")

    monkeypatch.setattr(reader, "read", fake)


@pytest.fixture
def filed(monkeypatch):
    issues = []

    async def file_issue(title, body, labels=("app",)):
        issues.append({"title": title, "body": body, "labels": list(labels)})
        return ISSUE

    monkeypatch.setattr(github, "file_issue", file_issue)
    return issues


@pytest.fixture
def github_down(monkeypatch):
    async def file_issue(title, body, labels=("app",)):
        raise github.GitHubError(GITHUB_DOWN)

    monkeypatch.setattr(github, "file_issue", file_issue)


def _refusal(draft):
    with pytest.raises(apps.AppError) as caught:
        apps.parse("draft", yaml.safe_load(draft))
    return str(caught.value)


def _yaml_block(body):
    found = re.search(r"```yaml\n(.*?)\n*```", body, re.DOTALL)
    return None if found is None else found.group(1)


async def _filed_body(api, filed, **changes):
    await api.post("/api/builder/submit", json={**SUBMIT, **changes})
    [issue] = filed
    return issue["body"]


class TestTurns:
    async def test_a_turn_answers_with_the_reply_questions_draft_and_problems(
        self, api, on, answered
    ):
        answered(draft=RECEIPTS)
        response = await api.post("/api/builder/turns", json={"messages": MESSAGES})
        assert response.status_code == 200
        assert response.json() == {
            "reply": REPLY,
            "questions": QUESTIONS,
            "draft": RECEIPTS,
            "problems": [],
        }

    async def test_an_invalid_draft_answers_with_its_problems(self, api, on, answered):
        answered(draft=INVALID)
        response = await api.post("/api/builder/turns", json={"messages": MESSAGES})
        assert response.json()["problems"] == [_refusal(INVALID)]

    async def test_the_messages_reach_the_model_with_each_speaker(
        self, api, on, answered
    ):
        calls = answered()
        await api.post("/api/builder/turns", json={"messages": MESSAGES})
        [call] = calls
        for message in MESSAGES:
            assert f"{message['role']}: {message['text']}" in call["user"]

    async def test_the_builder_off_is_a_409_with_the_refusal(self, api, answered):
        calls = answered()
        response = await api.post("/api/builder/turns", json={"messages": MESSAGES})
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert calls == []

    async def test_a_model_failure_is_a_409_with_its_message(self, api, on, overloaded):
        response = await api.post("/api/builder/turns", json={"messages": MESSAGES})
        assert response.status_code == 409
        assert response.json()["detail"] == "overloaded"

    @pytest.mark.parametrize("body", BAD_TURNS)
    async def test_a_bad_body_is_a_422_and_asks_nothing(self, api, on, answered, body):
        calls = answered()
        response = await api.post("/api/builder/turns", json=body)
        assert response.status_code == 422
        assert calls == []


class TestTry:
    async def test_the_reading_comes_back_as_the_answer(self, api, on, read):
        response = await api.post(
            "/api/builder/try", json={"draft": RECEIPTS, "files": [SAMPLE]}
        )
        assert response.status_code == 200
        assert response.json() == READING

    async def test_the_sample_is_read_with_the_draft_parsed_as_draft(
        self, api, on, read
    ):
        await api.post("/api/builder/try", json={"draft": RECEIPTS, "text": TEXT})
        [call] = read
        assert call["app"] == apps.parse("draft", yaml.safe_load(RECEIPTS))

    async def test_files_reach_the_reader_decoded_with_their_media_type(
        self, api, on, read
    ):
        await api.post("/api/builder/try", json={"draft": RECEIPTS, "files": [SAMPLE]})
        [call] = read
        assert call["files"] == [("image/jpeg", JPEG)]

    async def test_the_text_reaches_the_reader(self, api, on, read):
        await api.post("/api/builder/try", json={"draft": RECEIPTS, "text": TEXT})
        [call] = read
        assert call["text"] == TEXT

    async def test_without_files_the_reader_gets_an_empty_list(self, api, on, read):
        await api.post("/api/builder/try", json={"draft": RECEIPTS, "text": TEXT})
        [call] = read
        assert call["files"] == []

    async def test_without_text_the_reader_gets_none(self, api, on, read):
        await api.post("/api/builder/try", json={"draft": RECEIPTS, "files": [SAMPLE]})
        [call] = read
        assert call["text"] is None

    async def test_an_invalid_draft_is_a_422_with_the_app_error(self, api, on, read):
        response = await api.post(
            "/api/builder/try", json={"draft": INVALID, "text": TEXT}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == _refusal(INVALID)

    async def test_a_draft_that_is_not_yaml_is_a_422_naming_yaml(self, api, on, read):
        response = await api.post(
            "/api/builder/try", json={"draft": NOT_YAML, "text": TEXT}
        )
        assert response.status_code == 422
        assert response.json()["detail"].startswith("the draft is not YAML: ")

    async def test_a_draft_that_is_not_a_mapping_is_a_422(self, api, on, read):
        response = await api.post(
            "/api/builder/try", json={"draft": NOT_A_MAPPING, "text": TEXT}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == "the draft is not a mapping"

    @pytest.mark.parametrize("draft", BAD_DRAFTS)
    async def test_a_bad_draft_reads_nothing(self, api, on, read, draft):
        await api.post("/api/builder/try", json={"draft": draft, "text": TEXT})
        assert read == []

    async def test_the_builder_off_is_a_409_and_reads_nothing(self, api, read):
        response = await api.post(
            "/api/builder/try", json={"draft": RECEIPTS, "text": TEXT}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert read == []

    async def test_reading_off_is_a_409_with_the_readers_words(
        self, api, on, reading_off
    ):
        response = await api.post(
            "/api/builder/try", json={"draft": RECEIPTS, "text": TEXT}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "reading is off: set CUSTOM_ENABLED"

    @pytest.mark.parametrize("body", BAD_TRIES)
    async def test_a_bad_body_is_a_422_and_reads_nothing(self, api, on, read, body):
        response = await api.post("/api/builder/try", json=body)
        assert response.status_code == 422
        assert read == []


class TestSubmit:
    async def test_the_issue_is_titled_after_the_draft(self, api, on, filed):
        await api.post("/api/builder/submit", json=SUBMIT)
        [issue] = filed
        assert issue["title"] == "New app: Receipts"

    async def test_the_issue_body_holds_the_description(self, api, on, filed):
        assert DESCRIPTION in await _filed_body(api, filed)

    async def test_the_issue_body_holds_every_answer(self, api, on, filed):
        body = await _filed_body(api, filed)
        assert [answer for answer in ANSWERS if answer not in body] == []

    async def test_the_issue_body_holds_the_draft_in_a_yaml_block(self, api, on, filed):
        body = await _filed_body(api, filed)
        assert _yaml_block(body) == RECEIPTS.strip()

    async def test_the_issue_is_labelled_app(self, api, on, filed):
        await api.post("/api/builder/submit", json=SUBMIT)
        [issue] = filed
        assert issue["labels"] == ["app"]

    async def test_no_answers_still_files_the_issue(self, api, on, filed):
        body = await _filed_body(api, filed, answers=[])
        assert _yaml_block(body) == RECEIPTS.strip()

    async def test_submit_answers_with_the_issue_number_and_url(self, api, on, filed):
        response = await api.post("/api/builder/submit", json=SUBMIT)
        assert response.status_code == 200
        assert response.json() == ISSUE

    async def test_github_failing_is_a_502_with_its_message(self, api, on, github_down):
        response = await api.post("/api/builder/submit", json=SUBMIT)
        assert response.status_code == 502
        assert response.json()["detail"] == GITHUB_DOWN

    async def test_the_builder_off_is_a_409_and_files_nothing(self, api, filed):
        response = await api.post("/api/builder/submit", json=SUBMIT)
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert filed == []

    async def test_an_invalid_draft_is_a_422_with_the_app_error(self, api, on, filed):
        response = await api.post(
            "/api/builder/submit", json={**SUBMIT, "draft": INVALID}
        )
        assert response.status_code == 422
        assert response.json()["detail"] == _refusal(INVALID)

    @pytest.mark.parametrize("draft", BAD_DRAFTS)
    async def test_a_bad_draft_is_a_422_and_files_nothing(self, api, on, filed, draft):
        response = await api.post(
            "/api/builder/submit", json={**SUBMIT, "draft": draft}
        )
        assert response.status_code == 422
        assert filed == []

    @pytest.mark.parametrize("body", BAD_SUBMITS)
    async def test_a_bad_body_is_a_422_and_files_nothing(self, api, on, filed, body):
        response = await api.post("/api/builder/submit", json=body)
        assert response.status_code == 422
        assert filed == []
