import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, mappings, ontology, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.client import ConnectorError
from app.sources.x_posts import connector, extract
from tools.pull_source import key_types

SOURCE = "x_posts"
SNAPSHOT = "sd_mx4k2p7qd9r1t8vw3z"
DATASET_ID = "gd_lwxkxvnf1cynvib9co"
INGESTED = datetime(2026, 9, 27, tzinfo=UTC)
PHOTO = "https://pbs.twimg.com/media/HSgCBVmagAA49ih.jpg"
VIDEO = {
    "video_url": "https://video.twimg.com/amplify_video/2102971355063078912/vid/avc1/1080x1920/MjD_BXQvs0vcyjvu.mp4?tag=29",
    "duration": 40830,
}
MOCK_FIXTURES = checks.REAL_FIXTURES.parent / "mock" / SOURCE
REAL_FIXTURES = checks.REAL_FIXTURES / SOURCE
needs_real_capture = pytest.mark.skipif(
    not REAL_FIXTURES.is_dir(),
    reason=f"no real capture under fixtures/real/{SOURCE}",
)

TRIGGER_PARAMS = {
    "dataset_id": DATASET_ID,
    "type": "discover_new",
    "discover_by": "profile_url",
    "format": "json",
    "include_errors": "true",
    "limit_per_input": "50",
}
PROFILE_URLS = [
    "https://x.com/HubSpot",
    "https://x.com/Zoho",
    "https://x.com/FreshworksInc",
]
RECORD_KEYS = (
    "ai_generated_images",
    "biography",
    "bookmarks",
    "context_added",
    "date_posted",
    "description",
    "discovery_input",
    "external_image_urls",
    "external_url",
    "external_video_urls",
    "followers",
    "following",
    "hashtags",
    "id",
    "input",
    "is_repost",
    "is_verified",
    "likes",
    "name",
    "parent_post_details",
    "photos",
    "posts_count",
    "profile_image_link",
    "quoted_post",
    "quotes",
    "replies",
    "reposts",
    "tagged_users",
    "timestamp",
    "url",
    "user_id",
    "user_posted",
    "verification_type",
    "videos",
    "views",
)
MAPPED = {
    ("_company", "company"),
    ("_platform", "platform"),
    ("description", "name"),
    ("_category", "category"),
    ("date_posted", "posted_at"),
    ("likes", "likes"),
    ("replies", "comments"),
    ("reposts", "shares"),
    ("views", "views"),
    ("_preview", "preview"),
    ("url", "url"),
}


def discovered(handle):
    return {"url": f"https://x.com/{handle}", "start_date": "", "end_date": ""}


def post(**overrides):
    record = {
        "id": "2100955544362058048",
        "url": "https://x.com/hubspot/status/2100955544362058048",
        "user_id": "14458280",
        "user_posted": "HubSpot",
        "name": "HubSpot",
        "description": "Overheard at UNBOUND: what if the CRM updated you?",
        "date_posted": "2026-09-18T13:13:26.000Z",
        "likes": 10,
        "replies": 7,
        "reposts": 3,
        "views": 4011,
        "quotes": 2,
        "bookmarks": 2,
        "followers": 782863,
        "is_repost": False,
        "photos": None,
        "videos": None,
        "discovery_input": discovered("HubSpot"),
    }
    record.update(overrides)
    return record


def dead_page(handle="Freshworks"):
    return {
        "timestamp": "2026-09-27T19:39:15.561Z",
        "input": discovered(handle),
        "error": "No public posts were found in the profile.",
        "error_code": "dead_page",
    }


def progress(status):
    return {"status": status, "snapshot_id": SNAPSHOT, "dataset_id": DATASET_ID}


READY = progress("ready")


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


