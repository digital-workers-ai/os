import base64
import gzip
import importlib
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest
from starlette.requests import Request

from app.caches import BACKEND_DIR
from tests import ground_truth

PROVIDER = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers" / "amplitude.py"
FIXTURES = BACKEND_DIR / "fixtures" / "mock" / "amplitude"

CREDENTIALS = base64.b64encode(b"mock_amplitude_key:mock_amplitude_secret").decode()

GONE_FROM_THE_EXPORT = ("insert_id", "browser", "browser_version")


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
