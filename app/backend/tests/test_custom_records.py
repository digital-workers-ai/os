import struct
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app import media
from app.config import settings
from app.custom import audit, reader, records, scripts, transcribe
from app.engine import apps
from app.models import (
    CanonicalMember,
    CustomRecord,
    CustomRecordAudit,
    CustomRecordFile,
    EngineRun,
    Entity,
    EntityCanonical,
    RawEvent,
)
from tests.conftest import NOW

JPEG = b"\xff\xd8\xff\xe0 a receipt"
PNG = b"\x89PNG\r\n\x1a\n a signature"
WEBP = b"RIFF\x10\x00\x00\x00WEBPVP8  a shelf"
PHOTO = ("photo-1.jpg", "image/jpeg", JPEG)
PHOTO_FILE = {"path": "photo-1.jpg", "media_type": "image/jpeg", "kind": "photo"}
SIGNATURE_FILE = {
    "path": "signature.png",
    "media_type": "image/png",
    "kind": "signature",
}
STAMP = "2026-09-04T12:00:00Z"
HARBOR_FUEL = {
    "vendor": "Harbor Fuel",
    "date": "2026-09-03",
    "total": 48.2,
    "category": "fuel",
    "items": [{"description": "Diesel", "amount": 48.2}],
}
MILEAGE = {
    "vehicle": "Truck 7",
    "odometer": 1250,
    "stage": "end",
    "purpose": "delivery",
}
PERIO = {"patient": "Jordan Rivera", "exam_date": "2026-09-02"}
GRID = {
    "rows": {"3": {"status": "present"}},
    "cells": {"3:B": {"depth": 2, "bleeding": "bleeding"}},
}
TIRES = {"vehicle:tires": {"result": "fail", "defect": "Front left tread low"}}
CURSOR = {"row": "3", "column": "DB"}
HEARD = {
    "updates": [{"row": "3", "column": "DB", "field": "depth", "value": 3}],
    "cursor": {"row": "3", "column": "B"},
    "readback": "Tooth 3, DB 3",
}
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


def ebml(element: bytes, content: bytes) -> bytes:
    return element + bytes([0x80 | len(content)]) + content


def webm(milliseconds: float | None = None) -> bytes:
    info = ebml(b"\x2a\xd7\xb1", (1_000_000).to_bytes(3, "big"))
    if milliseconds is not None:
        info += ebml(b"\x44\x89", struct.pack(">d", milliseconds))
    header = ebml(b"\x1a\x45\xdf\xa3", ebml(b"\x42\x82", b"webm"))
    segment = b"\x18\x53\x80\x67\x01" + b"\xff" * 7
    return header + segment + ebml(b"\x15\x49\xa9\x66", info)


def wav(seconds: int, rate: int = 1000) -> bytes:
    samples = bytes(seconds * rate)
    fmt = struct.pack("<4sIHHIIHH", b"fmt ", 16, 1, 1, rate, rate, 1, 8)
    body = b"WAVE" + fmt + struct.pack("<4sI", b"data", len(samples)) + samples
    return struct.pack("<4sI", b"RIFF", len(body)) + body


def m4a(seconds: int) -> bytes:
    ftyp = struct.pack(">I4s4sI4s4s", 24, b"ftyp", b"M4A ", 0, b"M4A ", b"isom")
    mvhd = struct.pack(">I4sB3xIIII", 108, b"mvhd", 0, 0, 0, 1000, seconds * 1000)
    mvhd += bytes(108 - len(mvhd))
    return ftyp + struct.pack(">I4s", 8 + len(mvhd), b"moov") + mvhd


def pdf(pages: int) -> bytes:
    kids = b"".join(b"%d 0 obj << /Type /Page >> endobj\n" % n for n in range(pages))
    tree = b"<< /Type /Pages /Count %d >>\n" % pages
    return b"%PDF-1.7\n" + kids + tree + b"%%EOF\n"


CLIP = webm()


def photos(count: int) -> list[tuple[str, str, bytes]]:
    return [(f"photo-{n}.jpg", "image/jpeg", JPEG) for n in range(1, count + 1)]


def big_photo(name: str, size: int) -> tuple[str, str, bytes]:
    return (name, "image/jpeg", JPEG + bytes(size - len(JPEG)))


def entry(action: str, actor: str = "admin", minutes: int = 0) -> dict:
    at = NOW + timedelta(minutes=minutes)
    return {"action": action, "actor": actor, "at": at.isoformat()}


def at(monkeypatch, minutes: int):
    when = NOW + timedelta(minutes=minutes)
    monkeypatch.setattr(settings, "CLOCK_PINNED_AT", when)
    return when


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def read_as(monkeypatch):
    seen = []

    def install(answer):
        async def read(app, *, files, text, **kwargs):
            seen.append({"app": app.name, "files": files, "text": text})
            return answer

        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
        monkeypatch.setattr(reader, "read", read)
        return seen

    return install


@pytest.fixture
def unread(monkeypatch):
    async def read(*args, **kwargs):
        raise AssertionError("nothing was there to read")

    monkeypatch.setattr(reader, "read", read)


@pytest.fixture
def heard_as(monkeypatch):
    seen = []

    def install(*transcripts):
        queue = list(transcripts)

        async def fake(app, audio, media_type):
            seen.append({"app": app.name, "audio": audio, "media_type": media_type})
            return queue.pop(0)

        monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)
        monkeypatch.setattr(transcribe, "transcribe", fake)
        return seen

    return install


@pytest.fixture
def untranscribed(monkeypatch):
    async def fake(*args, **kwargs):
        raise AssertionError("transcribing is off")

    monkeypatch.setattr(transcribe, "transcribe", fake)


@pytest.fixture
def hearing(monkeypatch):
    seen = []

    async def hear(app, *, text, cursor, **kwargs):
        seen.append({"app": app.name, "text": text, "cursor": cursor})
        return HEARD

    monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
    monkeypatch.setattr(reader, "hear", hear)
    return seen


@pytest.fixture
def unheard(monkeypatch):
    async def hear(*args, **kwargs):
        raise AssertionError("nothing was said")

    monkeypatch.setattr(reader, "hear", hear)


@pytest.fixture
def scripted(monkeypatch):
    seen = []

    async def run(app, record, ctx):
        seen.append({"app": app.name, "record": dict(record), "ctx": ctx})
        return {"miles": 12}

    monkeypatch.setattr(scripts, "run", run)
    return seen


