import base64
import struct
import uuid
from datetime import timedelta

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app import media
from app.config import settings
from app.custom import access, reader, records, scripts, transcribe
from app.db import get_session
from app.engine import apps
from app.main import app
from app.models import (
    CustomRecord,
    CustomRecordAudit,
    CustomRecordFile,
    EngineRun,
    RawEvent,
)
from tests.conftest import NOW

JPEG = b"\xff\xd8\xff\xe0 a receipt"
PNG = b"\x89PNG\r\n\x1a\n a signature"
CLIP = b"\x1a\x45\xdf\xa3\x87\x42\x82\x84webm"
PHOTO_FILE = {"path": "photo-1.jpg", "media_type": "image/jpeg", "kind": "photo"}
HARBOR_FUEL = {
    "vendor": "Harbor Fuel",
    "date": "2026-09-03",
    "total": 48.2,
    "category": "fuel",
    "items": [{"description": "Diesel", "amount": 48.2}],
}
PRESS = {
    "asset": "PRESS-02",
    "work_done": "Replaced hydraulic seal",
    "status": "working",
}
CURSOR = {"row": "3", "column": "DB"}
HEARD = {
    "updates": [{"row": "3", "column": "DB", "field": "depth", "value": 3}],
    "cursor": {"row": "3", "column": "B"},
    "readback": "Tooth 3, DB 3",
}
APP_NAMES = [
    "batch_trace",
    "check_deposits",
    "damage_claims",
    "equipment_checkout",
    "event_check_in",
    "field_service_report",
    "food_safety_log",
    "inventory_count",
    "mailroom",
    "maintenance_tags",
    "mileage_log",
    "perio_charting",
    "proof_of_delivery",
    "property_inspection",
    "receipts",
    "sales_visit_debrief",
    "shelf_audit",
    "site_safety_walk",
    "supplier_invoices",
    "vehicle_pre_trip",
    "vet_visit_notes",
]
RECEIPTS = {
    "name": "receipts",
    "title": "Receipts",
    "description": "A photo of a paper receipt for something bought for the business.",
    "input": ["photo"],
    "roles": ["staff", "finance"],
    "lands_as": "expense",
    "script": False,
    "screen": False,
}
CREATE_KEYS = {"id", "app", "fields", "missing", "files", "transcript"}
DETAIL_KEYS = {
    "id",
    "app",
    "fields",
    "files",
    "history",
    "counted",
    "entity",
    "removed",
}
ROUTES = {
    ("get", "/api/custom/apps"): set(),
    ("get", "/api/custom/apps/{app}"): {"403", "404"},
    ("get", "/api/custom/apps/{app}/lookup/{field}"): {"403", "404"},
    ("post", "/api/custom/apps/{app}/records"): {"403", "404", "409", "413", "422"},
    ("put", "/api/custom/records/{id}"): {"403", "404", "409", "422"},
    ("post", "/api/custom/records/{id}/hear"): {"403", "404", "409", "413", "422"},
    ("post", "/api/custom/records/{id}/files"): {"403", "404", "413", "422"},
    ("get", "/api/custom/records"): {"403", "404"},
    ("get", "/api/custom/records/{id}"): {"403", "404"},
    ("get", "/api/custom/records/{id}/files/{path}"): {"403", "404"},
    ("delete", "/api/custom/records/{id}"): {"403", "404"},
}


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def wav(seconds: int, rate: int = 1000) -> bytes:
    samples = bytes(seconds * rate)
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, rate, rate, 1, 8)
    body = b"WAVE" + fmt + struct.pack("<4sI", b"data", len(samples)) + samples
    return struct.pack("<4sI", b"RIFF", len(body)) + body


def sent(name: str, media_type: str, data: bytes) -> dict:
    return {"name": name, "media_type": media_type, "data": b64(data)}


PHOTO = sent("photo-1.jpg", "image/jpeg", JPEG)
SIGNATURE = sent("signature.png", "image/png", PNG)
SIGNATURE_FILE = {
    "path": "signature.png",
    "media_type": "image/png",
    "kind": "signature",
}
SPOKEN = {"media_type": "audio/webm", "data": b64(CLIP)}
RECORD_ROUTES = [
    ("PUT", "", {"fields": {}}),
    ("POST", "/hear", {"audio": SPOKEN}),
    ("POST", "/files", SIGNATURE),
    ("GET", "", None),
    ("GET", "/files/photo-1.jpg", None),
    ("DELETE", "", None),
]
RECORD_IDS = ["save", "hear", "attach", "detail", "file", "remove"]


