from app.engine import competitors
from app.sources import client
from app.sources.util import client_for, store_all

SOURCE = "linkedin_posts"

OBSERVED_AT = {"posts": "date_posted"}

DATASET = "gd_lyy3tktm25m4avu764"

TRIGGER = {
    "dataset_id": DATASET,
    "type": "discover_new",
    "discover_by": "company_url",
    "format": "json",
    "include_errors": "true",
}

MAX_POLLS = 30

POLL_SECONDS = 10


async def _snapshot(api, company_url, notes):
    triggered = await api.post(
        "/datasets/v3/trigger", params=TRIGGER, json=[{"url": company_url}]
    )
    snapshot = triggered["snapshot_id"]
    for poll in range(MAX_POLLS):
        if poll:
            await client._sleep(POLL_SECONDS)
        progress = await api.get(f"/datasets/v3/progress/{snapshot}")
        if progress.get("status") == "ready":
            return await api.get(
                f"/datasets/v3/snapshot/{snapshot}", params={"format": "json"}
            )
        if progress.get("status") == "failed":
            notes["failed_snapshots"] = notes.get("failed_snapshots", 0) + 1
            return []
    notes["unfinished_snapshots"] = notes.get("unfinished_snapshots", 0) + 1
    return []


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for spec in competitors.tracked().values():
        records = await _snapshot(api, str(spec["linkedin_url"]), notes)
        posts = [
            {**post, "_competitor_ref": str(spec["domain"])}
            for post in records
            if isinstance(post, dict)
        ]
        await store_all(
            session,
            store,
            posts,
            source=SOURCE,
            object_type="posts",
            id_fields=("id", "url"),
            notes=notes,
        )
    return notes or None