@pytest.fixture
def blank_script(monkeypatch):
    async def run(app, record, ctx):
        return {}

    monkeypatch.setattr(scripts, "run", run)


@pytest.fixture
def unscripted(monkeypatch):
    async def run(*args, **kwargs):
        raise AssertionError("this app has no script")

    monkeypatch.setattr(scripts, "run", run)


async def create(
    session, name="receipts", *, files=None, scan=None, audio=None, actor="admin"
):
    return await records.create(
        session,
        apps.load(name),
        files=[PHOTO] if files is None else files,
        scan=scan,
        audio=audio,
        actor=actor,
    )


async def save(session, created, fields, *, actor="admin"):
    return await records.save(
        session,
        apps.load(created["app"]),
        uuid.UUID(created["id"]),
        fields,
        actor=actor,
    )


async def saved(session, name="receipts", fields=HARBOR_FUEL, *, files=None):
    created = await create(session, name, files=files)
    await save(session, created, fields)
    return created


async def view(session, created, *, actor="admin"):
    return await records.view(session, uuid.UUID(created["id"]), actor=actor)


async def remove(session, created, *, actor="admin"):
    return await records.remove(session, uuid.UUID(created["id"]), actor=actor)


async def hear(session, created, audio=("audio/webm", CLIP), *, cursor=CURSOR):
    return await records.hear(
        session,
        apps.load(created["app"]),
        uuid.UUID(created["id"]),
        audio,
        cursor=cursor,
        actor="admin",
    )


async def attach(
    session, created, name="signature.png", media_type="image/png", data=PNG
):
    return await records.attach(
        session,
        apps.load(created["app"]),
        uuid.UUID(created["id"]),
        name,
        media_type,
        data,
        actor="admin",
    )


async def history(session, created):
    return await audit.history(session, uuid.UUID(created["id"]))


async def row(session, created):
    query = (
        select(CustomRecord)
        .where(CustomRecord.id == uuid.UUID(created["id"]))
        .execution_options(populate_existing=True)
    )
    return (await session.execute(query)).scalar_one()


async def file_rows(session, created):
    query = (
        select(CustomRecordFile)
        .where(CustomRecordFile.record_id == uuid.UUID(created["id"]))
        .order_by(CustomRecordFile.path)
    )
    return (await session.execute(query)).scalars().all()


async def raw_events(session, created):
    query = (
        select(RawEvent)
        .where(RawEvent.source == "custom", RawEvent.source_id == created["id"])
        .order_by(RawEvent.seq)
    )
    return (await session.execute(query)).scalars().all()


async def payload(session, created):
    return (await raw_events(session, created))[-1].raw_payload


async def count(session, model):
    return await session.scalar(select(func.count()).select_from(model))


async def rebuilt(session, minutes, *, ok=True):
    session.add(EngineRun(ok=ok, created_at=NOW + timedelta(minutes=minutes)))
    await session.flush()


async def became(session, entity_type, source_id, minted):
    canonical_id, entity_id = uuid.uuid4(), uuid.uuid4()
    session.add(
        EntityCanonical(
            canonical_id=canonical_id,
            entity_type=entity_type,
            anchor_key=f"custom|{entity_type}|{source_id}",
            minted_seq=minted,
            member_count=1,
        )
    )
    session.add(
        Entity(
            id=entity_id,
            source="custom",
            entity_type=entity_type,
            source_id=source_id,
            object_type="receipts",
            first_seq=minted,
        )
    )
    await session.flush()
    session.add(CanonicalMember(canonical_id=canonical_id, entity_id=entity_id))
    await session.flush()
    return canonical_id


async def bare_record(session):
    record = CustomRecord(
        id=uuid.uuid4(), app="receipts", recorded_by="admin", created_at=NOW
    )
    session.add(record)
    await session.flush()
    return record


