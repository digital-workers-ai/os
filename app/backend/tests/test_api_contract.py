import os

import httpx
import pytest
import schemathesis
from hypothesis import HealthCheck, settings

BASE_URL = os.environ.get("OS_SELF_URL", "http://localhost:8000")

EXCLUDED = {
    ("POST", "/api/sync"),
    ("POST", "/api/rebuild"),
    ("POST", "/api/metrics/snapshots"),
    ("POST", "/api/enrichment/run"),
    ("POST", "/api/coaching/{role}"),
    ("POST", "/api/conversation"),
    ("POST", "/api/conversation/conversations"),
}


def _serving() -> bool:
    try:
        return httpx.get(f"{BASE_URL}/api/health", timeout=3).status_code == 200
    except Exception:
        return False


if not _serving():
    pytest.skip(f"no service at {BASE_URL}", allow_module_level=True)

pytestmark = pytest.mark.e2e

schema = schemathesis.openapi.from_url(f"{BASE_URL}/openapi.json")


def test_every_write_operation_is_excluded():
    declared = set()
    for operation in schema.get_all_operations():
        result = operation.ok()
        if result.method.upper() != "GET":
            declared.add((result.method.upper(), result.path))
    unlisted = declared - EXCLUDED
    assert not unlisted, f"write operations missing from EXCLUDED: {unlisted}"


@schema.parametrize()
@settings(max_examples=20, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_no_route_returns_a_server_error_or_breaks_its_own_schema(case):
    if (case.method.upper(), case.path) in EXCLUDED:
        pytest.skip("writes to the database this suite is pointed at")
    response = case.call()
    assert response.status_code < 500, (
        f"{case.method} {case.path} -> {response.status_code}"
    )
    case.validate_response(
        response, excluded_checks=[schemathesis.checks.positive_data_acceptance]
    )
