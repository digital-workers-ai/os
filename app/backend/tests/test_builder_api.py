import base64
import json
import re
import uuid
from datetime import UTC, datetime

import httpx
import pytest
import pytest_asyncio
import yaml
from sqlalchemy import delete, select

from app import llm
from app.builder import github
from app.config import settings
from app.custom import reader, records
from app.db import get_session
from app.engine import apps
from app.main import app
from app.models import BuilderQuestion, BuilderSuggestion, BuilderThread, BuilderTurn

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
THREADS = "/api/builder/threads"
NOBODY = "00000000-0000-4000-8000-000000000000"
REPLY = "A few questions before the draft."
QUESTIONS = ["Who sends receipts in?", "Which categories do you use?"]
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
REVISED = RECEIPTS.replace(
    "vendor: { type: text }",
    "vendor: { type: text, description: The store or station when it is named }",
)
TRIPPED = (
    REVISED.replace("title: Receipts", "title: Fuel and meal receipts")
    + "  trip: { type: text }\n"
)
INVALID = RECEIPTS.replace("vendor: { type: text }", "vendor: { type: paragraph }")
NOT_YAML = "title: [Receipts\n"
NOT_A_MAPPING = "- receipts\n- invoices\n"
BAD_DRAFTS = [INVALID, NOT_YAML, NOT_A_MAPPING]
UNPARSEABLE = [NOT_YAML, NOT_A_MAPPING]
UNTITLED = [
    RECEIPTS.replace("title: Receipts\n", ""),
    RECEIPTS.replace("title: Receipts", "title: 3"),
    RECEIPTS.replace("title: Receipts", 'title: ""'),
    RECEIPTS.replace("title: Receipts", 'title: "  "'),
    RECEIPTS.replace("title: Receipts", "title: [Receipts]"),
]
TITLED_WITH_PROBLEMS = [
    (INVALID, "Receipts"),
    (INVALID.replace("title: Receipts", 'title: "  Receipts  "'), "Receipts"),
]
OFF = "the builder is off: set BUILDER_ENABLED"
NO_DRAFT = "there is no draft yet"
JPEG = b"\xff\xd8\xff\xe0 a synthetic receipt"
PNG = b"\x89PNG\r\n\x1a\n a synthetic receipt"
PDF = "application/pdf"
DATA = base64.b64encode(JPEG).decode()
SAMPLE = {"name": "receipt.jpg", "media_type": "image/jpeg", "data": DATA}
REFUSED_FILES = [
    ("receipt.jpg", "image/jpeg", PNG),
    ("receipt.png", "image/png", JPEG),
    ("invoice.pdf", PDF, JPEG),
    ("receipt.gif", "image/gif", b"GIF89a a synthetic receipt"),
    ("clip.webm", "audio/webm", b"\x1a\x45\xdf\xa3 a synthetic clip"),
    ("notes.txt", "text/plain", b"Harbor Fuel, diesel"),
]
REFUSED_IDS = ["png-as-jpeg", "jpeg-as-png", "jpeg-as-pdf", "gif", "a-clip", "text"]
TEXT = "Harbor Fuel, diesel, 48.20"
READING = {"fields": {"vendor": "Harbor Fuel", "total": 48.2}, "missing": ["tax"]}
DESCRIPTION = "We snap receipts for fuel and meals and want them sorted."
ANSWERED = (
    "Who sends receipts in?\nStaff and finance.\n\n"
    "Which categories do you use?\nFuel, meals, supplies and travel."
)
EXISTING = {
    "app": "receipts",
    "title": "Receipts",
    "reason": "Your drivers photograph every fuel stop.",
}
NEW_IDEA = {
    "app": None,
    "title": "Trip log",
    "reason": "Each trip keeps its own fuel and meals together.",
}
UNKNOWN = {
    "app": "dental_xrays",
    "title": "Dental x-rays",
    "reason": "Every x-ray is filed with its patient.",
}
SAID = [
    DESCRIPTION,
    ANSWERED,
    "Make the vendor optional.",
    "Add a field for the trip.",
]
REPLIES = [
    {"reply": REPLY, "questions": QUESTIONS, "suggestions": [NEW_IDEA], "draft": None},
    {
        "reply": "Here is the draft.",
        "questions": [],
        "suggestions": [],
        "draft": RECEIPTS,
    },
    {
        "reply": "The vendor may be left empty now.",
        "questions": [],
        "suggestions": [],
        "draft": REVISED,
    },
    {
        "reply": "The trip has its own field.",
        "questions": [],
        "suggestions": [],
        "draft": TRIPPED,
    },
]
ISSUE = {"number": 7, "url": "https://github.com/acme/widgets/issues/7"}
FILED_ALREADY = "this thread was filed as issue #7"
GITHUB_DOWN = "[github] HTTP 503 from https://api.github.com/repos/acme/widgets/issues"
BAD_THREADS = [{"app": 3}, {"app": ["receipts"]}, "receipts"]
BAD_TURNS = [
    {},
    {"text": ""},
    {"text": "  \n"},
    {"text": 3},
    {"messages": [{"role": "person", "text": "hello"}]},
]
BAD_TRIES = [
    {"files": "receipt.jpg"},
    {"files": [{"media_type": "image/jpeg", "data": DATA}]},
    {"files": [{"name": "receipt.jpg", "media_type": "image/jpeg"}]},
    {"files": [{"name": "receipt.jpg", "data": DATA}]},
    {"files": [{**SAMPLE, "data": "abc"}]},
    {"text": 3},
]
ROUTES = [
    ("GET", "", None),
    ("POST", "/turns", {"text": "hello"}),
    ("POST", "/try", {"text": TEXT}),
    ("POST", "/submit", None),
]


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
def on(monkeypatch):
    monkeypatch.setattr(settings, "BUILDER_ENABLED", True)


