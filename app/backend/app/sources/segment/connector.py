from app.sources.util import client_for, store_all

SOURCE = "segment"

OBSERVED_AT = {"sources": "updatedAt"}


async def pull(session, store):
    api = client_for(SOURCE)
    sources = await api.get(
        "/sources", params={"pagination.count": 1}, paginate="cursor_segment"
    )
    return (
        await store_all(
            session,
            store,
            sources,
            source=SOURCE,
            object_type="sources",
            id_fields=("id", "name"),
        )
        or None
    )
