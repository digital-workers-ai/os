import importlib
import json
import sys
from pathlib import Path

import pytest
from starlette.requests import Request

from app.engine import checks
from tests import ground_truth

PROVIDER = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers" / "intercom.py"
FIXTURES = checks.REAL_FIXTURES.parent / "mock" / "intercom"


@pytest.fixture(scope="module")
def provider():
    if not PROVIDER.is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.intercom")


def request_for(path):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer mock_intercom_token"),
                (b"intercom-version", b"2.10"),
            ],
            "scheme": "http",
            "server": ("mock", 8100),
            "root_path": "",
        }
    )


async def contacts(provider):
    body = await provider.list_contacts(
        request_for("/intercom/contacts"), starting_after=None, per_page=150
    )
    return {row["id"]: row for row in body["data"]}


async def conversations(provider):
    body = await provider.list_conversations(
        request_for("/intercom/conversations"), starting_after=None, per_page=150
    )
    return {row["id"]: row for row in body["conversations"]}


def fixture(name):
    rows = json.loads((FIXTURES / f"{name}.json").read_text())
    return {row["source_id"]: row["payload"] for row in rows}


class TestTheFixturesAreWhatTheStandInServes:
    async def test_every_fixture_contact_is_the_payload_the_stand_in_returns(
        self, provider
    ):
        served = await contacts(provider)
        assert {k: served.get(k) for k in fixture("contacts")} == fixture("contacts")

    async def test_every_fixture_conversation_is_the_payload_the_stand_in_returns(
        self, provider
    ):
        served = await conversations(provider)
        assert {k: served.get(k) for k in fixture("conversations")} == fixture(
            "conversations"
        )


class TestAContactCarriesOnlyWhatTheApiReturns:
    async def test_custom_attributes_are_empty_rather_than_invented(self, provider):
        served = await contacts(provider)
        assert {json.dumps(c["custom_attributes"]) for c in served.values()} == {"{}"}

    async def test_the_company_mini_list_names_no_company(self, provider):
        served = await contacts(provider)
        keys = {
            tuple(sorted(row))
            for c in served.values()
            for row in c["companies"]["data"]
        }
        assert keys == {("id", "type", "url")}

    async def test_the_fields_a_workspace_never_filled_are_null(self, provider):
        served = await contacts(provider)
        for contact in served.values():
            assert contact["browser"] is None
            assert contact["browser_version"] is None
            assert contact["os"] is None
            assert contact["referrer"] is None
            assert set(contact["location"]) == {
                "type",
                "city",
                "country",
                "country_code",
                "region",
                "continent_code",
            }
            assert [v for k, v in contact["location"].items() if k != "type"] == [
                None
            ] * 5

    async def test_the_mini_lists_carry_their_url(self, provider):
        served = await contacts(provider)
        contact = served["con_p3"]
        for name in ("tags", "notes", "companies"):
            assert contact[name]["url"] == f"/contacts/con_p3/{name}"


class TestAConversationComesInBothShapes:
    async def test_a_messenger_conversation_has_no_source_part(self, provider):
        served = await conversations(provider)
        conversation = served["conv_t1"]
        assert conversation["source"] is None
        assert conversation["title"] is None
        assert conversation["first_contact_reply"] is None
        assert conversation["admin_assignee_id"] is None
        assert conversation["statistics"]["time_to_admin_reply"] is None
        assert conversation["statistics"]["time_to_assignment"] is None
        assert conversation["statistics"]["time_to_first_close"] is None

    async def test_an_email_conversation_carries_its_author(self, provider):
        served = await conversations(provider)
        conversation = served["conv_t5"]
        assert conversation["source"]["author"]["email"] == "tony@stark.io"
        assert conversation["title"] == "Payment method declined"
        assert conversation["statistics"]["time_to_admin_reply"] == 300

    async def test_both_shapes_carry_the_same_keys(self, provider):
        served = await conversations(provider)
        assert set(served["conv_t1"]) == set(served["conv_t5"])
        assert set(served["conv_t1"]["statistics"]) == set(
            served["conv_t5"]["statistics"]
        )

    async def test_the_workspace_attributes_are_the_ones_a_workspace_returns(
        self, provider
    ):
        served = await conversations(provider)
        assert set(served["conv_t1"]["custom_attributes"]) == {
            "Auto-translated",
            "Copilot used",
            "Fin AI Agent: Image used in reply",
            "Fin AI Agent: Preview",
            "Fin awaiting teammate input",
            "Has attachments",
            "Imported via standalone",
            "SDR Success Counted",
        }