class TestCreate:
    async def test_a_photo_becomes_a_record_row(self, session):
        created = await create(session, actor="kim")
        record = await row(session, created)
        assert (
            record.app,
            record.recorded_by,
            record.created_at,
            record.saved_at,
            record.removed_at,
        ) == ("receipts", "kim", NOW, None, None)

    async def test_a_photo_becomes_a_photo_file_row(self, session):
        created = await create(session)
        assert [
            (f.path, f.media_type, f.bytes, f.kind, f.created_at)
            for f in await file_rows(session, created)
        ] == [("photo-1.jpg", "image/jpeg", len(JPEG), "photo", NOW)]

    async def test_the_photo_bytes_are_written_to_the_record_media_store(self, session):
        created = await create(session)
        assert media.read_record(uuid.UUID(created["id"]), "photo-1.jpg") == JPEG

    @pytest.mark.parametrize(
        "name,file,kind",
        [
            ("receipts", ("photo-1.jpg", "image/jpeg", JPEG), "photo"),
            ("receipts", ("photo-1.png", "image/png", PNG), "photo"),
            ("receipts", ("photo-1.webp", "image/webp", WEBP), "photo"),
            ("supplier_invoices", ("invoice.pdf", "application/pdf", pdf(2)), "pdf"),
            ("proof_of_delivery", ("signature.png", "image/png", PNG), "signature"),
            ("proof_of_delivery", ("doorstep.png", "image/png", PNG), "photo"),
        ],
        ids=["jpeg", "png", "webp", "pdf", "signature", "png-not-a-screen-field"],
    )
    async def test_each_file_is_stored_with_its_kind(self, session, name, file, kind):
        created = await create(session, name, files=[file])
        assert [
            (f.path, f.media_type, f.kind) for f in await file_rows(session, created)
        ] == [(file[0], file[1], kind)]

    @pytest.mark.parametrize(
        "media_type,data",
        [("audio/webm", CLIP), ("audio/mp4", m4a(5)), ("audio/wav", wav(5))],
        ids=["webm", "m4a", "wav"],
    )
    async def test_a_clip_is_stored_as_an_audio_file(self, session, media_type, data):
        created = await create(
            session, "sales_visit_debrief", files=[], audio=(media_type, data)
        )
        [stored] = await file_rows(session, created)
        assert (stored.media_type, stored.bytes, stored.kind) == (
            media_type,
            len(data),
            "audio",
        )
        assert media.read_record(uuid.UUID(created["id"]), stored.path) == data

    async def test_a_record_can_start_with_nothing(self, session):
        created = await create(session, files=[])
        assert (created["files"], created["fields"]) == ([], {})
        assert await file_rows(session, created) == []

    async def test_creating_writes_a_create_audit_row(self, session):
        created = await create(session, actor="kim")
        assert await history(session, created) == [entry("create", "kim")]

    async def test_with_reading_off_the_fields_come_back_empty(self, session, unread):
        created = await create(session)
        assert created == {
            "id": str((await row(session, created)).id),
            "app": "receipts",
            "fields": {},
            "missing": [],
            "files": [PHOTO_FILE],
            "transcript": None,
        }

    async def test_with_reading_on_the_photos_are_read(self, session, read_as):
        seen = read_as({"fields": {"vendor": "Harbor Fuel"}, "missing": ["tax"]})
        await create(session)
        assert seen == [
            {"app": "receipts", "files": [("image/jpeg", JPEG)], "text": None}
        ]

    async def test_with_reading_on_the_reading_comes_back(self, session, read_as):
        read_as({"fields": {"vendor": "Harbor Fuel"}, "missing": ["tax"]})
        created = await create(session)
        assert (created["fields"], created["missing"]) == (
            {"vendor": "Harbor Fuel"},
            ["tax"],
        )

    async def test_a_pdf_is_read_after_the_photo_it_was_sent_with(
        self, session, read_as
    ):
        seen = read_as({"fields": {}, "missing": []})
        invoice = pdf(2)
        await create(
            session,
            "supplier_invoices",
            files=[PHOTO, ("invoice.pdf", "application/pdf", invoice)],
        )
        assert seen[0]["files"] == [
            ("image/jpeg", JPEG),
            ("application/pdf", invoice),
        ]

    async def test_a_scanned_code_fills_its_field_with_reading_off(
        self, session, unread
    ):
        created = await create(session, "equipment_checkout", files=[], scan="LAP-014")
        assert (created["fields"], created["missing"]) == ({"asset": "LAP-014"}, [])

    async def test_a_record_with_nothing_to_read_is_not_read(
        self, session, monkeypatch, unread
    ):
        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
        created = await create(session, "equipment_checkout", files=[], scan="LAP-014")
        assert created["fields"] == {"asset": "LAP-014"}

    async def test_a_scanned_code_wins_over_the_reading(self, session, read_as):
        read_as(
            {
                "fields": {"tracking_number": "1Z-MISREAD", "carrier": "ups"},
                "missing": [],
            }
        )
        created = await create(session, "mailroom", scan="1Z999AA10123456784")
        assert created["fields"] == {
            "tracking_number": "1Z999AA10123456784",
            "carrier": "ups",
        }

    async def test_with_transcribing_on_the_clip_is_transcribed(
        self, session, heard_as, unread
    ):
        seen = heard_as("Met Dana at Acme")
        await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
        )
        assert seen == [
            {"app": "sales_visit_debrief", "audio": CLIP, "media_type": "audio/webm"}
        ]

    async def test_with_both_on_the_transcript_is_what_is_read(
        self, session, heard_as, read_as
    ):
        heard_as("Met Dana at Acme")
        seen = read_as(
            {"fields": {"next_step": "Send the quote"}, "missing": ["account"]}
        )
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
        )
        assert seen == [
            {"app": "sales_visit_debrief", "files": [], "text": "Met Dana at Acme"}
        ]
        assert (created["transcript"], created["fields"], created["missing"]) == (
            "Met Dana at Acme",
            {"next_step": "Send the quote"},
            ["account"],
        )

    async def test_with_reading_off_the_transcript_comes_back_unread(
        self, session, heard_as, unread
    ):
        heard_as("Met Dana at Acme")
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
        )
        assert (created["transcript"], created["fields"]) == ("Met Dana at Acme", {})

    async def test_with_transcribing_off_the_clip_is_kept_untranscribed(
        self, session, monkeypatch, untranscribed, unread
    ):
        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
        )
        assert (created["transcript"], created["fields"]) == (None, {})
        assert [f["kind"] for f in created["files"]] == ["audio"]

    async def test_a_failed_reading_raises_its_error(self, session, monkeypatch):
        async def down(*args, **kwargs):
            raise reader.ReadError("the reader is down")

        monkeypatch.setattr(settings, "CUSTOM_ENABLED", True)
        monkeypatch.setattr(reader, "read", down)
        with pytest.raises(reader.ReadError, match="the reader is down"):
            await create(session)

    async def test_a_failed_transcription_raises_its_error(self, session, monkeypatch):
        async def down(*args, **kwargs):
            raise transcribe.TranscribeError("Deepgram answered 401")

        monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)
        monkeypatch.setattr(transcribe, "transcribe", down)
        with pytest.raises(transcribe.TranscribeError, match="401"):
            await create(
                session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
            )


