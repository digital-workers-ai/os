from app.engine import competitors
from app.sources.util import client_for, store_all

SOURCE = "ai_answers"

OBSERVED_AT = {"mentions": "_checked_on"}


def _rows(reading: dict) -> list[dict]:
    stamp = {
        "_prompt": reading.get("prompt"),
        "_engine": reading.get("engine"),
        "_checked_on": str(reading.get("checked_at") or "")[:10],
    }
    return [{**mention, **stamp} for mention in reading.get("mentions") or []]


def _row_id(record: dict) -> str | None:
    parts = [record.get(key) for key in ("_prompt", "_engine", "brand", "_checked_on")]
    return "|".join(str(part) for part in parts) if all(parts) else None


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    definitions = competitors.definitions()
    for prompt in definitions["prompts"]:
        for engine in definitions["engines"]:
            reading = await api.get(
                "/v1/mentions", params={"prompt": prompt, "engine": engine}
            )
            await store_all(
                session,
                store,
                _rows(reading),
                source=SOURCE,
                object_type="mentions",
                id_of=_row_id,
                notes=notes,
            )
    return notes or None
