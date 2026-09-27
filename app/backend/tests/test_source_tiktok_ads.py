import importlib
import json
from datetime import UTC, datetime

import httpx
import pytest

from app.config import settings
from app.engine import checks, mappings, ontology, pipeline, spy, transforms
from app.engine.pipeline import observed_at_for
from app.engine.report import SyncReport
from app.sources import catalog, client, creds, hooks, registry
from tests.test_env_example import ENV_EXAMPLE, documented_keys
from tests.test_fixture_replay import replay
from tools.pull_source import key_types

SOURCE = "tiktok_ads"
ENGINE = "tiktok_ads_library"
SEARCH = "/api/v1/search"
SORT = "last_shown_date_newest_to_oldest"
FIXTURES = checks.REAL_FIXTURES.parent
MOCK_FIXTURES = FIXTURES / "mock" / SOURCE
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
AD_ID = "1876041387259298"
HUBSPOT_ID = "6948549846680732417"
HUBSPOT_NAME = "HUBSPOT, INC."
ZOHO_ID = "7000000000000000001"
ZOHO_NAME = "ZOHO CORPORATION"
LIBRARY = "https://library.tiktok.com/ads/detail/?ad_id="
TITLE = (
    "Découvrez comment utiliser l'IA pour booster la croissance de votre entreprise."
)
IMAGE = (
    "https://p16-common-sign.tiktokcdn.com/ad-site-i18n-sg"
    "/202609115d0d5b657d36b7ef4f00a749~tplv-tiktokx-origin.jpeg"
    "?dr=14582&refresh_token=4b1b539e&x-expires=1790510400"
    "&x-signature=dbmhlPWu8bZoNbfVWHHsUL1a9g8%3D&t=4d5b0474&ps=13740610"
    "&shp=0c75dd76&shcp=9b759fb9&idc=sg1"
)
COVER = (
    "https://p16-common-sign.tiktokcdn.com/tos-alisg-p-0051c001-sg"
    "/owQieDQDpB0vcEvFEnVOhAQZDBDJfJGgvNQThV~tplv-tiktokx-origin.jpeg"
    "?dr=14582&refresh_token=a3d4e1b8&x-expires=1790510400"
    "&x-signature=J5qT3cgPHik2dWBsV%2BuuuY%2BUbxY%3D&t=4d5b0474&ps=13740610"
    "&shp=0c75dd76&shcp=9b759fb9&idc=sg1"
)
VIDEO = (
    "https://library.tiktok.com/api/v1/cdn/1790488929/video"
    "/aHR0cHM6Ly92NzcudGlrdG9rY2RuLmNvbS81YzY1Y2U2YWVjNzJiMDk4YjMxODVjNTk0ZTFmMmIxNS8"
    "2YWI5MDVkYy92aWRlby90b3MvYWxpc2cvdG9zLWFsaXNnLXZlLTAwNTFjMDAxLXNnL29FMzBrUUIzSUF"
    "BaUJNM0VmQkF3RXdUaWhua0tqSXVSSkpzbW82Lw=="
    "/c62f1d96-769c-466e-b2c6-a58aac84d7de?a=475769&bt=386&mime_type=video_mp4"
)
NO_RESULTS = "TikTok ads library didn't return any results."
MISSING_Q = (
    "Missing required parameter q. When searching by advertiser_id, you must also "
    "provide the advertiser's name via q (or use advertiser_token, which bundles "
    "both). You can look up advertisers with the "
    "tiktok_ads_library_advertiser_search engine."
)
ENV_COMMENT = "# linkedin_ads, tiktok_ads, meta_ads — https://www.searchapi.io"
ADS_READ_PATHS = (
    "request.company",
    "request.advertiser_id",
    "ad.id",
    "ad.advertiser_id",
    "ad.advertiser",
    "ad.title",
    "ad.format",
    "ad.first_shown_datetime",
    "ad.last_shown_datetime",
    "ad.image_urls",
)
MAPPED = {
    ("ads", "_company", "company"),
    ("ads", "_platform", "platform"),
    ("ads", "ad.title", "name"),
    ("ads", "ad.format", "category"),
    ("ads", "_preview", "preview"),
    ("ads", "ad.video_link", "media"),
    ("ads", "ad.first_shown_datetime", "first_seen"),
    ("ads", "ad.last_shown_datetime", "last_seen"),
    ("ads", "_url", "url"),
}