class TestLimits:
    def test_the_limits_are_the_plans(self):
        assert (
            records.MAX_PHOTOS,
            records.MAX_PDF_PAGES,
            records.MAX_CLIP_SECONDS,
            records.MAX_REQUEST_BYTES,
        ) == (10, 100, 60, 32 * 1024 * 1024)

    async def test_ten_photos_are_taken(self, session):
        created = await create(session, files=photos(10))
        assert len(await file_rows(session, created)) == 10

    async def test_an_eleventh_photo_is_too_large(self, session):
        with pytest.raises(records.TooLarge, match=str(records.MAX_PHOTOS)):
            await create(session, files=photos(11))

    async def test_a_refusal_past_a_limit_writes_no_record(self, session):
        with pytest.raises(records.TooLarge):
            await create(session, files=photos(11))
        assert await count(session, CustomRecord) == 0

    async def test_a_pdf_of_the_most_pages_is_taken(self, session):
        created = await create(
            session,
            "supplier_invoices",
            files=[("invoice.pdf", "application/pdf", pdf(100))],
        )
        assert [f["kind"] for f in created["files"]] == ["pdf"]

    async def test_a_pdf_past_the_most_pages_is_too_large(self, session):
        with pytest.raises(records.TooLarge, match=str(records.MAX_PDF_PAGES)):
            await create(
                session,
                "supplier_invoices",
                files=[("invoice.pdf", "application/pdf", pdf(101))],
            )

    async def test_a_second_pdf_is_too_large(self, session):
        with pytest.raises(records.TooLarge):
            await create(
                session,
                "supplier_invoices",
                files=[
                    ("invoice.pdf", "application/pdf", pdf(1)),
                    ("credit-note.pdf", "application/pdf", pdf(1)),
                ],
            )

    async def test_a_request_of_the_most_bytes_is_taken(self, session):
        half = records.MAX_REQUEST_BYTES // 2
        created = await create(
            session,
            files=[big_photo("photo-1.jpg", half), big_photo("photo-2.jpg", half)],
        )
        assert sum(f.bytes for f in await file_rows(session, created)) == (
            records.MAX_REQUEST_BYTES
        )

    async def test_a_request_past_the_most_bytes_is_too_large(self, session):
        half = records.MAX_REQUEST_BYTES // 2
        with pytest.raises(records.TooLarge):
            await create(
                session,
                files=[
                    big_photo("photo-1.jpg", half),
                    big_photo("photo-2.jpg", half + 1),
                ],
            )

    async def test_the_clip_counts_toward_the_request_bytes(self, session):
        size = records.MAX_REQUEST_BYTES - len(CLIP) + 1
        with pytest.raises(records.TooLarge):
            await create(
                session,
                "property_inspection",
                files=[big_photo("photo-1.jpg", size)],
                audio=("audio/webm", CLIP),
            )

    async def test_a_wav_clip_of_the_most_seconds_is_taken(self, session):
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/wav", wav(60))
        )
        assert [f["kind"] for f in created["files"]] == ["audio"]

    async def test_a_wav_clip_past_the_most_seconds_is_too_large(self, session):
        with pytest.raises(records.TooLarge, match=str(records.MAX_CLIP_SECONDS)):
            await create(
                session, "sales_visit_debrief", files=[], audio=("audio/wav", wav(61))
            )

    async def test_a_webm_clip_whose_header_says_the_most_seconds_is_taken(
        self, session
    ):
        created = await create(
            session,
            "sales_visit_debrief",
            files=[],
            audio=("audio/webm", webm(60_000.0)),
        )
        assert [f["kind"] for f in created["files"]] == ["audio"]

    async def test_a_webm_clip_whose_header_says_more_seconds_is_too_large(
        self, session
    ):
        with pytest.raises(records.TooLarge, match=str(records.MAX_CLIP_SECONDS)):
            await create(
                session,
                "sales_visit_debrief",
                files=[],
                audio=("audio/webm", webm(61_000.0)),
            )

    async def test_an_m4a_clip_whose_header_says_more_seconds_is_too_large(
        self, session
    ):
        with pytest.raises(records.TooLarge, match=str(records.MAX_CLIP_SECONDS)):
            await create(
                session, "sales_visit_debrief", files=[], audio=("audio/mp4", m4a(61))
            )

    async def test_a_clip_whose_header_states_no_length_is_taken(self, session):
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", webm())
        )
        assert [f["kind"] for f in created["files"]] == ["audio"]


class TestSniff:
    @pytest.mark.parametrize(
        "file",
        [
            ("photo-1.jpg", "image/jpeg", PNG),
            ("photo-1.png", "image/png", JPEG),
            ("photo-1.webp", "image/webp", wav(1)),
            ("invoice.pdf", "application/pdf", JPEG),
            ("photo-1.gif", "image/gif", b"GIF89a a gif"),
            ("notes.txt", "text/plain", b"plain words"),
            ("clip.webm", "audio/webm", CLIP),
        ],
        ids=[
            "png-as-jpeg",
            "jpeg-as-png",
            "wav-as-webp",
            "jpeg-as-pdf",
            "gif",
            "text",
            "a-clip-among-the-files",
        ],
    )
    async def test_a_file_that_is_not_a_photo_or_pdf_of_its_type_is_refused(
        self, session, file
    ):
        with pytest.raises(records.Refused, match=file[0]):
            await create(session, files=[file])

    @pytest.mark.parametrize(
        "audio",
        [
            ("audio/webm", wav(1)),
            ("audio/wav", CLIP),
            ("audio/mp4", JPEG),
            ("image/jpeg", JPEG),
        ],
        ids=["wav-as-webm", "webm-as-wav", "jpeg-as-m4a", "a-photo-as-the-clip"],
    )
    async def test_a_clip_that_is_not_audio_of_its_type_is_refused(
        self, session, audio
    ):
        with pytest.raises(records.Refused, match=audio[0]):
            await create(session, "sales_visit_debrief", files=[], audio=audio)

    async def test_a_refused_file_writes_no_record(self, session):
        with pytest.raises(records.Refused):
            await create(session, files=[("photo-1.jpg", "image/jpeg", PNG)])
        assert await count(session, CustomRecord) == 0

    async def test_a_file_name_that_climbs_is_refused(self, session):
        with pytest.raises(records.Refused):
            await create(session, files=[("../photo-1.jpg", "image/jpeg", JPEG)])


