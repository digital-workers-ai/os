import json

import pytest

from app.engine import checks
from app.sources import paginators
from app.sources.klaviyo import connector

KLAVIYO = checks.REAL_FIXTURES.parent / "mock" / "klaviyo"

RECORD_KEYS = {"attributes", "id", "links", "relationships", "type"}

PROFILE_ATTRIBUTES = {
    "anonymous_id",
    "created",
    "email",
    "external_id",
    "first_name",
    "image",
    "last_event_date",
    "last_name",
    "locale",
    "location",
    "organization",
    "phone_number",
    "properties",
    "title",
    "updated",
    "whatsapp_bsuid",
}

LOCATION_KEYS = {
    "address1",
    "address2",
    "city",
    "country",
    "ip",
    "latitude",
    "longitude",
    "region",
    "timezone",
    "zip",
}

PROFILE_RELATIONSHIPS = {"conversation", "lists", "push-tokens", "segments"}

PROFILE_PROPERTIES = {
    "$consent",
    "$consent_timestamp",
    "$phone_number_region",
    "$source",
}

ADDITIONAL_FIELDS_ONLY = ("predictive_analytics", "subscriptions")

FLOW_ATTRIBUTES = {"archived", "created", "name", "status", "trigger_type", "updated"}

FLOW_RELATIONSHIPS = {"flow-actions", "tags"}


def payloads(name):
    rows = json.loads((KLAVIYO / f"{name}.json").read_text())
    return [row["payload"] for row in rows]


def kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "list" if isinstance(value, list) else "object"


def kinds_at(records, *path):
    seen = set()
    for record in records:
        value = record["attributes"]
        for segment in path:
            value = value[segment]
        seen.add(kind(value))
    return seen


class TestTheProfileSampleCarriesWhatTheLiveEnvelopeCarries:
    def test_every_record_is_a_json_api_resource(self):
        for record in payloads("profiles"):
            assert set(record) == RECORD_KEYS
            assert record["type"] == "profile"

    def test_every_profile_carries_the_live_attribute_set(self):
        for record in payloads("profiles"):
            assert set(record["attributes"]) == PROFILE_ATTRIBUTES

    @pytest.mark.parametrize("block", ADDITIONAL_FIELDS_ONLY)
    def test_no_profile_carries_a_block_the_pull_never_asks_for(self, block):
        for record in payloads("profiles"):
            assert block not in record["attributes"]

    def test_every_location_carries_the_live_key_set(self):
        for record in payloads("profiles"):
            assert set(record["attributes"]["location"]) == LOCATION_KEYS

    def test_every_profile_carries_the_live_relationships(self):
        for record in payloads("profiles"):
            assert set(record["relationships"]) == PROFILE_RELATIONSHIPS
            for related in record["relationships"].values():
                assert set(related["links"]) == {"related", "self"}

    def test_the_freeform_properties_span_the_live_keys(self):
        seen: set = set()
        for record in payloads("profiles"):
            seen |= set(record["attributes"]["properties"])
        assert seen == PROFILE_PROPERTIES

    @pytest.mark.parametrize(
        "path, expected",
        [
            (("anonymous_id",), {"null"}),
            (("created",), {"string"}),
            (("email",), {"string"}),
            (("external_id",), {"null"}),
            (("first_name",), {"string"}),
            (("image",), {"null"}),
            (("last_event_date",), {"string"}),
            (("last_name",), {"null", "string"}),
            (("locale",), {"null"}),
            (("organization",), {"null"}),
            (("phone_number",), {"null", "string"}),
            (("title",), {"null"}),
            (("updated",), {"string"}),
            (("whatsapp_bsuid",), {"null"}),
            (("location", "address1"), {"null"}),
            (("location", "address2"), {"null"}),
            (("location", "city"), {"null", "string"}),
            (("location", "country"), {"null", "string"}),
            (("location", "ip"), {"null", "string"}),
            (("location", "latitude"), {"null", "number"}),
            (("location", "longitude"), {"null", "number"}),
            (("location", "region"), {"null", "string"}),
            (("location", "timezone"), {"null", "string"}),
            (("location", "zip"), {"null"}),
        ],
    )
    def test_the_sample_spans_the_nullability_the_live_account_shows(
        self, path, expected
    ):
        assert kinds_at(payloads("profiles"), *path) == expected

    @pytest.mark.parametrize(
        "name, expected",
        [
            ("$consent", "list"),
            ("$consent_timestamp", "string"),
            ("$phone_number_region", "null"),
            ("$source", "number"),
        ],
    )
    def test_each_freeform_property_holds_the_live_type(self, name, expected):
        seen = {
            kind(record["attributes"]["properties"][name])
            for record in payloads("profiles")
            if name in record["attributes"]["properties"]
        }
        assert seen == {expected}


class TestTheFlowSampleCarriesWhatTheLiveEnvelopeCarries:
    def test_every_record_is_a_json_api_resource(self):
        for record in payloads("flows"):
            assert set(record) == RECORD_KEYS
            assert record["type"] == "flow"

    def test_every_flow_carries_the_live_attribute_set(self):
        for record in payloads("flows"):
            assert set(record["attributes"]) == FLOW_ATTRIBUTES

    def test_every_flow_carries_the_live_relationships(self):
        for record in payloads("flows"):
            assert set(record["relationships"]) == FLOW_RELATIONSHIPS
            for related in record["relationships"].values():
                assert set(related["links"]) == {"related", "self"}


class TestObservedAtReadsAPathEveryRecordCarries:
    def test_both_object_types_date_themselves_by_attributes_updated(self):
        assert connector.OBSERVED_AT == {
            "profiles": "attributes.updated",
            "flows": "attributes.updated",
        }

    @pytest.mark.parametrize("name", ["profiles", "flows"])
    def test_every_record_carries_that_path(self, name):
        for record in payloads(name):
            assert isinstance(record["attributes"]["updated"], str)


class TestTheCursorWalksTheLiveEnvelope:
    def test_the_records_come_out_of_the_data_list(self):
        envelope = {
            "data": [{"id": "kl_prof_p1"}],
            "links": {"self": "/api/profiles", "next": None, "prev": None},
        }
        assert paginators.resolve("cursor_klaviyo").extract(envelope) == [
            {"id": "kl_prof_p1"}
        ]

    def test_a_null_next_link_ends_the_walk(self):
        envelope = {
            "data": [],
            "links": {"self": "/api/profiles", "next": None, "prev": None},
        }
        cursor = paginators.resolve("cursor_klaviyo")
        assert cursor.next_params(envelope, {"page[size]": 8}) is None
