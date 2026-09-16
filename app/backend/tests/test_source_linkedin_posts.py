import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, mappings, ontology, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.client import ConnectorError
from app.sources.linkedin_posts import connector, extract
from tools.pull_source import key_types

SOURCE = "linkedin_posts"
SNAPSHOT = "sd_mu3j5zf4i64vu5aoj"
DATASET_ID = "gd_lyy3tktm25m4avu764"
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
MOCK_FIXTURES = checks.REAL_FIXTURES.parent / "mock" / SOURCE
REAL_FIXTURES = checks.REAL_FIXTURES / SOURCE

TRIGGER_PARAMS = {
    "dataset_id": DATASET_ID,
    "type": "discover_new",
    "discover_by": "company_url",
    "format": "json",
    "include_errors": "true",
    "limit_per_input": "50",
}
COMPANY_URLS = [
    "https://www.linkedin.com/company/hubspot",
    "https://www.linkedin.com/company/zoho",
    "https://www.linkedin.com/company/freshworks-inc",
]
RECORD_KEYS = (
    "url",
    "id",
    "user_id",
    "use_url",
    "title",
    "headline",
    "post_text",
    "date_posted",
    "hashtags",
    "embedded_links",
    "images",
    "videos",
    "num_likes",
    "num_comments",
    "more_articles_by_user",
    "more_relevant_posts",
    "top_visible_comments",
    "user_followers",
    "user_posts",
    "user_articles",
    "post_type",
    "account_type",
    "post_text_html",
    "repost",
    "tagged_companies",
    "tagged_people",
    "user_title",
    "author_profile_pic",
    "num_connections",
    "video_duration",
    "external_link_data",
    "video_thumbnail",
    "document_cover_image",
    "document_page_count",
    "user_profile_pic",
    "user_name",
    "original_post_text",
    "timestamp",
    "input",
    "discovery_input",
)
MAPPED = {
    ("_company", "company"),
    ("_platform", "platform"),
    ("post_text", "name"),
    ("post_type", "category"),
    ("date_posted", "posted_at"),
    ("num_likes", "likes"),
    ("num_comments", "comments"),
    ("url", "url"),
}


def post(**overrides):
    record = {
        "url": "https://www.linkedin.com/posts/hubspot_x-activity-7503504518433878017-WAjk",
        "id": "7503504518433878017",
        "user_id": "hubspot",
        "use_url": "https://www.linkedin.com/company/hubspot?trk=public_post_feed-actor-image",
        "title": "Fantasy football is actually just pipeline management | HubSpot",
        "post_text": "Fantasy football is actually just pipeline management",
        "date_posted": "2026-09-09T17:28:05.539Z",
        "num_likes": 454,
        "num_comments": 26,
        "post_type": "post",
    }
    record.update(overrides)
    return record


