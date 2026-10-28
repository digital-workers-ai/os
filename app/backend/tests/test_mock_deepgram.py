import hashlib
import importlib
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.caches import BACKEND_DIR
from tests import ground_truth

SEEDS = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds"
SAMPLES = BACKEND_DIR / "fixtures" / "custom" / "samples"
KEY = {"Authorization": "Token mock_deepgram_key"}
QUERY = {
    "model": "nova-3",
    "language": "en",
    "smart_format": "true",
    "keyterm": ["walk in cooler", "freezer"],
}
CLIPS = {
    "food_safety_walk_in.webm": "walk-in cooler, 37",
    "perio_tooth_3.webm": "three, three two four, bleeding on the two",
}
DEFINED = b"\x1a\x45\xdf\xa3 a clip these tests define"
UNKNOWN = b"\x1a\x45\xdf\xa3 a clip nobody recorded"


@pytest.fixture(scope="module")
def provider():
    if not (SEEDS / "server.py").is_file():
        pytest.skip("the mock providers are not mounted at /adversarial")
    if ground_truth.ADVERSARIAL_ROOT not in sys.path:
        sys.path.insert(0, ground_truth.ADVERSARIAL_ROOT)
    return importlib.import_module("seeds.providers.deepgram")


@pytest.fixture(scope="module")
def deepgram(provider):
    app = FastAPI()
    app.include_router(provider.router, prefix="/deepgram")
    return TestClient(app)


@pytest.fixture
def defined(provider, monkeypatch):
    monkeypatch.setitem(provider.TRANSCRIPTS, sha256(DEFINED), "hello there")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def clip(name):
    return (SAMPLES / name).read_bytes()


def listen(deepgram, audio, *, headers=KEY, params=QUERY):
    return deepgram.post(
        "/deepgram/v1/listen",
        params=params,
        content=audio,
        headers={**headers, "Content-Type": "audio/webm"},
    )


def alternative(answer):
    return answer.json()["results"]["channels"][0]["alternatives"][0]


class TestAKnownClipIsTranscribedByItsSha256:
    @pytest.mark.parametrize(("name", "transcript"), sorted(CLIPS.items()))
    def test_each_fixture_clip_answers_with_its_documented_transcript(
        self, deepgram, name, transcript
    ):
        assert alternative(listen(deepgram, clip(name)))["transcript"] == transcript

    def test_the_table_maps_the_sha256_of_each_fixture_clip_to_its_transcript(
        self, provider
    ):
        documented = {sha256(clip(name)): text for name, text in CLIPS.items()}
        assert documented.items() <= provider.TRANSCRIPTS.items()

    def test_any_bytes_whose_sha256_the_table_holds_get_that_transcript(
        self, deepgram, defined
    ):
        assert alternative(listen(deepgram, DEFINED))["transcript"] == "hello there"

    def test_other_keyterms_do_not_change_the_transcript(self, deepgram, defined):
        params = {**QUERY, "keyterm": ["horn"]}
        answer = listen(deepgram, DEFINED, params=params)
        assert alternative(answer)["transcript"] == "hello there"

    def test_a_known_clip_answers_200(self, deepgram, defined):
        assert listen(deepgram, DEFINED).status_code == 200


class TestUnknownAudioIsHeardAsNothing:
    def test_unknown_bytes_get_an_empty_transcript(self, deepgram):
        assert alternative(listen(deepgram, UNKNOWN))["transcript"] == ""

    def test_unknown_bytes_get_no_words(self, deepgram):
        assert alternative(listen(deepgram, UNKNOWN))["words"] == []

    def test_an_empty_body_gets_an_empty_transcript(self, deepgram):
        assert alternative(listen(deepgram, b""))["transcript"] == ""

    def test_unknown_bytes_still_answer_200(self, deepgram):
        assert listen(deepgram, UNKNOWN).status_code == 200

    def test_the_keyterms_are_never_echoed_back(self, deepgram):
        params = {**QUERY, "keyterm": ["zebra crossing", "tangerine"]}
        text = listen(deepgram, UNKNOWN, params=params).text
        assert ("zebra crossing" in text, "tangerine" in text) == (False, False)


class TestTheAnswerHasThePrerecordedShape:
    def test_the_answer_carries_only_results(self, deepgram, defined):
        assert set(listen(deepgram, DEFINED).json()) == {"results"}

    def test_the_alternative_carries_a_transcript_a_confidence_and_words(
        self, deepgram, defined
    ):
        assert set(alternative(listen(deepgram, DEFINED))) == {
            "transcript",
            "confidence",
            "words",
        }

    def test_the_confidence_is_a_float(self, deepgram, defined):
        assert isinstance(alternative(listen(deepgram, DEFINED))["confidence"], float)

    def test_the_words_are_a_list(self, deepgram, defined):
        assert isinstance(alternative(listen(deepgram, DEFINED))["words"], list)


class TestTheKeyIsChecked:
    def test_a_missing_key_is_refused_with_401(self, deepgram, defined):
        assert listen(deepgram, DEFINED, headers={}).status_code == 401

    def test_a_wrong_key_is_refused_with_401(self, deepgram, defined):
        wrong = {"Authorization": "Token someone_elses_key"}
        assert listen(deepgram, DEFINED, headers=wrong).status_code == 401

    def test_the_key_under_another_scheme_is_refused_with_401(self, deepgram, defined):
        bearer = {"Authorization": "Bearer mock_deepgram_key"}
        assert listen(deepgram, DEFINED, headers=bearer).status_code == 401


class TestTheServerMountsTheStandIn:
    def test_the_stand_in_is_mounted_at_deepgram(self, provider):
        assert importlib.import_module("seeds.server").routers["/deepgram"] is provider
