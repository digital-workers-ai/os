from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app import clock
from app.models import Asset
from app.studio import rows

SPAN = timedelta(days=90)
NO_FILE = ""


def _bounds(frm, to) -> tuple[date, date]:
    if to is None:
        to = clock.now().date()
    if frm is None:
        frm = to - SPAN if to - date.min >= SPAN else date.min
    return frm, to


def _node(asset, lookup) -> dict:
    seq = asset.seq
    version = lookup.version(seq)
    file = lookup.first(seq, "image/") or lookup.first(seq, "text/")
    return {
        "id": f"asset:{seq}",
        "asset_seq": seq,
        "version": version,
        "date": asset.created_at.date().isoformat(),
        "kind": asset.kind,
        "label": asset.name,
        "media_type": NO_FILE if file is None else file.media_type,
        "url": None if file is None else rows.file_url(seq, version, file.path),
        "origin": asset.origin,
        "skill": asset.skill,
        "look": asset.look,
        "status": lookup.status(seq),
    }


async def nodes(session, frm=None, to=None, kind=None) -> list[dict]:
    frm, to = _bounds(frm, to)
    query = (
        select(Asset)
        .where(
            Asset.created_at >= datetime.combine(frm, time.min, tzinfo=UTC),
            Asset.created_at <= datetime.combine(to, time.max, tzinfo=UTC),
        )
        .order_by(Asset.created_at.desc(), Asset.seq.desc())
    )
    if kind is not None:
        query = query.where(Asset.kind == kind)
    assets = (await session.execute(query)).scalars().all()
    lookup = await rows.Lookup.load(session, [asset.seq for asset in assets])
    return [_node(asset, lookup) for asset in assets]