@pytest.fixture
def turned_off(monkeypatch):
    def turn_off():
        monkeypatch.setattr(settings, "BUILDER_ENABLED", False)

    return turn_off


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


def _sample(name, media_type, data):
    return {
        "name": name,
        "media_type": media_type,
        "data": base64.b64encode(data).decode(),
    }


def _photos(count):
    return [_sample(f"photo-{n}.jpg", "image/jpeg", JPEG) for n in range(1, count + 1)]


def _pdf(pages):
    kids = b"".join(b"%d 0 obj << /Type /Page >> endobj\n" % n for n in range(pages))
    tree = b"<< /Type /Pages /Count %d >>\n" % pages
    return b"%PDF-1.7\n" + kids + tree + b"%%EOF\n"


def _refusal(draft):
    with pytest.raises(apps.AppError) as caught:
        apps.parse("draft", yaml.safe_load(draft))
    return str(caught.value)


def _as_draft(draft):
    return apps.parse("draft", yaml.safe_load(draft))


def _yaml_block(body):
    found = re.search(r"```yaml\n(.*?)\n*```", body, re.DOTALL)
    return None if found is None else found.group(1)


def _sections(body):
    return re.findall(r"^## .+$", body, re.MULTILINE)


def _person(text):
    return {
        "role": "person",
        "text": text,
        "questions": [],
        "suggestions": [],
        "draft": None,
        "problems": [],
    }


def _builder(reply, questions=(), suggestions=(), draft=None, problems=()):
    return {
        "role": "builder",
        "text": reply,
        "questions": list(questions),
        "suggestions": list(suggestions),
        "draft": draft,
        "problems": list(problems),
    }


def _answer_of(answer, problems=()):
    keys = ("reply", "questions", "suggestions", "draft")
    return {**{key: answer[key] for key in keys}, "problems": list(problems)}


async def _fresh(sessionmaker_for_test, model, order):
    async with sessionmaker_for_test() as fresh:
        return (await fresh.execute(select(model).order_by(order))).scalars().all()


async def _thread(api, **body):
    response = await api.post(THREADS, json=body or None)
    return response.json()["id"]


async def _say(api, thread, text=DESCRIPTION):
    return await api.post(f"{THREADS}/{thread}/turns", json={"text": text})


async def _drafted(api, answered, draft=RECEIPTS, **body):
    answered(draft=draft, questions=[])
    thread = await _thread(api, **body)
    await _say(api, thread)
    return thread


async def _tried(api, thread, files):
    return await api.post(f"{THREADS}/{thread}/try", json={"files": files})


async def _conversation(api, answered, turns=4, **body):
    thread = await _thread(api, **body)
    calls = []
    for text, reply in zip(SAID[:turns], REPLIES[:turns], strict=True):
        calls = answered(**reply)
        await _say(api, thread, text)
    return thread, calls


async def _filed_body(api, filed, thread):
    await api.post(f"{THREADS}/{thread}/submit")
    [issue] = filed
    return issue["body"]


def _assistant(message):
    assert message["role"] == "assistant"
    return json.loads(message["content"])


