import base64
import gzip
import importlib
import io
import json
import sys
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pytest
from starlette.requests import Request

from app.caches import BACKEND_DIR
from tests import ground_truth

PROVIDER = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers" / "amplitude.py"
FIXTURES = BACKEND_DIR / "fixtures" / "mock" / "amplitude"

CREDENTIALS = base64.b64encode(b"mock_amplitude_key:mock_amplitude_secret").decode()

GONE_FROM_THE_EXPORT = ("insert_id", "browser", "browser_version")

EXPORT_TIME_FORMAT = "%Y-%m-%d %H:%M:%S.%f"

EXPORT_COLUMNS = frozenset(
    {
        "$insert_id",
        "$insert_key",
        "$schema",
        "adid",
        "amplitude_attribution_ids",
        "amplitude_event_type",
        "amplitude_id",
        "app",
        "city",
        "client_event_time",
        "client_upload_time",
        "country",
        "data",
        "data_type",
        "device_brand",
        "device_carrier",
        "device_family",
        "device_id",
        "device_manufacturer",
        "device_model",
        "device_type",
        "dma",
        "event_id",
        "event_properties",
        "event_time",
        "event_type",
        "global_user_properties",
        "group_properties",
        "groups",
        "idfa",
        "ip_address",
        "is_attribution_event",
        "language",
        "library",
        "location_lat",
        "location_lng",
        "os_name",
        "os_version",
        "partner_id",
        "paying",
        "plan",
        "platform",
        "processed_time",
        "region",
        "sample_rate",
        "server_received_time",
        "server_upload_time",
        "session_id",
        "source_id",
        "start_version",
        "user_creation_time",
        "user_id",
        "user_properties",
        "uuid",
        "version_name",
    }
)

NULL_ON_EVERY_ROW = (
    "$insert_key",
    "$schema",
    "adid",
    "amplitude_attribution_ids",
    "amplitude_event_type",
    "device_brand",
    "device_carrier",
    "device_manufacturer",
    "device_model",
    "dma",
    "global_user_properties",
    "idfa",
    "is_attribution_event",
    "location_lat",
    "location_lng",
    "partner_id",
    "sample_rate",
    "source_id",
    "start_version",
    "user_creation_time",
    "version_name",
)

DERIVED_FROM_THE_EVENT_TIME = (
    "client_event_time",
    "client_upload_time",
    "server_received_time",
    "server_upload_time",
    "processed_time",
)

AMPLITUDE_DEFINED_CONTAINERS = ("data", "group_properties", "groups", "plan")


@pytest.fixture(scope="module")
def provider():
    if not PROVIDER.is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.amplitude")


def request_for(path):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [(b"authorization", f"Basic {CREDENTIALS}".encode())],
            "scheme": "http",
            "server": ("mock", 8100),
            "root_path": "",
        }
    )


async def export(provider):
    return await provider.export_events(
        request_for("/api/2/export"), start="20260607T00", end="20260904T23"
    )


def members(response):
    with zipfile.ZipFile(io.BytesIO(response.body)) as bundle:
        return {name: bundle.read(name) for name in bundle.namelist()}


def events(response):
    rows = []
    for raw in members(response).values():
        text = gzip.decompress(raw).decode()
        rows.extend(json.loads(line) for line in text.split("\n") if line.strip())
    return rows


def fixture_events():
    records = json.loads((FIXTURES / "events.json").read_text())
    return [record["payload"] for record in records]


def moment(stamp):
    return datetime.strptime(stamp, EXPORT_TIME_FORMAT).replace(tzinfo=UTC)


class TestTheExportIsAnArchiveNotPlainText:
    async def test_the_content_type_is_a_zip(self, provider):
        assert (await export(provider)).media_type == "application/zip"

    async def test_the_body_is_a_readable_zip_archive(self, provider):
        assert members(await export(provider))

    async def test_every_member_is_a_gzipped_json_file(self, provider):
        for name, raw in members(await export(provider)).items():
            assert name.endswith(".json.gz")
            assert raw[:2] == b"\x1f\x8b"

    async def test_the_member_sits_under_a_project_directory(self, provider):
        for name in members(await export(provider)):
            assert "/" in name

    async def test_the_unpacked_member_is_newline_delimited_json(self, provider):
        assert len(events(await export(provider))) > 1


class TestTheEventCarriesTheFieldsTheExportReallyHas:
    async def test_every_event_carries_a_dollar_prefixed_insert_id(self, provider):
        for event in events(await export(provider)):
            assert event["$insert_id"]

    async def test_every_event_carries_a_uuid(self, provider):
        for event in events(await export(provider)):
            assert event["uuid"]

    async def test_no_event_carries_a_field_the_export_does_not_have(self, provider):
        for event in events(await export(provider)):
            for field in GONE_FROM_THE_EXPORT:
                assert field not in event

    async def test_every_event_carries_the_timestamp_observed_at_names(self, provider):
        for event in events(await export(provider)):
            assert event["event_time"]

    async def test_every_event_keeps_the_email_the_mapping_reads(self, provider):
        for event in events(await export(provider)):
            assert "email" in event["user_properties"]


