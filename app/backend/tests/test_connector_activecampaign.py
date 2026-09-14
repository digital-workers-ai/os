import importlib
import json
import sys
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import pytest
from starlette.requests import Request

from app.engine import checks, mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import registry
from app.sources.activecampaign import extract
from app.sources.paginators import Offset
from tools.pull_source import json_type

FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "activecampaign"
SEEDS_ROOT = "/adversarial"
ACCOUNT_HOST = "https://acme.api-us1.com"

LIVE_CONTACT = {
    "accountContacts": "list",
    "adate": "null",
    "anonymized": "string",
    "best_send_hour": "null",
    "bounced_date": "null",
    "bounced_hard": "string",
    "bounced_soft": "string",
    "cdate": "string",
    "created_by": "null",
    "created_timestamp": "string",
    "created_utc_timestamp": "string",
    "deleted": "string",
    "deleted_at": "null",
    "edate": "null",
    "email": "string",
    "email_domain": "string",
    "email_local": "string",
    "firstName": "string",
    "gravatar": "string",
    "hash": "string",
    "id": "string",
    "ip": "string",
    "lastName": "string",
    "last_click_date": "null",
    "last_mpp_open_date": "null",
    "last_open_date": "null",
    "links": "object",
    "mpp_tracking": "string",
    "organization": "null",
    "orgid": "string",
    "orgname": "string",
    "phone": "string",
    "rating_tstamp": "null",
    "scoreValues": "list",
    "segmentio_id": "string",
    "sentcnt": "string",
    "sms_consent": "null",
    "sms_consent_updated_at": "null",
    "socialdata_lastcheck": "null",
    "ua": "null",
    "udate": "string",
    "updated_by": "null",
    "updated_timestamp": "string",
    "updated_utc_timestamp": "string",
    "whatsapp_id": "null",
    "whatsapp_username": "null",
}

LIVE_CONTACT_LINKS = (
    "accountContacts",
    "automationEntryCounts",
    "bounceLogs",
    "contactAutomations",
    "contactData",
    "contactDeals",
    "contactGoals",
    "contactLists",
    "contactLogs",
    "contactTags",
    "deals",
    "fieldValues",
    "geoIps",
    "notes",
    "organization",
    "plusAppend",
    "scoreValues",
    "trackingLogs",
)

LIVE_CONTACTS_ENVELOPE = ("contacts", "meta", "scoreValues")


def payloads(name: str) -> list[dict]:
    return [
        row["payload"] for row in json.loads((FIXTURES / f"{name}.json").read_text())
    ]


def shape(payload: dict) -> dict:
    return {key: json_type(value) for key, value in payload.items()}


def project(payload: dict):
    report = SyncReport()
    entities = pipeline.project_payload(
        source="activecampaign",
        object_type="contacts",
        source_id=payload["id"],
        payload=payload,
        raw_event_id=None,
        ingested_at=datetime(2026, 9, 14, tzinfo=UTC),
        seq=1,
        onto=ontology.load(),
        line_index=mappings.by_object(mappings.load()),
        transform_map=transforms.load_map(),
        report=report,
        connector_module=registry.get("activecampaign"),
    )
    return entities, report


def provider():
    if not Path(f"{SEEDS_ROOT}/seeds/providers/activecampaign.py").is_file():
        pytest.skip(f"mock provider not mounted at {SEEDS_ROOT}")
    if SEEDS_ROOT not in sys.path:
        sys.path.insert(0, SEEDS_ROOT)
    return importlib.import_module("seeds.providers.activecampaign")


def a_request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/3/contacts",
            "query_string": b"",
            "headers": [(b"api-token", b"mock_ac_token")],
        }
    )


@pytest.fixture
def mock_provider():
    return provider()


@pytest.fixture
def a_mock_contact(mock_provider):
    return mock_provider._ac_contact(mock_provider.PEOPLE[0], 0)


@pytest.fixture
def a_nameless_mock_contact(mock_provider):
    person = replace(mock_provider.PEOPLE[0], first_name="", last_name="")
    return mock_provider._ac_contact(person, 0)


class TestTheContactFixtureCarriesTheShapeTheAccountReturns:
    def test_every_field_the_account_returns_is_present(self):
        for payload in payloads("contacts"):
            assert set(LIVE_CONTACT) <= set(payload), payload["id"]

    def test_no_field_the_account_never_returned_is_invented(self):
        for payload in payloads("contacts"):
            assert set(payload) <= set(LIVE_CONTACT), payload["id"]

    def test_every_field_has_the_type_the_account_returned(self):
        for payload in payloads("contacts"):
            assert shape(payload) == LIVE_CONTACT, payload["id"]

    def test_the_records_agree_on_one_field_set(self):
        assert len({tuple(sorted(p)) for p in payloads("contacts")}) == 1


