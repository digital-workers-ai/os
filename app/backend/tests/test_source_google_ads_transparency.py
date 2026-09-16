import json
from datetime import UTC, datetime

import httpx
import pytest

from app import store
from app.engine import checks, spy
from app.engine.pipeline import observed_at_for
from app.sources import catalog, client, creds, hooks, registry, util
from tools.pull_source import key_types

SOURCE = "google_ads_transparency"
READER = "chatgpt"
FIXTURES = checks.REAL_FIXTURES.parent
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
SEARCH = "/search.json"
COMPLETIONS = "/api/v1/chat/completions"
ADS_ENGINE = "google_ads_transparency_center"
HUBSPOT_ID = "AR10072600183532683265"
ZOHO_ID = "AR07034216898162065409"
FRESHWORKS_ID = "AR03035893441289519105"
ADVERTISER_IDS = {HUBSPOT_ID, ZOHO_ID, FRESHWORKS_ID}
PREVIEW = "https://tpc.googlesyndication.com/archive/simgad/15529968583071394590"
PLAYER = (
    "https://displayads-formats.googleusercontent.com/ads/preview/content.js"
    "?client=ads-integrity-transparency&creativeId=762393471498"
)
NO_RESULTS = "Google hasn't returned any results for this query."
MISMATCH = (
    "OPENROUTER_API_KEY and SERPAPI_API_KEY must both be set or both unset — "
    "the ad text is read by OpenRouter"
)
PROMPT = (
    "Read the advertisement in this image. Reply with only the words visible in "
    "the ad, headline first, in reading order. Reply NONE when there is no text."
)
HOOK_READ_PATHS = (
    "request.company",
    "request.advertiser_id",
    "creative.advertiser_id",
    "creative.ad_creative_id",
    "creative.format",
    "creative.image",
    "creative.first_shown",
    "creative.last_shown",
    "creative.details_link",
)
TEXT_READ_PATHS = (
    "request.creative_id",
    "request.image",
    "request.model",
    "request.prompt_version",
    "response.choices",
    "response.choices[].message",
    "response.choices[].message.content",
)


def connector():
    return registry.get(SOURCE)


def reshape(object_type, payload):
    return hooks.hooks()[SOURCE](object_type, payload)


def creative(creative_id="CR1", fmt="text", advertiser_id=HUBSPOT_ID, **extra):
    item = {
        "advertiser_id": advertiser_id,
        "advertiser": "Hubspot, Inc.",
        "ad_creative_id": creative_id,
        "format": fmt,
        "total_days_shown": 91,
        "first_shown": 1781709978,
        "last_shown": 1789524559,
        "details_link": (
            f"https://adstransparency.google.com/advertiser/{advertiser_id}"
            f"/creative/{creative_id}?region=anywhere"
        ),
        "serpapi_details_link": (
            f"https://serpapi.com/search.json?advertiser_id={advertiser_id}"
            f"&creative_id={creative_id}&engine={ADS_ENGINE}_ad_details"
        ),
    }
    if fmt == "video":
        item["link"] = PLAYER
    else:
        item["image"] = PREVIEW
        item["width"] = 348
        item["height"] = 451
    item.update(extra)
    return item


def ads_page(creatives, next_page_token=None):
    body = {
        "search_metadata": {"id": "6aaa0a10ab28c664cc7add8b", "status": "Success"},
        "search_parameters": {"engine": ADS_ENGINE, "num": "100"},
        "search_information": {"total_results": 3000},
        "ad_creatives": list(creatives),
    }
    if next_page_token:
        body["serpapi_pagination"] = {
            "next_page_token": next_page_token,
            "next": f"https://serpapi.com/search.json?next_page_token={next_page_token}",
        }
    return body


def completion(content):
    return {
        "id": "gen-1789528712-a3mjVz0aJU7zn2HaGcMo",
        "object": "chat.completion",
        "created": 1789528712,
        "model": "openai/gpt-5.6-luna",
        "provider": "OpenAI",
        "system_fingerprint": None,
        "service_tier": "default",
        "choices": [
            {
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
                "native_finish_reason": "completed",
                "message": {
                    "role": "assistant",
                    "content": content,
                    "refusal": None,
                    "reasoning": None,
                },
            }
        ],
        "usage": {"prompt_tokens": 425, "completion_tokens": 12, "total_tokens": 437},
    }


