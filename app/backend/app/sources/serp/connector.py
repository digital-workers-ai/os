from app.engine import competitors
from app.sources.serp.extract import domain_of
from app.sources.util import client_for, store_all

SOURCE = "serp"

OBSERVED_AT = {"organic_results": "_checked_on"}

ENGINE = "google"

LOCATION = "United States"

TRACKED_POSITIONS = 10


def _readings(page: dict) -> list[dict]:
    parameters = page.get("search_parameters") or {}
    metadata = page.get("search_metadata") or {}
    stamp = {
        "_keyword": parameters.get("q"),
        "_engine": parameters.get("engine"),
        "_checked_on": str(metadata.get("created_at") or "")[:10],
    }
    return [
        {**result, **stamp, "_domain": domain_of(result.get("link"))}
        for result in page.get("organic_results") or []
    ]


def _row_id(record: dict) -> str | None:
    parts = [
        record.get(key) for key in ("_keyword", "_engine", "_domain", "_checked_on")
    ]
    return "|".join(str(part) for part in parts) if all(parts) else None


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for keyword in competitors.definitions()["keywords"]:
        page = await api.get(
            "/search",
            params={
                "engine": ENGINE,
                "q": keyword,
                "location": LOCATION,
                "num": TRACKED_POSITIONS,
            },
        )
        await store_all(
            session,
            store,
            _readings(page),
            source=SOURCE,
            object_type="organic_results",
            id_of=_row_id,
            notes=notes,
        )
    return notes or None