class TestTheContactLinks:
    def test_every_sub_resource_the_account_links_is_linked(self):
        for payload in payloads("contacts"):
            assert tuple(sorted(payload["links"])) == LIVE_CONTACT_LINKS

    def test_each_link_is_an_absolute_url_on_the_account_host(self):
        for payload in payloads("contacts"):
            for target in payload["links"].values():
                assert target.startswith(f"{ACCOUNT_HOST}/api/3/contacts/")

    def test_each_link_names_the_contact_it_belongs_to(self):
        for payload in payloads("contacts"):
            prefix = f"{ACCOUNT_HOST}/api/3/contacts/{payload['id']}/"
            for name, target in payload["links"].items():
                assert target == f"{prefix}{name}"


class TestTheCampaignLinks:
    def test_each_link_is_an_absolute_url_on_the_account_host(self):
        for payload in payloads("campaigns"):
            for target in payload["links"].values():
                assert target.startswith(f"{ACCOUNT_HOST}/api/3/campaigns/")

    def test_each_link_names_the_campaign_it_belongs_to(self):
        for payload in payloads("campaigns"):
            prefix = f"{ACCOUNT_HOST}/api/3/campaigns/{payload['id']}/"
            for name, target in payload["links"].items():
                assert target == f"{prefix}{name}"


class TestTheFieldsTheConnectorObserves:
    def test_a_contact_carries_the_udate_the_connector_reads(self):
        for payload in payloads("contacts"):
            assert json_type(payload["udate"]) == "string"

    def test_a_campaign_carries_the_mdate_the_connector_reads(self):
        for payload in payloads("campaigns"):
            assert json_type(payload["mdate"]) == "string"


class TestTheContactsEnvelope:
    def test_the_paginator_reads_contacts_past_the_third_key(self):
        body = {
            "scoreValues": [],
            "contacts": [{"id": "1"}],
            "meta": {"total": "1", "sortable": True},
        }
        assert Offset("contacts", count_param="limit").extract(body) == [{"id": "1"}]

    def test_a_short_page_ends_the_walk_despite_the_nested_string_total(self):
        body = {
            "scoreValues": [],
            "contacts": [{"id": "1"}],
            "meta": {"total": "2450"},
        }
        paginator = Offset("contacts", count_param="limit")
        assert paginator.next_params(body, {"limit": 8, "offset": 0}) is None

    def test_a_full_page_walks_on_by_the_page_length(self):
        body = {
            "scoreValues": [],
            "contacts": [{"id": str(n)} for n in range(8)],
            "meta": {"total": "2450"},
        }
        paginator = Offset("contacts", count_param="limit")
        assert paginator.next_params(body, {"limit": 8, "offset": 0}) == {
            "limit": 8,
            "offset": 8,
        }


class TestTheMockServesWhatTheFixtureRecords:
    def test_a_contact_has_the_shape_the_account_returns(self, a_mock_contact):
        assert shape(a_mock_contact) == LIVE_CONTACT

    def test_a_contact_links_every_sub_resource(self, a_mock_contact):
        assert tuple(sorted(a_mock_contact["links"])) == LIVE_CONTACT_LINKS

    async def test_the_contacts_response_carries_the_third_top_level_key(
        self, mock_provider
    ):
        body = await mock_provider.list_contacts(a_request(), limit=8, offset=0)
        assert tuple(sorted(body)) == LIVE_CONTACTS_ENVELOPE

    async def test_the_third_top_level_key_is_a_list(self, mock_provider):
        body = await mock_provider.list_contacts(a_request(), limit=8, offset=0)
        assert body["scoreValues"] == []

    async def test_the_served_contacts_have_the_shape_the_account_returns(
        self, mock_provider
    ):
        body = await mock_provider.list_contacts(a_request(), limit=8, offset=0)
        assert body["contacts"]
        for contact in body["contacts"]:
            assert shape(contact) == LIVE_CONTACT


class TestACampaignThatWasNeverSent:
    def test_the_mock_sends_null_rather_than_an_empty_string(self, mock_provider):
        unsent = [c for c in mock_provider.EMAIL_CAMPAIGNS if not c.sent_at]
        assert unsent
        for index, campaign in enumerate(unsent):
            assert mock_provider._ac_campaign(campaign, index)["sdate"] is None

    def test_the_fixture_records_a_campaign_that_was_never_sent(self):
        assert any(p["sdate"] is None for p in payloads("campaigns"))

    def test_a_sent_campaign_still_carries_its_send_date(self):
        sent = [p for p in payloads("campaigns") if p["sdate"] is not None]
        assert sent
        for payload in sent:
            assert json_type(payload["sdate"]) == "string"

    def test_a_campaign_that_was_never_sent_still_carries_a_modified_date(self):
        for payload in payloads("campaigns"):
            assert json_type(payload["mdate"]) == "string"


