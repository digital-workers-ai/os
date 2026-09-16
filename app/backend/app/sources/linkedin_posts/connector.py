from app.engine import spy
from app.sources.client import ConnectorError
from app.sources.util import client_for, store_all

SOURCE = "linkedin_posts"

OBSERVED_AT = {"posts": "date_posted"}

DATASET_ID = "gd_lyy3tktm25m4avu764"
POLL_SECONDS = 10
POLL_LIMIT = 30

TRIGGER_PARAMS = {
    "dataset_id": DATASET_ID,
    "type": "discover_new",
    "discover_by": "company_url",
    "format": "json",
    "include_errors": "true",
    "limit_per_input": 50,
}
_DEAD_STATUSES = ("failed", "canceled")
_FAILURE_KEYS = ("error", "error_code")


def company_urls() -> list[str]:
    return [
        f"https://www.linkedin.com/company/{company.linkedin}"
        for company in spy.definition().competitors
        if company.linkedin
    ]


def _status(body):
    return body.get("status") if isinstance(body, dict) else None


def _failed(record) -> bool:
    return isinstance(record, dict) and any(key in record for key in _FAILURE_KEYS)


async def _records(api, snapshot_id: str) -> list:
    ready = False
    for _ in range(POLL_LIMIT):
        if not ready:
            status = _status(await api.get(f"/datasets/v3/progress/{snapshot_id}"))
            if status in _DEAD_STATUSES:
                raise ConnectorError(SOURCE, f"snapshot {snapshot_id} {status}")
            ready = status == "ready"
        if ready:
            records = await api.get(
                f"/datasets/v3/snapshot/{snapshot_id}", params={"format": "json"}
            )
            if isinstance(records, list):
                return records
            if _status(records) is None:
                raise ConnectorError(
                    SOURCE,
                    f"snapshot {snapshot_id} answered "
                    f"{type(records).__name__}, not a list of records",
                )
        await api.wait(POLL_SECONDS)
    raise ConnectorError(
        SOURCE,
        f"snapshot {snapshot_id} not ready after {POLL_SECONDS * POLL_LIMIT}s",
    )


async def pull(session, store):
    api = client_for(SOURCE)
    urls = company_urls()
    if not urls:
        return {"no_linkedin_handles": 1}
    triggered = await api.post(
        "/datasets/v3/trigger",
        params=TRIGGER_PARAMS,
        json=[{"url": url} for url in urls],
    )
    snapshot_id = triggered.get("snapshot_id") if isinstance(triggered, dict) else None
    if not snapshot_id:
        raise ConnectorError(SOURCE, "trigger answered with no snapshot_id")
    notes: dict = {}
    posts = []
    for record in await _records(api, str(snapshot_id)):
        if _failed(record):
            notes["dead_pages"] = notes.get("dead_pages", 0) + 1
            continue
        posts.append(record)
    await store_all(
        session, store, posts, source=SOURCE, object_type="posts", notes=notes
    )
    return notes or None