def connector():
    return registry.get(SOURCE)


def extract():
    return importlib.import_module(f"app.sources.{SOURCE}.extract")


def reshape(object_type, payload):
    return hooks.hooks()[SOURCE](object_type, payload)


def ad(
    ad_id=AD_ID,
    fmt="image",
    advertiser_id=HUBSPOT_ID,
    advertiser=HUBSPOT_NAME,
    **extra,
):
    item = {
        "position": 1,
        "id": ad_id,
        "advertiser_id": advertiser_id,
        "advertiser": advertiser,
        "title": TITLE,
        "format": fmt,
        "first_shown_datetime": "2026-09-15T00:00:00Z",
        "last_shown_datetime": "2026-09-23T00:00:00Z",
        "image_urls": [COVER if fmt == "video" else IMAGE],
        "estimated_audience": "10K-100K",
        "estimated_audience_min": 10000,
        "estimated_audience_max": 100000,
    }
    if fmt == "video":
        item["video_link"] = VIDEO
        item["cover_image"] = COVER
    item.update(extra)
    return item


def ads_page(ads, next_page_token=None):
    body = {
        "search_metadata": {"status": "Success"},
        "search_parameters": {
            "engine": ENGINE,
            "q": HUBSPOT_NAME,
            "advertiser_id": HUBSPOT_ID,
            "country": "US",
            "time_period": "2025-09-27..2026-09-27",
            "sort_by": SORT,
        },
        "search_information": {"total_results": 143},
        "ads": list(ads),
    }
    if next_page_token:
        body["pagination"] = {"next_page_token": next_page_token}
    return body


def no_results():
    return {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": ENGINE},
        "error": NO_RESULTS,
    }


def ad_payload(item=None, company="HubSpot", advertiser_id=HUBSPOT_ID):
    return {
        "request": {"company": company, "advertiser_id": advertiser_id},
        "ad": item if item is not None else ad(),
    }


def payloads(fixture_class, name):
    path = FIXTURES / fixture_class / SOURCE / f"{name}.json"
    return [row["payload"] for row in json.loads(path.read_text())]


def definition_with(**advertisers):
    doc = spy.load()
    competitors = []
    for spec in doc["competitors"]:
        kept = {k: v for k, v in spec.items() if not k.startswith("tiktok_")}
        if spec["name"] in advertisers:
            advertiser_id, name = advertisers[spec["name"]]
            kept["tiktok_advertiser_id"] = advertiser_id
            kept["tiktok_advertiser_name"] = name
        competitors.append(kept)
    return spy.parse({**doc, "competitors": competitors})


@pytest.fixture
def tracked(monkeypatch):
    def _install(**advertisers):
        definition = definition_with(**advertisers)
        monkeypatch.setattr(spy, "definition", lambda: definition)
        return definition

    return _install


@pytest.fixture
def library(monkeypatch):
    seen = []

    def _install(pages=None):
        by_advertiser = pages or {}

        def handler(request):
            seen.append(request)
            params = request.url.params
            if params.get("advertiser_id") and not params.get("q"):
                return httpx.Response(400, json={"error": MISSING_Q})
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


def asked(seen, advertiser_id):
    return [r for r in seen if r.url.params.get("advertiser_id") == advertiser_id]


def ids(stored):
    return [s["source_id"] for s in stored if s["object_type"] == "ads"]


