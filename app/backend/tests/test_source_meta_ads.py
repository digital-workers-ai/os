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

SOURCE = "meta_ads"
ENGINE = "meta_ad_library"
SEARCH = "/api/v1/search"
STATUS = "all"
SORT = "most_recent"
FIXTURES = checks.REAL_FIXTURES.parent
MOCK_FIXTURES = FIXTURES / "mock" / SOURCE
INGESTED = datetime(2026, 9, 14, tzinfo=UTC)
AD_ID = "1901999767451525"
HUBSPOT_PAGE = "6039999393"
ZOHO_PAGE = "231460215383"
FRESHSALES_PAGE = "300722220374123"
LIBRARY = "https://www.facebook.com/ads/library/?id="
BODY = (
    "With the free HubSpot connector, Claude conversations start with your "
    "customer context."
)
TITLE = "From Insight to Action"
LANDING = "https://www.hubspot.com/claude"
IMAGE = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.35426-6"
    "/825218234_1885787422120784_1095061145878185617_n.jpg"
    "?_nc_cat=105&ccb=1-7&_nc_sid=c53f8f&oh=00_AQIj8S2TJkqDP26qWMzM7uA2"
    "&oe=6ABE9DDF"
)
RESIZED = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.35426-6"
    "/821311463_2006501693402367_593500081087269488_n.jpg"
    "?stp=dst-jpg_s600x600_tt6&_nc_cat=103&oh=00_AQI2VPcqV7G3xt_OvAKG9HqquyYw"
    "&oe=6ABE7D5F"
)
PREVIEW = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.35426-6"
    "/795582314_1409876521330290_6904036856925862183_n.jpg"
    "?_nc_cat=110&ccb=1-7&_nc_sid=c53f8f&oh=00_AQLTNNI8yErlX0iA4Irv7LggGf4C"
    "&oe=6ABE7C5E"
)
HD = (
    "https://video-msp1-1.xx.fbcdn.net/o1/v/t2/f2/m366"
    "/AQOuJS36bubqGHH_p_QMUOwmjjGGDH-ev7SzrfcdfA60Lfv9d12mmsXfDRvcjFrHPj4U.mp4"
    "?_nc_cat=105&_nc_sid=b66105&oh=00_AQKqiMBfpBt4AlZuIX56NONCwKuEs2Fu"
    "&oe=6ABE9697"
)
SD = (
    "https://video-msp1-1.xx.fbcdn.net/o1/v/t2/f2/m412"
    "/AQOwpCWH_55ydDA7L6LxKhhljLIjxQ1Usd4qbZh4ki9e_-SG_dfBCPSLSvNEvBsxwiwY.mp4"
    "?_nc_cat=103&_nc_sid=ef5aa3&oh=00_AQJUS1w_kcbaPkmX8DJ7TyhGq0MKeyAhnx9P"
    "&oe=6ABE7B0F"
)
CARD = (
    "https://scontent-msp1-1.xx.fbcdn.net/v/t39.35426-6"
    "/803110021_1234567890123456_1122334455667788990_n.jpg"
    "?_nc_cat=107&ccb=1-7&_nc_sid=c53f8f&oh=00_AQKcardcardcardcardcardcard"
    "&oe=6ABE7A11"
)
ENV_COMMENT = "# linkedin_ads, tiktok_ads, meta_ads — https://www.searchapi.io"
ADS_READ_PATHS = (
    "request.company",
    "request.page_id",
    "ad.ad_archive_id",
    "ad.page_id",
    "ad.start_date",
    "ad.end_date",
    "ad.snapshot",
    "ad.snapshot.display_format",
    "ad.snapshot.body",
    "ad.snapshot.body.text",
    "ad.snapshot.title",
    "ad.snapshot.link_url",
    "ad.snapshot.images",
    "ad.snapshot.videos",
    "ad.snapshot.cards",
)
MAPPED = {
    ("ads", "_company", "company"),
    ("ads", "_platform", "platform"),
    ("ads", "_name", "name"),
    ("ads", "_category", "category"),
    ("ads", "_preview", "preview"),
    ("ads", "_media", "media"),
    ("ads", "ad.snapshot.link_url", "landing_url"),
    ("ads", "ad.start_date", "first_seen"),
    ("ads", "ad.end_date", "last_seen"),
    ("ads", "_url", "url"),
}