class TestThreads:
    async def test_a_new_thread_is_a_201_with_no_app_title_issue_or_turns(
        self, api, on
    ):
        response = await api.post(THREADS)
        assert response.status_code == 201
        body = response.json()
        assert uuid.UUID(body["id"])
        assert body == {
            "id": body["id"],
            "app": None,
            "title": None,
            "created_at": NOW.isoformat(),
            "issue": None,
            "turns": [],
        }

    async def test_an_empty_body_starts_a_new_app_thread_too(self, api, on):
        response = await api.post(THREADS, json={})
        assert response.status_code == 201
        assert response.json()["app"] is None

    async def test_the_thread_is_stored_with_no_app_and_no_issue(
        self, api, on, sessionmaker_for_test
    ):
        thread = await _thread(api)
        [row] = await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq)
        assert (str(row.id), row.app, row.issue_number, row.issue_url) == (
            thread,
            None,
            None,
            None,
        )
        assert row.created_at == NOW

    async def test_a_thread_changing_an_app_here_names_it(
        self, api, on, sessionmaker_for_test
    ):
        response = await api.post(THREADS, json={"app": "receipts"})
        assert response.status_code == 201
        assert response.json()["app"] == "receipts"
        [row] = await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq)
        assert row.app == "receipts"

    async def test_a_thread_for_an_app_not_here_is_a_404_and_stores_nothing(
        self, api, on, sessionmaker_for_test
    ):
        response = await api.post(THREADS, json={"app": "dental_xrays"})
        assert response.status_code == 404
        assert response.json()["detail"] == "no app named 'dental_xrays'"
        assert (
            await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq) == []
        )

    async def test_the_builder_off_is_a_409_and_stores_no_thread(
        self, api, sessionmaker_for_test
    ):
        response = await api.post(THREADS)
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert (
            await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq) == []
        )

    @pytest.mark.parametrize("body", BAD_THREADS)
    async def test_a_bad_body_is_a_422_and_stores_nothing(
        self, api, on, sessionmaker_for_test, body
    ):
        response = await api.post(THREADS, json=body)
        assert response.status_code == 422
        assert (
            await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq) == []
        )

    async def test_a_thread_reads_back_with_every_turn_in_order(
        self, api, on, answered
    ):
        thread, _calls = await _conversation(api, answered, turns=2)
        response = await api.get(f"{THREADS}/{thread}")
        assert response.status_code == 200
        assert response.json() == {
            "id": thread,
            "app": None,
            "title": "Receipts",
            "created_at": NOW.isoformat(),
            "issue": None,
            "turns": [
                _person(DESCRIPTION),
                _builder(REPLY, QUESTIONS, [NEW_IDEA]),
                _person(ANSWERED),
                _builder("Here is the draft.", draft=RECEIPTS),
            ],
        }

    async def test_a_long_conversation_reads_back_whole(self, api, on, answered):
        thread, _calls = await _conversation(api, answered)
        turns = (await api.get(f"{THREADS}/{thread}")).json()["turns"]
        assert [(turn["role"], turn["text"]) for turn in turns] == [
            pair
            for text, reply in zip(SAID, REPLIES, strict=True)
            for pair in (("person", text), ("builder", reply["reply"]))
        ]
        assert [turn["draft"] for turn in turns[1::2]] == [
            None,
            RECEIPTS,
            REVISED,
            TRIPPED,
        ]

    async def test_a_builder_turn_with_an_invalid_draft_reads_back_its_problems(
        self, api, on, answered
    ):
        thread = await _drafted(api, answered, draft=INVALID)
        builder = (await api.get(f"{THREADS}/{thread}")).json()["turns"][1]
        assert builder["problems"] == [_refusal(INVALID)]

    async def test_the_title_is_the_latest_drafts_title(self, api, on, answered):
        thread, _calls = await _conversation(api, answered)
        thread_row = (await api.get(f"{THREADS}/{thread}")).json()
        assert thread_row["title"] == "Fuel and meal receipts"

    @pytest.mark.parametrize("draft", UNPARSEABLE)
    async def test_a_latest_draft_that_does_not_parse_leaves_no_title(
        self, api, on, answered, draft
    ):
        thread = await _drafted(api, answered, draft=draft)
        assert (await api.get(f"{THREADS}/{thread}")).json()["title"] is None

    @pytest.mark.parametrize("draft,title", TITLED_WITH_PROBLEMS)
    async def test_a_latest_draft_with_problems_still_gives_its_title(
        self, api, on, answered, draft, title
    ):
        thread = await _drafted(api, answered, draft=draft)
        thread_row = (await api.get(f"{THREADS}/{thread}")).json()
        assert thread_row["title"] == title
        assert thread_row["turns"][1]["problems"] == [_refusal(draft)]

    @pytest.mark.parametrize("draft", UNTITLED)
    async def test_a_latest_draft_without_a_title_in_words_leaves_no_title(
        self, api, on, answered, draft
    ):
        thread = await _drafted(api, answered, draft=draft)
        assert (await api.get(f"{THREADS}/{thread}")).json()["title"] is None

    async def test_the_list_titles_a_thread_whose_draft_has_problems(
        self, api, on, answered
    ):
        thread = await _drafted(api, answered, draft=INVALID)
        listed = (await api.get(THREADS)).json()
        assert [(row["id"], row["title"]) for row in listed] == [(thread, "Receipts")]

    async def test_a_thread_reads_back_with_the_builder_off(
        self, api, on, answered, turned_off
    ):
        thread = await _drafted(api, answered)
        turned_off()
        response = await api.get(f"{THREADS}/{thread}")
        assert response.status_code == 200
        assert len(response.json()["turns"]) == 2

    async def test_threads_list_newest_first_with_app_title_and_issue(
        self, api, on, answered, filed
    ):
        first = await _drafted(api, answered)
        await api.post(f"{THREADS}/{first}/submit")
        second = await _thread(api, app="receipts")
        response = await api.get(THREADS)
        assert response.status_code == 200
        assert response.json() == [
            {
                "id": second,
                "app": "receipts",
                "title": None,
                "created_at": NOW.isoformat(),
                "issue": None,
            },
            {
                "id": first,
                "app": None,
                "title": "Receipts",
                "created_at": NOW.isoformat(),
                "issue": ISSUE,
            },
        ]

    async def test_the_list_titles_each_thread_after_its_own_latest_draft(
        self, api, on, answered
    ):
        long, _calls = await _conversation(api, answered)
        short = await _drafted(api, answered, draft=REVISED)
        listed = (await api.get(THREADS)).json()
        assert [(row["id"], row["title"]) for row in listed] == [
            (short, "Receipts"),
            (long, "Fuel and meal receipts"),
        ]

    async def test_removing_a_thread_removes_its_turns_questions_and_suggestions(
        self, api, on, answered, session, sessionmaker_for_test
    ):
        answered(suggestions=[NEW_IDEA])
        thread = await _thread(api)
        await _say(api, thread)
        await session.execute(
            delete(BuilderThread).where(BuilderThread.id == uuid.UUID(thread))
        )
        await session.commit()
        for model in (BuilderTurn, BuilderQuestion, BuilderSuggestion):
            assert await _fresh(sessionmaker_for_test, model, model.seq) == []

    async def test_no_threads_list_as_an_empty_list(self, api):
        response = await api.get(THREADS)
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.parametrize("method,path,body", ROUTES)
    async def test_an_unknown_thread_is_a_404_naming_it(
        self, api, on, read, filed, method, path, body
    ):
        response = await api.request(method, f"{THREADS}/{NOBODY}{path}", json=body)
        assert response.status_code == 404
        assert response.json()["detail"] == f"no thread {NOBODY}"

    @pytest.mark.parametrize("method,path,body", ROUTES)
    async def test_a_thread_id_that_is_not_a_uuid_is_a_422(
        self, api, on, method, path, body
    ):
        response = await api.request(method, f"{THREADS}/42{path}", json=body)
        assert response.status_code == 422