def text_payload(content):
    return {
        "request": {
            "creative_id": "CR1",
            "image": PREVIEW,
            "model": "openai/gpt-5.6-luna",
            "prompt_version": "2026-09-15.1",
        },
        "response": completion(content),
    }


def payloads(fixture_class, name):
    path = FIXTURES / fixture_class / SOURCE / f"{name}.json"
    return [row["payload"] for row in json.loads(path.read_text())]


def image_of(request):
    return json.loads(request.content)["messages"][0]["content"][1]["image_url"]["url"]


@pytest.fixture
def estate(monkeypatch):
    seen = []

    def _install(pages=None, read=None):
        by_advertiser = pages or {}

        def handler(request):
            seen.append(request)
            if request.url.path == COMPLETIONS:
                text = read(image_of(request)) if read else "Grow better\nStart free"
                return httpx.Response(200, json=completion(text))
            params = request.url.params
            by_token = by_advertiser.get(params.get("advertiser_id"), {})
            page = by_token.get(params.get("next_page_token"), ads_page([]))
            return httpx.Response(200, json=page)

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        return seen

    yield _install
    monkeypatch.setattr(client, "_transport", None)


@pytest.fixture
def stored():
    return []


@pytest.fixture
def save(stored):
    async def _store(session, **kwargs):
        stored.append(kwargs)

    return _store


def searches(seen):
    return [r for r in seen if r.url.path == SEARCH]


def reads(seen):
    return [r for r in seen if r.url.path == COMPLETIONS]


def of_type(stored, object_type):
    return [s for s in stored if s["object_type"] == object_type]


class TestTheConstantsTheContractNames:
    def test_the_source_and_the_observation_path(self):
        module = connector()
        assert module.SOURCE == SOURCE
        assert module.OBSERVED_AT == {"creatives": "creative.last_shown"}

    def test_the_reader_model_and_its_prompt(self):
        module = connector()
        assert module.MODEL == "openai/gpt-5.6-luna"
        assert module.PROMPT == PROMPT
        assert module.PROMPT_VERSION == "2026-09-15.1"

    def test_the_read_cap_and_the_completions_path(self):
        module = connector()
        assert module.READS_PER_PULL == 50
        assert module.OPENROUTER_PATH == COMPLETIONS

    def test_the_walk_is_bounded_to_two_pages_of_forty(self):
        module = connector()
        assert module.PAGES_PER_ADVERTISER == 2
        assert module.PAGE_SIZE == 40

    def test_the_catalog_lists_the_source_under_spy(self):
        assert catalog.entry(SOURCE) == {
            "source": SOURCE,
            "label": "Google Ads Transparency",
            "category": "Spy",
            "unlocks": "Competitor creatives, ad text",
        }


class TestThePaginatorReadsSerpApiPages:
    def test_the_creatives_are_the_ad_creatives_list(self):
        page = ads_page([creative("CR1"), creative("CR2")])
        assert [c["ad_creative_id"] for c in connector().AdsPage().extract(page)] == [
            "CR1",
            "CR2",
        ]

    def test_the_documented_no_results_shape_is_an_empty_page(self):
        body = {
            "search_metadata": {"status": "Success"},
            "search_parameters": {"engine": ADS_ENGINE},
            "error": NO_RESULTS,
        }
        assert connector().AdsPage().extract(body) == []

    @pytest.mark.parametrize("body", ["not an object", {"ad_creatives": "nope"}])
    def test_an_alien_body_is_an_empty_page(self, body):
        assert connector().AdsPage().extract(body) == []

    def test_the_next_page_token_becomes_the_next_request(self):
        page = ads_page([], next_page_token="CgoAP7zmkb+8Cn9n")
        params = {"engine": ADS_ENGINE, "advertiser_id": HUBSPOT_ID, "num": 100}
        assert connector().AdsPage().next_params(page, params) == {
            **params,
            "next_page_token": "CgoAP7zmkb+8Cn9n",
        }

    @pytest.mark.parametrize(
        "body",
        [
            ads_page([]),
            {**ads_page([]), "serpapi_pagination": "nope"},
            {**ads_page([]), "serpapi_pagination": {"next_page_token": ""}},
            "not an object",
        ],
    )
    def test_no_token_ends_the_walk(self, body):
        walk = connector().AdsPage()
        assert walk.next_params(body, {"num": 40}) is None
        assert walk.more is False

    def test_a_token_after_the_last_allowed_page_ends_the_walk_and_says_so(self):
        walk = connector().AdsPage()
        page = ads_page([], next_page_token="t2")
        assert walk.next_params(page, {"num": 40}) == {
            "num": 40,
            "next_page_token": "t2",
        }
        assert walk.next_params(page, {"num": 40, "next_page_token": "t2"}) is None
        assert walk.more is True

    def test_a_walk_ending_on_its_last_allowed_page_is_not_more(self):
        walk = connector().AdsPage()
        walk.next_params(ads_page([], next_page_token="t2"), {"num": 40})
        assert walk.next_params(ads_page([]), {"num": 40}) is None
        assert walk.more is False