def dead_page(slug="zq-no-such-company"):
    return {
        "timestamp": "2026-09-16T03:21:49.135Z",
        "input": {"url": f"https://www.linkedin.com/company/{slug}"},
        "error": "4XX page - dead page.",
        "error_code": "dead_page",
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
        snapshot_queue = list(snapshot or [[post()]])

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


async def run():
    stored = []

    async def store(session, **kwargs):
        stored.append(kwargs)

    notes = await registry.get(SOURCE).pull(None, store)
    return notes, stored


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

    async def test_the_body_is_the_bare_list_of_company_urls(self, brightdata):
        seen = brightdata()
        await run()
        assert json.loads(seen[0].content) == [{"url": u} for u in COMPANY_URLS]

    async def test_the_urls_come_from_the_competitors_linkedin_handles(self):
        assert connector.company_urls() == COMPANY_URLS

    async def test_no_handles_is_a_note_and_no_request(self, brightdata, monkeypatch):
        seen = brightdata()
        doc = spy.load()
        for competitor in doc["competitors"]:
            competitor.pop("linkedin")
        monkeypatch.setattr(spy, "definition", lambda: spy.parse(doc))
        notes, stored = await run()
        assert notes == {"no_linkedin_handles": 1}
        assert seen == []
        assert stored == []

    async def test_a_trigger_without_a_snapshot_id_is_refused(self, brightdata):
        brightdata(trigger={"error": "Invalid input provided"})
        with pytest.raises(ConnectorError, match="no snapshot_id"):
            await run()

    async def test_a_trigger_that_is_not_a_mapping_is_refused(self, brightdata):
        brightdata(trigger=[])
        with pytest.raises(ConnectorError, match="no snapshot_id"):
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

    async def test_thirty_polls_without_ready_give_up(self, brightdata, waits):
        seen = brightdata(progress=(progress("running"),))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} not ready after 300s"
        ):
            await run()
        assert waits == [10] * 30
        assert len(seen) == 31

    async def test_the_not_ready_snapshot_body_is_retried(self, brightdata, waits):
        seen = brightdata(snapshot=(NOT_READY, [post()]))
        _notes, stored = await run()
        assert waits == [10]
        assert _paths(seen)[-3:] == [
            f"GET /datasets/v3/progress/{SNAPSHOT}",
            f"GET /datasets/v3/snapshot/{SNAPSHOT}",
            f"GET /datasets/v3/snapshot/{SNAPSHOT}",
        ]
        assert len(stored) == 1

    async def test_the_not_ready_body_counts_against_the_same_limit(
        self, brightdata, waits
    ):
        brightdata(snapshot=(NOT_READY,))
        with pytest.raises(ConnectorError, match="not ready after 300s"):
            await run()
        assert waits == [10] * 30

    async def test_a_snapshot_that_is_not_a_list_is_refused(self, brightdata):
        brightdata(snapshot=({"records": []},))
        with pytest.raises(ConnectorError, match=f"snapshot {SNAPSHOT}.*not a list"):
            await run()


class TestRecords:
    async def test_posts_are_stored_verbatim_under_posts_with_the_record_id(
        self, brightdata
    ):
        brightdata(snapshot=([post()],))
        _notes, stored = await run()
        assert stored == [
            {
                "source": SOURCE,
                "object_type": "posts",
                "source_id": "7503504518433878017",
                "raw_payload": post(),
            }
        ]

    async def test_a_clean_pull_returns_no_notes(self, brightdata):
        notes, _stored = await run()
        assert notes is None

    async def test_error_records_are_skipped_and_counted(self, brightdata):
        brightdata(snapshot=([dead_page(), post(), dead_page("other")],))
        notes, stored = await run()
        assert notes == {"dead_pages": 2}
        assert [s["source_id"] for s in stored] == ["7503504518433878017"]

    async def test_an_error_code_alone_marks_a_dead_page(self, brightdata):
        brightdata(snapshot=([{"error_code": "dead_page", "id": "1"}],))
        notes, stored = await run()
        assert notes == {"dead_pages": 1}
        assert stored == []

    async def test_a_record_without_an_id_is_noted(self, brightdata):
        brightdata(snapshot=([post(id=None), post(id="  ")],))
        notes, stored = await run()
        assert notes == {"missing_id": 2}
        assert stored == []

    async def test_a_record_that_is_not_a_mapping_is_a_missing_id(self, brightdata):
        brightdata(snapshot=(["junk", post()],))
        notes, stored = await run()
        assert notes == {"missing_id": 1}
        assert len(stored) == 1