def connector():
    return registry.get(SOURCE)


def extract():
    return importlib.import_module(f"app.sources.{SOURCE}.extract")


def reshape(object_type, payload):
    return hooks.hooks()[SOURCE](object_type, payload)


def image():
    return {
        "original_image_url": IMAGE,
        "resized_image_url": RESIZED,
        "watermarked_resized_image_url": "",
    }


def video():
    return {
        "video_hd_url": HD,
        "video_preview_image_url": PREVIEW,
        "video_sd_url": SD,
    }


def ad(ad_id=AD_ID, fmt="IMAGE", page_id=HUBSPOT_PAGE, snapshot=None, **extra):
    creative = {
        "page_id": page_id,
        "page_name": "HubSpot",
        "caption": "hubspot.com/claude",
        "cta_text": "Learn more",
        "cta_type": "LEARN_MORE",
        "cards": [],
        "body": {"text": BODY},
        "display_format": fmt,
        "link_description": "Connect HubSpot & Claude.",
        "link_url": LANDING,
        "images": [] if fmt == "VIDEO" else [image()],
        "title": TITLE,
        "videos": [video()] if fmt == "VIDEO" else [],
    }
    creative.update(snapshot or {})
    item = {
        "ad_archive_id": ad_id,
        "is_active": True,
        "page_id": page_id,
        "page_name": "HubSpot",
        "currency": "",
        "start_date": "2026-09-25T07:00:00Z",
        "end_date": "2026-09-26T07:00:00Z",
        "publisher_platform": ["FACEBOOK", "INSTAGRAM", "THREADS"],
        "snapshot": creative,
    }
    item.update(extra)
    return item


def ads_page(ads, next_page_token=None):
    body = {
        "search_metadata": {"status": "Success"},
        "search_parameters": {
            "engine": ENGINE,
            "page_id": HUBSPOT_PAGE,
            "country": "US",
            "sort_by": SORT,
        },
        "search_information": {
            "total_results": 149,
            "page": {"name": "HubSpot", "id": HUBSPOT_PAGE},
        },
        "ads": list(ads),
    }
    if next_page_token:
        body["pagination"] = {"next_page_token": next_page_token}
    return body


def ad_payload(item=None, company="HubSpot", page_id=HUBSPOT_PAGE):
    return {
        "request": {"company": company, "page_id": page_id},
        "ad": item if item is not None else ad(),
    }


def payloads(fixture_class, name):
    path = FIXTURES / fixture_class / SOURCE / f"{name}.json"
    return [row["payload"] for row in json.loads(path.read_text())]


def definition_with(**pages):
    doc = spy.load()
    competitors = []
    for spec in doc["competitors"]:
        kept = {k: v for k, v in spec.items() if k != "meta_page_id"}
        if spec["name"] in pages:
            kept["meta_page_id"] = pages[spec["name"]]
        competitors.append(kept)
    return spy.parse({**doc, "competitors": competitors})


@pytest.fixture
def tracked(monkeypatch):
    def _install(**pages):
        definition = definition_with(**pages)
        monkeypatch.setattr(spy, "definition", lambda: definition)
        return definition

    return _install


@pytest.fixture
def hubspot_only(tracked):
    return tracked(HubSpot=HUBSPOT_PAGE)


@pytest.fixture
def library(monkeypatch):
    seen = []

    def _install(pages=None):
        by_page = pages or {}

        def handler(request):
            seen.append(request)
            params = request.url.params
            by_token = by_page.get(params.get("page_id"), {})
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


