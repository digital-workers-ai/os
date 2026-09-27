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
from tests.test_env_example import documented_keys
from tests.test_fixture_replay import replay
from tools.pull_source import key_types

SOURCE = "linkedin_ads"
ENGINE = "linkedin_ad_library"
DETAILS_ENGINE = "linkedin_ad_library_ad_details"
SEARCH = "/api/v1/search"
FIXTURES = checks.REAL_FIXTURES.parent
MOCK_FIXTURES = FIXTURES / "mock" / SOURCE
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
AD_ID = "1558385343"
COMPETITORS = ("HubSpot", "Zoho CRM", "Freshsales")
THUMBNAIL = (
    "https://media.licdn.com/dms/image/v2/C4D0BAQF8H-SLmMDZlA/company-logo_100_100"
    "/0/1646683330132/hubspot_logo?e=1792022400&v=beta"
)
IMAGE = (
    "https://media.licdn.com/dms/image/v2/D4D10AQEalS9qsVoVIw/image-shrink_1280"
    "/B4DaDK_CWYGYAc-/0/1790111917855/2png?e=2147483647&v=beta"
)
PAGES = [
    "https://media.licdn.com/dms/image/v2/D4E10AQHmI4hPKl01sg"
    "/ads-document-cover-images_480/B4EaCqoAGoIgAw-/0/1789569009480?e=2147483647",
    "https://media.licdn.com/dms/image/v2/D4E10AQHmI4hPKl01sg"
    "/ads-document-cover-images_480/B4EaCqoAGoIgAw-/1/1789569009480?e=2147483647",
]
LANDING = (
    "https://www.hubspot.com/startups/resources/gtm/founder-led-brand-toolkit"
    "?utm_campaign=HSFS&utm_source=linkedin&utm_medium=paid&hsa_ad=1558385343"
)
HEADLINE = (
    "Your messy notes are closer to a great post than you think. These free skills "
    "turn what's already in your head into poli…"
)
FULL_HEADLINE = (
    "Your messy notes are closer to a great post than you think. These free skills "
    "turn what's already in your head into polished, on-voice content."
)
CTA = "Raw notes in. Post-ready drafts out."
NO_RESULTS = "LinkedIn Ad Library didn't return any results."
ADS_READ_PATHS = (
    "request.company",
    "request.advertiser",
    "ad.id",
    "ad.ad_type",
    "ad.advertiser",
    "ad.advertiser.name",
    "ad.content",
    "ad.content.headline",
    "ad.link",
)
DETAILS_READ_PATHS = (
    "request.company",
    "request.ad_id",
    "ad.id",
    "ad.external_link",
    "ad.first_shown_date",
    "ad.last_shown_date",
)
MAPPED = {
    ("ads", "_company", "company"),
    ("ads", "_platform", "platform"),
    ("ads", "ad.ad_type", "category"),
    ("ads", "ad.content.headline", "name"),
    ("ads", "_preview", "preview"),
    ("ads", "ad.link", "url"),
    ("ad_details", "_company", "company"),
    ("ad_details", "_platform", "platform"),
    ("ad_details", "ad.first_shown_date", "first_seen"),
    ("ad_details", "ad.last_shown_date", "last_seen"),
    ("ad_details", "ad.external_link", "landing_url"),
}


def connector():
    return registry.get(SOURCE)


def extract():
    return importlib.import_module(f"app.sources.{SOURCE}.extract")


def token_page(pages=2, list_key="ads"):
    return importlib.import_module("app.sources.searchapi").TokenPage(list_key, pages)


def reshape(object_type, payload):
    return hooks.hooks()[SOURCE](object_type, payload)


def content(ad_type):
    if ad_type == "text":
        return {"headline": HEADLINE}
    if ad_type == "document":
        return {"headline": HEADLINE, "title": "Spotlight", "pages": list(PAGES)}
    return {"headline": HEADLINE, "image": IMAGE, "cta": CTA}


def ad(ad_id=AD_ID, ad_type="image", advertiser="HubSpot", **extra):
    item = {
        "position": 1,
        "advertiser": {"name": advertiser, "thumbnail": THUMBNAIL},
        "ad_type": ad_type,
        "content": content(ad_type),
        "link": f"https://www.linkedin.com/ad-library/detail/{ad_id}",
        "id": ad_id,
    }
    item.update(extra)
    return item