class TestTheCapturedFixturesCarryTheSameShape:
    def test_every_fixture_event_carries_a_dollar_prefixed_insert_id(self):
        records = json.loads((FIXTURES / "events.json").read_text())
        assert records
        for record in records:
            assert record["payload"]["$insert_id"]

    def test_every_fixture_event_carries_a_uuid(self):
        records = json.loads((FIXTURES / "events.json").read_text())
        for record in records:
            assert record["payload"]["uuid"]

    def test_no_fixture_event_carries_a_field_the_export_does_not_have(self):
        records = json.loads((FIXTURES / "events.json").read_text())
        for record in records:
            for field in GONE_FROM_THE_EXPORT:
                assert field not in record["payload"]

    def test_the_fixture_is_keyed_by_the_id_the_connector_reads(self):
        records = json.loads((FIXTURES / "events.json").read_text())
        for record in records:
            assert record["source_id"] == record["payload"]["$insert_id"]


class TestEveryRowIsTheWholeAmplitudeColumnSet:
    async def test_a_served_event_carries_every_column_and_no_other(self, provider):
        for event in events(await export(provider)):
            assert set(event) == EXPORT_COLUMNS

    async def test_the_served_events_do_not_differ_in_shape(self, provider):
        assert len({frozenset(e) for e in events(await export(provider))}) == 1

    def test_a_fixture_event_carries_every_column_and_no_other(self):
        for payload in fixture_events():
            assert set(payload) == EXPORT_COLUMNS


class TestTheDerivedTimestampsTrackTheEventTime:
    async def test_every_timestamp_reads_in_the_one_export_format(self, provider):
        for event in events(await export(provider)):
            for column in ("event_time", *DERIVED_FROM_THE_EVENT_TIME):
                assert moment(event[column])

    async def test_no_derived_timestamp_precedes_the_event(self, provider):
        for event in events(await export(provider)):
            at = moment(event["event_time"])
            for column in DERIVED_FROM_THE_EVENT_TIME:
                assert moment(event[column]) >= at

    async def test_the_client_clock_reads_the_event_moment_itself(self, provider):
        for event in events(await export(provider)):
            assert event["client_event_time"] == event["event_time"]

    async def test_the_stamps_run_client_then_server_then_processed(self, provider):
        for event in events(await export(provider)):
            stamps = [moment(event[c]) for c in DERIVED_FROM_THE_EVENT_TIME]
            assert stamps == sorted(stamps)

    async def test_each_lag_is_fixed_rather_than_clocked(self, provider):
        served = events(await export(provider))
        for column in DERIVED_FROM_THE_EVENT_TIME:
            lags = {moment(e[column]) - moment(e["event_time"]) for e in served}
            assert len(lags) == 1

    def test_a_fixture_event_keeps_the_same_ordering(self):
        for payload in fixture_events():
            at = moment(payload["event_time"])
            for column in DERIVED_FROM_THE_EVENT_TIME:
                assert moment(payload[column]) >= at


class TestAnAbsentValueIsNullRatherThanAMissingKey:
    async def test_the_columns_with_nothing_to_report_are_null(self, provider):
        for event in events(await export(provider)):
            assert [event[c] for c in NULL_ON_EVERY_ROW] == [None] * len(
                NULL_ON_EVERY_ROW
            )

    async def test_no_other_column_is_null(self, provider):
        for event in events(await export(provider)):
            assert {c for c, v in event.items() if v is None} == set(NULL_ON_EVERY_ROW)

    def test_a_fixture_event_carries_the_same_nulls(self):
        for payload in fixture_events():
            empty = {c for c, v in payload.items() if v is None}
            assert empty == set(NULL_ON_EVERY_ROW)


class TestTheContainerColumnsAreObjects:
    async def test_the_amplitude_defined_containers_are_dicts(self, provider):
        for event in events(await export(provider)):
            for column in AMPLITUDE_DEFINED_CONTAINERS:
                assert isinstance(event[column], dict)

    async def test_the_containers_a_project_without_accounts_has_are_empty(
        self, provider
    ):
        for event in events(await export(provider)):
            assert event["groups"] == {}
            assert event["group_properties"] == {}
            assert event["plan"] == {}

    async def test_the_ingest_metadata_names_the_path_the_event_arrived_on(
        self, provider
    ):
        for event in events(await export(provider)):
            assert event["data"]["path"] == provider.INGEST_PATH

    async def test_the_customer_defined_property_bags_are_dicts(self, provider):
        for event in events(await export(provider)):
            assert isinstance(event["event_properties"], dict)
            assert isinstance(event["user_properties"], dict)

    def test_a_fixture_event_carries_the_same_containers(self):
        for payload in fixture_events():
            for column in AMPLITUDE_DEFINED_CONTAINERS:
                assert isinstance(payload[column], dict)
