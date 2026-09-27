from app.sources.paginators import Paginator

SEARCH_PATH = "/api/v1/search"


class TokenPage(Paginator):
    def __init__(self, list_key: str, pages: int):
        self.list_key = list_key
        self.pages = pages
        self.read = 0
        self.more = False

    def extract(self, data):
        records = data.get(self.list_key) if isinstance(data, dict) else None
        return records if isinstance(records, list) else []

    def next_params(self, data, params):
        self.read += 1
        paging = data.get("pagination") if isinstance(data, dict) else None
        token = paging.get("next_page_token") if isinstance(paging, dict) else None
        if not token:
            return None
        if self.read >= self.pages:
            self.more = True
            return None
        return {**params, "next_page_token": token}
