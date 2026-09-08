from datetime import UTC, datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app import clock
from app.config import Settings, settings
from tests.conftest import NOW


class TestThePinnedClock:
    def test_every_test_runs_on_the_pinned_clock(self):
        assert clock.now() == NOW

    def test_the_pin_reads_the_same_twice(self):
        assert clock.now() == clock.now() == NOW

    def test_a_pin_in_another_zone_reads_in_utc(self, monkeypatch):
        monkeypatch.setattr(
            settings, "CLOCK_PINNED_AT", NOW.astimezone(timezone(timedelta(hours=2)))
        )
        assert clock.now() == NOW
        assert clock.now().utcoffset() == timedelta(0)
        assert clock.now().isoformat() == "2026-09-04T12:00:00+00:00"


class TestTheWallClock:
    def test_an_unpinned_clock_reads_the_wall_clock(self, monkeypatch):
        monkeypatch.setattr(settings, "CLOCK_PINNED_AT", None)
        before = datetime.now(UTC)
        read = clock.now()
        assert before <= read <= datetime.now(UTC)
        assert read.tzinfo is not None


class TestThePinSetting:
    def test_the_pin_is_off_by_default(self, monkeypatch):
        monkeypatch.delenv("CLOCK_PINNED_AT", raising=False)
        assert Settings(_env_file=None).CLOCK_PINNED_AT is None

    def test_the_pin_parses_an_iso_instant(self, monkeypatch):
        monkeypatch.delenv("CLOCK_PINNED_AT", raising=False)
        pinned = Settings(_env_file=None, CLOCK_PINNED_AT="2026-09-04T12:00:00Z")
        assert pinned.CLOCK_PINNED_AT == NOW

    def test_a_naive_pin_is_refused(self, monkeypatch):
        monkeypatch.delenv("CLOCK_PINNED_AT", raising=False)
        with pytest.raises(ValidationError, match="timezone"):
            Settings(_env_file=None, CLOCK_PINNED_AT="2026-09-04T12:00:00")

    def test_an_explicit_none_is_unpinned(self, monkeypatch):
        monkeypatch.delenv("CLOCK_PINNED_AT", raising=False)
        assert Settings(_env_file=None, CLOCK_PINNED_AT=None).CLOCK_PINNED_AT is None