class TestTurns:
    async def test_a_turn_answers_with_the_persons_turn_and_the_builders_reply(
        self, api, on, answered
    ):
        answered(draft=RECEIPTS, suggestions=[EXISTING])
        response = await _say(api, await _thread(api))
        assert response.status_code == 200
        assert response.json() == {
            "turn": _person(DESCRIPTION),
            "reply": _builder(REPLY, QUESTIONS, [EXISTING], RECEIPTS),
        }

    async def test_an_invalid_draft_answers_with_its_problems(self, api, on, answered):
        answered(draft=INVALID)
        response = await _say(api, await _thread(api))
        assert response.json()["reply"]["problems"] == [_refusal(INVALID)]

    async def test_the_persons_text_is_kept_without_its_surrounding_space(
        self, api, on, answered
    ):
        answered()
        response = await _say(api, await _thread(api), f"  {DESCRIPTION}\n")
        assert response.json()["turn"]["text"] == DESCRIPTION

    async def test_both_turns_are_stored_in_order(
        self, api, on, answered, sessionmaker_for_test
    ):
        answered(draft=RECEIPTS)
        thread = await _thread(api)
        await _say(api, thread)
        rows = await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq)
        assert [(str(r.thread_id), r.role, r.text, r.draft) for r in rows] == [
            (thread, "person", DESCRIPTION, None),
            (thread, "builder", REPLY, RECEIPTS),
        ]
        assert [row.created_at for row in rows] == [NOW, NOW]

    async def test_the_builders_questions_are_stored_in_order_on_its_turn(
        self, api, on, answered, sessionmaker_for_test
    ):
        answered()
        await _say(api, await _thread(api))
        turns = await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq)
        rows = await _fresh(sessionmaker_for_test, BuilderQuestion, BuilderQuestion.seq)
        assert [(row.turn_seq, row.text) for row in rows] == [
            (turns[1].seq, question) for question in QUESTIONS
        ]

    async def test_the_builders_suggestions_are_stored_in_order_on_its_turn(
        self, api, on, answered, sessionmaker_for_test
    ):
        answered(suggestions=[NEW_IDEA, EXISTING], questions=[])
        await _say(api, await _thread(api))
        turns = await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq)
        rows = await _fresh(
            sessionmaker_for_test, BuilderSuggestion, BuilderSuggestion.seq
        )
        assert [(row.turn_seq, row.app, row.title, row.reason) for row in rows] == [
            (turns[1].seq, *suggestion.values()) for suggestion in (NEW_IDEA, EXISTING)
        ]

    async def test_a_suggestion_naming_an_app_not_here_is_dropped_from_the_store(
        self, api, on, answered, sessionmaker_for_test
    ):
        answered(suggestions=[UNKNOWN, EXISTING], questions=[])
        thread = await _thread(api)
        response = await _say(api, thread)
        assert response.json()["reply"]["suggestions"] == [EXISTING]
        rows = await _fresh(
            sessionmaker_for_test, BuilderSuggestion, BuilderSuggestion.seq
        )
        assert [row.app for row in rows] == ["receipts"]
        turns = (await api.get(f"{THREADS}/{thread}")).json()["turns"]
        assert turns[1]["suggestions"] == [EXISTING]

    async def test_every_turn_reaches_the_model_with_the_whole_conversation_so_far(
        self, api, on, answered
    ):
        _thread_id, calls = await _conversation(api, answered)
        assert [len(call["messages"]) for call in calls] == [1, 3, 5, 7]

    async def test_a_third_and_fourth_turn_reach_the_model_as_alternating_turns(
        self, api, on, answered
    ):
        _thread_id, calls = await _conversation(api, answered)
        for call in calls[2:]:
            roles = [message["role"] for message in call["messages"]]
            assert roles == ["user", "assistant"] * (len(roles) // 2) + ["user"]
        assert [message["content"] for message in calls[3]["messages"][::2]] == SAID

    async def test_each_builder_turn_goes_back_as_its_whole_answer(
        self, api, on, answered
    ):
        _thread_id, calls = await _conversation(api, answered)
        sent = [_assistant(message) for message in calls[3]["messages"][1::2]]
        assert sent == [_answer_of(reply) for reply in REPLIES[:3]]

    async def test_a_drafts_problems_go_back_to_the_model_to_fix(
        self, api, on, answered
    ):
        thread = await _drafted(api, answered, draft=INVALID)
        calls = answered(draft=RECEIPTS, questions=[])
        await _say(api, thread, "Fix the errors.")
        assert _assistant(calls[1]["messages"][1]) == _answer_of(
            {"reply": REPLY, "questions": [], "suggestions": [], "draft": INVALID},
            [_refusal(INVALID)],
        )

    async def test_a_builder_turns_draft_goes_back_to_the_model(
        self, api, on, answered
    ):
        _thread_id, calls = await _conversation(api, answered, turns=3)
        assert _assistant(calls[2]["messages"][3])["draft"] == RECEIPTS

    async def test_a_revised_draft_goes_back_after_the_one_it_replaces(
        self, api, on, answered
    ):
        _thread_id, calls = await _conversation(api, answered)
        drafts = [
            _assistant(message)["draft"] for message in calls[3]["messages"][1::2]
        ]
        assert drafts == [None, RECEIPTS, REVISED]

    async def test_only_the_stored_suggestions_go_back_to_the_model(
        self, api, on, answered
    ):
        answered(suggestions=[UNKNOWN, NEW_IDEA], questions=[])
        thread = await _thread(api)
        await _say(api, thread)
        calls = answered(draft=RECEIPTS, questions=[])
        await _say(api, thread, "Draft the Trip log app.")
        assert _assistant(calls[1]["messages"][1])["suggestions"] == [NEW_IDEA]

    async def test_the_turns_of_other_threads_stay_out_of_the_conversation(
        self, api, on, answered
    ):
        await _conversation(api, answered, turns=2)
        calls = answered()
        await _say(api, await _thread(api), "We log every pour.")
        assert calls[-1]["messages"] == [
            {"role": "user", "content": "We log every pour."}
        ]

    async def test_a_thread_changing_an_app_shows_the_model_the_app_as_it_is_now(
        self, api, on, answered
    ):
        calls = answered()
        await _say(api, await _thread(api, app="receipts"), "Add a field for the trip.")
        written = (apps.APPS_DIR / "receipts" / "app.yaml").read_text()
        assert f"## The app to change: receipts\n\n{written}" in calls[0]["system"]

    async def test_a_new_app_thread_shows_the_model_no_app_to_change(
        self, api, on, answered
    ):
        calls = answered()
        await _say(api, await _thread(api))
        assert "## The app to change" not in calls[0]["system"]

    async def test_the_builder_off_is_a_409_and_stores_and_asks_nothing(
        self, api, on, answered, turned_off, sessionmaker_for_test
    ):
        calls = answered()
        thread = await _thread(api)
        turned_off()
        response = await _say(api, thread)
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert calls == []
        assert await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq) == []

    async def test_a_turn_on_a_filed_thread_is_a_409_and_stores_and_asks_nothing(
        self, api, on, answered, filed, sessionmaker_for_test
    ):
        calls = answered(draft=RECEIPTS, questions=[], suggestions=[NEW_IDEA])
        thread = await _thread(api)
        await _say(api, thread)
        await api.post(f"{THREADS}/{thread}/submit")
        response = await _say(api, thread, "Add a field for the trip.")
        assert response.status_code == 409
        assert response.json()["detail"] == FILED_ALREADY
        assert len(calls) == 1
        turns = await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq)
        assert [(row.role, row.text) for row in turns] == [
            ("person", DESCRIPTION),
            ("builder", REPLY),
        ]
        suggestions = await _fresh(
            sessionmaker_for_test, BuilderSuggestion, BuilderSuggestion.seq
        )
        assert [row.title for row in suggestions] == [NEW_IDEA["title"]]

    async def test_a_model_failure_is_a_409_with_its_message_and_stores_nothing(
        self, api, on, overloaded, sessionmaker_for_test
    ):
        response = await _say(api, await _thread(api))
        assert response.status_code == 409
        assert response.json()["detail"] == "overloaded"
        assert await _fresh(sessionmaker_for_test, BuilderTurn, BuilderTurn.seq) == []

    @pytest.mark.parametrize("body", BAD_TURNS)
    async def test_a_bad_body_is_a_422_and_asks_nothing(self, api, on, answered, body):
        calls = answered()
        thread = await _thread(api)
        response = await api.post(f"{THREADS}/{thread}/turns", json=body)
        assert response.status_code == 422
        assert calls == []