def ads_page(ads, next_page_token=None):
    body = {
        "search_metadata": {"status": "Success"},
        "search_parameters": {
            "engine": ENGINE,
            "advertiser": "HubSpot",
            "country": "US",
        },
        "search_information": {"total_results": 754},
        "ads": list(ads),
    }
    if next_page_token:
        body["pagination"] = {"next_page_token": next_page_token}
    return body


def no_results(engine=ENGINE):
    return {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": engine},
        "error": NO_RESULTS,
    }


def detail(ad_id=AD_ID, **overrides):
    body = {
        "id": ad_id,
        "link": f"https://www.linkedin.com/ad-library/detail/{ad_id}",
        "external_link": LANDING,
        "ad_type": "image",
        "ad_format": "Single Image Ad",
        "advertiser": {
            "name": "HubSpot",
            "thumbnail": THUMBNAIL,
            "link": "https://www.linkedin.com/company/68529?trk=ad_library_about_ad_advertiser",
        },
        "content": {
            "headline": FULL_HEADLINE,
            "image": IMAGE,
            "cta": CTA,
            "call_to_action": "Learn more",
        },
        "paid_for_by": "HubSpot, Inc.",
        "first_shown_date": "2026-09-24",
        "last_shown_date": "2026-09-26",
        "total_impressions": "< 1k",
        "total_impressions_max": 1000,
        "impressions_by_country": [
            {"country": "United States", "percentage": 47, "percentage_display": "47%"}
        ],
        "targeting": [{"name": "Language", "included": ["English"]}],
        "targeting_parameters": [
            {"name": "Audience", "is_targeted": True, "is_excluded": True}
        ],
    }
    body.update(overrides)
    return body


def details_page(ad_id=AD_ID, **overrides):
    return {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": DETAILS_ENGINE, "ad_id": ad_id},
        "ad": detail(ad_id, **overrides),
    }


def ad_payload(item=None, company="HubSpot"):
    return {
        "request": {"company": company, "advertiser": company},
        "ad": item if item is not None else ad(),
    }


def details_payload(ad_id=AD_ID, company="HubSpot", **overrides):
    return {
        "request": {"company": company, "ad_id": ad_id},
        "ad": detail(ad_id, **overrides),
    }


def payloads(fixture_class, name):
    path = FIXTURES / fixture_class / SOURCE / f"{name}.json"
    return [row["payload"] for row in json.loads(path.read_text())]


@pytest.fixture
def library(monkeypatch):
    seen = []

    def _install(pages=None, details=None):
        by_advertiser = pages or {}
        by_ad = details or {}

        def handler(request):
            seen.append(request)
            params = request.url.params
            if params.get("engine") == DETAILS_ENGINE:
                ad_id = params.get("ad_id")
                return httpx.Response(200, json=by_ad.get(ad_id, details_page(ad_id)))
            by_token = by_advertiser.get(params.get("advertiser"), {})
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
    return [r for r in seen if r.url.params.get("engine") == ENGINE]


def reads(seen):
    return [r for r in seen if r.url.params.get("engine") == DETAILS_ENGINE]


def of_type(stored, object_type):
    return [s for s in stored if s["object_type"] == object_type]


def ids(stored, object_type):
    return [s["source_id"] for s in of_type(stored, object_type)]


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


