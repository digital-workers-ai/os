from app.sources.paginators import Paginator
from app.sources.util import client_for, declare_page_complete, store_all, window

SOURCE = "twitter"

OBSERVED_AT = {"accounts": "updated_at"}

USER_ID = "1"

TWEET_FIELDS = "created_at,public_metrics"


class _NextToken(Paginator):
    def extract(self, data):
        records = data.get("data") if isinstance(data, dict) else None
        return records if isinstance(records, list) else []

    def next_params(self, data, params):
        meta = data.get("meta") if isinstance(data, dict) else None
        token = (meta or {}).get("next_token")
        return {**params, "pagination_token": token} if token else None


_TWEETS = _NextToken()


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    since, until = window()
    data = await api.get("/12/accounts", params={"count": 100})
    accounts = data.get("data", data) if isinstance(data, dict) else data
    if isinstance(accounts, list):
        declare_page_complete(api, accounts, 100, "accounts")
        await store_all(
            session, store, accounts, source=SOURCE, object_type="accounts", notes=notes
        )
    tweets = await api.get(
        f"/2/users/{USER_ID}/tweets",
        params={
            "start_time": f"{since}T00:00:00Z",
            "end_time": f"{until}T23:59:59Z",
            "max_results": 100,
            "tweet.fields": TWEET_FIELDS,
        },
        paginate=_TWEETS,
    )
    await store_all(
        session, store, tweets, source=SOURCE, object_type="tweets", notes=notes
    )
    return notes or None
