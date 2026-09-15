import json

import pytest

from app.caches import BACKEND_DIR
from app.engine import checks
from tools import promote_capture

MOCK = checks.REAL_FIXTURES.parent / "mock" / "serp"
EXPECTED_KEYS = ("clears", "extracted", "skips")
FACEBOOK_POST = (
    "https://www.facebook.com/groups/2141454752849625/posts/4429445690717175/"
)


def mock_expected() -> dict:
    expected = json.loads((MOCK / "expected.json").read_text())
    return {key: expected[key] for key in EXPECTED_KEYS}


@pytest.fixture
def captured(tmp_path):
    rows = json.loads((MOCK / "organic_results.json").read_text())
    directory = tmp_path / "captures" / "serp"
    directory.mkdir(parents=True)

    def write(name="organic_results", rows=rows):
        text = json.dumps(rows, indent=2, sort_keys=True)
        (directory / f"{name}.json").write_text(text + "\n")

    write()
    return rows, write


def promote(tmp_path):
    return promote_capture.promote("serp", tmp_path / "captures", tmp_path / "real")


class TestPromotion:
    def test_copies_each_capture_file_into_the_real_layout(self, captured, tmp_path):
        rows, _write = captured
        _text, code = promote(tmp_path)
        landed = tmp_path / "real" / "serp" / "organic_results.json"
        assert json.loads(landed.read_text()) == rows
        assert code == 0

    def test_writes_the_expected_the_mock_was_verified_against(
        self, captured, tmp_path
    ):
        promote(tmp_path)
        written = json.loads((tmp_path / "real" / "serp" / "expected.json").read_text())
        assert written == mock_expected()

    def test_the_replay_reproduces_what_was_written(self, captured, tmp_path):
        promote(tmp_path)
        target = tmp_path / "real" / "serp"
        written = json.loads((target / "expected.json").read_text())
        extracted, report = promote_capture.replay(
            "serp", [target / "organic_results.json"]
        )
        assert extracted == written["extracted"]
        assert dict(report.skips) == written["skips"]
        assert dict(report.clears) == written["clears"]
        assert report.dead_paths() == []

    def test_the_report_names_the_target_counts_and_paths(self, captured, tmp_path):
        text, _code = promote(tmp_path)
        target = tmp_path / "real" / "serp"
        assert text.splitlines() == [
            f"serp: {target}",
            "organic_results: records=40 ranking=40",
            "dead paths: none",
            "skips: none",
            "clears: none",
            f"expected: {target / 'expected.json'}",
        ]

    def test_skips_and_clears_are_recorded_and_reported(self, captured, tmp_path):
        rows, write = captured
        rows[0]["payload"]["position"] = "first"
        rows[1]["payload"]["link"] = None
        write()
        text, code = promote(tmp_path)
        written = json.loads((tmp_path / "real" / "serp" / "expected.json").read_text())
        assert written["skips"] == {"position/serp/not_a_number": 1}
        assert written["clears"] == {"url/serp": 1}
        assert "skips: position/serp/not_a_number=1" in text
        assert "clears: url/serp=1" in text
        assert code == 0

    def test_a_capture_file_with_no_records_is_copied_and_counted(
        self, captured, tmp_path
    ):
        _rows, write = captured
        write("nothing_pulled", [])
        text, _code = promote(tmp_path)
        assert (tmp_path / "real" / "serp" / "nothing_pulled.json").exists()
        assert "nothing_pulled: records=0 extracted=0" in text
        written = json.loads((tmp_path / "real" / "serp" / "expected.json").read_text())
        assert "nothing_pulled" not in written["extracted"]

    def test_expected_holds_exactly_what_the_replay_test_reads(
        self, captured, tmp_path
    ):
        promote(tmp_path)
        written = json.loads((tmp_path / "real" / "serp" / "expected.json").read_text())
        assert tuple(sorted(written)) == EXPECTED_KEYS


