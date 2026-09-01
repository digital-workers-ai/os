from app.sources.util import client_for, store_all

SOURCE = "salesforce"

OBSERVED_AT: dict = {}

ACCOUNT_CURRENCY = "usd"

QUERIES = {
    "accounts": (
        "SELECT Id, Name, Industry, Website, AnnualRevenue, NumberOfEmployees "
        "FROM Account"
    ),
    "contacts": (
        "SELECT Id, FirstName, LastName, Email, Phone, Title, AccountId FROM Contact"
    ),
    "opportunities": (
        "SELECT Id, Name, StageName, Amount, CloseDate, AccountId FROM Opportunity"
    ),
}


async def pull(session, store):
    api = client_for(SOURCE)
    notes: dict = {}
    for object_type, soql in QUERIES.items():
        data = await api.get("/query", params={"q": soql})
        records: list = []
        guard = 0
        while isinstance(data, dict):
            records.extend(data.get("records") or [])
            if data.get("done", True) or not data.get("nextRecordsUrl"):
                break
            if guard >= 100:
                api.truncate(f"salesforce cursor guard reached on {object_type}")
                break
            guard += 1
            locator = str(data["nextRecordsUrl"]).rsplit("/query", 1)[-1]
            data = await api.get(f"/query{locator}")
        await store_all(
            session,
            store,
            records,
            source=SOURCE,
            object_type=object_type,
            id_fields=("Id",),
            notes=notes,
        )
    return notes or None
