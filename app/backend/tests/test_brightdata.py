import json

import httpx
import pytest

from app.sources import client
from app.sources.brightdata import discover, failed
from app.sources.client import ConnectorError
from app.sources.util import client_for

SOURCE = "any_source"
DATASET_ID = "gd_test0000000000000"
SNAPSHOT = "sd_test"
URLS = ["https://x.com/HubSpot", "https://x.com/Zoho"]
RECORDS = [{"id": "1"}, {"id": "2"}]
DEAD_PAGE = {"error": "4XX page - dead page.", "error_code": "dead_page"}
TRIGGER_PARAMS = {
    "dataset_id": DATASET_ID,
    "type": "discover_new",
    "discover_by": "profile_url",
    "format": "json",
    "include_errors": "true",
    "limit_per_input": "50",
}


def progress(status):
    return {"status": status, "snapshot_id": SNAPSHOT, "dataset_id": DATASET_ID}


READY = progress("ready")
NOT_READY = httpx.Response(
    202,
    json={
        "status": "running",
        "message": "Snapshot is not ready yet, try again in 30s",
    },
)


def _next(queue):
    return queue.pop(0) if len(queue) > 1 else queue[0]


def _response(body):
    return body if isinstance(body, httpx.Response) else httpx.Response(200, json=body)


@pytest.fixture
def waits(monkeypatch):
    seen = []

    async def record(seconds):
        seen.append(seconds)

    monkeypatch.setattr(client, "_sleep", record)
    return seen


@pytest.fixture
def brightdata(monkeypatch, waits):
    def _install(*, trigger=None, progress=None, snapshot=None):
        seen = []
        progress_queue = list(progress or [READY])
        snapshot_queue = list(snapshot or [RECORDS])

        def handler(request):
            seen.append(request)
            if request.url.path == "/datasets/v3/trigger":
                body = {"snapshot_id": SNAPSHOT} if trigger is None else trigger
                return _response(body)
            if request.url.path.startswith("/datasets/v3/progress/"):
                return _response(_next(progress_queue))
            return _response(_next(snapshot_queue))

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        return seen

    yield _install
    monkeypatch.setattr(client, "_transport", None)


async def run(**overrides):
    return await discover(
        client_for("linkedin_posts"),
        SOURCE,
        dataset_id=DATASET_ID,
        discover_by="profile_url",
        urls=URLS,
        **overrides,
    )


def _paths(seen):
    return [f"{r.method} {r.url.path}" for r in seen]


class TestTheTrigger:
    async def test_the_trigger_carries_the_dataset_params(self, brightdata):
        seen = brightdata()
        await run()
        trigger = seen[0]
        assert trigger.method == "POST"
        assert trigger.url.path == "/datasets/v3/trigger"
        assert dict(trigger.url.params) == TRIGGER_PARAMS

    async def test_the_limit_becomes_limit_per_input(self, brightdata):
        seen = brightdata()
        await run(limit=20)
        assert dict(seen[0].url.params)["limit_per_input"] == "20"

    async def test_the_body_is_the_bare_list_of_urls(self, brightdata):
        seen = brightdata()
        await run()
        assert json.loads(seen[0].content) == [{"url": u} for u in URLS]

    async def test_a_trigger_without_a_snapshot_id_is_refused(self, brightdata):
        brightdata(trigger={"error": "Invalid input provided"})
        with pytest.raises(
            ConnectorError, match=rf"\[{SOURCE}\] trigger answered with no snapshot_id"
        ):
            await run()

    async def test_a_trigger_that_is_not_a_mapping_is_refused(self, brightdata):
        brightdata(trigger=[])
        with pytest.raises(
            ConnectorError, match=rf"\[{SOURCE}\] trigger answered with no snapshot_id"
        ):
            await run()


class TestPolling:
    async def test_starting_and_running_wait_and_ready_stops(self, brightdata, waits):
        seen = brightdata(
            progress=(progress("starting"), progress("running"), progress("ready"))
        )
        await run()
        assert waits == [10, 10]
        assert _paths(seen) == [
            "POST /datasets/v3/trigger",
            f"GET /datasets/v3/progress/{SNAPSHOT}",
            f"GET /datasets/v3/progress/{SNAPSHOT}",
            f"GET /datasets/v3/progress/{SNAPSHOT}",
            f"GET /datasets/v3/snapshot/{SNAPSHOT}",
        ]

    async def test_ready_at_once_never_waits(self, brightdata, waits):
        seen = brightdata()
        await run()
        assert waits == []
        assert seen[-1].url.path == f"/datasets/v3/snapshot/{SNAPSHOT}"
        assert dict(seen[-1].url.params) == {"format": "json"}

    async def test_a_progress_body_without_a_status_is_not_ready(
        self, brightdata, waits
    ):
        brightdata(progress=([], progress("ready")))
        await run()
        assert waits == [10]

    async def test_an_unknown_status_is_not_ready(self, brightdata, waits):
        brightdata(progress=(progress("queued"), progress("ready")))
        await run()
        assert waits == [10]

    @pytest.mark.parametrize("status", ["failed", "canceled"])
    async def test_a_dead_snapshot_names_itself_and_its_status(
        self, brightdata, status
    ):
        brightdata(progress=(progress(status),))
        with pytest.raises(ConnectorError, match=f"snapshot {SNAPSHOT} {status}"):
            await run()

    async def test_thirty_polls_without_ready_give_up_by_default(
        self, brightdata, waits
    ):
        seen = brightdata(progress=(progress("running"),))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} not ready after 300s"
        ):
            await run()
        assert waits == [10] * 30
        assert len(seen) == 31

    async def test_the_poll_limit_bounds_the_wait(self, brightdata, waits):
        seen = brightdata(progress=(progress("running"),))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} not ready after 50s"
        ):
            await run(poll_limit=5)
        assert waits == [10] * 5
        assert len(seen) == 6

    async def test_the_not_ready_snapshot_body_is_retried(self, brightdata, waits):
        seen = brightdata(snapshot=(NOT_READY, RECORDS))
        records = await run()
        assert waits == [10]
        assert _paths(seen)[-3:] == [
            f"GET /datasets/v3/progress/{SNAPSHOT}",
            f"GET /datasets/v3/snapshot/{SNAPSHOT}",
            f"GET /datasets/v3/snapshot/{SNAPSHOT}",
        ]
        assert records == RECORDS

    async def test_the_not_ready_body_counts_against_the_same_limit(
        self, brightdata, waits
    ):
        brightdata(snapshot=(NOT_READY,))
        with pytest.raises(ConnectorError, match="not ready after 300s"):
            await run()
        assert waits == [10] * 30

    async def test_a_snapshot_that_is_not_a_list_is_refused(self, brightdata):
        brightdata(snapshot=({"records": []},))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} answered dict, not a list"
        ):
            await run()

    async def test_a_ready_snapshot_is_returned_verbatim_errors_included(
        self, brightdata
    ):
        brightdata(snapshot=([DEAD_PAGE, *RECORDS],))
        assert await run() == [DEAD_PAGE, *RECORDS]


class TestFailed:
    @pytest.mark.parametrize("record", [{"error": "x"}, {"error_code": "dead_page"}])
    def test_an_error_or_error_code_key_marks_a_failure(self, record):
        assert failed(record) is True

    @pytest.mark.parametrize("record", [{"id": "1"}, "junk", None])
    def test_anything_else_is_not_a_failure(self, record):
        assert failed(record) is False