def pages(prefix, count):
    tokens = [None, *(f"t{n}" for n in range(2, count + 1)), None]
    return {
        token: ads_page([ad(f"{prefix}{n}")], next_page_token=tokens[n])
        for n, token in enumerate(tokens[:-1], start=1)
    }


def project(object_type, payload, source_id=AD_ID):
    return pipeline.project_payload(
        source=SOURCE,
        object_type=object_type,
        source_id=source_id,
        payload=payload,
        raw_event_id=None,
        ingested_at=INGESTED,
        seq=1,
        onto=ontology.load(),
        line_index=mappings.by_object(mappings.load()),
        transform_map=transforms.load_map(),
        report=SyncReport(),
        connector_module=connector(),
    )


def facts(entity):
    return {attr: fact.value for attr, fact in entity.facts.items()}


class TestTheConstantsTheContractNames:
    def test_the_source_and_the_observation_path(self):
        module = connector()
        assert module.SOURCE == SOURCE
        assert module.OBSERVED_AT == {"ads": "ad.last_shown_datetime"}

    def test_the_engine_the_cap_and_the_sort(self):
        module = connector()
        assert module.ENGINE == ENGINE
        assert module.PAGES_PER_ADVERTISER == 4
        assert module.SORT == SORT

    def test_the_search_path_is_shared_by_every_searchapi_source(self):
        assert importlib.import_module("app.sources.searchapi").SEARCH_PATH == SEARCH

    def test_the_registry_discovers_the_connector_and_its_hook(self):
        assert SOURCE in registry.discover()
        assert hooks.hooks()[SOURCE] is extract().reshape
        assert extract().PLATFORM == "tiktok"

    def test_the_catalog_lists_the_source_under_spy(self):
        assert catalog.entry(SOURCE) == {
            "source": SOURCE,
            "label": "TikTok Ads Library",
            "category": "Spy",
            "unlocks": "Competitor video creatives, audience bands",
        }


class TestCredentials:
    def test_the_stand_in_is_the_searchapi_prefix(self):
        found = creds.credentials_for(SOURCE)
        assert found.base_url == f"{settings.MOCK_BASE_URL}/searchapi"
        assert found.headers == {"Authorization": "Bearer mock_searchapi_key"}
        assert found.params == {}
        assert found.real is False

    def test_the_key_becomes_a_bearer_on_the_real_api(self, monkeypatch):
        monkeypatch.setenv("SEARCHAPI_API_KEY", "searchapi-test-0000")
        found = creds.credentials_for(SOURCE)
        assert found.base_url == "https://www.searchapi.io"
        assert found.headers == {"Authorization": "Bearer searchapi-test-0000"}
        assert found.params == {}
        assert found.real is True

    def test_the_one_variable_is_shared_with_linkedin_ads_and_documented_once(self):
        assert creds._REAL[SOURCE][1] == ("SEARCHAPI_API_KEY",)
        assert creds._REAL[SOURCE] == creds._REAL["linkedin_ads"]
        assert documented_keys().count("SEARCHAPI_API_KEY") == 1
        assert ENV_COMMENT in ENV_EXAMPLE.read_text().splitlines()


