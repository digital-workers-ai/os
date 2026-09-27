import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, mappings, ontology, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, registry
from app.sources.client import ConnectorError
from app.sources.tiktok_posts import connector, extract
from tools.pull_source import key_types

SOURCE = "tiktok_posts"
SNAPSHOT = "sd_tk7m3x9qp2wv5rz1nb4"
DATASET_ID = "gd_lu702nij2f790tmv9h"
INGESTED = datetime(2026, 9, 27, tzinfo=UTC)
PREVIEW = "https://p16-common-sign.tiktokcdn-us.com/tos-useast5-p-85c255-tx/ooDy6q1Bul2EwfFB9QQDWGESXugfu9oGjMgI4D~tplv-tiktokx-origin.image?dr=9636&x-expires=1790708400&x-signature=8OBL0JDuIZSKZCTdgZp8Hzz0pAE%3D&t=4d5b0474&ps=13740610&shp=81f88b70&shcp=43f4a2f9&idc=useast5"
VIDEO = "https://v16-webapp-prime.us.tiktok.com/video/tos/useast5/tos-useast5-v-85c255-tx/oUXq7l2LCET0QBpCgIiXgXSBefZoyc1iDwB6DE/?a=1988&bti=ODszNWYuMDE6&&bt=1775&mime_type=video_mp4"
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
    "https://www.tiktok.com/@hubspot",
    "https://www.tiktok.com/@freshworksinc",
]
RECORD_KEYS = (
    "account_id",
    "carousel_images",
    "cdn_link",
    "cdn_url",
    "collect_count",
    "comment_count",
    "comments",
    "commerce_info",
    "create_time",
    "description",
    "digg_count",
    "discovery_input",
    "hashtags",
    "input",
    "is_verified",
    "music",
    "num_share_count",
    "offical_item",
    "original_item",
    "original_sound",
    "play_count",
    "post_id",
    "post_type",
    "preview_image",
    "profile_avatar",
    "profile_biography",
    "profile_followers",
    "profile_id",
    "profile_url",
    "profile_username",
    "ratio",
    "region",
    "secu_id",
    "share_count",
    "shortcode",
    "subtitle_format",
    "subtitle_info",
    "subtitle_url",
    "tagged_user",
    "timestamp",
    "tt_chain_token",
    "url",
    "video_duration",
    "video_url",
    "width",
)
MAPPED = {
    ("_company", "company"),
    ("_platform", "platform"),
    ("description", "name"),
    ("post_type", "category"),
    ("create_time", "posted_at"),
    ("digg_count", "likes"),
    ("comment_count", "comments"),
    ("num_share_count", "shares"),
    ("play_count", "views"),
    ("_preview", "preview"),
    ("url", "url"),
}


def discovered(handle):
    return {
        "url": f"https://www.tiktok.com/@{handle}",
        "start_date": "",
        "end_date": "",
        "what_to_collect": "",
        "post_type": "",
        "country": "",
        "sort_by": "",
    }


def post(**overrides):
    record = {
        "post_id": "7675081150406216973",
        "shortcode": "7675081150406216973",
        "url": "https://www.tiktok.com/@hubspot/video/7675081150406216973",
        "account_id": "hubspot",
        "profile_id": "6921028957732193285",
        "profile_username": "HubSpot",
        "profile_url": "https://www.tiktok.com/@hubspot",
        "profile_followers": 43400,
        "description": "creating pipeline from the pickup line",
        "create_time": "2026-08-17T19:15:05.000Z",
        "post_type": "video",
        "digg_count": 22,
        "comment_count": 2,
        "collect_count": 2,
        "play_count": 1798,
        "num_share_count": 1,
        "share_count": "1",
        "is_verified": True,
        "region": "US",
        "preview_image": PREVIEW,
        "video_url": VIDEO,
        "video_duration": 10,
        "discovery_input": discovered("hubspot"),
        "input": {
            "url": "https://www.tiktok.com/@hubspot/video/7675081150406216973",
            "discovery_input": None,
        },
    }
    record.update(overrides)
    return record


