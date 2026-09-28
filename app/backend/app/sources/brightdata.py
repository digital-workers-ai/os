from app.sources.client import ConnectorError

TRIGGER_PATH = "/datasets/v3/trigger"
POLL_SECONDS = 10
_DEAD_STATUSES = ("failed", "canceled")
_FAILURE_KEYS = ("error", "error_code")


def failed(record) -> bool:
    return isinstance(record, dict) and any(key in record for key in _FAILURE_KEYS)


def _status(body):
    return body.get("status") if isinstance(body, dict) else None


async def _snapshot(api, source, snapshot_id, poll_limit) -> list:
    ready = False
    for _ in range(poll_limit):
        if not ready:
            status = _status(await api.get(f"/datasets/v3/progress/{snapshot_id}"))
            if status in _DEAD_STATUSES:
                raise ConnectorError(source, f"snapshot {snapshot_id} {status}")
            ready = status == "ready"
        if ready:
            records = await api.get(
                f"/datasets/v3/snapshot/{snapshot_id}", params={"format": "json"}
            )
            if isinstance(records, list):
                return records
            if _status(records) is None:
                raise ConnectorError(
                    source,
                    f"snapshot {snapshot_id} answered "
                    f"{type(records).__name__}, not a list of records",
                )
        await api.wait(POLL_SECONDS)
    raise ConnectorError(
        source, f"snapshot {snapshot_id} not ready after {POLL_SECONDS * poll_limit}s"
    )


async def discover(
    api, source, *, dataset_id, discover_by, urls, limit=50, poll_limit=30
) -> list:
    triggered = await api.post(
        TRIGGER_PATH,
        params={
            "dataset_id": dataset_id,
            "type": "discover_new",
            "discover_by": discover_by,
            "format": "json",
            "include_errors": "true",
            "limit_per_input": limit,
        },
        json=[{"url": url} for url in urls],
    )
    snapshot_id = triggered.get("snapshot_id") if isinstance(triggered, dict) else None
    if not snapshot_id:
        raise ConnectorError(source, "trigger answered with no snapshot_id")
    return await _snapshot(api, source, str(snapshot_id), poll_limit)