class TestSave:
    async def test_saving_writes_the_raw_event_the_contract_names(self, session):
        created = await saved(session)
        [event] = await raw_events(session, created)
        assert (event.source, event.object_type, event.source_id) == (
            "custom",
            "receipts",
            created["id"],
        )
        assert event.raw_payload == {
            "record": created["id"],
            "app": "receipts",
            "recorded_at": STAMP,
            "recorded_by": "admin",
            "removed": False,
            "currency": "USD",
            "files": [PHOTO_FILE],
            "fields": HARBOR_FUEL,
        }

    async def test_recorded_at_is_when_the_record_was_created(
        self, session, monkeypatch
    ):
        created = await create(session)
        at(monkeypatch, 5)
        await save(session, created, HARBOR_FUEL)
        assert (await payload(session, created))["recorded_at"] == STAMP

    async def test_recorded_by_is_who_created_the_record(self, session):
        created = await create(session, actor="kim")
        await save(session, created, HARBOR_FUEL, actor="lee")
        assert (await payload(session, created))["recorded_by"] == "kim"

    async def test_an_app_without_money_voice_or_template_carries_none_of_them(
        self, session
    ):
        created = await saved(
            session,
            "equipment_checkout",
            {"asset": "LAP-014", "action": "check_out"},
            files=[],
        )
        assert set(await payload(session, created)) == {
            "record",
            "app",
            "recorded_at",
            "recorded_by",
            "removed",
            "files",
            "fields",
        }

    async def test_a_money_field_in_a_list_brings_the_currency(
        self, session, blank_script
    ):
        created = await saved(
            session,
            "shelf_audit",
            {"location": "Store 4, aisle 9", "items": [{"shelf_price": 3.49}]},
        )
        assert (await payload(session, created))["currency"] == "USD"

    async def test_a_voice_app_carries_its_transcript(self, session, heard_as, unread):
        heard_as("Met Dana at Acme")
        created = await create(
            session, "sales_visit_debrief", files=[], audio=("audio/webm", CLIP)
        )
        await save(session, created, {"next_step": "Send the quote"})
        assert (await payload(session, created))["transcript"] == "Met Dana at Acme"

    async def test_a_voice_app_never_transcribed_carries_no_transcript(self, session):
        created = await saved(
            session, "sales_visit_debrief", {"next_step": "Send the quote"}, files=[]
        )
        assert (await payload(session, created))["transcript"] is None

    async def test_a_grid_app_carries_its_rows_and_cells(self, session):
        created = await saved(
            session, "perio_charting", {**PERIO, "template": GRID}, files=[]
        )
        assert await payload(session, created) == {
            "record": created["id"],
            "app": "perio_charting",
            "recorded_at": STAMP,
            "recorded_by": "admin",
            "removed": False,
            "transcript": None,
            "files": [],
            "fields": PERIO,
            "template": {**GRID, "items": {}},
        }

    async def test_a_checklist_app_carries_its_items(self, session):
        created = await saved(
            session,
            "vehicle_pre_trip",
            {"vehicle": "Truck 7", "template": {"items": TIRES}},
            files=[],
        )
        assert (await payload(session, created))["template"] == {
            "rows": {},
            "cells": {},
            "items": TIRES,
        }

    async def test_a_template_app_saved_without_template_values_carries_empty_ones(
        self, session
    ):
        created = await saved(
            session, "vehicle_pre_trip", {"vehicle": "Truck 7"}, files=[]
        )
        assert (await payload(session, created))["template"] == {
            "rows": {},
            "cells": {},
            "items": {},
        }

    async def test_saved_at_is_set_on_the_first_save(self, session, monkeypatch):
        created = await create(session)
        when = at(monkeypatch, 1)
        await save(session, created, HARBOR_FUEL)
        assert (await row(session, created)).saved_at == when

    async def test_saved_at_stays_at_the_first_save(self, session, monkeypatch):
        created = await create(session)
        first = at(monkeypatch, 1)
        await save(session, created, HARBOR_FUEL)
        at(monkeypatch, 2)
        await save(session, created, {**HARBOR_FUEL, "total": 50.0})
        assert (await row(session, created)).saved_at == first

    async def test_the_first_save_is_a_save_and_later_ones_are_edits(
        self, session, monkeypatch
    ):
        created = await create(session)
        at(monkeypatch, 1)
        await save(session, created, HARBOR_FUEL)
        at(monkeypatch, 2)
        await save(session, created, {**HARBOR_FUEL, "total": 50.0}, actor="lee")
        assert await history(session, created) == [
            entry("create"),
            entry("save", minutes=1),
            entry("edit", "lee", 2),
        ]

    async def test_an_edit_appends_a_newer_raw_event(self, session):
        created = await saved(session)
        await save(session, created, {**HARBOR_FUEL, "total": 50.0})
        assert [
            e.raw_payload["fields"]["total"] for e in await raw_events(session, created)
        ] == [
            48.2,
            50.0,
        ]

    async def test_saving_returns_the_detail(self, session, monkeypatch):
        created = await create(session)
        at(monkeypatch, 1)
        detail = await save(session, created, HARBOR_FUEL)
        assert detail == {
            "id": created["id"],
            "app": "receipts",
            "fields": HARBOR_FUEL,
            "files": [PHOTO_FILE],
            "history": [entry("create"), entry("save", minutes=1)],
            "counted": False,
            "entity": None,
            "removed": False,
        }

    async def test_the_script_fills_its_fields(self, session, scripted):
        created = await saved(session, "mileage_log", MILEAGE)
        assert (await payload(session, created))["fields"] == {**MILEAGE, "miles": 12}

    async def test_the_script_is_given_the_app_the_fields_and_a_context(
        self, session, scripted
    ):
        await saved(session, "mileage_log", MILEAGE)
        [call] = scripted
        assert (call["app"], call["record"]) == ("mileage_log", MILEAGE)
        assert isinstance(call["ctx"], scripts.Context)

    async def test_an_app_without_a_script_runs_none(self, session, unscripted):
        created = await saved(session)
        assert (await payload(session, created))["fields"] == HARBOR_FUEL

    async def test_a_failing_script_raises_its_error(self, session, monkeypatch):
        async def fails(app, record, ctx):
            raise scripts.ScriptError("mileage_log/script.py: no start reading")

        monkeypatch.setattr(scripts, "run", fails)
        created = await create(session, "mileage_log")
        with pytest.raises(scripts.ScriptError, match="no start reading"):
            await save(session, created, MILEAGE)

    async def test_a_failing_script_saves_nothing(self, session, monkeypatch):
        async def fails(app, record, ctx):
            raise scripts.ScriptError("mileage_log/script.py: no start reading")

        monkeypatch.setattr(scripts, "run", fails)
        created = await create(session, "mileage_log")
        with pytest.raises(scripts.ScriptError):
            await save(session, created, MILEAGE)
        assert await raw_events(session, created) == []
        assert (await row(session, created)).saved_at is None
        assert await history(session, created) == [entry("create")]

    async def test_saving_an_unknown_record_is_missing(self, session):
        with pytest.raises(records.Missing):
            await records.save(
                session, apps.load("receipts"), uuid.uuid4(), HARBOR_FUEL, actor="admin"
            )


