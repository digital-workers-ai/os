import os

import pytest

from app.enrichment import vocabulary
from tests import ground_truth


@pytest.fixture(scope="session")
def world():
    module = ground_truth.world()
    if module is None:
        pytest.skip("seed world not mounted at /adversarial")
    return module


@pytest.fixture(scope="session")
def credential():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("no Anthropic credential in this container")


@pytest.fixture(scope="session")
def reading():
    return vocabulary.load()["sales_call"]
