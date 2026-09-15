import importlib
import json
import sys
from pathlib import Path

import pytest
from starlette.requests import Request

from tests import ground_truth

PROVIDERS = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "providers"
PROVIDER = PROVIDERS / "social_scrape.py"
DATASET = "gd_lyy3tktm25m4avu764"
COMPANY = "https://www.linkedin.com/company/vidora"
LIMIT = 2


@pytest.fixture(scope="module")
def provider():
    if not PROVIDER.is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.social_scrape")


def request_for(method, path, body=None):
    payload = b"" if body is None else json.dumps(body).encode()

    async def receive():
        return {"type": "http.request", "body": payload, "more_body": False}

    return Request(
        {
            "type": "http",
            "method": method,
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [
                (b"authorization", b"Bearer mock_linkedin_posts_token"),
                (b"content-type", b"application/json"),
            ],
            "scheme": "http",
            "server": ("mock", 8100),
            "root_path": "",
        },
        receive,
    )


async def collect(provider, limit):
    triggered = await provider.trigger(
        request_for("POST", "/datasets/v3/trigger", [{"url": COMPANY}]),
        dataset_id=DATASET,
        kind="discover_new",
        discover_by="company_url",
        fmt="json",
        include_errors=True,
        limit_per_input=limit,
    )
    snapshot = triggered["snapshot_id"]
    for _poll in range(2):
        await provider.progress(
            request_for("GET", f"/datasets/v3/progress/{snapshot}"), snapshot
        )
    return await provider.snapshot(
        request_for("GET", f"/datasets/v3/snapshot/{snapshot}"), snapshot, fmt="json"
    )


class TestTheStandInHonoursThePerInputLimit:
    async def test_a_company_with_more_posts_than_the_limit_answers_exactly_the_limit(
        self, provider
    ):
        everything = await collect(provider, 100)
        assert len(everything) > LIMIT
        assert len(await collect(provider, LIMIT)) == LIMIT

    async def test_the_posts_kept_are_the_newest_by_date_posted(self, provider):
        everything = await collect(provider, 100)
        newest = sorted((row["date_posted"] for row in everything), reverse=True)
        kept = await collect(provider, LIMIT)
        assert [row["date_posted"] for row in kept] == newest[:LIMIT]