class TestRefusals:
    def test_an_email_is_refused_and_named(self, captured, tmp_path):
        rows, write = captured
        rows[2]["payload"]["snippet"] = "Write to sales@vidora.ai for pricing"
        write()
        text, code = promote(tmp_path)
        assert text == (
            "refused:\n"
            "  organic_results.json[2].payload.snippet looks like an email address"
        )
        assert code == 1
        assert not (tmp_path / "real").exists()

    def test_a_phone_number_is_refused_and_named_at_its_nested_path(
        self, captured, tmp_path
    ):
        rows, write = captured
        rows[4]["payload"]["sitelinks"] = {"inline": [{"title": "Call (415) 555-0123"}]}
        write()
        text, code = promote(tmp_path)
        assert (
            "  organic_results.json[4].payload.sitelinks.inline[0].title "
            "looks like a phone number" in text
        )
        assert code == 1
        assert not (tmp_path / "real").exists()

    @pytest.mark.parametrize(
        "number", ["+1 415 555 0123", "415-555-0123", "415.555.0123", "+14155550123"]
    )
    def test_common_phone_spellings_are_all_refused(self, captured, tmp_path, number):
        rows, write = captured
        rows[0]["payload"]["title"] = f"Talk to us: {number}"
        write()
        text, code = promote(tmp_path)
        assert "organic_results.json[0].payload.title looks like a phone number" in text
        assert code == 1

    def test_an_api_key_is_refused_and_named(self, captured, tmp_path):
        rows, write = captured
        rows[0]["payload"]["link"] = "https://serpapi.com/search?api_key=shh&q=x"
        write()
        text, code = promote(tmp_path)
        assert text == (
            "refused:\n  organic_results.json[0].payload.link looks like an api_key"
        )
        assert code == 1

    def test_every_offence_is_named_not_just_the_first(self, captured, tmp_path):
        rows, write = captured
        rows[1]["payload"]["snippet"] = "mail me: someone@example.com"
        rows[3]["payload"]["link"] = "https://x.test/?api_key=shh"
        write()
        text, code = promote(tmp_path)
        assert text == (
            "refused:\n"
            "  organic_results.json[1].payload.snippet looks like an email address\n"
            "  organic_results.json[3].payload.link looks like an api_key"
        )
        assert code == 1

    def test_dates_numeric_ids_ratings_and_counts_are_not_phone_numbers(
        self, captured, tmp_path
    ):
        rows, write = captured
        rows[0]["payload"]["_checked_on"] = "2026-09-15"
        rows[0]["payload"]["link"] = FACEBOOK_POST
        rows[0]["payload"]["rich_snippet"] = {"top": {"extensions": ["4.8(1,517)"]}}
        rows[0]["payload"]["snippet"] = "1000+ avatars in 40+ languages, 5.9K views"
        rows[0]["payload"]["date"] = "May 6, 2026"
        write()
        _text, code = promote(tmp_path)
        assert code == 0

    def test_a_source_id_is_scanned_like_any_payload_string(self, captured, tmp_path):
        rows, write = captured
        rows[5]["source_id"] = "someone@example.com|google"
        write()
        text, code = promote(tmp_path)
        assert "organic_results.json[5].source_id looks like an email address" in text
        assert code == 1

    def test_nothing_captured_is_refused(self, tmp_path):
        text, code = promote(tmp_path)
        assert text == f"refused: no capture files under {tmp_path / 'captures/serp'}"
        assert code == 1
        assert not (tmp_path / "real").exists()


class TestTheCommandLine:
    @pytest.fixture
    def redirected(self, monkeypatch, tmp_path):
        monkeypatch.setattr(promote_capture, "CAPTURES", tmp_path / "captures")
        monkeypatch.setattr(promote_capture, "REAL_FIXTURES", tmp_path / "real")

    def test_an_unknown_source_is_refused_before_anything_runs(self, capsys):
        with pytest.raises(SystemExit) as stop:
            promote_capture.main(["nope"])
        assert stop.value.code == 2
        assert "nope" in capsys.readouterr().err

    def test_the_source_lands_under_fixtures_real(
        self, captured, redirected, tmp_path, capsys
    ):
        assert promote_capture.main(["serp"]) == 0
        assert (tmp_path / "real" / "serp" / "expected.json").exists()
        assert "organic_results: records=40 ranking=40" in capsys.readouterr().out

    def test_the_exit_code_follows_the_refusal(
        self, captured, redirected, tmp_path, capsys
    ):
        rows, write = captured
        rows[0]["payload"]["title"] = "someone@example.com"
        write()
        assert promote_capture.main(["serp"]) == 1
        assert "refused:" in capsys.readouterr().out
        assert not (tmp_path / "real").exists()

    def test_promotion_reads_captures_and_writes_the_load_bearing_dir(self):
        assert promote_capture.CAPTURES == BACKEND_DIR / "captures"
        assert promote_capture.REAL_FIXTURES == checks.REAL_FIXTURES