@pytest_asyncio.fixture
async def api(session):
    async def override():
        yield session

    app.dependency_overrides[get_session] = override
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://backend"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def driver(monkeypatch):
    monkeypatch.setattr(access, "roles", lambda: ("driver",))


@pytest.fixture
def heard_as(monkeypatch):
    def install(transcript):
        async def fake(app, audio, media_type):
            return transcript

        monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)
        monkeypatch.setattr(transcribe, "transcribe", fake)

    return install


@pytest.fixture
def hearing(monkeypatch):
    seen = []

    async def hear(app, *, text, cursor, **kwargs):
        seen.append({"text": text, "cursor": cursor})
        return HEARD

    monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
    monkeypatch.setattr(reader, "hear", hear)
    return seen


def at(monkeypatch, minutes: int):
    when = NOW + timedelta(minutes=minutes)
    monkeypatch.setattr(settings, "CLOCK_PINNED_AT", when)
    return when


async def created(session, name="receipts", *, files=None, scan=None, audio=None):
    made = await records.create(
        session,
        apps.load(name),
        files=[("photo-1.jpg", "image/jpeg", JPEG)] if files is None else files,
        scan=scan,
        audio=audio,
        actor="admin",
    )
    return made["id"]


async def saved(session, name="receipts", fields=HARBOR_FUEL, *, files=None):
    record_id = await created(session, name, files=files)
    await records.save(
        session, apps.load(name), uuid.UUID(record_id), fields, actor="admin"
    )
    return record_id


async def fresh_rows(sessionmaker_for_test, model, *where):
    query = select(model).where(*where) if where else select(model)
    async with sessionmaker_for_test() as fresh:
        return (await fresh.execute(query)).scalars().all()


class TestApps:
    async def test_admin_sees_every_app_by_name(self, api):
        body = (await api.get("/api/custom/apps")).json()
        assert [entry["name"] for entry in body] == APP_NAMES

    async def test_an_app_is_listed_with_its_summary(self, api):
        body = (await api.get("/api/custom/apps")).json()
        assert next(e for e in body if e["name"] == "receipts") == RECEIPTS

    async def test_several_inputs_are_listed_in_order(self, api):
        body = (await api.get("/api/custom/apps")).json()
        assert next(e for e in body if e["name"] == "mailroom")["input"] == [
            "scan",
            "photo",
        ]

    async def test_an_app_with_a_script_says_so(self, api):
        body = (await api.get("/api/custom/apps")).json()
        mileage = next(e for e in body if e["name"] == "mileage_log")
        assert (mileage["script"], mileage["screen"]) == (True, False)

    async def test_an_app_with_a_screen_says_so(self, api):
        body = (await api.get("/api/custom/apps")).json()
        delivery = next(e for e in body if e["name"] == "proof_of_delivery")
        assert (delivery["script"], delivery["screen"]) == (False, True)

    async def test_apps_the_roles_may_not_open_are_left_out(self, api, driver):
        body = (await api.get("/api/custom/apps")).json()
        assert [entry["name"] for entry in body] == [
            "proof_of_delivery",
            "vehicle_pre_trip",
        ]

    async def test_the_definition_carries_the_summary(self, api):
        body = (await api.get("/api/custom/apps/receipts")).json()
        assert {key: body[key] for key in RECEIPTS} == RECEIPTS

    async def test_the_definition_lists_its_fields_in_order(self, api):
        body = (await api.get("/api/custom/apps/receipts")).json()
        assert [(f["name"], f["type"]) for f in body["fields"]] == [
            ("vendor", "text"),
            ("date", "date"),
            ("total", "money"),
            ("tax", "money"),
            ("category", "one_of"),
            ("items", "list"),
        ]

    async def test_a_list_field_carries_its_own_fields(self, api):
        body = (await api.get("/api/custom/apps/receipts")).json()
        assert [f["name"] for f in body["fields"][-1]["fields"]] == [
            "description",
            "amount",
        ]

    async def test_an_app_without_a_template_has_none(self, api):
        body = (await api.get("/api/custom/apps/receipts")).json()
        assert body["template"] is None

    async def test_a_template_is_served_with_its_kind(self, api):
        body = (await api.get("/api/custom/apps/perio_charting")).json()
        assert body["template"]["kind"] == "grid"

    async def test_an_unknown_app_is_a_404(self, api):
        response = await api.get("/api/custom/apps/nope")
        assert response.status_code == 404
        assert "nope" in response.json()["detail"]

    async def test_an_app_the_roles_may_not_open_is_a_403(self, api, driver):
        response = await api.get("/api/custom/apps/receipts")
        assert response.status_code == 403
        assert "receipts" in response.json()["detail"]