class TestValidation:
    async def test_known_labels_and_empty_values_are_taken(self, session):
        fields = {
            "item": "Pallet of mugs",
            "damage": ["broken", "dented"],
            "severity": None,
        }
        created = await saved(session, "damage_claims", fields)
        assert (await payload(session, created))["fields"] == fields

    async def test_an_unknown_field_is_refused_by_name(self, session):
        created = await create(session)
        with pytest.raises(records.Refused, match="colour"):
            await save(session, created, {"colour": "red"})

    async def test_a_label_outside_the_field_labels_is_refused(self, session):
        created = await create(session)
        with pytest.raises(records.Refused, match="snacks"):
            await save(session, created, {"category": "snacks"})

    async def test_a_many_of_with_one_unknown_label_is_refused(self, session):
        created = await create(session, "damage_claims")
        with pytest.raises(records.Refused, match="crushed"):
            await save(session, created, {"damage": ["broken", "crushed"]})

    async def test_an_unknown_list_field_is_refused(self, session):
        created = await create(session)
        with pytest.raises(records.Refused, match="colour"):
            await save(session, created, {"items": [{"colour": "red"}]})

    async def test_a_list_label_outside_its_labels_is_refused(self, session):
        created = await create(session, "food_safety_log", files=[])
        with pytest.raises(records.Refused, match="fridge"):
            await save(
                session, created, {"readings": [{"unit": "fridge", "temperature": 37}]}
            )

    async def test_template_values_on_an_app_without_a_template_are_refused(
        self, session
    ):
        created = await create(session)
        with pytest.raises(records.Refused, match="template"):
            await save(session, created, {**HARBOR_FUEL, "template": {"items": TIRES}})

    async def test_an_unknown_part_of_the_template_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="teeth"):
            await save(session, created, {"template": {"teeth": {}}})

    async def test_a_row_outside_the_grid_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="33"):
            await save(
                session, created, {"template": {"rows": {"33": {"status": "present"}}}}
            )

    async def test_a_column_outside_the_grid_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="3:X"):
            await save(session, created, {"template": {"cells": {"3:X": {"depth": 3}}}})

    async def test_a_row_label_outside_its_labels_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="gone"):
            await save(
                session, created, {"template": {"rows": {"3": {"status": "gone"}}}}
            )

    async def test_a_cell_label_outside_its_labels_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="lots"):
            await save(
                session, created, {"template": {"cells": {"3:B": {"bleeding": "lots"}}}}
            )

    async def test_an_unknown_cell_field_is_refused(self, session):
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="colour"):
            await save(
                session, created, {"template": {"cells": {"3:B": {"colour": "red"}}}}
            )

    async def test_an_item_outside_the_checklist_is_refused(self, session):
        created = await create(session, "vehicle_pre_trip", files=[])
        with pytest.raises(records.Refused, match="vehicle:radio"):
            await save(
                session,
                created,
                {"template": {"items": {"vehicle:radio": {"result": "pass"}}}},
            )

    async def test_a_refused_save_writes_nothing(self, session):
        created = await create(session)
        with pytest.raises(records.Refused):
            await save(session, created, {"category": "snacks"})
        assert await raw_events(session, created) == []
        assert (await row(session, created)).saved_at is None
        assert await history(session, created) == [entry("create")]


class TestView:
    async def test_viewing_writes_a_view_audit_row(self, session, monkeypatch):
        created = await saved(session)
        at(monkeypatch, 2)
        await view(session, created, actor="lee")
        assert (await history(session, created))[-1] == entry("view", "lee", 2)

    async def test_the_detail_history_includes_this_view(self, session, monkeypatch):
        created = await create(session)
        at(monkeypatch, 1)
        await save(session, created, HARBOR_FUEL)
        at(monkeypatch, 2)
        detail = await view(session, created)
        assert detail["history"] == [
            entry("create"),
            entry("save", minutes=1),
            entry("view", minutes=2),
        ]

    async def test_the_detail_has_the_contract_keys(self, session):
        created = await saved(session)
        assert set(await view(session, created)) == DETAIL_KEYS

    async def test_the_detail_carries_the_saved_fields_and_files(self, session):
        created = await saved(session)
        detail = await view(session, created)
        assert (detail["id"], detail["app"], detail["fields"], detail["files"]) == (
            created["id"],
            "receipts",
            HARBOR_FUEL,
            [PHOTO_FILE],
        )

    async def test_the_detail_carries_the_latest_edit(self, session):
        created = await saved(session)
        await save(session, created, {**HARBOR_FUEL, "total": 50.0})
        assert (await view(session, created))["fields"]["total"] == 50.0

    async def test_a_template_record_shows_its_template_among_its_fields(self, session):
        created = await saved(
            session, "perio_charting", {**PERIO, "template": GRID}, files=[]
        )
        assert (await view(session, created))["fields"] == {
            **PERIO,
            "template": {**GRID, "items": {}},
        }

    async def test_an_unsaved_record_has_no_fields_and_is_not_counted(self, session):
        created = await create(session)
        await rebuilt(session, 1)
        detail = await view(session, created)
        assert (detail["fields"], detail["counted"]) == ({}, False)

    async def test_a_saved_record_is_not_counted_before_any_rebuild(self, session):
        created = await saved(session)
        assert (await view(session, created))["counted"] is False

    async def test_a_rebuild_that_finished_before_the_save_does_not_count_it(
        self, session
    ):
        created = await saved(session)
        await rebuilt(session, -1)
        assert (await view(session, created))["counted"] is False

    async def test_a_rebuild_that_finished_at_the_save_does_not_count_it(self, session):
        created = await saved(session)
        await rebuilt(session, 0)
        assert (await view(session, created))["counted"] is False

    async def test_a_failed_rebuild_after_the_save_does_not_count_it(self, session):
        created = await saved(session)
        await rebuilt(session, 1, ok=False)
        assert (await view(session, created))["counted"] is False

    async def test_a_rebuild_that_finished_after_the_save_counts_it(self, session):
        created = await saved(session)
        await rebuilt(session, 1)
        assert (await view(session, created))["counted"] is True

    async def test_the_entity_is_none_before_a_rebuild(self, session):
        created = await saved(session)
        assert (await view(session, created))["entity"] is None

    async def test_the_entity_is_the_parent_the_record_became(self, session):
        created = await saved(session)
        parent = await became(session, "expense", created["id"], 1)
        await became(session, "expense_item", f"{created['id']}:items:0", 2)
        assert (await view(session, created))["entity"] == {
            "type": "expense",
            "id": str(parent),
        }

    async def test_a_removed_record_says_so(self, session):
        created = await saved(session)
        await remove(session, created)
        assert (await view(session, created))["removed"] is True

    async def test_viewing_an_unknown_record_is_missing(self, session):
        with pytest.raises(records.Missing):
            await records.view(session, uuid.uuid4(), actor="admin")