class TestEveryAdvertiserIsAskedByIdAndName:
    async def test_the_competitor_with_an_advertiser_is_asked_in_the_country(
        self, library, save
    ):
        seen = library()

        await connector().pull(None, save)

        assert [dict(r.url.params) for r in seen] == [
            {
                "engine": ENGINE,
                "advertiser_id": HUBSPOT_ID,
                "q": HUBSPOT_NAME,
                "country": "US",
                "sort_by": SORT,
            }
        ]
        for request in seen:
            assert request.method == "GET"
            assert request.url.path == SEARCH
            assert request.headers["Authorization"] == "Bearer mock_searchapi_key"

    async def test_every_competitor_with_an_advertiser_is_asked_in_order(
        self, library, save, tracked
    ):
        tracked(
            **{"Zoho CRM": (ZOHO_ID, ZOHO_NAME), "HubSpot": (HUBSPOT_ID, HUBSPOT_NAME)}
        )
        seen = library()

        await connector().pull(None, save)

        assert [(r.url.params["advertiser_id"], r.url.params["q"]) for r in seen] == [
            (HUBSPOT_ID, HUBSPOT_NAME),
            (ZOHO_ID, ZOHO_NAME),
        ]

    async def test_the_second_request_carries_the_token(self, library, save, stored):
        seen = library(
            {
                HUBSPOT_ID: {
                    None: ads_page([ad("1")], next_page_token="t2"),
                    "t2": ads_page([ad("2", "video")]),
                }
            }
        )

        notes = await connector().pull(None, save)

        hubspot = asked(seen, HUBSPOT_ID)
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert ids(stored) == ["1", "2"]
        assert notes is None

    async def test_only_four_pages_are_asked_and_the_advertiser_is_noted(
        self, library, save, stored
    ):
        seen = library({HUBSPOT_ID: pages("H", 5)})

        notes = await connector().pull(None, save)

        hubspot = asked(seen, HUBSPOT_ID)
        assert [r.url.params.get("next_page_token") for r in hubspot] == [
            None,
            "t2",
            "t3",
            "t4",
        ]
        assert ids(stored) == ["H1", "H2", "H3", "H4"]
        assert notes == {"ads_capped": 1}

    async def test_a_walk_ending_on_its_last_allowed_page_is_not_noted(
        self, library, save, stored
    ):
        library({HUBSPOT_ID: pages("H", 4)})

        notes = await connector().pull(None, save)

        assert ids(stored) == ["H1", "H2", "H3", "H4"]
        assert notes is None

    async def test_every_advertiser_with_more_pages_counts(
        self, library, save, tracked
    ):
        tracked(
            **{"HubSpot": (HUBSPOT_ID, HUBSPOT_NAME), "Zoho CRM": (ZOHO_ID, ZOHO_NAME)}
        )
        library({HUBSPOT_ID: pages("H", 5), ZOHO_ID: pages("Z", 5)})

        notes = await connector().pull(None, save)

        assert notes == {"ads_capped": 2}

    async def test_no_advertiser_anywhere_asks_nothing_and_says_so(
        self, library, save, stored, tracked
    ):
        tracked()
        seen = library()

        notes = await connector().pull(None, save)

        assert seen == []
        assert stored == []
        assert notes == {"no_tiktok_advertisers": 1}


class TestAdsAreStoredWithTheirRequest:
    async def test_the_payload_wraps_the_ad_with_who_was_asked(
        self, library, save, stored
    ):
        item = ad()
        library({HUBSPOT_ID: {None: ads_page([item])}})

        await connector().pull(None, save)

        assert stored == [
            {
                "source": SOURCE,
                "object_type": "ads",
                "source_id": AD_ID,
                "raw_payload": {
                    "request": {"company": "HubSpot", "advertiser_id": HUBSPOT_ID},
                    "ad": item,
                },
            }
        ]

    async def test_an_ad_without_an_id_is_counted(self, library, save, stored):
        nameless = {k: v for k, v in ad().items() if k != "id"}
        library({HUBSPOT_ID: {None: ads_page([nameless, ad("2")])}})

        notes = await connector().pull(None, save)

        assert ids(stored) == ["2"]
        assert notes == {"missing_id": 1}

    async def test_nothing_listed_means_nothing_stored_and_no_notes(
        self, library, save, stored
    ):
        library()

        notes = await connector().pull(None, save)

        assert stored == []
        assert notes is None

    async def test_the_documented_no_results_answer_is_an_empty_page(
        self, library, save, stored
    ):
        library({HUBSPOT_ID: {None: no_results()}})

        notes = await connector().pull(None, save)

        assert stored == []
        assert notes is None


