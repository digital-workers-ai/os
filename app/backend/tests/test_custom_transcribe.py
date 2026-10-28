import httpx
import pytest

from app.config import settings
from app.custom import transcribe
from app.engine import apps
from app.sources import client, creds

CLIP = b"\x1a\x45\xdf\xa3 walk-in cooler clip"


def heard(*transcripts):
    return {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {"transcript": text, "confidence": 0.98, "words": []}
                        for text in transcripts
                    ]
                }
            ]
        }
    }


def endpoint(request):
    return str(request.url).split("?")[0]


@pytest.fixture
def food_safety_log():
    return apps.load("food_safety_log")


@pytest.fixture
def enabled(monkeypatch):
    monkeypatch.setattr(settings, "TRANSCRIBE_ENABLED", True)


@pytest.fixture
def deepgram(monkeypatch):
    def _install(answer=None):
        seen = []

        def handler(request):
            seen.append(request)
            if isinstance(answer, Exception):
                raise answer
            if isinstance(answer, httpx.Response):
                return answer
            body = heard("walk-in cooler, 37") if answer is None else answer
            return httpx.Response(200, json=body)

        monkeypatch.setattr(client, "_transport", httpx.MockTransport(handler))
        return seen

    return _install


class TestKeyterms:
    def test_perio_charting_hears_its_labels_template_names_and_fields(self):
        assert transcribe.keyterms(apps.load("perio_charting")) == [
            "patient",
            "exam date",
            "tooth",
            "status",
            "present",
            "missing",
            "implant",
            "mobility",
            "0",
            "1",
            "2",
            "3",
            "site",
            "depth",
            "bleeding",
            "none",
        ]

    def test_vehicle_pre_trip_hears_its_fields_sections_and_items(self):
        assert transcribe.keyterms(apps.load("vehicle_pre_trip")) == [
            "vehicle",
            "odometer",
            "service brakes",
            "parking brake",
            "steering",
            "lights and reflectors",
            "tires",
            "horn",
            "wipers",
            "mirrors",
            "coupling devices",
            "wheels and rims",
            "emergency equipment",
            "result",
            "pass",
            "fail",
            "defect",
            "photo",
        ]

    def test_food_safety_log_hears_its_fields_list_and_labels(self, food_safety_log):
        assert transcribe.keyterms(food_safety_log) == [
            "shift",
            "opening",
            "midday",
            "closing",
            "readings",
            "unit",
            "walk in cooler",
            "reach in cooler",
            "freezer",
            "hot holding",
            "temperature",
            "action",
        ]

    def test_an_item_shared_by_several_sections_is_heard_once(self):
        assert transcribe.keyterms(apps.load("property_inspection")) == [
            "property",
            "kind",
            "move in",
            "move out",
            "routine",
            "living room",
            "walls",
            "floor",
            "windows",
            "lights",
            "doors",
            "kitchen",
            "sink",
            "appliances",
            "cabinets",
            "bathroom",
            "toilet",
            "shower",
            "ventilation",
            "bedroom",
            "closet",
            "safety",
            "smoke alarms",
            "co alarms",
            "fire extinguisher",
            "exterior",
            "entry",
            "yard",
            "condition",
            "good",
            "fair",
            "poor",
            "defect",
            "photo",
        ]

    def test_labels_from_a_reading_are_heard(self):
        assert transcribe.keyterms(apps.load("sales_visit_debrief")) == [
            "account",
            "contact",
            "interest",
            "strong",
            "moderate",
            "weak",
            "none",
            "next step",
            "next step date",
        ]


class TestTranscribeIsGated:
    async def test_transcribing_is_refused_while_it_is_off(
        self, food_safety_log, deepgram
    ):
        seen = deepgram()
        with pytest.raises(transcribe.TranscribeError) as caught:
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert str(caught.value) == "transcribing is off: set TRANSCRIBE_ENABLED"
        assert seen == []


