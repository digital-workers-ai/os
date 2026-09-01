from app.sources.util import client_for, store_all

SOURCE = "twilio"

OBSERVED_AT = {"messages": "date_updated"}


async def pull(session, store):
    api = client_for(SOURCE)
    messages = await api.get(
        "/2010-04-01/Accounts/mock_account_sid/Messages.json",
        params={"PageSize": 1},
        paginate="page_twilio",
    )
    return (
        await store_all(
            session,
            store,
            messages,
            source=SOURCE,
            object_type="messages",
            id_fields=("sid",),
        )
        or None
    )
