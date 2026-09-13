import json

import httpx
import pytest

from app.config import settings
from app.engine import checks
from app.sources import client
from tools import pull_source

MOCK = checks.REAL_FIXTURES.parent / "mock" / "hubspot"
PULLS = ("contacts", "companies", "deals")
TOKEN = "pat-test-0000"


def fixture_payloads(name: str) -> list[dict]:
    return [row["payload"] for row in json.loads((MOCK / f"{name}.json").read_text())]


@pytest.fixture
def served(monkeypatch):
    payloads = {name: fixture_payloads(name) for name in PULLS}
    seen: list[httpx.Request] = []

    def handler(request):
        seen.append(request)
        name = request.url.path.rsplit("/", 1)[-1]
        rows = payloads[name]
        if name != "contacts":
            return httpx.Response(200, json={"results": rows, "paging": {}})
        if request.url.params.get("after"):
            return httpx.Response(200, json={"results": rows[2:], "paging": {}})
        return httpx.Response(
            200,
            json={"results": rows[:2], "paging": {"next": {"after": "page-two"}}},
        )

    monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
    for name in ("HUBSPOT_ACCESS_TOKEN", "HUBSPOT_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    return payloads, seen


class TestTheReport:
    async def test_each_pull_reports_requests_records_and_accepted(self, served):
        text, code = await pull_source.report("hubspot")
        assert "contacts: requests=2 records=4 accepted=4" in text
        assert "companies: requests=1 records=4 accepted=4" in text
        assert "deals: requests=1 records=4 accepted=4" in text
        assert code == 0

    async def test_the_header_names_the_source_and_where_it_pulled_from(self, served):
        text, _code = await pull_source.report("hubspot")
        assert text.splitlines()[0] == f"hubspot: {settings.MOCK_BASE_URL}/hubspot"

    async def test_the_mock_shape_leaves_no_dead_path_and_no_skip(self, served):
        text, code = await pull_source.report("hubspot")
        assert text.count("  dead paths: none") == 3
        assert text.count("  skips: none") == 3
        assert "compare:" not in text
        assert code == 0

    async def test_a_path_no_record_carries_is_dead_and_fails_the_run(self, served):
        payloads, _seen = served
        for row in payloads["companies"]:
            del row["properties"]["industry"]
        text, code = await pull_source.report("hubspot")
        assert "  dead paths: company:hubspot.companies.properties.industry" in text
        assert code == 1

    async def test_skips_are_counted_by_reason(self, served):
        payloads, _seen = served
        payloads["deals"][0]["properties"]["amount"] = "lots"
        payloads["deals"][1]["properties"]["amount"] = "many"
        payloads["deals"][2]["properties"]["closedate"] = "someday"
        payloads["contacts"][0]["properties"] = {"email": "not-an-email"}
        text, code = await pull_source.report("hubspot")
        assert (
            "  skips: amount/hubspot/not_a_number=2, closed_at/hubspot/not_a_date=1"
            in text
        )
        assert (
            "  skips: email/hubspot/not_an_email=1, hubspot/contacts/no_facts/person=1"
            in text
        )
        assert "contacts: requests=2 records=4 accepted=3" in text
        assert code == 0

    async def test_a_pull_that_returns_nothing_lists_every_mapped_path_as_dead(
        self, served
    ):
        payloads, _seen = served
        for name in PULLS:
            payloads[name].clear()
        text, code = await pull_source.report("hubspot")
        assert "contacts: requests=0 records=0 accepted=0" in text
        assert (
            "  dead paths: person:hubspot.contacts._full_name, "
            "person:hubspot.contacts.properties.email" in text
        )
        assert "unattributed requests: 4" in text
        assert code == 1

    async def test_records_the_connector_could_not_key_appear_as_notes(self, served):
        payloads, _seen = served
        del payloads["deals"][0]["id"]
        text, _code = await pull_source.report("hubspot")
        assert "deals: requests=1 records=3 accepted=3" in text
        assert "notes: missing_id=1" in text


class TestCapture:
    async def test_writes_one_file_per_pull_in_the_mock_layout(self, served, tmp_path):
        text, code = await pull_source.report("hubspot", capture=tmp_path)
        for name in PULLS:
            written = json.loads((tmp_path / "hubspot" / f"{name}.json").read_text())
            assert written == json.loads((MOCK / f"{name}.json").read_text())
        assert f"captured: {tmp_path / 'hubspot'}" in text
        assert code == 0

    async def test_a_pull_with_nothing_still_gets_an_empty_file(self, served, tmp_path):
        payloads, _seen = served
        payloads["deals"].clear()
        await pull_source.report("hubspot", capture=tmp_path)
        assert json.loads((tmp_path / "hubspot" / "deals.json").read_text()) == []

    def test_the_flag_alone_targets_the_real_fixture_dir(
        self, served, tmp_path, monkeypatch, capsys
    ):
        monkeypatch.setattr(checks, "REAL_FIXTURES", tmp_path / "real")
        code = pull_source.main(["hubspot", "--capture"])
        assert (tmp_path / "real" / "hubspot" / "contacts.json").exists()
        assert "contacts: requests=2 records=4 accepted=4" in capsys.readouterr().out
        assert code == 0


class TestCompare:
    async def test_agreeing_shapes_report_no_difference(self, served):
        text, code = await pull_source.report("hubspot", compare=True)
        assert (
            text.count(
                "  compare: only in real: none; only in mock: none; "
                "type mismatches: none"
            )
            == 3
        )
        assert code == 0

    async def test_an_injected_difference_is_reported_by_kind_and_fails(self, served):
        payloads, _seen = served
        for row in payloads["contacts"]:
            row["properties"]["extra"] = "x"
            del row["properties"]["company"]
            row["properties"]["lifecyclestage"] = 3
        text, code = await pull_source.report("hubspot", compare=True)
        assert (
            "  compare: only in real: properties.extra; "
            "only in mock: properties.company; "
            "type mismatches: properties.lifecyclestage real=number mock=string" in text
        )
        assert code == 1

    async def test_a_null_in_one_record_widens_the_real_type(self, served):
        payloads, _seen = served
        payloads["companies"][0]["properties"]["industry"] = None
        text, code = await pull_source.report("hubspot", compare=True)
        assert "properties.industry real=null|string mock=string" in text
        assert code == 1

    async def test_nested_objects_and_lists_of_objects_are_walked(self, served):
        payloads, _seen = served
        payloads["deals"][0]["associations"] = {
            "companies": [{"id": "c1", "type": "deal_to_company"}],
            "count": 1,
        }
        text, _code = await pull_source.report("hubspot", compare=True)
        assert (
            "only in real: associations, associations.companies, "
            "associations.companies[].id, associations.companies[].type, "
            "associations.count;" in text
        )

    async def test_a_pull_with_no_mock_fixture_is_a_difference(
        self, served, monkeypatch, tmp_path
    ):
        monkeypatch.setattr(pull_source, "MOCK_FIXTURES", tmp_path)
        text, code = await pull_source.report("hubspot", compare=True)
        expected = tmp_path / "hubspot" / "contacts.json"
        assert f"  compare: no mock fixture at {expected}" in text
        assert code == 1


class TestNothingSecretIsPrinted:
    async def test_the_real_token_reaches_the_api_but_never_the_output(
        self, served, monkeypatch
    ):
        _payloads, seen = served
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        text, code = await pull_source.report("hubspot", compare=True)
        assert seen
        assert all(r.headers["Authorization"] == f"Bearer {TOKEN}" for r in seen)
        assert all(str(r.url).startswith("https://api.hubapi.com/") for r in seen)
        assert text.splitlines()[0] == "hubspot: https://api.hubapi.com"
        assert TOKEN not in text
        assert "Bearer" not in text
        assert code == 0

    async def test_a_base_url_override_is_printed_without_its_query(
        self, served, monkeypatch
    ):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        monkeypatch.setenv("HUBSPOT_BASE_URL", "https://hubspot.example.test/v3?k=shh")
        text, _code = await pull_source.report("hubspot")
        assert text.splitlines()[0] == "hubspot: https://hubspot.example.test/v3"
        assert "shh" not in text

    async def test_a_failing_request_is_reported_without_its_headers(
        self, served, monkeypatch
    ):
        monkeypatch.setenv("HUBSPOT_ACCESS_TOKEN", TOKEN)
        monkeypatch.setattr(
            client,
            "_transport",
            httpx.MockTransport(lambda request: httpx.Response(401, json={})),
        )
        text, code = await pull_source.report("hubspot")
        assert (
            "error: ConnectorError: [hubspot] HTTP 401 from "
            "https://api.hubapi.com/crm/v3/objects/contacts" in text
        )
        assert "contacts: requests=0 records=0 accepted=0" in text
        assert TOKEN not in text
        assert code == 1


class TestTheCommandLine:
    def test_an_unknown_source_is_refused_before_anything_runs(self, capsys):
        with pytest.raises(SystemExit) as stop:
            pull_source.main(["nope"])
        assert stop.value.code == 2
        assert "nope" in capsys.readouterr().err

    def test_the_exit_code_follows_the_report(self, served, capsys):
        payloads, _seen = served
        for row in payloads["companies"]:
            del row["properties"]["industry"]
        assert pull_source.main(["hubspot"]) == 1
        out = capsys.readouterr().out
        assert "  dead paths: company:hubspot.companies.properties.industry" in out