class TestTheWalkFollowsNextPageToken:
    @pytest.fixture
    def two_pages(self, estate):
        return estate(
            {
                HUBSPOT_ID: {
                    None: ads_page([creative("CR1")], next_page_token="t2"),
                    "t2": ads_page([creative("CR2", "video")]),
                }
            }
        )

    async def test_the_second_request_carries_the_token(self, two_pages, save):
        await connector().pull(None, save)

        hubspot = [
            r
            for r in searches(two_pages)
            if r.url.params["advertiser_id"] == HUBSPOT_ID
        ]
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]

    async def test_every_page_of_creatives_is_stored(self, two_pages, save, stored):
        await connector().pull(None, save)

        assert [s["source_id"] for s in of_type(stored, "creatives")] == ["CR1", "CR2"]


class TestTheWalkStopsAtTheCap:
    @staticmethod
    def _three_pages(prefix):
        return {
            None: ads_page([creative(f"{prefix}1")], next_page_token="t2"),
            "t2": ads_page([creative(f"{prefix}2")], next_page_token="t3"),
            "t3": ads_page([creative(f"{prefix}3")]),
        }

    async def test_only_two_pages_are_asked_and_the_advertiser_is_noted(
        self, estate, save, stored
    ):
        seen = estate({HUBSPOT_ID: self._three_pages("CR")})

        notes = await connector().pull(None, save)

        hubspot = [
            r for r in searches(seen) if r.url.params["advertiser_id"] == HUBSPOT_ID
        ]
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert [s["source_id"] for s in of_type(stored, "creatives")] == ["CR1", "CR2"]
        assert notes["creatives_capped"] == 1

    async def test_every_advertiser_with_more_pages_counts(self, estate, save):
        estate({HUBSPOT_ID: self._three_pages("CR"), ZOHO_ID: self._three_pages("CZ")})

        notes = await connector().pull(None, save)

        assert notes["creatives_capped"] == 2

    async def test_an_advertiser_under_the_cap_is_not_noted(self, estate, save, stored):
        estate(
            {
                HUBSPOT_ID: {
                    None: ads_page([creative("CR1", "video")], next_page_token="t2"),
                    "t2": ads_page([creative("CR2", "video")]),
                }
            }
        )

        notes = await connector().pull(None, save)

        assert [s["source_id"] for s in of_type(stored, "creatives")] == ["CR1", "CR2"]
        assert notes is None


class TestEveryCompetitorWithAnIdIsAsked:
    async def test_the_three_shipped_advertisers_are_asked_once_each(
        self, estate, save
    ):
        seen = estate()

        await connector().pull(None, save)

        assert [r.url.params["advertiser_id"] for r in searches(seen)] == [
            HUBSPOT_ID,
            ZOHO_ID,
            FRESHWORKS_ID,
        ]

    async def test_each_search_names_the_engine_the_page_size_and_the_key(
        self, estate, save
    ):
        seen = estate()

        await connector().pull(None, save)

        for request in searches(seen):
            assert request.url.params["engine"] == ADS_ENGINE
            assert request.url.params["num"] == "40"
            assert request.url.params["api_key"] == "mock_serpapi_key"

    async def test_a_competitor_without_an_id_is_skipped(
        self, estate, save, monkeypatch
    ):
        seen = estate()
        doc = spy.load()
        doc["competitors"][1] = {
            k: v
            for k, v in doc["competitors"][1].items()
            if k != "google_advertiser_id"
        }
        monkeypatch.setattr(spy, "definition", lambda: spy.parse(doc))

        await connector().pull(None, save)

        assert [r.url.params["advertiser_id"] for r in searches(seen)] == [
            HUBSPOT_ID,
            FRESHWORKS_ID,
        ]

    @pytest.mark.parametrize(
        "advertiser_id,name",
        [(HUBSPOT_ID, "HubSpot"), (ZOHO_ID, "Zoho CRM"), (FRESHWORKS_ID, "Freshsales")],
    )
    def test_the_shipped_definition_carries_the_real_advertiser_ids(
        self, advertiser_id, name
    ):
        assert spy.definition().by_advertiser(advertiser_id).name == name


