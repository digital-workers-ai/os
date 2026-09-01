import re
from typing import Any
from urllib.parse import unquote


class PaginationError(ValueError):
    pass


class Paginator:
    def extract(self, data: Any) -> list[dict]:
        raise NotImplementedError

    def next_params(self, data: Any, params: dict) -> dict | None:
        raise NotImplementedError

    def next_from_headers(self, headers: Any, params: dict) -> dict | None:
        return None

    def _require_list(self, data: Any, key: str) -> list:
        if not isinstance(data, dict):
            raise PaginationError(
                f"expected an object with {key!r}, got {type(data).__name__}"
            )
        value = data.get(key)
        if value is None:
            raise PaginationError(
                f"response has no {key!r} list — shape drift or error body"
            )
        if not isinstance(value, list):
            raise PaginationError(f"{key!r} is {type(value).__name__}, not a list")
        return value


class HubspotCursor(Paginator):
    def extract(self, data):
        return self._require_list(data, "results")

    def next_params(self, data, params):
        after = ((data.get("paging") or {}).get("next") or {}).get("after")
        return {**params, "after": after} if after else None


class StripeCursor(Paginator):
    def extract(self, data):
        return self._require_list(data, "data")

    def next_params(self, data, params):
        if not data.get("has_more"):
            return None
        records = data.get("data") or []
        if not records:
            return None
        return {**params, "starting_after": records[-1]["id"]}


class _KeyedCursor(Paginator):
    KEYS: tuple = ()

    def extract(self, data):
        if not isinstance(data, dict):
            raise PaginationError(f"expected object, got {type(data).__name__}")
        for key in self.KEYS:
            if isinstance(data.get(key), list):
                return data[key]
        raise PaginationError(
            f"none of {self.KEYS} present — shape drift or error body"
        )


class ZendeskCursor(_KeyedCursor):
    KEYS = ("tickets", "users", "organizations")

    def next_params(self, data, params):
        meta = data.get("meta") or {}
        if meta.get("has_more") and meta.get("after_cursor"):
            return {**params, "page[after]": meta["after_cursor"]}
        return None


class IntercomCursor(Paginator):
    def __init__(self, key: str = "data"):
        self.key = key

    def extract(self, data):
        return self._require_list(data, self.key)

    def next_params(self, data, params):
        starting_after = ((data.get("pages") or {}).get("next") or {}).get(
            "starting_after"
        )
        return {**params, "starting_after": starting_after} if starting_after else None


class CustomerioCursor(_KeyedCursor):
    KEYS = ("campaigns", "segments")

    def next_params(self, data, params):
        cursor = data.get("next_cursor")
        return {**params, "cursor": cursor} if cursor else None


class CustomerioActivityCursor(Paginator):
    def extract(self, data):
        return self._require_list(data, "activities")

    def next_params(self, data, params):
        cursor = data.get("next_cursor")
        return {**params, "start": cursor} if cursor else None


class KlaviyoCursor(Paginator):
    def extract(self, data):
        return self._require_list(data, "data")

    def next_params(self, data, params):
        next_link = (data.get("links") or {}).get("next")
        if not next_link:
            return None
        for marker in ("page%5Bcursor%5D=", "page[cursor]="):
            if marker in next_link:
                cursor = unquote(next_link.split(marker)[-1].split("&")[0])
                return {**params, "page[cursor]": cursor} if cursor else None
        return None


class CalendlyToken(Paginator):
    def extract(self, data):
        return self._require_list(data, "collection")

    def next_params(self, data, params):
        token = (data.get("pagination") or {}).get("next_page_token")
        return {**params, "page_token": token} if token else None


class Offset(Paginator):
    TOTAL_KEYS = ("total_count", "total_items", "total")

    def __init__(self, list_key: str):
        self.list_key = list_key

    def extract(self, data):
        return self._require_list(data, self.list_key)

    def next_params(self, data, params):
        count = int(params.get("count", 100))
        offset = int(params.get("offset", 0))
        page_len = len(self.extract(data))
        total = None
        for key in self.TOTAL_KEYS:
            if isinstance(data.get(key), int | float):
                total = int(data[key])
                break
        if total is not None:
            if offset + count >= total:
                return None
        elif page_len < count:
            return None
        return {**params, "offset": offset + count}


class ShopifyLink(Paginator):
    def __init__(self, key: str):
        self.key = key

    def extract(self, data):
        return self._require_list(data, self.key)

    def next_params(self, data, params):
        return None

    def next_from_headers(self, headers, params):
        link = headers.get("Link") or headers.get("link") or ""
        match = re.search(r'<[^>]*[?&]page_info=([^&>]+)[^>]*>;\s*rel="next"', link)
        if not match:
            return None
        return {"limit": params.get("limit"), "page_info": match.group(1)}


class TwilioPage(Paginator):
    def extract(self, data):
        return self._require_list(data, "messages")

    def next_params(self, data, params):
        if not data.get("next_page_uri"):
            return None
        return {
            **params,
            "Page": int(data.get("page", 0)) + 1,
            "PageToken": data.get("next_page_token") or "",
        }


PAGINATORS: dict[str, Paginator] = {
    "cursor_customerio": CustomerioCursor(),
    "cursor_customerio_activities": CustomerioActivityCursor(),
    "cursor_hubspot": HubspotCursor(),
    "cursor_intercom": IntercomCursor(),
    "cursor_klaviyo": KlaviyoCursor(),
    "cursor_stripe": StripeCursor(),
    "cursor_zendesk": ZendeskCursor(),
    "page_twilio": TwilioPage(),
    "token_calendly": CalendlyToken(),
}


def resolve(paginate: str | Paginator) -> Paginator:
    if isinstance(paginate, Paginator):
        return paginate
    try:
        return PAGINATORS[paginate]
    except KeyError:
        raise ValueError(
            f"unknown paginate mode {paginate!r} — expected one of {sorted(PAGINATORS)}"
        ) from None