class TestLookup:
    async def test_a_scanned_code_matches_its_by_value_exactly(self, api, canonical):
        await canonical("asset", {"code": "LAP-014", "name": "Laptop 14"})
        await canonical("asset", {"code": "LAP-0145", "name": "Laptop 145"})
        response = await api.get(
            "/api/custom/apps/equipment_checkout/lookup/asset", params={"q": "LAP-014"}
        )
        assert response.status_code == 200
        assert response.json() == {
            "matches": [{"value": "LAP-014", "label": "Laptop 14"}],
            "history": [],
        }

    async def test_a_scanned_code_does_not_match_a_part_of_one(self, api, canonical):
        await canonical("asset", {"code": "LAP-014", "name": "Laptop 14"})
        body = (
            await api.get(
                "/api/custom/apps/equipment_checkout/lookup/asset",
                params={"q": "LAP"},
            )
        ).json()
        assert body["matches"] == []

    async def test_a_name_search_matches_labels_containing_it_in_any_case(
        self, api, canonical
    ):
        await canonical("company", {"name": "Acme Dental"})
        await canonical("company", {"name": "Blue Kettle"})
        body = (
            await api.get(
                "/api/custom/apps/check_deposits/lookup/customer",
                params={"q": "DENT"},
            )
        ).json()
        assert body["matches"] == [{"value": "Acme Dental", "label": "Acme Dental"}]

    async def test_matches_are_ordered_by_label(self, api, canonical):
        await canonical("company", {"name": "Harbor Lane"})
        await canonical("company", {"name": "Blue Harbor"})
        body = (
            await api.get(
                "/api/custom/apps/check_deposits/lookup/customer",
                params={"q": "harbor"},
            )
        ).json()
        assert [m["label"] for m in body["matches"]] == ["Blue Harbor", "Harbor Lane"]

    async def test_a_lookup_in_a_list_is_named_list_dot_field(self, api, canonical):
        await canonical("product", {"sku": "SKU-0042", "name": "Paper towels"})
        body = (
            await api.get(
                "/api/custom/apps/inventory_count/lookup/lines.product",
                params={"q": "SKU-0042"},
            )
        ).json()
        assert body["matches"] == [{"value": "SKU-0042", "label": "Paper towels"}]

    async def test_a_blank_query_matches_nothing(self, api, canonical):
        await canonical("company", {"name": "Acme Dental"})
        body = (
            await api.get(
                "/api/custom/apps/check_deposits/lookup/customer", params={"q": ""}
            )
        ).json()
        assert body == {"matches": [], "history": []}

    async def test_history_lists_the_apps_saved_records_for_the_value(
        self, api, session
    ):
        record_id = await saved(session, "maintenance_tags", PRESS, files=[])
        await saved(
            session, "maintenance_tags", {**PRESS, "asset": "PRESS-03"}, files=[]
        )
        body = (
            await api.get(
                "/api/custom/apps/maintenance_tags/lookup/asset",
                params={"q": "PRESS-02"},
            )
        ).json()
        assert body["history"] == [
            {
                "id": record_id,
                "app": "maintenance_tags",
                "fields": PRESS,
                "saved_at": NOW.isoformat(),
            }
        ]

    async def test_a_field_without_history_lists_none(self, api, session):
        await saved(
            session,
            "equipment_checkout",
            {"asset": "LAP-014", "action": "check_out"},
            files=[],
        )
        body = (
            await api.get(
                "/api/custom/apps/equipment_checkout/lookup/asset",
                params={"q": "LAP-014"},
            )
        ).json()
        assert body["history"] == []

    async def test_an_unknown_app_is_a_404(self, api):
        response = await api.get(
            "/api/custom/apps/nope/lookup/asset", params={"q": "x"}
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("field", ["vendor", "colour", "items.colour"])
    async def test_a_field_that_is_not_a_lookup_is_a_404(self, api, field):
        response = await api.get(
            f"/api/custom/apps/receipts/lookup/{field}", params={"q": "x"}
        )
        assert response.status_code == 404
        assert field in response.json()["detail"]

    async def test_a_lookup_the_roles_may_not_open_is_a_403(self, api, driver):
        response = await api.get(
            "/api/custom/apps/check_deposits/lookup/customer", params={"q": "acme"}
        )
        assert response.status_code == 403


class TestCreate:
    async def test_a_photo_record_is_a_201_with_the_create_result(self, api):
        response = await api.post(
            "/api/custom/apps/receipts/records", json={"files": [PHOTO]}
        )
        assert response.status_code == 201
        body = response.json()
        assert set(body) == CREATE_KEYS
        assert (body["app"], body["fields"], body["files"], body["transcript"]) == (
            "receipts",
            {},
            [PHOTO_FILE],
            None,
        )

    async def test_the_record_is_committed(self, api, sessionmaker_for_test):
        body = (
            await api.post("/api/custom/apps/receipts/records", json={"files": [PHOTO]})
        ).json()
        [stored] = await fresh_rows(
            sessionmaker_for_test,
            CustomRecord,
            CustomRecord.id == uuid.UUID(body["id"]),
        )
        assert stored.app == "receipts"

    async def test_the_data_is_decoded_from_base64_before_it_is_stored(self, api):
        body = (
            await api.post("/api/custom/apps/receipts/records", json={"files": [PHOTO]})
        ).json()
        assert media.read_record(uuid.UUID(body["id"]), "photo-1.jpg") == JPEG

    async def test_the_record_is_recorded_by_the_actor(
        self, api, monkeypatch, sessionmaker_for_test
    ):
        monkeypatch.setattr(access, "actor", lambda: "kim")
        body = (
            await api.post("/api/custom/apps/receipts/records", json={"files": [PHOTO]})
        ).json()
        [stored] = await fresh_rows(
            sessionmaker_for_test,
            CustomRecord,
            CustomRecord.id == uuid.UUID(body["id"]),
        )
        assert stored.recorded_by == "kim"

    async def test_a_scanned_code_fills_its_field(self, api):
        response = await api.post(
            "/api/custom/apps/equipment_checkout/records", json={"scan": "LAP-014"}
        )
        assert response.status_code == 201
        assert response.json()["fields"] == {"asset": "LAP-014"}

    async def test_a_clip_is_decoded_and_stored_as_audio(self, api):
        response = await api.post(
            "/api/custom/apps/sales_visit_debrief/records", json={"audio": SPOKEN}
        )
        assert response.status_code == 201
        [stored] = response.json()["files"]
        assert (stored["kind"], stored["media_type"]) == ("audio", "audio/webm")
        record_id = uuid.UUID(response.json()["id"])
        assert media.read_record(record_id, stored["path"]) == CLIP

    async def test_an_empty_body_starts_an_empty_record(self, api):
        response = await api.post("/api/custom/apps/receipts/records", json={})
        assert response.status_code == 201
        assert (response.json()["files"], response.json()["fields"]) == ([], {})

    @pytest.mark.parametrize("data", ["abc", "not base64!"])
    async def test_data_that_is_not_base64_is_a_422(self, api, data):
        photo = {"name": "photo-1.jpg", "media_type": "image/jpeg", "data": data}
        response = await api.post(
            "/api/custom/apps/receipts/records", json={"files": [photo]}
        )
        assert response.status_code == 422

    async def test_an_eleventh_photo_is_a_413_naming_the_limit(self, api):
        photos = [sent(f"photo-{n}.jpg", "image/jpeg", JPEG) for n in range(1, 12)]
        response = await api.post(
            "/api/custom/apps/receipts/records", json={"files": photos}
        )
        assert response.status_code == 413
        assert str(records.MAX_PHOTOS) in response.json()["detail"]

    async def test_a_file_whose_bytes_are_not_its_type_is_a_422_naming_it(self, api):
        response = await api.post(
            "/api/custom/apps/receipts/records",
            json={"files": [sent("photo-1.jpg", "image/jpeg", PNG)]},
        )
        assert response.status_code == 422
        assert "photo-1.jpg" in response.json()["detail"]

    async def test_a_failed_reading_is_a_409_with_its_message(self, api, monkeypatch):
        async def down(*args, **kwargs):
            raise reader.ReadError("the reader is down")

        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
        monkeypatch.setattr(reader, "read", down)
        response = await api.post(
            "/api/custom/apps/receipts/records", json={"files": [PHOTO]}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "the reader is down"

    async def test_a_failed_transcription_is_a_409_with_its_message(
        self, api, monkeypatch
    ):
        async def down(*args, **kwargs):
            raise transcribe.TranscribeError("Deepgram answered 401")

        monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)
        monkeypatch.setattr(transcribe, "transcribe", down)
        response = await api.post(
            "/api/custom/apps/sales_visit_debrief/records", json={"audio": SPOKEN}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "Deepgram answered 401"

    async def test_an_unknown_app_is_a_404(self, api):
        response = await api.post("/api/custom/apps/nope/records", json={})
        assert response.status_code == 404

    async def test_an_app_the_roles_may_not_open_is_a_403(
        self, api, driver, sessionmaker_for_test
    ):
        response = await api.post(
            "/api/custom/apps/receipts/records", json={"files": [PHOTO]}
        )
        assert response.status_code == 403
        assert await fresh_rows(sessionmaker_for_test, CustomRecord) == []


class TestSave:
    async def test_saving_answers_with_the_detail(self, api, session):
        record_id = await created(session)
        response = await api.put(
            f"/api/custom/records/{record_id}", json={"fields": HARBOR_FUEL}
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == DETAIL_KEYS
        assert (body["id"], body["fields"], body["counted"]) == (
            record_id,
            HARBOR_FUEL,
            False,
        )

    async def test_the_raw_event_is_committed(
        self, api, session, sessionmaker_for_test
    ):
        record_id = await created(session)
        await api.put(f"/api/custom/records/{record_id}", json={"fields": HARBOR_FUEL})
        [event] = await fresh_rows(
            sessionmaker_for_test, RawEvent, RawEvent.source_id == record_id
        )
        assert (event.source, event.object_type, event.raw_payload["fields"]) == (
            "custom",
            "receipts",
            HARBOR_FUEL,
        )

    async def test_the_actor_is_who_saved(self, api, session, monkeypatch):
        record_id = await created(session)
        monkeypatch.setattr(access, "actor", lambda: "lee")
        at(monkeypatch, 1)
        body = (
            await api.put(
                f"/api/custom/records/{record_id}", json={"fields": HARBOR_FUEL}
            )
        ).json()
        assert body["history"][-1] == {
            "action": "save",
            "actor": "lee",
            "at": (NOW + timedelta(minutes=1)).isoformat(),
        }

    async def test_a_second_save_is_an_edit(self, api, session, monkeypatch):
        record_id = await created(session)
        at(monkeypatch, 1)
        await api.put(f"/api/custom/records/{record_id}", json={"fields": HARBOR_FUEL})
        at(monkeypatch, 2)
        body = (
            await api.put(
                f"/api/custom/records/{record_id}",
                json={"fields": {**HARBOR_FUEL, "total": 50.0}},
            )
        ).json()
        assert [e["action"] for e in body["history"]] == ["create", "save", "edit"]

    async def test_an_unknown_field_is_a_422_naming_it(self, api, session):
        record_id = await created(session)
        response = await api.put(
            f"/api/custom/records/{record_id}", json={"fields": {"colour": "red"}}
        )
        assert response.status_code == 422
        assert "colour" in response.json()["detail"]

    async def test_a_label_outside_the_labels_is_a_422_naming_it(self, api, session):
        record_id = await created(session)
        response = await api.put(
            f"/api/custom/records/{record_id}", json={"fields": {"category": "snacks"}}
        )
        assert response.status_code == 422
        assert "snacks" in response.json()["detail"]

    async def test_a_failing_script_is_a_409_with_its_message(
        self, api, session, monkeypatch
    ):
        async def fails(app, record, ctx):
            raise scripts.ScriptError("mileage_log/script.py: no start reading")

        monkeypatch.setattr(scripts, "run", fails)
        record_id = await created(session, "mileage_log")
        response = await api.put(
            f"/api/custom/records/{record_id}",
            json={"fields": {"vehicle": "Truck 7", "stage": "end"}},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "mileage_log/script.py: no start reading"

    async def test_a_body_without_fields_is_a_422(self, api, session):
        record_id = await created(session)
        response = await api.put(f"/api/custom/records/{record_id}", json={})
        assert response.status_code == 422


class TestHear:
    async def test_a_clip_becomes_a_transcript_and_updates(
        self, api, session, heard_as, hearing
    ):
        heard_as("three, three two four")
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(
            f"/api/custom/records/{record_id}/hear",
            json={"audio": SPOKEN, "cursor": CURSOR},
        )
        assert response.status_code == 200
        assert response.json() == {"transcript": "three, three two four", **HEARD}
        assert hearing == [{"text": "three, three two four", "cursor": CURSOR}]

    async def test_the_cursor_defaults_to_none(self, api, session, heard_as, hearing):
        heard_as("three, three two four")
        record_id = await created(session, "perio_charting", files=[])
        await api.post(f"/api/custom/records/{record_id}/hear", json={"audio": SPOKEN})
        assert hearing == [{"text": "three, three two four", "cursor": None}]

    async def test_transcribing_off_is_a_409_naming_the_flag(self, api, session):
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(
            f"/api/custom/records/{record_id}/hear", json={"audio": SPOKEN}
        )
        assert response.status_code == 409
        assert (
            response.json()["detail"] == "transcribing is off: set TRANSCRIBE_ENABLED"
        )

    async def test_reading_off_is_a_409_naming_the_flag(self, api, session, heard_as):
        heard_as("three, three two four")
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(
            f"/api/custom/records/{record_id}/hear", json={"audio": SPOKEN}
        )
        assert response.status_code == 409
        assert response.json()["detail"] == "reading is off: set CUSTOM_ENABLED"

    async def test_a_clip_past_the_most_seconds_is_a_413(self, api, session):
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(
            f"/api/custom/records/{record_id}/hear",
            json={"audio": {"media_type": "audio/wav", "data": b64(wav(61))}},
        )
        assert response.status_code == 413
        assert str(records.MAX_CLIP_SECONDS) in response.json()["detail"]

    async def test_a_clip_whose_bytes_are_not_its_type_is_a_422(self, api, session):
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(
            f"/api/custom/records/{record_id}/hear",
            json={"audio": {"media_type": "audio/webm", "data": b64(JPEG)}},
        )
        assert response.status_code == 422

    async def test_a_body_without_audio_is_a_422(self, api, session):
        record_id = await created(session, "perio_charting", files=[])
        response = await api.post(f"/api/custom/records/{record_id}/hear", json={})
        assert response.status_code == 422


class TestListing:
    async def test_the_apps_saved_records_are_listed_newest_first(
        self, api, session, monkeypatch
    ):
        first = await saved(session)
        at(monkeypatch, 1)
        second = await saved(
            session, fields={**HARBOR_FUEL, "vendor": "Northside Office Supply"}
        )
        response = await api.get("/api/custom/records", params={"app": "receipts"})
        assert response.status_code == 200
        assert [r["id"] for r in response.json()] == [second, first]

    async def test_a_listed_record_carries_its_id_app_fields_and_saved_at(
        self, api, session
    ):
        record_id = await saved(session)
        body = (await api.get("/api/custom/records", params={"app": "receipts"})).json()
        assert body == [
            {
                "id": record_id,
                "app": "receipts",
                "fields": HARBOR_FUEL,
                "saved_at": NOW.isoformat(),
            }
        ]

    async def test_a_removed_record_leaves_the_listing(self, api, session):
        kept = await saved(session)
        gone = await saved(session)
        await api.delete(f"/api/custom/records/{gone}")
        body = (await api.get("/api/custom/records", params={"app": "receipts"})).json()
        assert [r["id"] for r in body] == [kept]

    async def test_an_app_with_no_records_lists_none(self, api):
        body = (await api.get("/api/custom/records", params={"app": "receipts"})).json()
        assert body == []

    async def test_the_app_is_required(self, api):
        assert (await api.get("/api/custom/records")).status_code == 422

    async def test_an_unknown_app_is_a_404(self, api):
        response = await api.get("/api/custom/records", params={"app": "nope"})
        assert response.status_code == 404

    async def test_an_app_the_roles_may_not_open_is_a_403(self, api, driver):
        response = await api.get("/api/custom/records", params={"app": "receipts"})
        assert response.status_code == 403


class TestDetail:
    async def test_the_detail_is_served(self, api, session):
        record_id = await saved(session)
        response = await api.get(f"/api/custom/records/{record_id}")
        assert response.status_code == 200
        body = response.json()
        assert set(body) == DETAIL_KEYS
        assert (body["fields"], body["files"], body["removed"]) == (
            HARBOR_FUEL,
            [PHOTO_FILE],
            False,
        )

    async def test_the_view_is_committed(self, api, session, sessionmaker_for_test):
        record_id = await saved(session)
        await api.get(f"/api/custom/records/{record_id}")
        notes = await fresh_rows(
            sessionmaker_for_test,
            CustomRecordAudit,
            CustomRecordAudit.record_id == uuid.UUID(record_id),
        )
        assert sorted(note.action for note in notes) == ["create", "save", "view"]

    async def test_a_record_a_rebuild_has_run_since_is_counted(self, api, session):
        record_id = await saved(session)
        session.add(EngineRun(ok=True, created_at=NOW + timedelta(minutes=1)))
        await session.flush()
        body = (await api.get(f"/api/custom/records/{record_id}")).json()
        assert body["counted"] is True

    async def test_a_record_saved_after_the_last_rebuild_is_not_counted(
        self, api, session
    ):
        session.add(EngineRun(ok=True, created_at=NOW - timedelta(minutes=1)))
        await session.flush()
        record_id = await saved(session)
        body = (await api.get(f"/api/custom/records/{record_id}")).json()
        assert body["counted"] is False


class TestFiles:
    async def test_the_bytes_are_served_with_their_media_type(self, api, session):
        record_id = await created(session)
        response = await api.get(f"/api/custom/records/{record_id}/files/photo-1.jpg")
        assert response.status_code == 200
        assert response.content == JPEG
        assert response.headers["content-type"] == "image/jpeg"

    async def test_a_clip_is_served_as_audio(self, api, session):
        made = await records.create(
            session,
            apps.load("sales_visit_debrief"),
            files=[],
            scan=None,
            audio=("audio/webm", CLIP),
            actor="admin",
        )
        path = made["files"][0]["path"]
        response = await api.get(f"/api/custom/records/{made['id']}/files/{path}")
        assert (response.content, response.headers["content-type"]) == (
            CLIP,
            "audio/webm",
        )

    async def test_a_file_the_record_does_not_have_is_a_404(self, api, session):
        record_id = await created(session)
        response = await api.get(f"/api/custom/records/{record_id}/files/photo-2.jpg")
        assert response.status_code == 404
        assert "photo-2.jpg" in response.json()["detail"]

    @pytest.mark.parametrize("path", ["%2e%2e/%2e%2e/etc/passwd", "a/%2e%2e/b"])
    async def test_a_path_that_climbs_is_a_404(self, api, session, path):
        record_id = await created(session)
        response = await api.get(f"/api/custom/records/{record_id}/files/{path}")
        assert response.status_code == 404


async def attached(api, record_id, body=SIGNATURE):
    return await api.post(f"/api/custom/records/{record_id}/files", json=body)


class TestAttach:
    async def test_a_signature_is_a_201_with_the_file(self, api, session):
        record_id = await created(session, "proof_of_delivery")
        response = await attached(api, record_id)
        assert response.status_code == 201
        assert response.json() == SIGNATURE_FILE

    async def test_the_file_is_committed(self, api, session, sessionmaker_for_test):
        record_id = await created(session, "proof_of_delivery")
        await attached(api, record_id)
        stored = await fresh_rows(
            sessionmaker_for_test,
            CustomRecordFile,
            CustomRecordFile.record_id == uuid.UUID(record_id),
        )
        assert sorted((f.path, f.kind) for f in stored) == [
            ("photo-1.jpg", "photo"),
            ("signature.png", "signature"),
        ]

    async def test_the_data_is_decoded_from_base64_before_it_is_stored(
        self, api, session
    ):
        record_id = await created(session, "proof_of_delivery")
        await attached(api, record_id)
        assert media.read_record(uuid.UUID(record_id), "signature.png") == PNG

    async def test_the_attached_file_is_served_with_its_media_type(self, api, session):
        record_id = await created(session, "proof_of_delivery")
        await attached(api, record_id)
        response = await api.get(f"/api/custom/records/{record_id}/files/signature.png")
        assert (
            response.status_code,
            response.content,
            response.headers["content-type"],
        ) == (200, PNG, "image/png")

    async def test_the_detail_lists_the_attached_file(self, api, session):
        record_id = await created(session, "proof_of_delivery")
        await attached(api, record_id)
        body = (await api.get(f"/api/custom/records/{record_id}")).json()
        assert body["files"] == [PHOTO_FILE, SIGNATURE_FILE]

    @pytest.mark.parametrize("data", ["abc", "not base64!"])
    async def test_data_that_is_not_base64_is_a_422(self, api, session, data):
        record_id = await created(session, "proof_of_delivery")
        response = await attached(api, record_id, {**SIGNATURE, "data": data})
        assert response.status_code == 422

    @pytest.mark.parametrize("key", ["name", "media_type", "data"])
    async def test_a_body_missing_a_key_is_a_422(self, api, session, key):
        record_id = await created(session, "proof_of_delivery")
        body = {name: value for name, value in SIGNATURE.items() if name != key}
        response = await attached(api, record_id, body)
        assert response.status_code == 422

    @pytest.mark.parametrize(
        "file",
        [
            sent("signature.png", "image/png", JPEG),
            sent("invoice.pdf", "application/pdf", b"%PDF-1.7\n%%EOF\n"),
        ],
        ids=["jpeg-as-png", "pdf"],
    )
    async def test_a_file_that_is_not_a_photo_of_its_type_is_a_422_naming_it(
        self, api, session, file
    ):
        record_id = await created(session, "proof_of_delivery")
        response = await attached(api, record_id, file)
        assert response.status_code == 422
        assert file["name"] in response.json()["detail"]

    async def test_an_eleventh_photo_is_a_413_naming_the_limit(self, api, session):
        ten = [(f"photo-{n}.jpg", "image/jpeg", JPEG) for n in range(1, 11)]
        record_id = await created(session, files=ten)
        response = await attached(
            api, record_id, sent("photo-11.jpg", "image/jpeg", JPEG)
        )
        assert response.status_code == 413
        assert str(records.MAX_PHOTOS) in response.json()["detail"]


class TestRemove:
    async def test_removing_answers_removed(self, api, session):
        record_id = await saved(session)
        response = await api.delete(f"/api/custom/records/{record_id}")
        assert response.status_code == 200
        assert response.json() == {"removed": True}

    async def test_the_removal_is_committed(self, api, session, sessionmaker_for_test):
        record_id = await saved(session)
        await api.delete(f"/api/custom/records/{record_id}")
        [stored] = await fresh_rows(
            sessionmaker_for_test, CustomRecord, CustomRecord.id == uuid.UUID(record_id)
        )
        assert stored.removed_at == NOW
        events = await fresh_rows(
            sessionmaker_for_test, RawEvent, RawEvent.source_id == record_id
        )
        assert sorted(e.raw_payload["removed"] for e in events) == [False, True]


class TestRecordRoutes:
    @pytest.mark.parametrize("method,route,body", RECORD_ROUTES, ids=RECORD_IDS)
    async def test_an_unknown_record_is_a_404(self, api, method, route, body):
        response = await api.request(
            method, f"/api/custom/records/{uuid.uuid4()}{route}", json=body
        )
        assert response.status_code == 404

    @pytest.mark.parametrize("method,route,body", RECORD_ROUTES, ids=RECORD_IDS)
    async def test_a_record_id_that_is_not_a_uuid_is_a_422(
        self, api, method, route, body
    ):
        response = await api.request(
            method, f"/api/custom/records/not-a-record{route}", json=body
        )
        assert response.status_code == 422

    @pytest.mark.parametrize("method,route,body", RECORD_ROUTES, ids=RECORD_IDS)
    async def test_a_record_of_an_app_the_roles_may_not_open_is_a_403(
        self, api, session, driver, method, route, body
    ):
        record_id = await created(session)
        response = await api.request(
            method, f"/api/custom/records/{record_id}{route}", json=body
        )
        assert response.status_code == 403
        assert "receipts" in response.json()["detail"]


class TestOpenApi:
    async def test_every_route_in_the_table_is_served(self, api):
        spec = (await api.get("/openapi.json")).json()
        served = {
            (method, path)
            for path, operations in spec["paths"].items()
            if path.startswith("/api/custom/")
            for method in operations
        }
        assert served == set(ROUTES)

    @pytest.mark.parametrize("operation", sorted(ROUTES), ids=lambda op: " ".join(op))
    async def test_each_error_answer_is_documented(self, api, operation):
        method, path = operation
        spec = (await api.get("/openapi.json")).json()
        documented = set(spec["paths"][path][method]["responses"])
        assert ROUTES[operation] <= documented
