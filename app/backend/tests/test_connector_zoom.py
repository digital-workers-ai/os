import importlib

import httpx
import pytest
from sqlalchemy import select

from app import sync
from app.models import RawEvent
from app.sources import client


@pytest.fixture
def zoom():
    return importlib.import_module("app.sources.zoom.connector")


@pytest.fixture
def route(monkeypatch):
    def _install(handler):
        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))

    yield _install
    monkeypatch.setattr(client, "_transport", None)


@pytest.fixture
def collect():
    stored = []

    async def store(session, **kwargs):
        stored.append(kwargs)

    return store, stored


def a_meeting(
    uuid="abc==",
    with_transcript=True,
    transcript_url="https://zoom.us/v2/rec/download/t1",
    extra_files=(),
):
    files = list(extra_files)
    if with_transcript:
        files.append({"file_type": "TRANSCRIPT", "download_url": transcript_url})
    return {"uuid": uuid, "topic": "Discovery call", "recording_files": files}


def a_vtt(text="hello"):
    return f"WEBVTT\n\n1\n00:00:00.000 --> 00:00:04.000\nJane Smith (OS): {text}\n"


class TestParticipantsPath:
    def test_an_ordinary_uuid_is_escaped_once(self, zoom):
        assert (
            zoom.participants_path("abc==")
            == "/v2/past_meetings/abc%3D%3D/participants"
        )

    @pytest.mark.parametrize("uuid", ["/abc==", "ab//c=="])
    def test_a_leading_or_doubled_slash_is_escaped_twice(self, zoom, uuid):
        path = zoom.participants_path(uuid)
        assert "%252F" in path
        assert path.count("/") == 4, path

    def test_no_raw_slash_from_the_uuid_reaches_the_path(self, zoom):
        path = zoom.participants_path("a/b/c")
        assert path.startswith("/v2/past_meetings/")
        assert path.endswith("/participants")
        assert path.count("/") == 4, path


class TestZoomPull:
    async def test_each_meeting_gets_its_transcript_and_participants(
        self, zoom, route, collect
    ):
        store, stored = collect
        seen = []

        def handler(request):
            seen.append(request)
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": [{"id": "p1"}]})
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(
                200,
                json={
                    "meetings": [
                        a_meeting(
                            uuid="m1",
                            transcript_url="https://zoom.us/v2/rec/download/t1",
                        ),
                        a_meeting(
                            uuid="m2",
                            transcript_url="https://zoom.us/v2/rec/download/t2",
                        ),
                    ],
                    "next_page_token": "",
                },
            )

        route(handler)
        notes = await zoom.pull(None, store)

        assert not notes
        listing = [r for r in seen if r.url.path == "/v2/users/me/recordings"]
        assert len(listing) == 1
        assert listing[0].url.params.get("page_size") == "30"
        assert {r.url.path for r in seen if "rec/download" in r.url.path} == {
            "/v2/rec/download/t1",
            "/v2/rec/download/t2",
        }
        assert {r.url.path for r in seen if "past_meetings" in r.url.path} == {
            "/v2/past_meetings/m1/participants",
            "/v2/past_meetings/m2/participants",
        }
        assert [s["source_id"] for s in stored] == ["m1", "m2"]
        assert all(s["source"] == "zoom" for s in stored)
        assert all(s["object_type"] == "meetings" for s in stored)
        for s in stored:
            assert s["raw_payload"]["_transcript_vtt"].startswith("WEBVTT")
            assert s["raw_payload"]["_participants"] == [{"id": "p1"}]

    async def test_a_meeting_with_no_uuid_is_counted_and_the_rest_land(
        self, zoom, route, collect
    ):
        store, stored = collect

        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(
                200,
                json={"meetings": [{"topic": "no uuid here"}, a_meeting(uuid="m1")]},
            )

        route(handler)
        notes = await zoom.pull(None, store)
        assert notes["missing_uuid"] == 1
        assert [s["source_id"] for s in stored] == ["m1"]

    async def test_a_failed_transcript_fetch_is_counted_on_the_record(
        self, zoom, route, collect
    ):
        store, stored = collect

        def handler(request):
            if request.url.path == "/v2/rec/download/t1":
                return httpx.Response(404)
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": [{"id": "p1"}]})
            return httpx.Response(
                200,
                json={
                    "meetings": [
                        a_meeting(
                            uuid="m1",
                            transcript_url="https://zoom.us/v2/rec/download/t1",
                        ),
                        a_meeting(
                            uuid="m2",
                            transcript_url="https://zoom.us/v2/rec/download/t2",
                        ),
                    ]
                },
            )

        route(handler)
        notes = await zoom.pull(None, store)

        assert notes["transcript_fetch_failed"] == 1
        assert [s["source_id"] for s in stored] == ["m1", "m2"]
        failed = stored[0]["raw_payload"]
        assert "_transcript_vtt" not in failed
        assert len(failed["_transcript_error"]) <= 200
        assert failed["_participants"] == [{"id": "p1"}]
        assert stored[1]["raw_payload"]["_transcript_vtt"].startswith("WEBVTT")

    async def test_a_failed_participants_fetch_still_lands_the_meeting(
        self, zoom, route, collect
    ):
        store, stored = collect

        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(404)
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(200, json={"meetings": [a_meeting(uuid="m1")]})

        route(handler)
        notes = await zoom.pull(None, store)

        assert notes["participants_fetch_failed"] == 1
        assert [s["source_id"] for s in stored] == ["m1"]
        assert stored[0]["raw_payload"]["_transcript_vtt"].startswith("WEBVTT")
        assert "_participants" not in stored[0]["raw_payload"]

    async def test_a_meeting_with_no_transcript_file_is_a_state_not_a_failure(
        self, zoom, route, collect
    ):
        store, stored = collect

        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            return httpx.Response(
                200, json={"meetings": [a_meeting(with_transcript=False)]}
            )

        route(handler)
        notes = await zoom.pull(None, store)

        assert notes["no_transcript"] == 1
        assert len(stored) == 1
        assert "_transcript_vtt" not in stored[0]["raw_payload"]

    async def test_an_m4a_file_is_ignored(self, zoom, route, collect):
        store, stored = collect
        seen = []

        def handler(request):
            seen.append(request)
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(
                200,
                json={
                    "meetings": [
                        a_meeting(
                            uuid="m1",
                            extra_files=[
                                {
                                    "file_type": "M4A",
                                    "download_url": "https://zoom.us/rec/audio/a1.m4a",
                                }
                            ],
                        )
                    ]
                },
            )

        route(handler)
        notes = await zoom.pull(None, store)

        assert not notes
        assert all("rec/audio" not in r.url.path for r in seen)
        assert [r.url.path for r in seen if "rec/download" in r.url.path] == [
            "/v2/rec/download/t1"
        ]
        assert stored[0]["raw_payload"]["_transcript_vtt"].startswith("WEBVTT")