class TestCreativesAreStoredWithTheirRequest:
    async def test_the_payload_wraps_the_creative_with_who_was_asked(
        self, estate, save, stored
    ):
        item = creative("CR1")
        estate({HUBSPOT_ID: {None: ads_page([item])}})

        await connector().pull(None, save)

        assert of_type(stored, "creatives") == [
            {
                "source": SOURCE,
                "object_type": "creatives",
                "source_id": "CR1",
                "raw_payload": {
                    "request": {"company": "HubSpot", "advertiser_id": HUBSPOT_ID},
                    "creative": item,
                },
            }
        ]

    async def test_a_creative_without_an_id_is_counted_and_not_read(
        self, estate, save, stored
    ):
        nameless = {k: v for k, v in creative().items() if k != "ad_creative_id"}
        seen = estate({HUBSPOT_ID: {None: ads_page([nameless, creative("CR2")])}})

        notes = await connector().pull(None, save)

        assert [s["source_id"] for s in of_type(stored, "creatives")] == ["CR2"]
        assert notes["missing_id"] == 1
        assert [image_of(r) for r in reads(seen)] == [PREVIEW]


class TestTheRealAndMockKeysMustAgree:
    def test_the_real_entry_names_both_keys_so_a_half_set_env_is_refused(
        self, monkeypatch
    ):
        monkeypatch.setenv("SERPAPI_API_KEY", "serpapi-test-0000")
        with pytest.raises(creds.CredentialsError, match="OPENROUTER_API_KEY"):
            creds.credentials_for(SOURCE)

    def test_both_keys_reach_serpapi_as_the_api_key_parameter(self, monkeypatch):
        monkeypatch.setenv("SERPAPI_API_KEY", "serpapi-test-0000")
        monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-0000")
        found = creds.credentials_for(SOURCE)
        assert found.base_url == "https://serpapi.com"
        assert found.params == {"api_key": "serpapi-test-0000"}
        assert found.headers == {}
        assert found.real is True

    def test_the_reader_key_becomes_a_bearer_on_openrouter(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-0000")
        found = creds.credentials_for(READER)
        assert found.base_url == "https://openrouter.ai"
        assert found.headers == {"Authorization": "Bearer openrouter-test-0000"}
        assert found.real is True

    def test_the_stand_ins_answer_under_serpapi_and_openrouter(self):
        ads = creds.credentials_for(SOURCE)
        reader = creds.credentials_for(READER)
        assert ads.base_url.endswith("/serpapi")
        assert ads.params == {"api_key": "mock_serpapi_key"}
        assert reader.base_url.endswith("/openrouter")
        assert reader.headers == {"Authorization": "Bearer mock_openrouter_key"}

    async def test_real_ads_with_a_stand_in_reader_is_refused(
        self, estate, save, monkeypatch
    ):
        estate()
        monkeypatch.setitem(
            creds._REAL,
            SOURCE,
            (
                "https://serpapi.com",
                ("SERPAPI_API_KEY",),
                lambda key: ({}, None, {"api_key": key}, {}),
            ),
        )
        monkeypatch.setenv("SERPAPI_API_KEY", "serpapi-test-0000")

        with pytest.raises(client.ConnectorError) as caught:
            await connector().pull(None, save)

        assert caught.value.source == SOURCE
        assert caught.value.detail == MISMATCH

    async def test_a_real_reader_with_stand_in_ads_is_refused(
        self, estate, save, monkeypatch
    ):
        seen = estate()
        monkeypatch.delitem(creds._REAL, SOURCE)
        monkeypatch.setenv("OPENROUTER_API_KEY", "openrouter-test-0000")

        with pytest.raises(client.ConnectorError, match=MISMATCH):
            await connector().pull(None, save)

        assert seen == []


class TestOnlyReadableCreativesAreRead:
    @pytest.fixture
    def mixed(self):
        return [
            creative("CR1", "text"),
            creative("CR2", "image"),
            creative("CR3", "video"),
            {k: v for k, v in creative("CR4", "text").items() if k != "image"},
            creative("CR5", "image", image=""),
        ]

    async def test_text_and_image_creatives_with_a_preview_are_read(
        self, estate, save, mixed
    ):
        seen = estate({HUBSPOT_ID: {None: ads_page(mixed)}})

        await connector().pull(None, save)

        assert [image_of(r) for r in reads(seen)] == [PREVIEW, PREVIEW]

    async def test_the_reader_request_carries_the_prompt_the_model_and_the_image(
        self, estate, save
    ):
        seen = estate({HUBSPOT_ID: {None: ads_page([creative("CR1")])}})

        await connector().pull(None, save)

        (request,) = reads(seen)
        assert request.headers["Authorization"] == "Bearer mock_openrouter_key"
        assert json.loads(request.content) == {
            "model": "openai/gpt-5.6-luna",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": PROMPT},
                        {"type": "image_url", "image_url": {"url": PREVIEW}},
                    ],
                }
            ],
        }

    async def test_the_text_is_stored_under_the_creative_with_its_request(
        self, estate, save, stored
    ):
        estate({HUBSPOT_ID: {None: ads_page([creative("CR1")])}})

        await connector().pull(None, save)

        assert of_type(stored, "creative_texts") == [
            {
                "source": SOURCE,
                "object_type": "creative_texts",
                "source_id": "CR1",
                "raw_payload": {
                    "request": {
                        "creative_id": "CR1",
                        "image": PREVIEW,
                        "model": "openai/gpt-5.6-luna",
                        "prompt_version": "2026-09-15.1",
                    },
                    "response": completion("Grow better\nStart free"),
                },
            }
        ]

    async def test_the_reads_are_counted(self, estate, save, mixed):
        estate({HUBSPOT_ID: {None: ads_page(mixed)}})

        notes = await connector().pull(None, save)

        assert notes == {"creative_texts_read": 2}

    async def test_a_creative_already_read_is_skipped_and_counted(
        self, estate, save, monkeypatch
    ):
        seen = estate(
            {HUBSPOT_ID: {None: ads_page([creative("CR1"), creative("CR2")])}}
        )
        asked = []

        async def already(session, source, object_type):
            asked.append((session, source, object_type))
            return {"CR1"}

        monkeypatch.setattr(connector(), "stored_ids", already)

        notes = await connector().pull("the session", save)

        assert asked == [("the session", SOURCE, "creative_texts")]
        assert [image_of(r) for r in reads(seen)] == [PREVIEW]
        assert notes == {"creative_texts_read": 1, "creative_texts_skipped": 1}

    async def test_the_cap_holds_and_the_overflow_is_counted(
        self, estate, save, monkeypatch
    ):
        seen = estate(
            {HUBSPOT_ID: {None: ads_page([creative(f"CR{n}") for n in range(5)])}}
        )
        monkeypatch.setattr(connector(), "READS_PER_PULL", 2)

        notes = await connector().pull(None, save)

        assert len(reads(seen)) == 2
        assert notes == {"creative_texts_read": 2, "creative_texts_capped": 3}

    async def test_a_creative_on_two_pages_is_read_once(self, estate, save):
        seen = estate(
            {
                HUBSPOT_ID: {
                    None: ads_page([creative("CR1")], next_page_token="t2"),
                    "t2": ads_page([creative("CR1")]),
                }
            }
        )

        await connector().pull(None, save)

        assert len(reads(seen)) == 1

    async def test_nothing_readable_means_no_reads_and_no_notes(
        self, estate, save, stored
    ):
        seen = estate({HUBSPOT_ID: {None: ads_page([creative("CR3", "video")])}})

        notes = await connector().pull(None, save)

        assert reads(seen) == []
        assert of_type(stored, "creative_texts") == []
        assert notes is None


