from app.sources.client import SourceClient
from app.sources.creds import credentials_for


def client_for(source: str) -> SourceClient:
    creds = credentials_for(source)
    return SourceClient(source, creds.base_url, headers=creds.headers)


def pick_id(record: dict, *fields: str) -> str | None:
    if not isinstance(record, dict):
        return None
    for f in fields:
        v = record.get(f)
        if v is not None and str(v).strip():
            return str(v)
    return None


async def store_all(
    session,
    store,
    records,
    *,
    source: str,
    object_type: str,
    id_fields: tuple = ("id",),
    id_of=None,
    notes: dict | None = None,
) -> dict:
    notes = notes if notes is not None else {}
    for r in records:
        rid = id_of(r) if id_of else pick_id(r, *id_fields)
        rid = str(rid) if rid is not None and str(rid).strip() else None
        if rid is None:
            notes["missing_id"] = notes.get("missing_id", 0) + 1
            continue
        await store(
            session,
            source=source,
            object_type=object_type,
            source_id=rid,
            raw_payload=r,
        )
    return notes