class TestListing:
    async def test_saved_records_are_listed_newest_first(self, session, monkeypatch):
        first = await saved(session)
        at(monkeypatch, 1)
        second = await saved(
            session, fields={**HARBOR_FUEL, "vendor": "Northside Office Supply"}
        )
        assert [r["id"] for r in await records.listing(session, "receipts")] == [
            second["id"],
            first["id"],
        ]

    async def test_a_listed_record_carries_its_id_app_fields_and_saved_at(
        self, session
    ):
        created = await saved(session)
        assert await records.listing(session, "receipts") == [
            {
                "id": created["id"],
                "app": "receipts",
                "fields": HARBOR_FUEL,
                "saved_at": NOW.isoformat(),
            }
        ]

    async def test_a_listed_record_carries_its_latest_edit(self, session):
        created = await saved(session)
        await save(session, created, {**HARBOR_FUEL, "total": 50.0})
        [listed] = await records.listing(session, "receipts")
        assert listed["fields"]["total"] == 50.0

    async def test_unsaved_records_are_left_out(self, session):
        await create(session)
        assert await records.listing(session, "receipts") == []

    async def test_removed_records_are_left_out(self, session):
        kept = await saved(session)
        await remove(session, await saved(session))
        assert [r["id"] for r in await records.listing(session, "receipts")] == [
            kept["id"]
        ]

    async def test_other_apps_records_are_left_out(self, session):
        await saved(session, "check_deposits", {"payer": "Acme Dental"})
        assert await records.listing(session, "receipts") == []

    async def test_listing_writes_no_audit_rows(self, session):
        await saved(session)
        before = await count(session, CustomRecordAudit)
        await records.listing(session, "receipts")
        assert await count(session, CustomRecordAudit) == before


class TestRemove:
    async def test_removing_appends_the_removed_payload(self, session, monkeypatch):
        created = await saved(session)
        at(monkeypatch, 2)
        await remove(session, created)
        events = await raw_events(session, created)
        assert len(events) == 2
        assert (events[-1].object_type, events[-1].raw_payload) == (
            "receipts",
            {
                "record": created["id"],
                "app": "receipts",
                "removed": True,
                "recorded_at": STAMP,
                "recorded_by": "admin",
            },
        )

    async def test_removing_sets_removed_at(self, session, monkeypatch):
        created = await saved(session)
        when = at(monkeypatch, 2)
        await remove(session, created)
        assert (await row(session, created)).removed_at == when

    async def test_removing_writes_a_remove_audit_row(self, session, monkeypatch):
        created = await saved(session)
        at(monkeypatch, 2)
        await remove(session, created, actor="lee")
        assert (await history(session, created))[-1] == entry("remove", "lee", 2)

    async def test_removing_an_unknown_record_is_missing(self, session):
        with pytest.raises(records.Missing):
            await records.remove(session, uuid.uuid4(), actor="admin")