class TestTheCreativesHook:
    def _payload(self, **creative_fields):
        return {
            "request": {"company": "Asked Co", "advertiser_id": HUBSPOT_ID},
            "creative": creative(**creative_fields),
        }

    def test_a_known_advertiser_becomes_its_company(self):
        (record,) = reshape("creatives", self._payload(advertiser_id=ZOHO_ID))
        assert record["_company"] == "Zoho CRM"
        assert record["_platform"] == "google"

    def test_an_unknown_advertiser_falls_back_to_who_was_asked(self):
        (record,) = reshape("creatives", self._payload(advertiser_id="AR000"))
        assert record["_company"] == "Asked Co"

    def test_the_request_advertiser_serves_when_the_creative_carries_none(self):
        payload = self._payload()
        del payload["creative"]["advertiser_id"]
        (record,) = reshape("creatives", payload)
        assert record["_company"] == "HubSpot"

    def test_no_company_anywhere_stamps_only_the_platform(self):
        (record,) = reshape("creatives", {"creative": {"format": "text"}})
        assert "_company" not in record
        assert record["_platform"] == "google"

    def test_the_rest_of_the_payload_survives(self):
        payload = self._payload()
        (record,) = reshape("creatives", payload)
        assert record["creative"] == payload["creative"]
        assert record["request"] == payload["request"]

    def test_the_stored_payload_is_not_mutated(self):
        payload = self._payload()
        reshape("creatives", payload)
        assert set(payload) == {"request", "creative"}

    @pytest.mark.parametrize("payload", [{}, {"creative": "nope", "request": []}])
    def test_a_malformed_payload_never_raises(self, payload):
        (record,) = reshape("creatives", payload)
        assert record["_platform"] == "google"