class TestTheAdsHook:
    def test_a_known_advertiser_becomes_its_company(self):
        (record,) = reshape("ads", ad_payload(company="Asked Co"))
        assert record["_company"] == "HubSpot"
        assert record["_platform"] == "tiktok"

    def test_an_unknown_advertiser_falls_back_to_who_was_asked(self):
        payload = ad_payload(
            ad(advertiser_id="1"), company="Asked Co", advertiser_id="1"
        )
        (record,) = reshape("ads", payload)
        assert record["_company"] == "Asked Co"

    def test_the_request_advertiser_serves_when_the_ad_carries_none(self):
        payload = ad_payload(company="Asked Co")
        del payload["ad"]["advertiser_id"]
        (record,) = reshape("ads", payload)
        assert record["_company"] == "HubSpot"

    def test_an_image_previews_its_first_image(self):
        (record,) = reshape("ads", ad_payload(ad()))
        assert record["_preview"] == IMAGE

    def test_a_video_previews_its_cover(self):
        (record,) = reshape("ads", ad_payload(ad(fmt="video")))
        assert record["_preview"] == COVER

    def test_a_blank_cover_falls_through_to_the_images(self):
        item = ad(fmt="video", cover_image="", image_urls=[IMAGE])
        (record,) = reshape("ads", ad_payload(item))
        assert record["_preview"] == IMAGE

    @pytest.mark.parametrize(
        "fields",
        [
            {"cover_image": 5, "image_urls": []},
            {"image_urls": "nope"},
            {"image_urls": [7]},
            {"image_urls": [""]},
            {"image_urls": None},
        ],
    )
    def test_nothing_usable_means_no_preview(self, fields):
        (record,) = reshape("ads", ad_payload(ad(**fields)))
        assert "_preview" not in record

    def test_an_ad_without_images_has_no_preview(self):
        item = {k: v for k, v in ad().items() if k != "image_urls"}
        (record,) = reshape("ads", ad_payload(item))
        assert "_preview" not in record

    def test_the_url_is_the_library_detail_page(self):
        (record,) = reshape("ads", ad_payload())
        assert record["_url"] == f"{LIBRARY}{AD_ID}"

    @pytest.mark.parametrize("ad_id", ["", 7, None])
    def test_an_ad_without_a_string_id_has_no_url(self, ad_id):
        (record,) = reshape("ads", ad_payload(ad(id=ad_id)))
        assert "_url" not in record

    def test_the_rest_of_the_payload_survives_unmutated(self):
        payload = ad_payload()
        (record,) = reshape("ads", payload)
        assert record["ad"] == payload["ad"]
        assert record["request"] == payload["request"]
        assert set(payload) == {"request", "ad"}

    def test_an_ad_that_is_not_a_mapping_never_raises(self):
        (record,) = reshape("ads", {"request": {"company": "HubSpot"}, "ad": "nope"})
        assert record["_company"] == "HubSpot"
        assert record["_platform"] == "tiktok"
        assert "_preview" not in record
        assert "_url" not in record

    def test_other_object_types_pass_through(self):
        payload = {"anything": 1}
        assert reshape("advertisers", payload) == [payload]


class TestWhenTheAdWasObserved:
    def test_a_listed_ad_is_dated_by_its_last_showing(self):
        observed, which = observed_at_for(connector(), "ads", ad_payload(), INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 23, tzinfo=UTC)

    def test_an_ad_without_the_stamp_falls_back_to_ingestion(self):
        payload = ad_payload()
        del payload["ad"]["last_shown_datetime"]
        observed, which = observed_at_for(connector(), "ads", payload, INGESTED)
        assert which == "ingested"
        assert observed == INGESTED


