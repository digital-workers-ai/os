from typing import Any


class PaginationError(ValueError):
    pass


class Paginator:
    def extract(self, data: Any) -> list[dict]:
        raise NotImplementedError

    def next_params(self, data: Any, params: dict) -> dict | None:
        raise NotImplementedError

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


PAGINATORS: dict[str, Paginator] = {
    "cursor_hubspot": HubspotCursor(),
    "cursor_stripe": StripeCursor(),
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