class TestTheHook:
    def test_the_company_comes_from_the_handle(self):
        record = extract.reshape("posts", post(user_id="zoho"))[0]
        assert record["_company"] == "Zoho CRM"

    def test_the_company_falls_back_to_use_url_with_its_query(self):
        record = extract.reshape(
            "posts",
            post(
                user_id="someone-else",
                use_url="https://www.linkedin.com/company/freshworks-inc?trk=public_post_feed-actor-image",
            ),
        )[0]
        assert record["_company"] == "Freshsales"

    def test_the_company_falls_back_to_use_url_when_the_handle_is_absent(self):
        payload = post(use_url="https://www.linkedin.com/company/zoho/")
        del payload["user_id"]
        assert extract.reshape("posts", payload)[0]["_company"] == "Zoho CRM"

    def test_the_company_falls_back_to_the_title(self):
        record = extract.reshape(
            "posts",
            post(
                user_id="nobody",
                use_url="https://www.linkedin.com/company/nobody",
                title="Nobody Inc",
            ),
        )[0]
        assert record["_company"] == "Nobody Inc"

    def test_no_company_when_nothing_resolves(self):
        record = extract.reshape(
            "posts", post(user_id="nobody", use_url=None, title=None)
        )[0]
        assert "_company" not in record

    def test_a_blank_title_does_not_resolve(self):
        record = extract.reshape(
            "posts", post(user_id="nobody", use_url="https://x.test/", title="  ")
        )[0]
        assert "_company" not in record

    def test_a_malformed_shape_never_raises(self):
        record = extract.reshape(
            "posts", post(user_id=["hubspot"], use_url=7, title={"x": 1})
        )[0]
        assert "_company" not in record
        assert record["_platform"] == "linkedin"

    def test_the_platform_is_linkedin(self):
        assert extract.reshape("posts", post())[0]["_platform"] == "linkedin"

    def test_the_payload_is_kept_verbatim(self):
        record = extract.reshape("posts", post())[0]
        assert {k: v for k, v in record.items() if not k.startswith("_")} == post()

    def test_other_object_types_pass_through(self):
        assert extract.reshape("other", {"a": 1}) == [{"a": 1}]

    def test_the_hook_is_discovered(self):
        from app.sources import hooks

        assert hooks.hooks()[SOURCE] is extract.reshape


class TestObservedAt:
    def test_the_connector_observes_the_posting_time(self):
        assert registry.get(SOURCE).OBSERVED_AT == {"posts": "date_posted"}

    def test_a_post_dates_itself_from_the_provider(self):
        observed, which = observed_at_for(
            registry.get(SOURCE), "posts", post(), INGESTED
        )
        assert which == "provider"
        assert observed == datetime(2026, 9, 9, 17, 28, 5, tzinfo=UTC)


class TestCredentialsAndCatalog:
    def test_the_stand_in_is_the_brightdata_prefix(self):
        found = creds.credentials_for(SOURCE)
        assert found.base_url == f"{settings.MOCK_BASE_URL}/brightdata"
        assert found.headers == {"Authorization": "Bearer mock_brightdata_key"}
        assert found.real is False

    def test_the_key_becomes_a_bearer_on_the_real_api(self, monkeypatch):
        monkeypatch.setenv("BRIGHTDATA_API_KEY", "bd-test-0000")
        found = creds.credentials_for(SOURCE)
        assert found.base_url == "https://api.brightdata.com"
        assert found.headers == {"Authorization": "Bearer bd-test-0000"}
        assert found.real is True

    def test_the_catalog_files_it_under_spy(self):
        assert catalog.entry(SOURCE) == {
            "source": SOURCE,
            "label": "LinkedIn Company Posts",
            "category": "Spy",
            "unlocks": "Competitor posts, engagement",
        }


class TestTheDefinitions:
    def test_the_competitor_post_entity_is_declared(self):
        spec = ontology.load().entities["competitor_post"]
        assert spec.attrs == {
            "company": "string",
            "platform": "string",
            "name": "string",
            "category": "string",
            "posted_at": "date",
            "likes": "number",
            "comments": "number",
            "url": "string",
        }

    def test_the_source_follows_google_sheets_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) > priority.index("google_sheets")

    def test_every_mapping_line_reads_the_posts_object(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {(line.path[0], line.label) for line in lines} == MAPPED
        assert {line.object_type for line in lines} == {"posts"}
        assert {line.entity for line in lines} == {"competitor_post"}


def payloads(root):
    return [row["payload"] for row in json.loads((root / "posts.json").read_text())]


class TestTheFixtures:
    def test_every_mock_post_carries_the_forty_keys_in_the_real_order(self):
        for payload in payloads(MOCK_FIXTURES):
            assert tuple(payload) == RECORD_KEYS

    def test_the_real_capture_covers_two_companies_in_three_posts_at_most(self):
        real = payloads(REAL_FIXTURES)
        assert 2 <= len(real) <= 3
        assert len({p["user_id"] for p in real}) >= 2

    def test_the_real_and_mock_captures_agree_on_the_hook_and_mapped_fields(self):
        real = key_types(payloads(REAL_FIXTURES))
        mock = key_types(payloads(MOCK_FIXTURES))
        for field in ("user_id", "use_url", "title", *(path for path, _ in MAPPED)):
            if not field.startswith("_"):
                assert real[field] == mock[field], field