class TestTheCreativeTextsHook:
    def test_the_content_becomes_the_text_stripped(self):
        (record,) = reshape(
            "creative_texts", text_payload("  Grow better  \nStart free\n")
        )
        assert record["_text"] == "Grow better  \nStart free"

    @pytest.mark.parametrize("content", ["NONE", "none", " None \n"])
    def test_none_means_no_text(self, content):
        (record,) = reshape("creative_texts", text_payload(content))
        assert "_text" not in record

    @pytest.mark.parametrize("content", ["", "   \n"])
    def test_an_empty_answer_means_no_text(self, content):
        (record,) = reshape("creative_texts", text_payload(content))
        assert "_text" not in record

    @pytest.mark.parametrize(
        "response",
        [
            {},
            {"choices": []},
            {"choices": "nope"},
            {"choices": [{"message": "nope"}]},
            {"choices": [{"message": {"content": None}}]},
            {"choices": [{"message": {"content": 7}}]},
            "nope",
        ],
    )
    def test_a_malformed_answer_means_no_text_and_never_raises(self, response):
        (record,) = reshape("creative_texts", {"request": {}, "response": response})
        assert "_text" not in record
        assert record["request"] == {}

    def test_the_stored_payload_is_not_mutated(self):
        payload = text_payload("Grow better")
        reshape("creative_texts", payload)
        assert set(payload) == {"request", "response"}

    def test_other_object_types_pass_through(self):
        payload = {"anything": 1}
        assert reshape("advertisers", payload) == [payload]


class TestTheObservationComesFromLastShown:
    def test_a_unix_stamp_dates_the_creative_from_the_provider(self):
        payload = {"creative": creative(last_shown=1788188385)}
        observed, which = observed_at_for(connector(), "creatives", payload, INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 8, 31, 14, 59, 45, tzinfo=UTC)

    def test_a_creative_without_the_stamp_falls_back_to_ingestion(self):
        payload = {"creative": {"ad_creative_id": "CR1"}}
        observed, which = observed_at_for(connector(), "creatives", payload, INGESTED)
        assert which == "ingested"
        assert observed == INGESTED

    def test_a_text_read_is_dated_by_ingestion(self):
        observed, which = observed_at_for(
            connector(), "creative_texts", text_payload("x"), INGESTED
        )
        assert which == "ingested"