class TestWhatAnUnsentCampaignProjectsTo:
    def expected(self) -> dict:
        return json.loads((FIXTURES / "expected.json").read_text())

    def test_the_send_date_is_cleared_rather_than_left_off(self):
        campaigns = self.expected()["extracted"]["campaigns"]["email_campaign"]
        unsent = [c for c in campaigns.values() if c.get("sent_at", "") is None]
        assert len(unsent) == 1

    def test_the_cleared_send_date_is_counted_as_a_clear(self):
        assert self.expected()["clears"]["sent_at/activecampaign"] == 1

    def test_the_unsent_campaign_still_projects_its_name_and_its_counts(self):
        campaigns = self.expected()["extracted"]["campaigns"]["email_campaign"]
        unsent = next(c for c in campaigns.values() if c.get("sent_at", "") is None)
        assert set(unsent) == {"clicks", "name", "opens", "sends", "sent_at"}

    def test_no_campaign_is_skipped(self):
        assert self.expected()["skips"] == {}


class TestTheNameTheHookComposes:
    def test_both_parts_make_the_whole_name(self):
        out = extract.reshape("contacts", {"firstName": "Jane", "lastName": "Smith"})
        assert out[0]["_full_name"] == "Jane Smith"

    def test_one_part_is_the_whole_name(self):
        out = extract.reshape("contacts", {"firstName": "Jane", "lastName": ""})
        assert out[0]["_full_name"] == "Jane"

    def test_neither_part_leaves_the_key_present_with_nothing_in_it(self):
        out = extract.reshape("contacts", {"firstName": "", "lastName": ""})
        assert out[0]["_full_name"] is None

    def test_the_stored_payload_is_not_touched(self):
        payload = {"firstName": "", "lastName": ""}
        extract.reshape("contacts", payload)
        assert payload == {"firstName": "", "lastName": ""}

    def test_a_campaign_passes_through(self):
        payload = {"id": "1", "name": "July Newsletter"}
        assert extract.reshape("campaigns", payload) == [payload]


class TestAContactTheAccountNeverNamed:
    def test_both_name_fields_come_back_empty_rather_than_absent(
        self, a_nameless_mock_contact
    ):
        assert a_nameless_mock_contact["firstName"] == ""
        assert a_nameless_mock_contact["lastName"] == ""

    def test_such_a_contact_still_has_the_shape_the_account_returns(
        self, a_nameless_mock_contact
    ):
        assert shape(a_nameless_mock_contact) == LIVE_CONTACT

    def test_the_hook_carries_the_name_key_with_nothing_in_it(
        self, a_nameless_mock_contact
    ):
        out = extract.reshape("contacts", a_nameless_mock_contact)
        assert out[0]["_full_name"] is None

    def test_the_name_mapping_is_hit_rather_than_dead(self, a_nameless_mock_contact):
        _entities, report = project(a_nameless_mock_contact)
        assert report.dead_paths() == []

    def test_the_name_is_cleared_rather_than_left_off(self, a_nameless_mock_contact):
        _entities, report = project(a_nameless_mock_contact)
        assert report.clears["name/activecampaign"] == 1

    def test_the_contact_is_still_accepted_with_the_rest_of_itself(
        self, a_nameless_mock_contact
    ):
        entities, _report = project(a_nameless_mock_contact)
        facts = {attr: fact.value for attr, fact in entities[0].facts.items()}
        assert facts["name"] is None
        assert facts["email"] == a_nameless_mock_contact["email"]

    def test_half_a_name_is_the_whole_name(self, mock_provider):
        person = replace(mock_provider.PEOPLE[0], last_name="")
        out = extract.reshape("contacts", mock_provider._ac_contact(person, 0))
        assert out[0]["_full_name"] == person.first_name

    def test_a_named_contact_still_composes_both_parts(
        self, mock_provider, a_mock_contact
    ):
        person = mock_provider.PEOPLE[0]
        out = extract.reshape("contacts", a_mock_contact)
        assert out[0]["_full_name"] == f"{person.first_name} {person.last_name}"

    def test_a_named_contact_clears_nothing(self, a_mock_contact):
        _entities, report = project(a_mock_contact)
        assert "name/activecampaign" not in report.clears
