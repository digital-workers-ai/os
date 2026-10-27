import asyncio
import copy
import importlib

from sqlalchemy import String, cast, select
from sqlalchemy.orm import aliased

from app.models import CustomRecord, FactCurrent, RawEvent

SOURCE = "custom"
SCRIPT_SECONDS = 5


class ScriptError(RuntimeError):
    pass


def module_for(app):
    return importlib.import_module(f"app.custom.apps.{app.name}.script")


def _merged(fields, record: dict, answer: dict) -> dict:
    merged = dict(record)
    for field in fields:
        if field.by_script:
            merged[field.name] = answer.get(field.name)
        elif field.type == "list":
            answered = answer.get(field.name) or []
            merged[field.name] = [
                _merged(
                    field.fields, row, answered[index] if index < len(answered) else {}
                )
                for index, row in enumerate(record.get(field.name) or [])
            ]
    return merged


async def run(app, record: dict, ctx) -> dict:
    fill = module_for(app).fill
    failed = f"{app.name}/script.py"
    try:
        answer = await asyncio.wait_for(
            fill(copy.deepcopy(record), ctx), SCRIPT_SECONDS
        )
    except TimeoutError as exc:
        raise ScriptError(
            f"{failed}: timed out after {SCRIPT_SECONDS} seconds"
        ) from exc
    except Exception as exc:
        raise ScriptError(f"{failed}: {type(exc).__name__}: {exc}") from exc
    if not isinstance(answer, dict):
        raise ScriptError(
            f"{failed}: fill returned {type(answer).__name__}, not a record"
        )
    return _merged(app.fields, record, answer)


class Context:
    def __init__(self, session, app, record_id=None):
        self.session = session
        self.app = app
        self.record_id = record_id

    async def previous(self, where: dict) -> dict | None:
        newest = (
            select(RawEvent.raw_payload, CustomRecord.saved_at)
            .join(CustomRecord, RawEvent.source_id == cast(CustomRecord.id, String))
            .where(
                RawEvent.source == SOURCE,
                RawEvent.object_type == self.app.name,
                CustomRecord.app == self.app.name,
                CustomRecord.saved_at.is_not(None),
                CustomRecord.removed_at.is_(None),
                CustomRecord.id != self.record_id,
            )
            .distinct(RawEvent.source_id)
            .order_by(RawEvent.source_id, RawEvent.seq.desc())
            .subquery()
        )
        fields = newest.c.raw_payload["fields"]
        found = await self.session.execute(
            select(fields)
            .where(fields.contains(where))
            .order_by(newest.c.saved_at.desc())
            .limit(1)
        )
        return found.scalar_one_or_none()

    async def entity(self, entity_type, by, value, attr):
        match = aliased(FactCurrent)
        found = await self.session.execute(
            select(FactCurrent.value)
            .join(match, match.canonical_id == FactCurrent.canonical_id)
            .where(
                match.entity_type == entity_type,
                match.attr == by,
                match.value == str(value),
                FactCurrent.attr == attr,
            )
            .limit(1)
        )
        return found.scalar_one_or_none()