class TestStoredIds:
    async def test_no_session_means_nothing_is_stored_yet(self):
        assert await util.stored_ids(None, SOURCE, "creative_texts") == set()

    async def test_the_distinct_ids_of_that_source_and_type(self, session):
        rows = [
            (SOURCE, "creative_texts", "CR1", {"n": 1}),
            (SOURCE, "creative_texts", "CR1", {"n": 2}),
            (SOURCE, "creative_texts", "CR2", {"n": 3}),
            (SOURCE, "creatives", "CR3", {"n": 4}),
            ("linkedin_posts", "creative_texts", "CR4", {"n": 5}),
        ]
        for source, object_type, source_id, payload in rows:
            await store.save_raw(
                session,
                source=source,
                object_type=object_type,
                source_id=source_id,
                raw_payload=payload,
            )

        assert await util.stored_ids(session, SOURCE, "creative_texts") == {
            "CR1",
            "CR2",
        }


class TestTheStandInFixtureCarriesTheRealShapes:
    def test_every_creative_is_wrapped_with_its_request(self):
        for payload in payloads("mock", "creatives"):
            assert set(payload) == {"request", "creative"}
            assert payload["request"]["advertiser_id"] in ADVERTISER_IDS
            assert (
                payload["creative"]["advertiser_id"]
                == payload["request"]["advertiser_id"]
            )

    def test_the_shown_stamps_are_unix_seconds_integers(self):
        types = key_types(payloads("mock", "creatives"))
        assert types["creative.first_shown"] == {"number"}
        assert types["creative.last_shown"] == {"number"}

    def test_video_creatives_carry_a_player_link_and_no_preview(self):
        videos = [
            p["creative"]
            for p in payloads("mock", "creatives")
            if p["creative"]["format"] == "video"
        ]
        assert videos
        for video in videos:
            assert "image" not in video
            assert video["link"].startswith("https://displayads-formats")

    def test_text_and_image_creatives_carry_a_preview(self):
        stills = [
            p["creative"]
            for p in payloads("mock", "creatives")
            if p["creative"]["format"] in ("text", "image")
        ]
        assert stills
        for still in stills:
            assert still["image"].startswith("https://tpc.googlesyndication.com/")

    def test_every_text_read_names_the_model_and_the_prompt_version(self):
        for payload in payloads("mock", "creative_texts"):
            assert payload["request"]["model"] == "openai/gpt-5.6-luna"
            assert payload["request"]["prompt_version"] == "2026-09-15.1"
            assert payload["request"]["creative_id"]

    def test_an_image_read_carries_content_and_no_annotations(self):
        for payload in payloads("mock", "creative_texts"):
            message = payload["response"]["choices"][0]["message"]
            assert isinstance(message["content"], str) and message["content"]
            assert "annotations" not in message


class TestTheRealCaptureAgreesWithTheStandIn:
    def test_the_creative_fields_the_hook_reads_have_one_type_on_both(self):
        real = key_types(payloads("real", "creatives"))
        mock = key_types(payloads("mock", "creatives"))
        for path in HOOK_READ_PATHS:
            assert real[path] == mock[path], path

    def test_the_text_fields_the_hook_reads_have_one_type_on_both(self):
        real = key_types(payloads("real", "creative_texts"))
        mock = key_types(payloads("mock", "creative_texts"))
        for path in TEXT_READ_PATHS:
            assert real[path] == mock[path], path

    def test_the_real_capture_keeps_a_still_with_its_preview(self):
        stills = [
            p["creative"]
            for p in payloads("real", "creatives")
            if p["creative"]["format"] in ("text", "image")
        ]
        assert stills
        assert all(still["image"].startswith("https://") for still in stills)

    def test_every_real_creative_belongs_to_a_tracked_competitor(self):
        for payload in payloads("real", "creatives"):
            assert spy.definition().by_advertiser(payload["creative"]["advertiser_id"])

    def test_the_real_capture_keeps_a_read_with_words_in_it(self):
        texts = [
            p["response"]["choices"][0]["message"]["content"].strip()
            for p in payloads("real", "creative_texts")
        ]
        assert any(text and text.upper() != "NONE" for text in texts)

    @pytest.mark.parametrize("name", ["creatives", "creative_texts"])
    def test_the_real_capture_is_trimmed_to_three(self, name):
        assert 1 <= len(payloads("real", name)) <= 3
