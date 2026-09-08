from datetime import UTC, datetime

from app.config import settings


def now() -> datetime:
    pinned = settings.CLOCK_PINNED_AT
    if pinned is None:
        return datetime.now(UTC)
    return pinned.astimezone(UTC)
