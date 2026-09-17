from sqlalchemy import func, select

from app import media
from app.engine import looks
from app.models import (
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    SkillRun,
)
from app.skills import runner
from app.studio import Missing, rows

CALLER = "chat"
ESCAPE = "\\"


class Refused(ValueError):
    pass


def _pattern(q) -> str:
    escaped = q
    for char in (ESCAPE, "%", "_"):
        escaped = escaped.replace(char, ESCAPE + char)
    return f"%{escaped}%"


async def listing(
    session, kind=None, look=None, origin=None, q=None, limit=50, offset=0
) -> dict:
    query = select(Asset)
    if kind:
        query = query.where(Asset.kind == kind)
    if look:
        query = query.where(Asset.look == look)
    if origin:
        query = query.where(Asset.origin == origin)
    if q:
        query = query.where(Asset.name.ilike(_pattern(q), escape=ESCAPE))
    total = await session.scalar(select(func.count()).select_from(query.subquery()))
    page = query.order_by(Asset.seq.desc()).limit(limit).offset(offset)
    assets = (await session.execute(page)).scalars().all()
    return {"assets": await rows.asset_rows(session, assets), "total": total}


async def _asset(session, seq) -> Asset:
    asset = await session.get(Asset, seq)
    if asset is None:
        raise Missing(f"no asset {seq}")
    return asset


async def _belonging(session, model, seq, order) -> list:
    query = select(model).where(model.asset_seq == seq).order_by(order)
    return (await session.execute(query)).scalars().all()


def _version_row(seq, version, files) -> dict:
    own = [file for file in files if file.version == version.version]
    return {
        "version": version.version,
        "note": version.note,
        "created_at": version.created_at.isoformat(),
        "files": [rows.file_row(seq, version.version, file) for file in own],
    }


def _claim_row(claim) -> dict:
    return {
        "version": claim.version,
        "text": claim.text,
        "source_kind": claim.source_kind,
        "source_ref": claim.source_ref,
        "verified": claim.verified,
    }


def _evidence_row(evidence) -> dict:
    return {
        "version": evidence.version,
        "kind": evidence.kind,
        "ref": evidence.ref,
        "detail": evidence.detail,
    }


async def detail(session, seq) -> dict:
    asset = await _asset(session, seq)
    [row] = await rows.asset_rows(session, [asset])
    versions = await _belonging(session, AssetVersion, seq, AssetVersion.version.desc())
    files = await _belonging(session, AssetFile, seq, AssetFile.path)
    claims = await _belonging(session, AssetClaim, seq, AssetClaim.version)
    evidence = await _belonging(session, AssetEvidence, seq, AssetEvidence.version)
    newest_run = (
        select(SkillRun.seq)
        .where(SkillRun.asset_seq == seq)
        .order_by(SkillRun.seq.desc())
        .limit(1)
    )
    return {
        **row,
        "versions": [_version_row(seq, version, files) for version in versions],
        "claims": [_claim_row(claim) for claim in claims],
        "evidence": [_evidence_row(item) for item in evidence],
        "feedback": asset.feedback,
        "skill_run_seq": await session.scalar(newest_run),
    }


async def file_bytes(session, seq, version, path) -> tuple[bytes, str]:
    if path.startswith("/") or ".." in path:
        raise Refused(f"{path!r} climbs out of the version it belongs to")
    file = await session.scalar(
        select(AssetFile).where(
            AssetFile.asset_seq == seq,
            AssetFile.version == version,
            AssetFile.path == path,
        )
    )
    if file is None:
        raise Missing(f"asset {seq} version {version} has no file {path!r}")
    try:
        return media.read(seq, version, path), file.media_type
    except media.MediaError as e:
        raise Missing(str(e)) from e


async def _open(session, asset, text, ratio) -> tuple:
    ask = runner.Ask(
        skill=asset.skill,
        caller=CALLER,
        input=text,
        look=asset.look,
        ratio=ratio,
        asset_seq=asset.seq,
    )
    return await runner.open_run(session, ask), ask


async def edit(session, seq, text) -> tuple:
    asset = await _asset(session, seq)
    return await _open(session, asset, text, asset.ratio)


async def resize(session, seq, ratio) -> tuple:
    asset = await _asset(session, seq)
    if ratio not in looks.FRAMES:
        raise Refused(f"ratio {ratio!r} is not one of {list(looks.FRAMES)}")
    if asset.look is None:
        raise Refused(f"asset {seq} has no look, so there is no image to remake")
    return await _open(session, asset, f"Remake this at {ratio}", ratio)


async def feedback(session, seq, text) -> dict:
    asset = await _asset(session, seq)
    asset.feedback = text
    await session.flush()
    return await detail(session, seq)