class TestTry:
    async def test_the_reading_comes_back_as_the_answer(self, api, on, answered, read):
        thread = await _drafted(api, answered)
        response = await api.post(f"{THREADS}/{thread}/try", json={"files": [SAMPLE]})
        assert response.status_code == 200
        assert response.json() == READING

    async def test_the_sample_is_read_with_the_threads_draft_parsed_as_draft(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        [call] = read
        assert call["app"] == _as_draft(RECEIPTS)

    async def test_a_revised_draft_replaces_the_old_one(self, api, on, answered, read):
        thread, _calls = await _conversation(api, answered, turns=3)
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        [call] = read
        assert call["app"] == _as_draft(REVISED)

    async def test_a_turn_without_a_draft_leaves_the_earlier_draft_to_try(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        answered(questions=["Should the trip be its own field?"])
        await _say(api, thread, "Add a field for the trip.")
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        [call] = read
        assert call["app"] == _as_draft(RECEIPTS)

    async def test_files_reach_the_reader_decoded_with_their_media_type(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/try", json={"files": [SAMPLE]})
        [call] = read
        assert call["files"] == [("image/jpeg", JPEG)]

    async def test_the_text_reaches_the_reader(self, api, on, answered, read):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        [call] = read
        assert call["text"] == TEXT

    async def test_without_files_the_reader_gets_an_empty_list(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        [call] = read
        assert call["files"] == []

    async def test_without_text_the_reader_gets_none(self, api, on, answered, read):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/try", json={"files": [SAMPLE]})
        [call] = read
        assert call["text"] is None

    async def test_a_thread_with_no_draft_yet_is_a_409_and_reads_nothing(
        self, api, on, answered, read
    ):
        answered()
        thread = await _thread(api)
        await _say(api, thread)
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 409
        assert response.json()["detail"] == NO_DRAFT
        assert read == []

    async def test_an_invalid_draft_is_a_422_with_the_app_error(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered, draft=INVALID)
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 422
        assert response.json()["detail"] == _refusal(INVALID)

    async def test_a_draft_that_is_not_yaml_is_a_422_naming_yaml(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered, draft=NOT_YAML)
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 422
        assert response.json()["detail"].startswith("the draft is not YAML: ")

    async def test_a_draft_that_is_not_a_mapping_is_a_422(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered, draft=NOT_A_MAPPING)
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 422
        assert response.json()["detail"] == "the draft is not a mapping"

    @pytest.mark.parametrize("draft", BAD_DRAFTS)
    async def test_a_bad_draft_reads_nothing(self, api, on, answered, read, draft):
        thread = await _drafted(api, answered, draft=draft)
        await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert read == []

    async def test_the_builder_off_is_a_409_and_reads_nothing(
        self, api, on, answered, read, turned_off
    ):
        thread = await _drafted(api, answered)
        turned_off()
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert read == []

    async def test_reading_off_is_a_409_with_the_readers_words(
        self, api, on, answered, reading_off
    ):
        thread = await _drafted(api, answered)
        response = await api.post(f"{THREADS}/{thread}/try", json={"text": TEXT})
        assert response.status_code == 409
        assert response.json()["detail"] == "reading is off: set CUSTOM_ENABLED"

    @pytest.mark.parametrize("body", BAD_TRIES)
    async def test_a_bad_body_is_a_422_and_reads_nothing(
        self, api, on, answered, read, body
    ):
        thread = await _drafted(api, answered)
        response = await api.post(f"{THREADS}/{thread}/try", json=body)
        assert response.status_code == 422
        assert read == []

    @pytest.mark.parametrize("file", REFUSED_FILES, ids=REFUSED_IDS)
    async def test_a_file_not_a_photo_or_pdf_of_its_type_is_a_422_naming_it(
        self, api, on, answered, read, file
    ):
        thread = await _drafted(api, answered)
        response = await _tried(api, thread, [SAMPLE, _sample(*file)])
        assert response.status_code == 422
        assert file[0] in response.json()["detail"]
        assert read == []

    async def test_a_file_name_that_climbs_is_a_422_naming_it(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        response = await _tried(api, thread, [{**SAMPLE, "name": "../receipt.jpg"}])
        assert response.status_code == 422
        assert "../receipt.jpg" in response.json()["detail"]
        assert read == []

    async def test_ten_photos_and_a_pdf_of_the_most_pages_reach_the_reader(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        invoice = _pdf(records.MAX_PDF_PAGES)
        sent = [*_photos(records.MAX_PHOTOS), _sample("invoice.pdf", PDF, invoice)]
        response = await _tried(api, thread, sent)
        assert response.status_code == 200
        [call] = read
        assert call["files"] == [("image/jpeg", JPEG)] * 10 + [(PDF, invoice)]

    async def test_an_eleventh_photo_is_a_413_naming_the_limit(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        response = await _tried(api, thread, _photos(records.MAX_PHOTOS + 1))
        assert response.status_code == 413
        assert str(records.MAX_PHOTOS) in response.json()["detail"]
        assert read == []

    async def test_a_second_pdf_is_a_413(self, api, on, answered, read):
        thread = await _drafted(api, answered)
        pdfs = [
            _sample("invoice.pdf", PDF, _pdf(1)),
            _sample("credit-note.pdf", PDF, _pdf(1)),
        ]
        response = await _tried(api, thread, pdfs)
        assert response.status_code == 413
        assert response.json()["detail"] == "2 PDFs came, and a record keeps one"
        assert read == []

    async def test_a_pdf_past_the_most_pages_is_a_413_naming_the_limit(
        self, api, on, answered, read
    ):
        thread = await _drafted(api, answered)
        invoice = _pdf(records.MAX_PDF_PAGES + 1)
        response = await _tried(api, thread, [_sample("invoice.pdf", PDF, invoice)])
        assert response.status_code == 413
        assert str(records.MAX_PDF_PAGES) in response.json()["detail"]
        assert read == []

    async def test_a_request_past_the_most_bytes_is_a_413_naming_the_limit(
        self, api, on, answered, read, monkeypatch
    ):
        thread = await _drafted(api, answered)
        monkeypatch.setattr(records, "MAX_REQUEST_BYTES", 2 * len(JPEG) - 1)
        response = await _tried(api, thread, _photos(2))
        assert response.status_code == 413
        assert str(2 * len(JPEG) - 1) in response.json()["detail"]
        assert read == []

    async def test_a_request_of_the_most_bytes_reaches_the_reader(
        self, api, on, answered, read, monkeypatch
    ):
        thread = await _drafted(api, answered)
        monkeypatch.setattr(records, "MAX_REQUEST_BYTES", 2 * len(JPEG))
        response = await _tried(api, thread, _photos(2))
        assert response.status_code == 200
        [call] = read
        assert len(call["files"]) == 2

    async def test_the_route_documents_its_413(self, api):
        spec = (await api.get("/openapi.json")).json()
        assert "413" in spec["paths"][f"{THREADS}/{{id}}/try"]["post"]["responses"]


class TestSubmit:
    async def test_the_issue_is_titled_after_the_draft(self, api, on, answered, filed):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/submit")
        [issue] = filed
        assert issue["title"] == "New app: Receipts"

    async def test_the_issue_is_titled_after_the_latest_draft(
        self, api, on, answered, filed
    ):
        thread, _calls = await _conversation(api, answered)
        await api.post(f"{THREADS}/{thread}/submit")
        [issue] = filed
        assert issue["title"] == "New app: Fuel and meal receipts"

    async def test_a_thread_changing_an_app_files_a_change_app_issue(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered, draft=REVISED, app="receipts")
        await api.post(f"{THREADS}/{thread}/submit")
        [issue] = filed
        assert issue["title"] == "Change app: Receipts"

    async def test_the_issue_body_holds_the_conversation_and_the_draft(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered)
        body = await _filed_body(api, filed, thread)
        assert _sections(body) == ["## Conversation", "## Draft"]

    async def test_a_change_app_issue_opens_naming_the_app_it_changes(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered, draft=REVISED, app="receipts")
        body = await _filed_body(api, filed, thread)
        assert _sections(body) == ["## App", "## Conversation", "## Draft"]
        assert body.startswith("## App\n\nreceipts\n\n## Conversation\n\n")

    async def test_the_issue_body_holds_every_message_in_order_with_its_speaker(
        self, api, on, answered, filed
    ):
        thread, _calls = await _conversation(api, answered)
        body = await _filed_body(api, filed, thread)
        said = [
            block
            for text, reply in zip(SAID, REPLIES, strict=True)
            for block in (f"### Person\n\n{text}", f"### Builder\n\n{reply['reply']}")
        ]
        assert [block for block in said if block not in body] == []
        positions = [body.index(block) for block in said]
        assert positions == sorted(positions)

    async def test_the_conversation_comes_before_the_draft(
        self, api, on, answered, filed
    ):
        thread, _calls = await _conversation(api, answered)
        body = await _filed_body(api, filed, thread)
        conversation, draft = body.index("## Conversation"), body.index("## Draft")
        assert conversation < body.index("### Person") < draft
        assert body.rindex("### Builder") < draft

    async def test_the_issue_body_holds_only_the_final_draft_in_a_yaml_block(
        self, api, on, answered, filed
    ):
        thread, _calls = await _conversation(api, answered)
        body = await _filed_body(api, filed, thread)
        assert _yaml_block(body) == TRIPPED.strip()
        assert body.count("```yaml") == 1

    async def test_the_issue_is_labelled_app(self, api, on, answered, filed):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/submit")
        [issue] = filed
        assert issue["labels"] == ["app"]

    async def test_submit_answers_with_the_issue_number_and_url(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered)
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 200
        assert response.json() == ISSUE

    async def test_the_issue_is_kept_on_the_thread(
        self, api, on, answered, filed, sessionmaker_for_test
    ):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/submit")
        assert (await api.get(f"{THREADS}/{thread}")).json()["issue"] == ISSUE
        [row] = await _fresh(sessionmaker_for_test, BuilderThread, BuilderThread.seq)
        assert (row.issue_number, row.issue_url) == (ISSUE["number"], ISSUE["url"])

    async def test_a_second_submit_is_a_409_and_files_nothing_more(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered)
        await api.post(f"{THREADS}/{thread}/submit")
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 409
        assert response.json()["detail"] == FILED_ALREADY
        assert len(filed) == 1

    async def test_github_failing_is_a_502_with_its_message_and_keeps_no_issue(
        self, api, on, answered, github_down
    ):
        thread = await _drafted(api, answered)
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 502
        assert response.json()["detail"] == GITHUB_DOWN
        assert (await api.get(f"{THREADS}/{thread}")).json()["issue"] is None

    async def test_the_builder_off_is_a_409_and_files_nothing(
        self, api, on, answered, filed, turned_off
    ):
        thread = await _drafted(api, answered)
        turned_off()
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 409
        assert response.json()["detail"] == OFF
        assert filed == []

    async def test_a_thread_with_no_draft_yet_is_a_409_and_files_nothing(
        self, api, on, answered, filed
    ):
        answered()
        thread = await _thread(api)
        await _say(api, thread)
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 409
        assert response.json()["detail"] == NO_DRAFT
        assert filed == []

    async def test_an_invalid_draft_is_a_422_with_the_app_error(
        self, api, on, answered, filed
    ):
        thread = await _drafted(api, answered, draft=INVALID)
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 422
        assert response.json()["detail"] == _refusal(INVALID)

    @pytest.mark.parametrize("draft", BAD_DRAFTS)
    async def test_a_bad_draft_is_a_422_and_files_nothing(
        self, api, on, answered, filed, draft
    ):
        thread = await _drafted(api, answered, draft=draft)
        response = await api.post(f"{THREADS}/{thread}/submit")
        assert response.status_code == 422
        assert filed == []


class TestAppYaml:
    async def test_an_apps_yaml_comes_back_as_written_with_the_builder_off(self, api):
        response = await api.get("/api/builder/apps/receipts/yaml")
        assert response.status_code == 200
        written = (apps.APPS_DIR / "receipts" / "app.yaml").read_text()
        assert response.json() == {"yaml": written}

    @pytest.mark.parametrize("name", ["dental_xrays", "..", "%2e%2e%2fprompts.yaml"])
    async def test_an_app_not_here_is_a_404(self, api, name):
        response = await api.get(f"/api/builder/apps/{name}/yaml")
        assert response.status_code == 404
