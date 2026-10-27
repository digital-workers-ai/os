from sqlalchemy import select

from app import clock
from app.models import CustomRecordAudit

ACTIONS = ("create", "view", "edit", "save", "remove")


async def note(session, record_id, action: str, actor: str) -> None:
    if action not in ACTIONS:
        raise ValueError(
            f"{action!r} is not an audit action; a record is noted only for "
            f"{list(ACTIONS)}"
        )
    session.add(
        CustomRecordAudit(
            record_id=record_id, action=action, actor=actor, at=clock.now()
        )
    )
    await session.flush()


async def history(session, record_id) -> list[dict]:
    notes = await session.execute(
        select(CustomRecordAudit)
        .where(CustomRecordAudit.record_id == record_id)
        .order_by(CustomRecordAudit.at, CustomRecordAudit.seq)
    )
    return [
        {"action": entry.action, "actor": entry.actor, "at": entry.at.isoformat()}
        for entry in notes.scalars()
    ]