def asked(seen, page_id):
    return [r for r in seen if r.url.params.get("page_id") == page_id]


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
        assert module.OBSERVED_AT == {"ads": "ad.end_date"}

    def test_the_engine_the_cap_the_status_and_the_sort(self):
        module = connector()
        assert module.ENGINE == ENGINE
        assert module.PAGES_PER_PAGE == 2
        assert module.STATUS == STATUS
        assert module.SORT == SORT

    def test_the_search_path_is_shared_by_every_searchapi_source(self):
        assert importlib.import_module("app.sources.searchapi").SEARCH_PATH == SEARCH

    def test_the_registry_discovers_the_connector_and_its_hook(self):
        assert SOURCE in registry.discover()
        assert hooks.hooks()[SOURCE] is extract().reshape
        assert extract().PLATFORM == "meta"

    def test_the_catalog_lists_the_source_under_spy(self):
        assert catalog.entry(SOURCE) == {
            "source": SOURCE,
            "label": "Meta Ad Library",
            "category": "Spy",
            "unlocks": "Competitor creatives, copy, landing pages, platforms",
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

    def test_the_one_variable_is_shared_with_the_other_libraries_and_documented_once(
        self,
    ):
        assert creds._REAL[SOURCE][1] == ("SEARCHAPI_API_KEY",)
        assert creds._REAL[SOURCE] == creds._REAL["linkedin_ads"]
        assert creds._REAL[SOURCE] == creds._REAL["tiktok_ads"]
        assert documented_keys().count("SEARCHAPI_API_KEY") == 1
        assert ENV_COMMENT in ENV_EXAMPLE.read_text().splitlines()


class TestEveryPageIsAskedById:
    async def test_the_competitor_with_a_page_is_asked_in_the_country(
        self, library, save, hubspot_only
    ):
        seen = library()

        await connector().pull(None, save)

        assert [dict(r.url.params) for r in seen] == [
            {
                "engine": ENGINE,
                "page_id": HUBSPOT_PAGE,
                "country": "US",
                "active_status": STATUS,
                "sort_by": SORT,
            }
        ]
        for request in seen:
            assert request.method == "GET"
            assert request.url.path == SEARCH
            assert request.headers["Authorization"] == "Bearer mock_searchapi_key"

    async def test_the_shipped_definition_asks_every_competitor_in_order(
        self, library, save
    ):
        seen = library()

        await connector().pull(None, save)

        assert [r.url.params["page_id"] for r in seen] == [
            HUBSPOT_PAGE,
            ZOHO_PAGE,
            FRESHSALES_PAGE,
        ]

    async def test_a_competitor_without_a_page_is_not_asked(
        self, library, save, tracked
    ):
        tracked(**{"Zoho CRM": ZOHO_PAGE})
        seen = library()

        await connector().pull(None, save)

        assert [r.url.params["page_id"] for r in seen] == [ZOHO_PAGE]

    async def test_the_second_request_carries_the_token(
        self, library, save, stored, hubspot_only
    ):
        seen = library(
            {
                HUBSPOT_PAGE: {
                    None: ads_page([ad("1")], next_page_token="t2"),
                    "t2": ads_page([ad("2", "VIDEO")]),
                }
            }
        )

        notes = await connector().pull(None, save)

        hubspot = asked(seen, HUBSPOT_PAGE)
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert ids(stored) == ["1", "2"]
        assert notes is None

    async def test_only_two_pages_are_asked_and_the_page_is_noted(
        self, library, save, stored, hubspot_only
    ):
        seen = library({HUBSPOT_PAGE: pages("H", 3)})

        notes = await connector().pull(None, save)

        hubspot = asked(seen, HUBSPOT_PAGE)
        assert [r.url.params.get("next_page_token") for r in hubspot] == [None, "t2"]
        assert ids(stored) == ["H1", "H2"]
        assert notes == {"ads_capped": 1}

    async def test_a_walk_ending_on_its_last_allowed_page_is_not_noted(
        self, library, save, stored, hubspot_only
    ):
        library({HUBSPOT_PAGE: pages("H", 2)})

        notes = await connector().pull(None, save)

        assert ids(stored) == ["H1", "H2"]
        assert notes is None

    async def test_every_page_with_more_pages_counts(self, library, save, tracked):
        tracked(**{"HubSpot": HUBSPOT_PAGE, "Zoho CRM": ZOHO_PAGE})
        library({HUBSPOT_PAGE: pages("H", 3), ZOHO_PAGE: pages("Z", 3)})

        notes = await connector().pull(None, save)

        assert notes == {"ads_capped": 2}

    async def test_no_page_anywhere_asks_nothing_and_says_so(
        self, library, save, stored, tracked
    ):
        tracked()
        seen = library()

        notes = await connector().pull(None, save)

        assert seen == []
        assert stored == []
        assert notes == {"no_meta_pages": 1}


class TestAdsAreStoredWithTheirRequest:
    async def test_the_payload_wraps_the_ad_with_who_was_asked(
        self, library, save, stored, hubspot_only
    ):
        item = ad()
        library({HUBSPOT_PAGE: {None: ads_page([item])}})

        await connector().pull(None, save)

        assert stored == [
            {
                "source": SOURCE,
                "object_type": "ads",
                "source_id": AD_ID,
                "raw_payload": {
                    "request": {"company": "HubSpot", "page_id": HUBSPOT_PAGE},
                    "ad": item,
                },
            }
        ]

    async def test_an_ad_without_an_archive_id_is_counted(
        self, library, save, stored, hubspot_only
    ):
        nameless = {k: v for k, v in ad().items() if k != "ad_archive_id"}
        library({HUBSPOT_PAGE: {None: ads_page([nameless, ad("2")])}})

        notes = await connector().pull(None, save)

        assert ids(stored) == ["2"]
        assert notes == {"missing_id": 1}

    async def test_nothing_listed_means_nothing_stored_and_no_notes(
        self, library, save, stored, hubspot_only
    ):
        library()

        notes = await connector().pull(None, save)

        assert stored == []
        assert notes is None


class TestTheAdsHook:
    def test_a_known_page_becomes_its_company(self):
        (record,) = reshape("ads", ad_payload(company="Asked Co"))
        assert record["_company"] == "HubSpot"
        assert record["_platform"] == "meta"

    def test_an_unknown_page_falls_back_to_who_was_asked(self):
        payload = ad_payload(ad(page_id="1"), company="Asked Co", page_id="1")
        (record,) = reshape("ads", payload)
        assert record["_company"] == "Asked Co"

    def test_the_request_page_serves_when_the_ad_carries_none(self):
        payload = ad_payload(company="Asked Co")
        del payload["ad"]["page_id"]
        (record,) = reshape("ads", payload)
        assert record["_company"] == "HubSpot"

    def test_the_body_text_is_the_name(self):
        (record,) = reshape("ads", ad_payload())
        assert record["_name"] == BODY

    @pytest.mark.parametrize(
        "body", [{"text": ""}, {"text": None}, {"text": 5}, {}, "nope", None]
    )
    def test_a_body_without_text_falls_through_to_the_title(self, body):
        (record,) = reshape("ads", ad_payload(ad(snapshot={"body": body})))
        assert record["_name"] == TITLE

    def test_an_ad_without_a_body_falls_through_to_the_title(self):
        item = ad()
        del item["snapshot"]["body"]
        (record,) = reshape("ads", ad_payload(item))
        assert record["_name"] == TITLE

    @pytest.mark.parametrize("title", ["", None, 5])
    def test_neither_body_nor_title_means_no_name(self, title):
        item = ad(snapshot={"body": {"text": ""}, "title": title})
        (record,) = reshape("ads", ad_payload(item))
        assert "_name" not in record

    @pytest.mark.parametrize(
        ("fmt", "category"), [("IMAGE", "image"), ("VIDEO", "video")]
    )
    def test_the_display_format_is_lowercased(self, fmt, category):
        (record,) = reshape("ads", ad_payload(ad(fmt=fmt)))
        assert record["_category"] == category

    @pytest.mark.parametrize("fmt", ["", None, 5])
    def test_a_format_that_is_not_a_word_means_no_category(self, fmt):
        (record,) = reshape("ads", ad_payload(ad(fmt=fmt)))
        assert "_category" not in record

    def test_a_video_previews_its_preview_image(self):
        (record,) = reshape("ads", ad_payload(ad(fmt="VIDEO")))
        assert record["_preview"] == PREVIEW

    def test_an_image_previews_its_original(self):
        (record,) = reshape("ads", ad_payload(ad()))
        assert record["_preview"] == IMAGE

    def test_a_video_without_a_preview_falls_through_to_the_images(self):
        item = ad(
            fmt="VIDEO",
            snapshot={
                "videos": [{**video(), "video_preview_image_url": ""}],
                "images": [image()],
            },
        )
        (record,) = reshape("ads", ad_payload(item))
        assert record["_preview"] == IMAGE

    def test_a_card_previews_when_nothing_else_does(self):
        item = ad(
            snapshot={
                "videos": [],
                "images": [],
                "cards": [{"original_image_url": CARD, "title": "Card one"}],
            }
        )
        (record,) = reshape("ads", ad_payload(item))
        assert record["_preview"] == CARD

    def test_only_the_first_of_each_list_is_read(self):
        item = ad(
            snapshot={
                "videos": [{"video_preview_image_url": ""}, video()],
                "images": [{"original_image_url": ""}, image()],
                "cards": [{"original_image_url": ""}, {"original_image_url": CARD}],
            }
        )
        (record,) = reshape("ads", ad_payload(item))
        assert "_preview" not in record

    @pytest.mark.parametrize(
        "fields",
        [
            {"videos": [{}], "images": [{}], "cards": [{}]},
            {"videos": "nope", "images": "nope", "cards": "nope"},
            {"videos": [7], "images": [7], "cards": [7]},
            {
                "videos": [{"video_preview_image_url": 5}],
                "images": [{"original_image_url": 5}],
                "cards": [{"original_image_url": 5}],
            },
            {"videos": None, "images": None, "cards": None},
        ],
    )
    def test_nothing_usable_means_no_preview(self, fields):
        (record,) = reshape("ads", ad_payload(ad(snapshot=fields)))
        assert "_preview" not in record

    def test_a_snapshot_without_any_media_list_has_no_preview(self):
        item = ad()
        for key in ("videos", "images", "cards"):
            del item["snapshot"][key]
        (record,) = reshape("ads", ad_payload(item))
        assert "_preview" not in record

    def test_a_video_carries_its_hd_rendition(self):
        (record,) = reshape("ads", ad_payload(ad(fmt="VIDEO")))
        assert record["_media"] == HD

    @pytest.mark.parametrize("hd", ["", None, 7])
    def test_a_video_without_hd_carries_sd(self, hd):
        item = ad(fmt="VIDEO", snapshot={"videos": [{**video(), "video_hd_url": hd}]})
        (record,) = reshape("ads", ad_payload(item))
        assert record["_media"] == SD

    def test_a_video_missing_the_hd_key_carries_sd(self):
        item = ad(fmt="VIDEO")
        del item["snapshot"]["videos"][0]["video_hd_url"]
        (record,) = reshape("ads", ad_payload(item))
        assert record["_media"] == SD

    @pytest.mark.parametrize(
        "videos",
        [
            [],
            [{}],
            [{"video_hd_url": "", "video_sd_url": ""}],
            [{"video_hd_url": 7, "video_sd_url": None}],
            [7],
            "nope",
            None,
        ],
    )
    def test_an_ad_without_a_playable_video_has_no_media(self, videos):
        (record,) = reshape("ads", ad_payload(ad(snapshot={"videos": videos})))
        assert "_media" not in record

    def test_the_url_is_the_library_page(self):
        (record,) = reshape("ads", ad_payload())
        assert record["_url"] == f"{LIBRARY}{AD_ID}"

    @pytest.mark.parametrize("ad_id", ["", 7, None])
    def test_an_ad_without_a_string_id_has_no_url(self, ad_id):
        (record,) = reshape("ads", ad_payload(ad(ad_archive_id=ad_id)))
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
        assert record["_platform"] == "meta"
        for key in ("_name", "_category", "_preview", "_media", "_url"):
            assert key not in record

    def test_a_snapshot_that_is_not_a_mapping_never_raises(self):
        item = ad()
        item["snapshot"] = 7
        (record,) = reshape("ads", ad_payload(item))
        assert record["_company"] == "HubSpot"
        assert record["_url"] == f"{LIBRARY}{AD_ID}"
        for key in ("_name", "_category", "_preview", "_media"):
            assert key not in record

    def test_other_object_types_pass_through(self):
        payload = {"anything": 1}
        assert reshape("pages", payload) == [payload]


class TestWhenTheAdWasObserved:
    def test_a_listed_ad_is_dated_by_its_end_date(self):
        observed, which = observed_at_for(connector(), "ads", ad_payload(), INGESTED)
        assert which == "provider"
        assert observed == datetime(2026, 9, 26, 7, tzinfo=UTC)

    def test_an_ad_without_the_stamp_falls_back_to_ingestion(self):
        payload = ad_payload()
        del payload["ad"]["end_date"]
        observed, which = observed_at_for(connector(), "ads", payload, INGESTED)
        assert which == "ingested"
        assert observed == INGESTED


class TestTheDefinitions:
    def test_the_source_follows_tiktok_ads_in_priority(self):
        priority = ontology.load().source_priority
        assert priority.index(SOURCE) == priority.index("tiktok_ads") + 1

    def test_every_mapping_line_lands_on_the_ad(self):
        lines = [line for line in mappings.load() if line.source == SOURCE]
        assert {
            (line.object_type, ".".join(line.path), line.label) for line in lines
        } == MAPPED
        assert {line.entity for line in lines} == {"ad"}


class TestTheMappedFactsOnTheAd:
    def test_a_video_lands_its_media_its_preview_its_landing_and_its_dates(self):
        (entity,) = project("ads", ad_payload(ad(fmt="VIDEO")))
        assert entity.entity_type == "ad"
        assert entity.source_id == AD_ID
        assert facts(entity) == {
            "company": "HubSpot",
            "platform": "meta",
            "name": BODY,
            "category": "video",
            "preview": PREVIEW,
            "media": HD,
            "landing_url": LANDING,
            "first_seen": "2026-09-25T07:00:00Z",
            "last_seen": "2026-09-26T07:00:00Z",
            "url": f"{LIBRARY}{AD_ID}",
        }

    def test_an_image_lands_its_image_and_no_media(self):
        (entity,) = project("ads", ad_payload(ad()))
        assert facts(entity) == {
            "company": "HubSpot",
            "platform": "meta",
            "name": BODY,
            "category": "image",
            "preview": IMAGE,
            "landing_url": LANDING,
            "first_seen": "2026-09-25T07:00:00Z",
            "last_seen": "2026-09-26T07:00:00Z",
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
        formats = {payload["ad"]["snapshot"]["display_format"] for payload in ads}
        assert formats == {"IMAGE", "VIDEO"}
        for payload in ads:
            assert set(payload) == {"request", "ad"}
            company = by_name[payload["request"]["company"]]
            assert payload["request"]["page_id"] == company.meta_page_id
            item = payload["ad"]
            assert item["page_id"] == company.meta_page_id
            assert item["ad_archive_id"].isdigit()
            for stamp in ("start_date", "end_date"):
                datetime.fromisoformat(item[stamp].replace("Z", "+00:00"))
            creative = item["snapshot"]
            assert creative["body"]["text"]
            assert creative["link_url"].startswith("https://")
            if creative["display_format"] == "VIDEO":
                (clip,) = creative["videos"]
                assert clip["video_hd_url"].startswith("https://")
                assert clip["video_preview_image_url"].startswith("https://")
            else:
                (picture,) = creative["images"]
                assert picture["original_image_url"].startswith("https://")
                assert creative["videos"] == []

    def test_the_capture_replays_to_the_expectation(self):
        expected = json.loads((MOCK_FIXTURES / "expected.json").read_text())
        extracted, report = replay(SOURCE, MOCK_FIXTURES)
        assert extracted == expected["extracted"]
        assert dict(report.skips) == expected["skips"]
        assert report.dead_paths() == []
        ads = extracted["ads"]["ad"].values()
        assert ads
        assert all(
            {"name", "last_seen", "url", "preview", "landing_url"} <= set(found)
            for found in ads
        )
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
