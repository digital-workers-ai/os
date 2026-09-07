import ast
import importlib
from pathlib import Path

import httpx
import pytest

from app import llm
from app.caches import BACKEND_DIR
from app.config import settings

APP_DIR = BACKEND_DIR / "app"
LLM_DIR = APP_DIR / "llm"
VENDORS = {"anthropic", "openai", "zeroentropy"}


def _roots(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom) and node.module and not node.level:
            yield node.module.split(".")[0]


def _vendor_imports() -> dict:
    found: dict = {}
    for path in sorted(APP_DIR.rglob("*.py")):
        roots = set(_roots(ast.parse(path.read_text())))
        hit = roots & VENDORS
        if hit:
            found[path.relative_to(APP_DIR)] = hit
    return found


class TestVendorSdksStayUnderLlm:
    def test_no_vendor_sdk_is_imported_outside_app_llm(self):
        outside = {
            str(path): roots
            for path, roots in _vendor_imports().items()
            if not path.parts or path.parts[0] != "llm"
        }
        assert outside == {}

    def test_the_walker_sees_the_imports_it_polices(self):
        found = _vendor_imports()
        assert found[Path("llm/__init__.py")] == {"anthropic"}
        assert found[Path("llm/embeddings.py")] == {"openai"}

    def test_rerank_talks_rest_without_a_vendor_sdk(self):
        found = _vendor_imports()
        assert Path("llm/rerank.py") not in found
        rerank = importlib.import_module("app.llm.rerank")
        assert rerank.RERANK_URL == "https://api.zeroentropy.dev/v1/models/rerank"


class FakeEmbeddingsApi:
    def __init__(self, raises=None):
        self.calls: list = []
        self.raises = raises

    @property
    def embeddings(self):
        return self

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.raises:
            raise self.raises
        return type(
            "Reply",
            (),
            {
                "data": [
                    type("Row", (), {"index": i, "embedding": [float(i)] * 3})()
                    for i, _ in enumerate(kwargs["input"])
                ]
            },
        )()


class TestEmbeddings:
    @pytest.fixture
    def embeddings(self):
        return importlib.import_module("app.llm.embeddings")

    async def test_vectors_come_back_in_input_order(self, embeddings):
        api = FakeEmbeddingsApi()
        out = await embeddings.embed(["a", "b"], client_override=api)
        assert out == [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]

    async def test_the_configured_model_and_dims_are_sent(self, embeddings):
        api = FakeEmbeddingsApi()
        await embeddings.embed(["a"], client_override=api)
        assert api.calls == [
            {
                "model": settings.EMBEDDING_MODEL,
                "input": ["a"],
                "dimensions": settings.EMBEDDING_DIMS,
            }
        ]

    async def test_an_explicit_model_wins(self, embeddings):
        api = FakeEmbeddingsApi()
        await embeddings.embed(["a"], model="other", client_override=api)
        assert api.calls[0]["model"] == "other"

    async def test_any_failure_is_an_llm_error(self, embeddings):
        api = FakeEmbeddingsApi(raises=RuntimeError("quota"))
        with pytest.raises(llm.LLMError, match="quota"):
            await embeddings.embed(["a"], client_override=api)

    def test_the_client_is_built_once_and_reused(self, embeddings, monkeypatch):
        openai = importlib.import_module("openai")
        built = []

        class Fake:
            def __init__(self):
                built.append(self)

        monkeypatch.setattr(openai, "AsyncOpenAI", Fake)
        embeddings.reset()
        first, second = embeddings.client(), embeddings.client()
        assert first is second
        assert len(built) == 1
        embeddings.reset()

    def test_reset_drops_the_cached_client(self, embeddings, monkeypatch):
        openai = importlib.import_module("openai")
        monkeypatch.setattr(openai, "AsyncOpenAI", lambda: object())
        embeddings.reset()
        first = embeddings.client()
        embeddings.reset()
        assert embeddings.client() is not first
        embeddings.reset()


class FakeResponse:
    def __init__(self, body, status_error=None):
        self.body, self.status_error = body, status_error

    def raise_for_status(self):
        if self.status_error:
            raise self.status_error

    def json(self):
        return self.body


class FakeHttp:
    def __init__(self, body=None, raises=None, status_error=None):
        self.body = body if body is not None else {"results": []}
        self.raises, self.status_error = raises, status_error
        self.calls: list = []

    async def post(self, url, json=None, headers=None):
        self.calls.append({"url": url, "json": json, "headers": headers})
        if self.raises:
            raise self.raises
        return FakeResponse(self.body, self.status_error)


class TestRerank:
    @pytest.fixture
    def rerank(self):
        return importlib.import_module("app.llm.rerank")

    @pytest.fixture
    def key(self, monkeypatch):
        monkeypatch.setenv("ZEROENTROPY_API_KEY", "ze-key")

    async def test_scores_are_aligned_to_the_documents(self, rerank, key):
        http = FakeHttp(
            {
                "results": [
                    {"index": 2, "relevance_score": 0.9},
                    {"index": 0, "relevance_score": 0.4},
                ]
            }
        )
        out = await rerank.rerank("q", ["a", "b", "c"], client_override=http)
        assert out == [0.4, 0.0, 0.9]

    async def test_the_request_carries_model_query_documents_and_the_key(
        self, rerank, key
    ):
        http = FakeHttp()
        await rerank.rerank("wayne", ["a", "b"], client_override=http)
        assert http.calls == [
            {
                "url": rerank.RERANK_URL,
                "json": {
                    "model": settings.RERANK_MODEL,
                    "query": "wayne",
                    "documents": ["a", "b"],
                },
                "headers": {"Authorization": "Bearer ze-key"},
            }
        ]

    async def test_an_explicit_model_wins(self, rerank, key):
        http = FakeHttp()
        await rerank.rerank("q", ["a"], model="other", client_override=http)
        assert http.calls[0]["json"]["model"] == "other"

    async def test_a_transport_failure_is_an_llm_error(self, rerank, key):
        http = FakeHttp(raises=RuntimeError("connection reset"))
        with pytest.raises(llm.LLMError, match="connection reset"):
            await rerank.rerank("q", ["a"], client_override=http)

    async def test_a_bad_status_is_an_llm_error(self, rerank, key):
        request = httpx.Request("POST", rerank.RERANK_URL)
        response = httpx.Response(401, request=request)
        http = FakeHttp(
            status_error=httpx.HTTPStatusError(
                "401", request=request, response=response
            )
        )
        with pytest.raises(llm.LLMError, match="401"):
            await rerank.rerank("q", ["a"], client_override=http)

    async def test_the_cached_client_is_used_when_none_is_given(
        self, rerank, key, monkeypatch
    ):
        http = FakeHttp({"results": [{"index": 0, "relevance_score": 0.5}]})
        monkeypatch.setattr(rerank, "_client", http)
        assert await rerank.rerank("q", ["a"]) == [0.5]
        assert http.calls[0]["url"] == rerank.RERANK_URL

    def test_the_client_is_built_once_and_reused(self, rerank, monkeypatch):
        built = []

        class Fake:
            def __init__(self, **kwargs):
                built.append(self)

        monkeypatch.setattr(httpx, "AsyncClient", Fake)
        rerank.reset()
        first, second = rerank.client(), rerank.client()
        assert first is second
        assert len(built) == 1
        rerank.reset()

    def test_reset_drops_the_cached_client(self, rerank, monkeypatch):
        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: object())
        rerank.reset()
        first = rerank.client()
        rerank.reset()
        assert rerank.client() is not first
        rerank.reset()