class TestTheListenRequest:
    async def test_the_clip_is_posted_to_the_listen_endpoint(
        self, enabled, food_safety_log, deepgram
    ):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert seen[0].method == "POST"
        assert endpoint(seen[0]) == (
            f"{creds.credentials_for('deepgram').base_url}/v1/listen"
        )

    async def test_the_clip_is_the_raw_body(self, enabled, food_safety_log, deepgram):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert seen[0].content == CLIP

    async def test_the_clip_media_type_is_the_content_type(
        self, enabled, food_safety_log, deepgram
    ):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/mp4")
        assert seen[0].headers["content-type"] == "audio/mp4"

    async def test_the_stand_in_key_is_sent(self, enabled, food_safety_log, deepgram):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert seen[0].headers["authorization"] == "Token mock_deepgram_key"

    async def test_nova_3_in_english_with_smart_formatting_is_asked_for(
        self, enabled, food_safety_log, deepgram
    ):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        params = seen[0].url.params
        assert params["model"] == "nova-3"
        assert params["language"] == "en"
        assert params["smart_format"] == "true"

    async def test_the_model_follows_the_setting(
        self, enabled, food_safety_log, deepgram, monkeypatch
    ):
        monkeypatch.setattr(settings, "TRANSCRIBE_MODEL", "nova-3-medical")
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert seen[0].url.params["model"] == "nova-3-medical"

    async def test_every_keyterm_is_sent_once_in_order(
        self, enabled, food_safety_log, deepgram
    ):
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert seen[0].url.params.get_list("keyterm") == transcribe.keyterms(
            food_safety_log
        )

    async def test_a_real_key_goes_to_deepgram_itself(
        self, enabled, food_safety_log, deepgram, monkeypatch
    ):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test-key")
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert endpoint(seen[0]) == "https://api.deepgram.com/v1/listen"
        assert seen[0].headers["authorization"] == "Token dg-test-key"

    async def test_the_stand_in_answers_under_stand_ins_only_even_with_a_key(
        self, enabled, food_safety_log, deepgram, monkeypatch
    ):
        monkeypatch.setenv("DEEPGRAM_API_KEY", "dg-test-key")
        monkeypatch.setattr(settings, "STAND_INS_ONLY", True)
        seen = deepgram()
        await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
        assert endpoint(seen[0]) == f"{settings.MOCK_BASE_URL}/deepgram/v1/listen"
        assert seen[0].headers["authorization"] == "Token mock_deepgram_key"


class TestWhatTranscribeReturns:
    async def test_the_first_alternatives_transcript_comes_back(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(heard("walk-in cooler, 37", "walking cooler, 37"))
        assert (
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
            == "walk-in cooler, 37"
        )

    async def test_a_clip_with_no_speech_is_an_empty_transcript(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(heard(""))
        assert await transcribe.transcribe(food_safety_log, CLIP, "audio/webm") == ""

    async def test_an_answer_with_no_channels_is_a_transcribe_error(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram({"results": {"channels": []}})
        with pytest.raises(transcribe.TranscribeError):
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")


class TestTranscribeErrors:
    async def test_a_refused_key_is_a_transcribe_error_naming_the_status(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(httpx.Response(401, json={"err_code": "INVALID_AUTH"}))
        with pytest.raises(transcribe.TranscribeError, match="401"):
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")

    async def test_a_refused_clip_is_a_transcribe_error_naming_the_status(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(httpx.Response(400, json={"err_code": "Bad Request"}))
        with pytest.raises(transcribe.TranscribeError, match="400"):
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")

    async def test_a_server_error_is_a_transcribe_error_naming_the_status(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(httpx.Response(503, text="upstream unavailable"))
        with pytest.raises(transcribe.TranscribeError, match="503"):
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")

    async def test_a_connection_failure_is_a_transcribe_error_naming_it(
        self, enabled, food_safety_log, deepgram
    ):
        deepgram(httpx.ConnectError("deepgram is unreachable"))
        with pytest.raises(transcribe.TranscribeError, match="ConnectError"):
            await transcribe.transcribe(food_safety_log, CLIP, "audio/webm")