class TestTheConstantsTheContractNames:
    def test_the_source_and_the_observation_path(self):
        module = connector()
        assert module.SOURCE == SOURCE
        assert module.OBSERVED_AT == {"ad_details": "ad.last_shown_date"}

    def test_the_two_engines_and_the_caps(self):
        module = connector()
        assert module.ENGINE == ENGINE
        assert module.DETAILS_ENGINE == DETAILS_ENGINE
        assert module.PAGES_PER_ADVERTISER == 2
        assert module.DETAILS_PER_PULL == 50

    def test_the_search_path_is_shared_by_every_searchapi_source(self):
        assert importlib.import_module("app.sources.searchapi").SEARCH_PATH == SEARCH

    def test_the_registry_discovers_the_connector_and_its_hook(self):
        assert SOURCE in registry.discover()
        assert hooks.hooks()[SOURCE] is extract().reshape
        assert extract().PLATFORM == "linkedin"

    def test_the_catalog_lists_the_source_under_spy(self):
        assert catalog.entry(SOURCE) == {
            "source": SOURCE,
            "label": "LinkedIn Ad Library",
            "category": "Spy",
            "unlocks": "Competitor creatives, copy, landing pages",
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

    def test_the_one_variable_the_source_reads_is_documented(self):
        assert creds._REAL[SOURCE][1] == ("SEARCHAPI_API_KEY",)
        assert "SEARCHAPI_API_KEY" in documented_keys()


class TestTheTokenPageReadsSearchApiPages:
    def test_the_records_are_the_list_under_the_callers_key(self):
        page = ads_page([ad("1"), ad("2")])
        assert [a["id"] for a in token_page().extract(page)] == ["1", "2"]
        assert token_page(list_key="items").extract({"items": [{"n": 1}]}) == [{"n": 1}]

    def test_the_documented_no_results_shape_is_an_empty_page(self):
        assert token_page().extract(no_results()) == []

    @pytest.mark.parametrize("body", ["not an object", {"ads": "nope"}])
    def test_an_alien_body_is_an_empty_page(self, body):
        assert token_page().extract(body) == []

    def test_the_next_page_token_becomes_the_next_request(self):
        page = ads_page([], next_page_token="MTU1MjU0MTY2My0xNzg5NTkxOTYzMzg2")
        params = {"engine": ENGINE, "advertiser": "HubSpot", "country": "US"}
        assert token_page().next_params(page, params) == {
            **params,
            "next_page_token": "MTU1MjU0MTY2My0xNzg5NTkxOTYzMzg2",
        }

    @pytest.mark.parametrize(
        "body",
        [
            ads_page([]),
            no_results(),
            {**ads_page([]), "pagination": "nope"},
            {**ads_page([]), "pagination": {"next_page_token": ""}},
            "not an object",
        ],
    )
    def test_no_token_ends_the_walk(self, body):
        walk = token_page()
        assert walk.next_params(body, {"country": "US"}) is None
        assert walk.more is False

    def test_a_token_after_the_last_allowed_page_ends_the_walk_and_says_so(self):
        walk = token_page()
        page = ads_page([], next_page_token="t2")
        assert walk.next_params(page, {"country": "US"}) == {
            "country": "US",
            "next_page_token": "t2",
        }
        capped = walk.next_params(page, {"country": "US", "next_page_token": "t2"})
        assert capped is None
        assert walk.more is True

    def test_a_walk_ending_on_its_last_allowed_page_is_not_more(self):
        walk = token_page()
        walk.next_params(ads_page([], next_page_token="t2"), {"country": "US"})
        assert walk.next_params(ads_page([]), {"country": "US"}) is None
        assert walk.more is False


class TestEveryCompetitorIsAskedByName:
    async def test_the_three_competitors_are_asked_once_each_in_the_country(
        self, library, save
    ):
        seen = library()

        await connector().pull(None, save)

        assert [dict(r.url.params) for r in searches(seen)] == [
            {"engine": ENGINE, "advertiser": name, "country": "US"}
            for name in COMPETITORS
        ]
        for request in seen:
            assert request.method == "GET"
            assert request.url.path == SEARCH
            assert request.headers["Authorization"] == "Bearer mock_searchapi_key"

    async def test_the_second_request_carries_the_token(self, library, save, stored):
        seen = library(
            {
                "HubSpot": {
                    None: ads_page([ad("1")], next_page_token="t2"),
                    "t2": ads_page([ad("2", "video")]),
                }
            }
        )

        notes = await connector().pull(None, save)

        hubspot = [r for r in searches(seen) if r.url.params["advertiser"] == "HubSpot"]
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert ids(stored, "ads") == ["1", "2"]
        assert "ads_capped" not in notes

    @staticmethod
    def _three_pages(prefix):
        return {
            None: ads_page([ad(f"{prefix}1")], next_page_token="t2"),
            "t2": ads_page([ad(f"{prefix}2")], next_page_token="t3"),
            "t3": ads_page([ad(f"{prefix}3")]),
        }

    async def test_only_two_pages_are_asked_and_the_advertiser_is_noted(
        self, library, save, stored
    ):
        seen = library({"HubSpot": self._three_pages("H")})

        notes = await connector().pull(None, save)

        hubspot = [r for r in searches(seen) if r.url.params["advertiser"] == "HubSpot"]
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert ids(stored, "ads") == ["H1", "H2"]
        assert notes["ads_capped"] == 1

    async def test_every_advertiser_with_more_pages_counts(self, library, save):
        library({"HubSpot": self._three_pages("H"), "Zoho CRM": self._three_pages("Z")})

        notes = await connector().pull(None, save)

        assert notes["ads_capped"] == 2


class TestAdsAreStoredWithTheirRequest:
    async def test_the_payload_wraps_the_ad_with_who_was_asked(
        self, library, save, stored
    ):
        item = ad()
        library({"HubSpot": {None: ads_page([item])}})

        await connector().pull(None, save)

        assert of_type(stored, "ads") == [
            {
                "source": SOURCE,
                "object_type": "ads",
                "source_id": AD_ID,
                "raw_payload": {
                    "request": {"company": "HubSpot", "advertiser": "HubSpot"},
                    "ad": item,
                },
            }
        ]

    async def test_an_ad_without_an_id_is_counted_and_not_read(
        self, library, save, stored
    ):
        nameless = {k: v for k, v in ad().items() if k != "id"}
        seen = library({"HubSpot": {None: ads_page([nameless, ad("2")])}})

        notes = await connector().pull(None, save)

        assert ids(stored, "ads") == ["2"]
        assert notes["missing_id"] == 1
        assert [r.url.params["ad_id"] for r in reads(seen)] == ["2"]

    async def test_an_ad_from_another_advertiser_is_dropped_and_never_read(
        self, library, save, stored
    ):
        seen = library(
            {
                "HubSpot": {
                    None: ads_page(
                        [ad("1552511793", "text", advertiser="Yamini Rangan"), ad()]
                    )
                }
            }
        )

        notes = await connector().pull(None, save)

        assert ids(stored, "ads") == [AD_ID]
        assert [r.url.params["ad_id"] for r in reads(seen)] == [AD_ID]
        assert notes == {"ads_foreign_advertiser": 1, "ad_details_read": 1}

    @pytest.mark.parametrize(
        "asked,spelled", [("HubSpot", "hubspot crm"), ("Zoho CRM", "ZOHO")]
    )
    async def test_an_alias_in_any_case_is_the_same_advertiser(
        self, library, save, stored, asked, spelled
    ):
        library({asked: {None: ads_page([ad("1", advertiser=spelled)])}})

        notes = await connector().pull(None, save)

        assert ids(stored, "ads") == ["1"]
        assert "ads_foreign_advertiser" not in notes

    async def test_nothing_listed_means_nothing_stored_and_no_notes(
        self, library, save, stored
    ):
        seen = library()

        notes = await connector().pull(None, save)

        assert stored == []
        assert reads(seen) == []
        assert notes is None


class TestTheDetailsFollowTheAds:
    async def test_each_kept_ad_is_read_once_by_id(self, library, save):
        seen = library({"HubSpot": {None: ads_page([ad("1"), ad("2", "document")])}})

        await connector().pull(None, save)

        assert [dict(r.url.params) for r in reads(seen)] == [
            {"engine": DETAILS_ENGINE, "ad_id": "1"},
            {"engine": DETAILS_ENGINE, "ad_id": "2"},
        ]
        for request in reads(seen):
            assert request.url.path == SEARCH

    async def test_the_details_are_stored_under_the_ad_with_its_request(
        self, library, save, stored
    ):
        library({"HubSpot": {None: ads_page([ad()])}})

        await connector().pull(None, save)

        assert of_type(stored, "ad_details") == [
            {
                "source": SOURCE,
                "object_type": "ad_details",
                "source_id": AD_ID,
                "raw_payload": {
                    "request": {"company": "HubSpot", "ad_id": AD_ID},
                    "ad": detail(),
                },
            }
        ]

    async def test_the_reads_are_counted(self, library, save):
        library({"HubSpot": {None: ads_page([ad("1"), ad("2")])}})

        notes = await connector().pull(None, save)

        assert notes == {"ad_details_read": 2}

    async def test_an_ad_already_read_is_skipped_and_counted(
        self, library, save, monkeypatch
    ):
        seen = library({"HubSpot": {None: ads_page([ad("1"), ad("2")])}})
        asked = []

        async def already(session, source, object_type):
            asked.append((session, source, object_type))
            return {"1"}

        monkeypatch.setattr(connector(), "stored_ids", already)

        notes = await connector().pull("the session", save)

        assert asked == [("the session", SOURCE, "ad_details")]
        assert [r.url.params["ad_id"] for r in reads(seen)] == ["2"]
        assert notes == {"ad_details_read": 1, "ad_details_skipped": 1}

    async def test_the_cap_holds_and_the_overflow_is_counted(
        self, library, save, monkeypatch
    ):
        seen = library({"HubSpot": {None: ads_page([ad(str(n)) for n in range(5)])}})
        monkeypatch.setattr(connector(), "DETAILS_PER_PULL", 2)

        notes = await connector().pull(None, save)

        assert [r.url.params["ad_id"] for r in reads(seen)] == ["0", "1"]
        assert notes == {"ad_details_read": 2, "ad_details_capped": 3}

    async def test_an_answer_without_an_ad_is_counted_and_not_stored(
        self, library, save, stored
    ):
        library(
            {"HubSpot": {None: ads_page([ad("1"), ad("2")])}},
            {"1": no_results(DETAILS_ENGINE)},
        )

        notes = await connector().pull(None, save)

        assert ids(stored, "ad_details") == ["2"]
        assert notes == {"ad_details_read": 1, "ad_details_missing": 1}


class TestTheAdsHook:
    def test_the_company_and_the_platform_come_from_the_request(self):
        (record,) = reshape("ads", ad_payload(company="Zoho CRM"))
        assert record["_company"] == "Zoho CRM"
        assert record["_platform"] == "linkedin"

    def test_an_image_previews_its_image(self):
        (record,) = reshape("ads", ad_payload(ad()))
        assert record["_preview"] == IMAGE

    def test_a_video_previews_its_cover(self):
        (record,) = reshape("ads", ad_payload(ad(ad_type="video")))
        assert record["_preview"] == IMAGE

    def test_a_document_previews_its_first_page(self):
        (record,) = reshape("ads", ad_payload(ad(ad_type="document")))
        assert record["_preview"] == PAGES[0]

    def test_a_text_ad_has_no_preview(self):
        (record,) = reshape("ads", ad_payload(ad(ad_type="text")))
        assert "_preview" not in record

    def test_a_blank_image_falls_through_to_the_pages(self):
        item = ad(content={"headline": HEADLINE, "image": "", "pages": PAGES})
        (record,) = reshape("ads", ad_payload(item))
        assert record["_preview"] == PAGES[0]

    @pytest.mark.parametrize(
        "body",
        [
            {"image": ""},
            {"image": 5},
            {"pages": []},
            {"pages": "nope"},
            {"pages": [7]},
            "nope",
        ],
    )
    def test_nothing_usable_means_no_preview(self, body):
        (record,) = reshape("ads", ad_payload(ad(content=body)))
        assert "_preview" not in record

    def test_the_rest_of_the_payload_survives_unmutated(self):
        payload = ad_payload()
        (record,) = reshape("ads", payload)
        assert record["ad"] == payload["ad"]
        assert record["request"] == payload["request"]
        assert set(payload) == {"request", "ad"}

    def test_an_ad_that_is_not_a_mapping_never_raises(self):
        (record,) = reshape("ads", {"request": {"company": "HubSpot"}, "ad": "nope"})
        assert record["_company"] == "HubSpot"
        assert record["_platform"] == "linkedin"
        assert "_preview" not in record


class TestTheDetailsHook:
    def test_the_company_and_the_platform_are_stamped(self):
        payload = details_payload(company="Freshsales")
        (record,) = reshape("ad_details", payload)
        assert record == {**payload, "_platform": "linkedin", "_company": "Freshsales"}

    def test_other_object_types_pass_through(self):
        payload = {"anything": 1}
        assert reshape("advertisers", payload) == [payload]


class TestTheObservationComesFromLastShown:
    def test_the_details_date_themselves_from_the_provider(self):
        observed, which = observed_at_for(
            connector(), "ad_details", details_payload(), INGESTED
        )
        assert which == "provider"
        assert observed == datetime(2026, 9, 26, tzinfo=UTC)

    def test_details_without_the_stamp_fall_back_to_ingestion(self):
        payload = details_payload()
        del payload["ad"]["last_shown_date"]
        observed, which = observed_at_for(connector(), "ad_details", payload, INGESTED)
        assert which == "ingested"
        assert observed == INGESTED

    def test_a_listed_ad_is_dated_by_ingestion(self):
        observed, which = observed_at_for(connector(), "ads", ad_payload(), INGESTED)
        assert which == "ingested"


class TestTheDefinitions:
    def test_the_landing_url_is_declared_on_the_ad_and_glossed(self):
        onto = ontology.load()
        assert onto.entities["ad"].attrs["landing_url"] == "string"
        assert (
            onto.attributes["landing_url"].description
            == "Where a click on the creative lands."
        )

    def test_the_source_follows_google_ads_transparency_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) == priority.index("google_ads_transparency") + 1

    def test_every_mapping_line_lands_on_the_ad(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {
            (line.object_type, ".".join(line.path), line.label) for line in lines
        } == MAPPED
        assert {line.entity for line in lines} == {"ad"}


class TestTheMappedFactsOnTheAd:
    def test_a_listed_ad_lands_its_copy_its_preview_and_its_library_link(self):
        (entity,) = project("ads", ad_payload())
        assert entity.entity_type == "ad"
        assert entity.source_id == AD_ID
        assert {attr: fact.value for attr, fact in entity.facts.items()} == {
            "company": "HubSpot",
            "platform": "linkedin",
            "category": "image",
            "name": HEADLINE,
            "preview": IMAGE,
            "url": f"https://www.linkedin.com/ad-library/detail/{AD_ID}",
        }

    def test_a_document_lands_its_first_page_as_the_preview(self):
        (entity,) = project("ads", ad_payload(ad(ad_type="document")))
        assert entity.facts["preview"].value == PAGES[0]
        assert entity.facts["category"].value == "document"

    def test_the_details_land_the_dates_and_the_landing_url(self):
        (entity,) = project("ad_details", details_payload())
        assert entity.entity_type == "ad"
        assert entity.source_id == AD_ID
        assert {attr: fact.value for attr, fact in entity.facts.items()} == {
            "company": "HubSpot",
            "platform": "linkedin",
            "first_seen": "2026-09-24T00:00:00Z",
            "last_seen": "2026-09-26T00:00:00Z",
            "landing_url": LANDING,
        }


class TestTheStandInFixtureCarriesTheRealShapes:
    def test_the_capture_holds_the_ads_the_details_and_the_expectation(self):
        assert sorted(p.name for p in MOCK_FIXTURES.iterdir()) == [
            "ad_details.json",
            "ads.json",
            "expected.json",
        ]

    def test_every_ad_is_wrapped_with_who_was_asked_and_belongs_to_them(self):
        by_name = {company.name: company for company in spy.definition().competitors}
        ads = payloads("mock", "ads")
        assert ads
        for payload in ads:
            assert set(payload) == {"request", "ad"}
            company = by_name[payload["request"]["company"]]
            assert payload["request"]["advertiser"] == company.name
            assert payload["ad"]["advertiser"]["name"].lower() in {
                name.lower() for name in company.names
            }
            assert payload["ad"]["ad_type"] in {"image", "video", "text", "document"}
            assert payload["ad"]["id"]
            assert payload["ad"]["link"].startswith(
                "https://www.linkedin.com/ad-library/detail/"
            )

    def test_every_detail_carries_its_dates_and_a_landing(self):
        details = payloads("mock", "ad_details")
        assert details
        for payload in details:
            assert set(payload) == {"request", "ad"}
            assert payload["request"]["ad_id"] == payload["ad"]["id"]
            assert payload["ad"]["external_link"].startswith("https://")
            for stamp in ("first_shown_date", "last_shown_date"):
                datetime.strptime(payload["ad"][stamp], "%Y-%m-%d").replace(tzinfo=UTC)

    def test_the_capture_replays_to_the_expectation(self):
        expected = json.loads((MOCK_FIXTURES / "expected.json").read_text())
        extracted, report = replay(SOURCE, MOCK_FIXTURES)
        assert extracted == expected["extracted"]
        assert dict(report.skips) == expected["skips"]
        assert report.dead_paths() == []
        details = extracted["ad_details"]["ad"].values()
        assert details
        assert all("landing_url" in facts for facts in details)


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

    def test_the_detail_fields_the_mappings_read_have_one_type_on_both(self):
        real = key_types(payloads("real", "ad_details"))
        mock = key_types(payloads("mock", "ad_details"))
        for path in DETAILS_READ_PATHS:
            assert real[path] == mock[path], path

    @pytest.mark.parametrize("name", ["ads", "ad_details"])
    def test_the_real_capture_is_trimmed_to_three(self, name):
        assert 1 <= len(payloads("real", name)) <= 3
