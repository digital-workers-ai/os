import asyncio
import contextvars
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.config import settings
from app.sources.paginators import PaginationError, Paginator, resolve

_RETRIABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_ATTEMPTS = 4

_sleep = asyncio.sleep

_transport: httpx.AsyncBaseTransport | None = None

_active: contextvars.ContextVar[list | None] = contextvars.ContextVar(
    "active_clients", default=None
)


class ConnectorError(RuntimeError):
    def __init__(self, source: str, detail: str):
        self.source = source
        self.detail = detail
        super().__init__(f"[{source}] {detail}")


class collect_stats:
    def __init__(self):
        self.clients: list[SourceClient] = []

    def __enter__(self):
        self._token = _active.set(self.clients)
        return self

    def __exit__(self, *exc):
        _active.reset(self._token)

    @property
    def pages_read(self) -> int:
        return sum(c.pages_read for c in self.clients)

    @property
    def truncated(self) -> bool:
        return any(c.truncated for c in self.clients)

    @property
    def truncation_reasons(self) -> list[str]:
        return [r for c in self.clients for r in c.truncation_reasons]


def redact_url(url: str) -> str:
    parts = urlsplit(str(url))
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


class SourceClient:
    def __init__(
        self,
        source: str,
        base_url: str,
        *,
        headers: dict | None = None,
        auth: tuple | None = None,
        params: dict | None = None,
    ):
        self.source = source
        self.base_url = base_url.rstrip("/")
        parts = urlsplit(self.base_url)
        self.origin = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
        self.headers = headers or {}
        self.auth = auth
        self.default_params = params or {}
        self.pages_read = 0
        self.truncated = False
        self.truncation_reasons: list[str] = []
        registry = _active.get()
        if registry is not None:
            registry.append(self)

    def _client(self) -> httpx.AsyncClient:
        kwargs: dict = {"timeout": 30.0}
        if _transport is not None:
            kwargs["transport"] = _transport
        return httpx.AsyncClient(**kwargs)

    async def _request(
        self, client: httpx.AsyncClient, method: str, url: str, **kwargs
    ) -> httpx.Response:
        last_detail = ""
        for attempt in range(_MAX_ATTEMPTS):
            try:
                r = await client.request(
                    method, url, headers=self.headers, auth=self.auth, **kwargs
                )
            except httpx.HTTPError as e:
                last_detail = f"{type(e).__name__} requesting {redact_url(url)}"
            else:
                if r.status_code not in _RETRIABLE_STATUS:
                    if r.status_code >= 400:
                        raise ConnectorError(
                            self.source,
                            f"HTTP {r.status_code} from {redact_url(url)}",
                        )
                    return r
                last_detail = f"HTTP {r.status_code} from {redact_url(url)}"
            if attempt < _MAX_ATTEMPTS - 1:
                await _sleep(min(2**attempt, 15))
        raise ConnectorError(
            self.source, f"{last_detail} after {_MAX_ATTEMPTS} attempts"
        )

    def _safe_json(self, r: httpx.Response):
        try:
            return r.json()
        except Exception as e:
            raise ConnectorError(
                self.source,
                f"invalid JSON body from {redact_url(str(r.request.url))}",
            ) from e

    async def get(
        self,
        path: str,
        *,
        params: dict | None = None,
        paginate: str | Paginator | None = None,
    ):
        base = self.origin if _transport is not None else self.base_url
        url = f"{base}{path}"
        merged = {**self.default_params, **(params or {})}

        if not paginate:
            async with self._client() as client:
                r = await self._request(client, "GET", url, params=merged)
                self.pages_read += 1
                return self._safe_json(r)

        paginator = resolve(paginate)
        records: list = []
        page_params = merged
        seen_params: set = set()
        bytes_read = 0
        pages_this_walk = 0

        async with self._client() as client:
            while True:
                frozen = tuple(sorted((k, str(v)) for k, v in page_params.items()))
                if frozen in seen_params:
                    self._truncate("repeated cursor detected — halting loop")
                    break
                seen_params.add(frozen)

                if pages_this_walk >= settings.CONNECTOR_MAX_PAGES:
                    self._truncate(f"page cap {settings.CONNECTOR_MAX_PAGES} reached")
                    break

                try:
                    r = await self._request(client, "GET", url, params=page_params)
                except ConnectorError:
                    if records:
                        self._truncate(
                            "request failed mid-pagination — keeping "
                            "pages already fetched"
                        )
                        break
                    raise

                self.pages_read += 1
                pages_this_walk += 1
                bytes_read += len(r.content)
                data = self._safe_json(r)

                try:
                    records.extend(paginator.extract(data))
                except PaginationError as e:
                    raise ConnectorError(self.source, str(e)) from e

                if bytes_read > settings.CONNECTOR_MAX_BYTES:
                    self._truncate(f"byte cap {settings.CONNECTOR_MAX_BYTES} reached")
                    break

                next_params = paginator.next_params(data, page_params)
                if next_params is None:
                    next_params = paginator.next_from_headers(r.headers, page_params)
                if next_params is None:
                    break
                page_params = next_params

        return records

    async def get_text(self, path: str, *, params: dict | None = None) -> str:
        base = self.origin if _transport is not None else self.base_url
        url = f"{base}{path}"
        merged = {**self.default_params, **(params or {})}
        async with self._client() as client:
            r = await self._request(client, "GET", url, params=merged)
            self.pages_read += 1
            body = r.text
            if len(r.content) > settings.CONNECTOR_MAX_BYTES:
                self._truncate(
                    f"byte cap {settings.CONNECTOR_MAX_BYTES} reached on an "
                    "export; the tail was not read"
                )
                body = body[: settings.CONNECTOR_MAX_BYTES]
            return body

    async def post(self, path: str, *, json: dict | None = None):
        base = self.origin if _transport is not None else self.base_url
        url = f"{base}{path}"
        async with self._client() as client:
            r = await self._request(
                client, "POST", url, params=self.default_params, json=json
            )
            self.pages_read += 1
            return self._safe_json(r)

    def truncate(self, reason: str) -> None:
        self._truncate(reason)

    def _truncate(self, reason: str) -> None:
        self.truncated = True
        self.truncation_reasons.append(reason)