class TestTheTrigger:
    async def test_the_trigger_carries_the_dataset_params(self, brightdata):
        seen = brightdata()
        await run()
        trigger = seen[0]
        assert trigger.method == "POST"
        assert trigger.url.path == "/datasets/v3/trigger"
        assert dict(trigger.url.params) == TRIGGER_PARAMS

    async def test_the_body_is_the_bare_list_of_profile_urls(self, brightdata):
        seen = brightdata()
        await run()
        assert json.loads(seen[0].content) == [{"url": u} for u in PROFILE_URLS]

    async def test_the_urls_come_from_the_competitors_x_handles(self):
        assert connector.profile_urls() == PROFILE_URLS

    async def test_no_handles_is_a_note_and_no_request(self, brightdata, monkeypatch):
        seen = brightdata()
        doc = spy.load()
        for competitor in doc["competitors"]:
            competitor.pop("x")
        monkeypatch.setattr(spy, "definition", lambda: spy.parse(doc))
        notes, stored = await run()
        assert notes == {"no_x_handles": 1}
        assert seen == []
        assert stored == []

    async def test_the_connector_gives_up_after_thirty_polls(self, brightdata, waits):
        brightdata(progress=(progress("running"),))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} not ready after 300s"
        ):
            await run()
        assert waits == [10] * 30


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
                "source_id": "2100955544362058048",
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
        assert [s["source_id"] for s in stored] == ["2100955544362058048"]

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
    def test_the_company_comes_from_the_discovered_profile(self):
        record = extract.reshape(
            "posts", post(discovery_input=discovered("zoho"), user_posted="someone")
        )[0]
        assert record["_company"] == "Zoho CRM"

    @pytest.mark.parametrize(
        "url", ["https://x.com/Zoho/", "https://x.com/zoho?x=1"], ids=["slash", "query"]
    )
    def test_a_trailing_slash_or_a_query_still_resolves(self, url):
        record = extract.reshape(
            "posts",
            post(discovery_input={"url": url}, user_posted="someone"),
        )[0]
        assert record["_company"] == "Zoho CRM"

    def test_the_discovered_handle_resolves_case_insensitively(self):
        record = extract.reshape(
            "posts",
            post(discovery_input=discovered("HUBSPOT"), user_posted="someone"),
        )[0]
        assert record["_company"] == "HubSpot"

    def test_the_company_falls_back_to_the_posting_handle(self):
        record = extract.reshape(
            "posts",
            post(discovery_input=discovered("nobody"), user_posted="FreshworksInc"),
        )[0]
        assert record["_company"] == "Freshsales"

    def test_the_company_falls_back_to_the_display_name(self):
        record = extract.reshape(
            "posts",
            post(
                discovery_input=discovered("nobody"),
                user_posted="nobody",
                name="Nobody Inc",
            ),
        )[0]
        assert record["_company"] == "Nobody Inc"

    @pytest.mark.parametrize("name", ["  ", None, 7], ids=["blank", "none", "number"])
    def test_no_company_when_nothing_resolves(self, name):
        record = extract.reshape(
            "posts",
            post(discovery_input=discovered("nobody"), user_posted="nobody", name=name),
        )[0]
        assert "_company" not in record

    def test_no_company_when_the_name_is_missing(self):
        payload = post(discovery_input=discovered("nobody"), user_posted="nobody")
        del payload["name"]
        assert "_company" not in extract.reshape("posts", payload)[0]

    @pytest.mark.parametrize(
        "discovery_input", [[], {"url": 5}, "x"], ids=["list", "number_url", "string"]
    )
    def test_a_malformed_discovery_input_is_ignored(self, discovery_input):
        record = extract.reshape(
            "posts", post(discovery_input=discovery_input, user_posted="Zoho")
        )[0]
        assert record["_company"] == "Zoho CRM"

    @pytest.mark.parametrize(
        ("overrides", "category"),
        [
            ({"is_repost": True, "videos": [VIDEO]}, "repost"),
            ({"videos": [VIDEO]}, "video"),
            ({"photos": [PHOTO]}, "image"),
            ({}, "text"),
        ],
        ids=["repost", "video", "image", "text"],
    )
    def test_the_category_is_repost_video_image_or_text(self, overrides, category):
        assert extract.reshape("posts", post(**overrides))[0]["_category"] == category

    def test_empty_media_lists_are_text(self):
        record = extract.reshape("posts", post(videos=[], photos=[]))[0]
        assert record["_category"] == "text"

    def test_the_preview_is_the_first_non_empty_photo(self):
        record = extract.reshape("posts", post(photos=["", PHOTO]))[0]
        assert record["_preview"] == PHOTO

    def test_no_preview_for_a_video_only_post(self):
        record = extract.reshape("posts", post(videos=[VIDEO]))[0]
        assert record["_category"] == "video"
        assert "_preview" not in record

    @pytest.mark.parametrize("photos", ["x", [None, 5]], ids=["string", "junk_list"])
    def test_a_malformed_photos_value_never_raises_and_gives_no_preview(self, photos):
        record = extract.reshape("posts", post(photos=photos))[0]
        assert "_preview" not in record

    def test_the_platform_is_x(self):
        assert extract.reshape("posts", post())[0]["_platform"] == "x"

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
        assert observed == datetime(2026, 9, 18, 13, 13, 26, tzinfo=UTC)


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
            "label": "X Posts",
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
            "preview": "string",
            "shares": "number",
            "views": "number",
        }

    def test_the_source_follows_linkedin_posts_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) > priority.index("linkedin_posts")

    def test_every_mapping_line_reads_the_posts_object(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {(line.path[0], line.label) for line in lines} == MAPPED
        assert {line.object_type for line in lines} == {"posts"}
        assert {line.entity for line in lines} == {"competitor_post"}


def payloads(root):
    return [row["payload"] for row in json.loads((root / "posts.json").read_text())]


class TestTheFixtures:
    def test_every_mock_post_carries_the_thirty_five_documented_keys(self):
        for payload in payloads(MOCK_FIXTURES):
            assert set(payload) == set(RECORD_KEYS)
            assert len(payload) == 35

    @needs_real_capture
    def test_the_real_and_mock_captures_agree_on_the_hook_and_mapped_fields(self):
        real = key_types(payloads(REAL_FIXTURES))
        mock = key_types(payloads(MOCK_FIXTURES))
        for field in (
            "user_posted",
            "name",
            "discovery_input",
            *(path for path, _ in MAPPED),
        ):
            if not field.startswith("_"):
                assert real[field] == mock[field], field