class TestTheDefinitions:
    def test_the_source_follows_linkedin_ads_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) == priority.index("linkedin_ads") + 1

    def test_every_mapping_line_lands_on_the_ad(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {
            (line.object_type, ".".join(line.path), line.label) for line in lines
        } == MAPPED
        assert {line.entity for line in lines} == {"ad"}


class TestTheMappedFactsOnTheAd:
    def test_a_video_lands_its_media_its_cover_its_link_and_its_dates(self):
        (entity,) = project("ads", ad_payload(ad(fmt="video")))
        assert entity.entity_type == "ad"
        assert entity.source_id == AD_ID
        assert facts(entity) == {
            "company": "HubSpot",
            "platform": "tiktok",
            "name": TITLE,
            "category": "video",
            "preview": COVER,
            "media": VIDEO,
            "first_seen": "2026-09-15T00:00:00Z",
            "last_seen": "2026-09-23T00:00:00Z",
            "url": f"{LIBRARY}{AD_ID}",
        }

    def test_an_image_lands_its_image_and_no_media(self):
        (entity,) = project("ads", ad_payload(ad()))
        assert facts(entity) == {
            "company": "HubSpot",
            "platform": "tiktok",
            "name": TITLE,
            "category": "image",
            "preview": IMAGE,
            "first_seen": "2026-09-15T00:00:00Z",
            "last_seen": "2026-09-23T00:00:00Z",
            "url": f"{LIBRARY}{AD_ID}",
        }


class TestTheStandInFixtureCarriesTheRealShapes:
    def test_the_capture_holds_the_ads_and_the_expectation(self):
        assert sorted(p.name for p in MOCK_FIXTURES.iterdir()) == [
            "ads.json",
            "expected.json",
        ]

    def test_every_ad_is_wrapped_with_who_was_asked_and_belongs_to_them(self):
        by_name = {company.name: company for company in spy.definition().competitors}
        ads = payloads("mock", "ads")
        assert ads
        assert {payload["ad"]["format"] for payload in ads} == {"image", "video"}
        for payload in ads:
            assert set(payload) == {"request", "ad"}
            company = by_name[payload["request"]["company"]]
            assert payload["request"]["advertiser_id"] == company.tiktok_advertiser_id
            item = payload["ad"]
            assert item["advertiser_id"] == company.tiktok_advertiser_id
            assert item["advertiser"] == company.tiktok_advertiser_name
            assert item["id"]
            for stamp in ("first_shown_datetime", "last_shown_datetime"):
                datetime.fromisoformat(item[stamp].replace("Z", "+00:00"))
            assert item["image_urls"]
            assert all(isinstance(url, str) and url for url in item["image_urls"])
            if item["format"] == "video":
                assert item["video_link"].startswith("https://")
                assert item["cover_image"].startswith("https://")
            else:
                assert "video_link" not in item
                assert "cover_image" not in item

    def test_the_capture_replays_to_the_expectation(self):
        expected = json.loads((MOCK_FIXTURES / "expected.json").read_text())
        extracted, report = replay(SOURCE, MOCK_FIXTURES)
        assert extracted == expected["extracted"]
        assert dict(report.skips) == expected["skips"]
        assert report.dead_paths() == []
        ads = extracted["ads"]["ad"].values()
        assert ads
        assert all({"last_seen", "url", "preview"} <= set(found) for found in ads)
        assert any("media" in found for found in ads)
        assert any("media" not in found for found in ads)


class TestTheRealCaptureAgreesWithTheStandIn:
    pytestmark = pytest.mark.skipif(
        not (FIXTURES / "real" / SOURCE).is_dir(),
        reason=f"no real capture under fixtures/real/{SOURCE}",
    )

    def test_the_ad_fields_the_hook_reads_have_one_type_on_both(self):
        real = key_types(payloads("real", "ads"))
        mock = key_types(payloads("mock", "ads"))
        for path in ADS_READ_PATHS:
            assert real[path] == mock[path], path

    def test_the_real_capture_is_trimmed_to_three(self):
        assert 1 <= len(payloads("real", "ads")) <= 3
