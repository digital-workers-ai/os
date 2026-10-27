from collections import defaultdict

from sqlalchemy import select

from app import clock
from app.builder import chat, github
from app.engine import apps
from app.models import BuilderQuestion, BuilderSuggestion, BuilderThread, BuilderTurn

NO_DRAFT = "there is no draft yet"
FILED = "this thread was filed as issue #{number}"


def _latest_draft():
    return (
        select(BuilderTurn.draft)
        .where(
            BuilderTurn.thread_id == BuilderThread.id, BuilderTurn.draft.is_not(None)
        )
        .order_by(BuilderTurn.seq.desc())
        .limit(1)
        .scalar_subquery()
    )


def _issue(thread) -> dict | None:
    if thread.issue_number is None:
        return None
    return {"number": thread.issue_number, "url": thread.issue_url}


def _row(thread, draft) -> dict:
    return {
        "id": str(thread.id),
        "app": thread.app,
        "title": chat.title(draft),
        "created_at": thread.created_at.isoformat(),
        "issue": _issue(thread),
    }


def _turn_row(turn, questions, suggestions) -> dict:
    return {
        "role": turn.role,
        "text": turn.text,
        "questions": questions,
        "suggestions": suggestions,
        "draft": turn.draft,
        "problems": chat.problems(turn.draft),
    }


def _suggestion_row(suggestion) -> dict:
    return {
        "app": suggestion.app,
        "title": suggestion.title,
        "reason": suggestion.reason,
    }


async def _per_turn(session, model, thread_id, shape) -> defaultdict:
    found = defaultdict(list)
    rows = await session.execute(
        select(model)
        .join(BuilderTurn, BuilderTurn.seq == model.turn_seq)
        .where(BuilderTurn.thread_id == thread_id)
        .order_by(model.seq)
    )
    for row in rows.scalars():
        found[row.turn_seq].append(shape(row))
    return found


async def _turns(session, thread_id) -> list[dict]:
    found = await session.execute(
        select(BuilderTurn)
        .where(BuilderTurn.thread_id == thread_id)
        .order_by(BuilderTurn.seq)
    )
    turns = found.scalars().all()
    asked = await _per_turn(session, BuilderQuestion, thread_id, lambda row: row.text)
    offered = await _per_turn(session, BuilderSuggestion, thread_id, _suggestion_row)
    return [_turn_row(turn, asked[turn.seq], offered[turn.seq]) for turn in turns]


async def _found(session, thread_id) -> tuple[BuilderThread, str | None]:
    found = await session.execute(
        select(BuilderThread, _latest_draft()).where(BuilderThread.id == thread_id)
    )
    row = found.first()
    if row is None:
        raise chat.Missing(f"no thread {thread_id}")
    return tuple(row)


async def _opened(session, thread_id) -> tuple[BuilderThread, str | None]:
    chat.ensure_on()
    return await _found(session, thread_id)


def _unfiled(thread) -> None:
    if thread.issue_number is not None:
        raise chat.BuilderError(FILED.format(number=thread.issue_number))


def _needed(draft) -> str:
    if draft is None:
        raise chat.BuilderError(NO_DRAFT)
    return draft


async def create(session, app=None) -> dict:
    chat.ensure_on()
    if app is not None:
        chat.app_yaml(app)
    thread = BuilderThread(app=app, created_at=clock.now())
    session.add(thread)
    await session.flush()
    return {**_row(thread, None), "turns": []}


async def threads(session) -> list[dict]:
    found = await session.execute(
        select(BuilderThread, _latest_draft()).order_by(BuilderThread.seq.desc())
    )
    return [_row(thread, draft) for thread, draft in found.all()]


async def thread(session, thread_id) -> dict:
    found, draft = await _found(session, thread_id)
    return {**_row(found, draft), "turns": await _turns(session, thread_id)}


async def _store(session, thread_id, role, text, draft=None) -> BuilderTurn:
    turn = BuilderTurn(
        thread_id=thread_id, role=role, text=text, draft=draft, created_at=clock.now()
    )
    session.add(turn)
    await session.flush()
    return turn


async def say(session, thread_id, text) -> dict:
    found, _draft = await _opened(session, thread_id)
    _unfiled(found)
    said = [*await _turns(session, thread_id), {"role": chat.PERSON, "text": text}]
    answer = await chat.turn(said, changing=found.app)
    person = await _store(session, thread_id, chat.PERSON, text)
    builder = await _store(
        session, thread_id, chat.BUILDER, answer["reply"], answer["draft"]
    )
    session.add_all(
        BuilderQuestion(turn_seq=builder.seq, text=question)
        for question in answer["questions"]
    )
    session.add_all(
        BuilderSuggestion(turn_seq=builder.seq, **suggestion)
        for suggestion in answer["suggestions"]
    )
    await session.flush()
    return {
        "turn": _turn_row(person, [], []),
        "reply": _turn_row(builder, answer["questions"], answer["suggestions"]),
    }


async def drafted(session, thread_id) -> apps.App:
    _thread, draft = await _opened(session, thread_id)
    return chat.parse_draft(_needed(draft))


async def file(session, thread_id) -> dict:
    found, draft = await _opened(session, thread_id)
    _unfiled(found)
    draft = _needed(draft)
    title, body = chat.issue(
        chat.parse_draft(draft), await _turns(session, thread_id), draft, found.app
    )
    filed = await github.file_issue(title, body)
    found.issue_number, found.issue_url = filed["number"], filed["url"]
    await session.flush()
    return filed