class TestPaging:
    async def test_a_provider_that_never_stops_paging_hits_the_guard(
        self, zoom, route, collect, monkeypatch
    ):
        monkeypatch.setattr(zoom, "_MAX_PAGES", 3)
        store, stored = collect

        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(
                200,
                json={"meetings": [a_meeting()], "next_page_token": "always"},
            )

        route(handler)
        with client.collect_stats() as stats:
            notes = await zoom.pull(None, store)

        assert notes["page_guard"] == 3
        assert len(stored) == 3
        assert stats.truncated is True
        assert any("page guard" in r for r in stats.truncation_reasons)

    async def test_an_empty_string_token_ends_the_walk_without_truncation(
        self, zoom, route, collect
    ):
        store, stored = collect
        listing_calls = {"n": 0}

        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            listing_calls["n"] += 1
            return httpx.Response(
                200,
                json={
                    "meetings": [a_meeting(uuid=f"m{listing_calls['n']}")],
                    "next_page_token": "t1" if listing_calls["n"] == 1 else "",
                },
            )

        route(handler)
        with client.collect_stats() as stats:
            await zoom.pull(None, store)

        assert listing_calls["n"] == 2
        assert [s["source_id"] for s in stored] == ["m1", "m2"]
        assert stats.truncated is False


class TestANulByteCostsOneMeeting:
    async def test_the_refused_row_is_counted_and_the_rest_land(
        self, session, sessionmaker_for_test, monkeypatch
    ):
        def handler(request):
            if "past_meetings" in request.url.path:
                return httpx.Response(200, json={"participants": []})
            if request.url.path == "/v2/rec/download/bad":
                return httpx.Response(200, text=a_vtt("poisoned\x00cue"))
            if "rec/download" in request.url.path:
                return httpx.Response(200, text=a_vtt())
            return httpx.Response(
                200,
                json={
                    "meetings": [
                        a_meeting(
                            uuid="bad==",
                            transcript_url="https://zoom.us/v2/rec/download/bad",
                        ),
                        a_meeting(
                            uuid="good==",
                            transcript_url="https://zoom.us/v2/rec/download/good",
                        ),
                    ],
                    "next_page_token": "",
                },
            )

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        result = await sync.run_all(sessionmaker_for_test, ["zoom"])
        monkeypatch.setattr(client, "_transport", None)

        report = result["results"][0]
        assert report["rows_refused"] == 1
        assert report["rows_written"] == 1
        assert "bad==" in (report["detail"] or "")

        survivors = (await session.execute(select(RawEvent.source_id))).scalars().all()
        assert survivors == ["good=="]