def dead_page(handle="zoho", error="There are no public posts in the profile."):
    return {
        "timestamp": "2026-09-27T19:39:36.327Z",
        "input": discovered(handle),
        "error": error,
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

    async def test_the_urls_come_from_the_competitors_tiktok_handles(self):
        assert connector.profile_urls() == PROFILE_URLS

    async def test_no_handles_is_a_note_and_no_request(self, brightdata, monkeypatch):
        seen = brightdata()
        doc = spy.load()
        for competitor in doc["competitors"]:
            competitor.pop("tiktok", None)
        monkeypatch.setattr(spy, "definition", lambda: spy.parse(doc))
        notes, stored = await run()
        assert notes == {"no_tiktok_handles": 1}
        assert seen == []
        assert stored == []

    async def test_the_connector_gives_up_after_ninety_polls(self, brightdata, waits):
        brightdata(progress=(progress("running"),))
        with pytest.raises(
            ConnectorError, match=f"snapshot {SNAPSHOT} not ready after 900s"
        ):
            await run()
        assert waits == [10] * 90


class TestRecords:
    async def test_posts_are_stored_verbatim_under_posts_with_the_post_id(
        self, brightdata
    ):
        brightdata(snapshot=([post()],))
        _notes, stored = await run()
        assert stored == [
            {
                "source": SOURCE,
                "object_type": "posts",
                "source_id": "7675081150406216973",
                "raw_payload": post(),
            }
        ]

    async def test_a_clean_pull_returns_no_notes(self, brightdata):
        notes, _stored = await run()
        assert notes is None

    async def test_error_records_are_skipped_and_counted(self, brightdata):
        brightdata(
            snapshot=(
                [dead_page(), post(), dead_page("freshworks_inc", "User is banned")],
            )
        )
        notes, stored = await run()
        assert notes == {"dead_pages": 2}
        assert [s["source_id"] for s in stored] == ["7675081150406216973"]

    async def test_an_error_code_alone_marks_a_dead_page(self, brightdata):
        brightdata(snapshot=([{"error_code": "dead_page", "post_id": "1"}],))
        notes, stored = await run()
        assert notes == {"dead_pages": 1}
        assert stored == []

    async def test_a_record_without_a_post_id_is_noted(self, brightdata):
        brightdata(snapshot=([post(post_id=None), post(post_id="  ")],))
        notes, stored = await run()
        assert notes == {"missing_id": 2}
        assert stored == []

    async def test_a_record_that_is_not_a_mapping_is_a_missing_id(self, brightdata):
        brightdata(snapshot=(["junk", post()],))
        notes, stored = await run()
        assert notes == {"missing_id": 1}
        assert len(stored) == 1


class TestTheHook:
    def test_the_company_comes_from_the_account_handle(self):
        record = extract.reshape(
            "posts",
            post(account_id="freshworksinc", discovery_input=discovered("hubspot")),
        )[0]
        assert record["_company"] == "Freshsales"

    def test_the_account_handle_resolves_case_insensitively(self):
        record = extract.reshape(
            "posts", post(account_id="HUBSPOT", discovery_input=discovered("nobody"))
        )[0]
        assert record["_company"] == "HubSpot"

    def test_the_company_falls_back_to_the_discovered_profile(self):
        record = extract.reshape(
            "posts",
            post(account_id="someone", discovery_input=discovered("freshworksinc")),
        )[0]
        assert record["_company"] == "Freshsales"

    def test_a_missing_account_handle_still_resolves_the_discovered_profile(self):
        payload = post(discovery_input=discovered("freshworksinc"))
        del payload["account_id"]
        assert extract.reshape("posts", payload)[0]["_company"] == "Freshsales"

    def test_no_company_when_neither_handle_resolves(self):
        record = extract.reshape(
            "posts",
            post(
                account_id="zoho",
                profile_username="Zoho",
                discovery_input=discovered("zoho"),
            ),
        )[0]
        assert "_company" not in record

    @pytest.mark.parametrize(
        "discovery_input", [[], {"url": 5}, "x"], ids=["list", "number_url", "string"]
    )
    def test_a_malformed_discovery_input_never_raises(self, discovery_input):
        record = extract.reshape(
            "posts", post(account_id="someone", discovery_input=discovery_input)
        )[0]
        assert "_company" not in record

    def test_the_preview_is_the_preview_image(self):
        assert extract.reshape("posts", post())[0]["_preview"] == PREVIEW

    @pytest.mark.parametrize(
        "preview_image", [None, "", 5], ids=["none", "blank", "number"]
    )
    def test_no_preview_when_the_preview_image_is_not_a_url(self, preview_image):
        record = extract.reshape("posts", post(preview_image=preview_image))[0]
        assert "_preview" not in record

    def test_no_preview_when_the_preview_image_is_missing(self):
        payload = post()
        del payload["preview_image"]
        assert "_preview" not in extract.reshape("posts", payload)[0]

    def test_the_platform_is_tiktok(self):
        assert extract.reshape("posts", post())[0]["_platform"] == "tiktok"

    def test_the_post_type_is_the_category_with_no_hook_of_its_own(self):
        record = extract.reshape("posts", post(post_type="video"))[0]
        assert "_category" not in record
        assert record["post_type"] == "video"

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
        assert registry.get(SOURCE).OBSERVED_AT == {"posts": "create_time"}

    def test_a_post_dates_itself_from_the_provider(self):
        observed, which = observed_at_for(
            registry.get(SOURCE), "posts", post(), INGESTED
        )
        assert which == "provider"
        assert observed == datetime(2026, 8, 17, 19, 15, 5, tzinfo=UTC)


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
            "label": "TikTok Posts",
            "category": "Spy",
            "unlocks": "Competitor videos, plays, engagement",
        }


class TestTheDefinitions:
    def test_the_competitor_post_entity_is_unchanged(self):
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

    def test_the_source_follows_instagram_posts_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) > priority.index("instagram_posts")

    def test_every_mapping_line_reads_the_posts_object(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {(line.path[0], line.label) for line in lines} == MAPPED
        assert {line.object_type for line in lines} == {"posts"}
        assert {line.entity for line in lines} == {"competitor_post"}


def payloads(root):
    return [row["payload"] for row in json.loads((root / "posts.json").read_text())]


class TestTheFixtures:
    def test_every_mock_post_carries_the_forty_five_documented_keys(self):
        for payload in payloads(MOCK_FIXTURES):
            assert set(payload) == set(RECORD_KEYS)
            assert len(payload) == 45

    @needs_real_capture
    def test_the_real_and_mock_captures_agree_on_the_hook_and_mapped_fields(self):
        real = key_types(payloads(REAL_FIXTURES))
        mock = key_types(payloads(MOCK_FIXTURES))
        for field in (
            "account_id",
            "profile_username",
            "discovery_input",
            "preview_image",
            *(path for path, _ in MAPPED),
        ):
            if not field.startswith("_"):
                assert real[field] == mock[field], field
