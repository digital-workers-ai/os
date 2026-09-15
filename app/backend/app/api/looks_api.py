from fastapi import Depends, HTTPException
from sqlalchemy import distinct, func, select

from app.api.routers import looks as router
from app.db import get_session
from app.engine import looks
from app.models import Asset, AssetFile


def _row(name: str, manifest: dict, counts: dict) -> dict:
    used_by, built = counts.get(name, (0, 0))
    measured = manifest.get("limits_measured")
    return {
        "name": name,
        "medium": manifest.get("medium"),
        "ratio": manifest.get("ratio"),
        "slots": [str(slot["name"]) for slot in manifest.get("slots") or []],
        "limits_measured": None if measured is None else str(measured),
        "used_by": used_by,
        "built": built,
        "build_cost": manifest.get("build"),
    }


async def _counts(session) -> dict:
    rows = (
        await session.execute(
            select(
                Asset.look,
                func.count(distinct(Asset.seq)),
                func.count(distinct(AssetFile.asset_seq)),
            )
            .join(AssetFile, AssetFile.asset_seq == Asset.seq, isouter=True)
            .where(Asset.look.is_not(None))
            .group_by(Asset.look)
        )
    ).all()
    return {look: (used_by, built) for look, used_by, built in rows}


def _read(name: str, filename: str) -> str:
    path = looks.directory(name) / filename
    return path.read_text() if path.is_file() else ""


@router.get("/looks")
async def list_looks(session=Depends(get_session)):
    counts = await _counts(session)
    return {"looks": [_row(name, looks.load(name), counts) for name in looks.names()]}


@router.get("/looks/{name}")
async def get_look(name: str, session=Depends(get_session)):
    try:
        manifest = looks.load(name)
    except looks.LookError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return {
        **_row(name, manifest, await _counts(session)),
        "layouts": _read(name, looks.LAYOUTS),
        "preview": _read(name, looks.PREVIEW),
    }