class TestHear:
    async def test_the_clip_is_stored_as_an_audio_file(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four")
        created = await create(session, "perio_charting", files=[])
        await hear(session, created)
        [stored] = await file_rows(session, created)
        assert (stored.kind, stored.media_type, stored.bytes) == (
            "audio",
            "audio/webm",
            len(CLIP),
        )
        assert media.read_record(uuid.UUID(created["id"]), stored.path) == CLIP

    async def test_a_second_clip_is_kept_beside_the_first(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four", "four, two two three")
        created = await create(session, "perio_charting", files=[])
        await hear(session, created)
        await hear(session, created)
        stored = await file_rows(session, created)
        assert [f.kind for f in stored] == ["audio", "audio"]
        assert len({f.path for f in stored}) == 2

    async def test_transcribe_is_given_the_app_the_clip_and_its_type(
        self, session, heard_as, hearing
    ):
        seen = heard_as("three, three two four")
        created = await create(session, "perio_charting", files=[])
        await hear(session, created)
        assert seen == [
            {"app": "perio_charting", "audio": CLIP, "media_type": "audio/webm"}
        ]

    async def test_the_transcript_and_the_cursor_reach_the_reader(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four")
        created = await create(session, "perio_charting", files=[])
        await hear(session, created)
        assert hearing == [
            {"app": "perio_charting", "text": "three, three two four", "cursor": CURSOR}
        ]

    async def test_hearing_returns_the_transcript_and_the_reading(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four")
        created = await create(session, "perio_charting", files=[])
        assert await hear(session, created) == {
            "transcript": "three, three two four",
            **HEARD,
        }

    async def test_an_empty_transcript_is_not_read(self, session, heard_as, unheard):
        heard_as("")
        created = await create(session, "perio_charting", files=[])
        assert await hear(session, created) == {
            "transcript": "",
            "updates": [],
            "cursor": CURSOR,
            "readback": "",
        }

    async def test_what_was_heard_is_the_transcript_the_save_carries(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four", "four, two two three")
        created = await create(session, "perio_charting", files=[])
        await hear(session, created)
        await hear(session, created)
        await save(session, created, PERIO)
        assert (await payload(session, created))["transcript"] == (
            "three, three two four\nfour, two two three"
        )

    async def test_a_clip_past_the_most_seconds_is_too_large(
        self, session, heard_as, unheard
    ):
        heard_as("never heard")
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.TooLarge, match=str(records.MAX_CLIP_SECONDS)):
            await hear(session, created, ("audio/wav", wav(61)))

    async def test_a_clip_that_is_not_audio_of_its_type_is_refused(
        self, session, heard_as, unheard
    ):
        heard_as("never heard")
        created = await create(session, "perio_charting", files=[])
        with pytest.raises(records.Refused, match="audio/webm"):
            await hear(session, created, ("audio/webm", wav(1)))

    async def test_hearing_an_unknown_record_is_missing(
        self, session, heard_as, hearing
    ):
        heard_as("three, three two four")
        with pytest.raises(records.Missing):
            await records.hear(
                session,
                apps.load("perio_charting"),
                uuid.uuid4(),
                ("audio/webm", CLIP),
                cursor=None,
                actor="admin",
            )


class TestAttach:
    async def test_a_signature_comes_back_as_a_signature_file(self, session):
        created = await create(session, "proof_of_delivery")
        assert await attach(session, created) == SIGNATURE_FILE

    async def test_the_file_becomes_a_file_row_beside_the_photo(self, session):
        created = await create(session, "proof_of_delivery")
        await attach(session, created)
        assert [
            (f.path, f.media_type, f.bytes, f.kind, f.created_at)
            for f in await file_rows(session, created)
        ] == [
            ("photo-1.jpg", "image/jpeg", len(JPEG), "photo", NOW),
            ("signature.png", "image/png", len(PNG), "signature", NOW),
        ]

    async def test_the_bytes_are_written_to_the_record_media_store(self, session):
        created = await create(session, "proof_of_delivery")
        await attach(session, created)
        assert media.read_record(uuid.UUID(created["id"]), "signature.png") == PNG

    @pytest.mark.parametrize(
        "name,file,kind",
        [
            ("proof_of_delivery", ("signature.png", "image/png", PNG), "signature"),
            ("proof_of_delivery", ("signature.jpg", "image/jpeg", JPEG), "signature"),
            ("proof_of_delivery", ("doorstep.png", "image/png", PNG), "photo"),
            ("proof_of_delivery", ("doorstep.webp", "image/webp", WEBP), "photo"),
            ("receipts", ("signature.png", "image/png", PNG), "photo"),
        ],
        ids=[
            "signature",
            "signature-as-jpeg",
            "png-not-a-screen-field",
            "webp",
            "an-app-without-a-screen",
        ],
    )
    async def test_each_photo_type_is_taken_with_its_kind(
        self, session, name, file, kind
    ):
        created = await create(session, name, files=[])
        assert await attach(session, created, *file) == {
            "path": file[0],
            "media_type": file[1],
            "kind": kind,
        }

    @pytest.mark.parametrize(
        "file",
        [
            ("signature.png", "image/png", JPEG),
            ("signature.jpg", "image/jpeg", PNG),
            ("signature.webp", "image/webp", wav(1)),
            ("invoice.pdf", "application/pdf", pdf(1)),
            ("clip.webm", "audio/webm", CLIP),
            ("signature.gif", "image/gif", b"GIF89a a gif"),
        ],
        ids=["jpeg-as-png", "png-as-jpeg", "wav-as-webp", "pdf", "a-clip", "gif"],
    )
    async def test_a_file_that_is_not_a_photo_of_its_type_is_refused_by_name(
        self, session, file
    ):
        created = await create(session, "proof_of_delivery", files=[])
        with pytest.raises(records.Refused, match=file[0]):
            await attach(session, created, *file)

    async def test_a_refused_file_writes_no_file_row(self, session):
        created = await create(session, "proof_of_delivery", files=[])
        with pytest.raises(records.Refused):
            await attach(session, created, "signature.png", "image/png", JPEG)
        assert await file_rows(session, created) == []

    @pytest.mark.parametrize(
        "name",
        ["../signature.png", "signature 1.png", "a" * 117 + ".png"],
        ids=["climbs", "a-space", "too-long"],
    )
    async def test_a_name_the_media_store_would_refuse_is_refused(self, session, name):
        created = await create(session, "proof_of_delivery", files=[])
        with pytest.raises(records.Refused):
            await attach(session, created, name, "image/png", PNG)

    async def test_a_file_of_the_most_bytes_is_taken(self, session):
        created = await create(session, "proof_of_delivery", files=[])
        data = PNG + bytes(media.MAX_FILE_BYTES - len(PNG))
        await attach(session, created, "signature.png", "image/png", data)
        [stored] = await file_rows(session, created)
        assert stored.bytes == media.MAX_FILE_BYTES

    async def test_a_file_past_the_most_bytes_is_too_large(self, session):
        created = await create(session, "proof_of_delivery", files=[])
        data = PNG + bytes(media.MAX_FILE_BYTES + 1 - len(PNG))
        with pytest.raises(records.TooLarge):
            await attach(session, created, "signature.png", "image/png", data)

    async def test_a_tenth_photo_is_taken(self, session):
        created = await create(session, files=photos(9))
        await attach(session, created, "photo-10.jpg", "image/jpeg", JPEG)
        assert len(await file_rows(session, created)) == 10

    async def test_an_eleventh_photo_is_too_large(self, session):
        created = await create(session, files=photos(10))
        with pytest.raises(records.TooLarge, match=str(records.MAX_PHOTOS)):
            await attach(session, created, "photo-11.jpg", "image/jpeg", JPEG)

    async def test_retaking_a_photo_on_a_full_record_is_taken(self, session):
        created = await create(session, files=photos(10))
        await attach(session, created, "photo-10.jpg", "image/jpeg", JPEG + b" again")
        assert len(await file_rows(session, created)) == 10

    async def test_attaching_the_same_name_again_replaces_the_file(self, session):
        created = await create(session, "proof_of_delivery", files=[])
        await attach(session, created)
        redrawn = PNG + b" redrawn"
        await attach(session, created, "signature.png", "image/png", redrawn)
        assert [(f.path, f.bytes) for f in await file_rows(session, created)] == [
            ("signature.png", len(redrawn))
        ]
        assert media.read_record(uuid.UUID(created["id"]), "signature.png") == redrawn

    async def test_attaching_to_an_unknown_record_is_missing(self, session):
        with pytest.raises(records.Missing):
            await records.attach(
                session,
                apps.load("proof_of_delivery"),
                uuid.uuid4(),
                "signature.png",
                "image/png",
                PNG,
                actor="admin",
            )

    async def test_attaching_to_a_removed_record_is_missing(self, session):
        created = await saved(session, "proof_of_delivery", {"order_number": "2077"})
        await remove(session, created)
        with pytest.raises(records.Missing):
            await attach(session, created)

    async def test_attaching_writes_no_audit_row(self, session, monkeypatch):
        created = await create(session, "proof_of_delivery")
        at(monkeypatch, 1)
        await attach(session, created)
        assert await history(session, created) == [entry("create")]

    async def test_the_save_that_follows_carries_the_attached_file(self, session):
        created = await create(session, "proof_of_delivery")
        await attach(session, created)
        await save(session, created, {"order_number": "2077", "signed_by": "Sam Lee"})
        assert (await payload(session, created))["files"] == [
            PHOTO_FILE,
            SIGNATURE_FILE,
        ]


class TestAudit:
    def test_the_actions_are_the_five(self):
        assert audit.ACTIONS == ("create", "view", "edit", "save", "remove")

    async def test_a_record_with_no_notes_has_no_history(self, session):
        record = await bare_record(session)
        assert await audit.history(session, record.id) == []

    async def test_a_note_names_the_action_the_actor_and_the_clock(self, session):
        record = await bare_record(session)
        await audit.note(session, record.id, "view", "kim")
        assert await audit.history(session, record.id) == [entry("view", "kim")]

    async def test_history_is_oldest_first(self, session, monkeypatch):
        record = await bare_record(session)
        at(monkeypatch, 2)
        await audit.note(session, record.id, "edit", "admin")
        at(monkeypatch, 1)
        await audit.note(session, record.id, "save", "admin")
        assert [e["action"] for e in await audit.history(session, record.id)] == [
            "save",
            "edit",
        ]

    async def test_an_action_outside_the_five_is_refused(self, session):
        record = await bare_record(session)
        with pytest.raises(ValueError, match="print"):
            await audit.note(session, record.id, "print", "admin")
