import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests import ground_truth

SEEDS = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds"
TOKEN = {
    "Authorization": "Bearer mock_github_token",
    "Accept": "application/vnd.github+json",
}
ISSUES = "/github/repos/digital-workers-ai/os/issues"
ISSUE = {
    "title": "New app: Receipts",
    "body": "Snap receipts and sort them.",
    "labels": ["app"],
}


@pytest.fixture
def provider():
    if not (SEEDS / "server.py").is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.reload(importlib.import_module("seeds.providers.github"))


@pytest.fixture
def github(provider):
    app = FastAPI()
    app.include_router(provider.router, prefix="/github")
    return TestClient(app)


def filed(github, *, issue=ISSUE, headers=TOKEN, path=ISSUES):
    return github.post(path, json=issue, headers=headers)


class TestAnIssueIsFiled:
    def test_a_filed_issue_answers_201(self, github):
        assert filed(github).status_code == 201

    def test_the_answer_carries_the_number_the_url_and_the_labels(self, github):
        assert set(filed(github).json()) == {"number", "html_url", "labels"}

    def test_the_first_issue_is_number_one(self, github):
        assert filed(github).json()["number"] == 1

    def test_each_further_issue_takes_the_next_number(self, github):
        numbers = [filed(github).json()["number"] for _ in range(3)]
        assert numbers == [1, 2, 3]

    def test_the_url_names_the_owner_the_repository_and_the_number(self, github):
        assert (
            filed(github).json()["html_url"]
            == "https://github.com/digital-workers-ai/os/issues/1"
        )

    def test_another_repository_is_named_in_its_url(self, github):
        answer = filed(github, path="/github/repos/acme/apps/issues")
        assert answer.json()["html_url"] == "https://github.com/acme/apps/issues/1"

    def test_each_label_comes_back_as_a_named_object_in_order(self, github):
        issue = {**ISSUE, "labels": ["app", "approved"]}
        assert filed(github, issue=issue).json()["labels"] == [
            {"name": "app"},
            {"name": "approved"},
        ]

    def test_no_labels_come_back_as_none(self, github):
        assert filed(github, issue={**ISSUE, "labels": []}).json()["labels"] == []


class TestTheTokenIsChecked:
    def test_a_missing_token_is_refused_with_401(self, github):
        accept = {"Accept": "application/vnd.github+json"}
        assert filed(github, headers=accept).status_code == 401

    def test_a_wrong_token_is_refused_with_401(self, github):
        wrong = {**TOKEN, "Authorization": "Bearer someone_elses_token"}
        assert filed(github, headers=wrong).status_code == 401

    def test_a_refused_issue_takes_no_number(self, github):
        filed(github, headers={})
        assert filed(github).json()["number"] == 1


class TestTheServerMountsTheStandIn:
    def test_the_stand_in_is_mounted_at_github(self, provider):
        assert importlib.import_module("seeds.server").routers["/github"] is provider
