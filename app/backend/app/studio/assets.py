from sqlalchemy import func, select

from app import media
from app.models import Asset, AssetFile, ProposalClaim, ProposalEvidence, SkillRun
from app.studio import errors, files, runs, store

FEEDBACK = "feedback-{seq}.txt"

RUNNING = "running"


def where(seq, version):
    return ("assets", seq, version)


def file_url(seq, path):
    return f"/api/assets/{seq}/files/{path}"


def tool_name(skill):
    head, _dash, rest = skill.partition("-")
    return f"{head}.{rest.replace('-', '_')}"


def _row(asset, building, preview, skills):
    skill = skills.get(asset.seq, "")
    return {
        "seq": asset.seq,
        "name": asset.name,
        "kind": asset.kind,
        "skill": skill,
        "look": asset.look,
        "made_by": tool_name(skill) if skill and asset.origin == "chat" else None,
        "origin": asset.origin,
        "proposal_seq": asset.proposal_seq,
        "status": "building" if asset.seq in building else "built",
        "created_at": asset.created_at.isoformat(),
        "preview": preview.get(asset.seq),
    }


async def _skills(session, seqs):
    rows = (
        await session.execute(
            select(SkillRun.asset_seq, SkillRun.skill)
            .where(SkillRun.asset_seq.in_(seqs))
            .order_by(SkillRun.seq.desc())
        )
    ).all()
    skills: dict = {}
    for asset_seq, skill in rows:
        skills.setdefault(asset_seq, skill)
    return skills


async def _building(session, seqs):
    rows = (
        (
            await session.execute(
                select(SkillRun.asset_seq).where(
                    SkillRun.asset_seq.in_(seqs), SkillRun.status == RUNNING
                )
            )
        )
        .scalars()
        .all()
    )
    return set(rows)


async def _files(session, seqs):
    rows = (
        (
            await session.execute(
                select(AssetFile)
                .where(AssetFile.asset_seq.in_(seqs))
                .order_by(AssetFile.asset_seq, AssetFile.version, AssetFile.path)
            )
        )
        .scalars()
        .all()
    )
    found: dict = {}
    for row in rows:
        found.setdefault(row.asset_seq, []).append(row)
    return found


def _preview(rows):
    newest = max((row.version for row in rows), default=0)
    return next(
        (
            file_url(row.asset_seq, row.path)
            for row in rows
            if row.version == newest and row.media_type.startswith("image/")
        ),
        None,
    )


async def listing(
    session, kind=None, look=None, origin=None, q=None, skill=None, limit=50, offset=0
):
    query = select(Asset).order_by(Asset.seq.desc())
    tally = select(func.count()).select_from(Asset)
    for column, value in (
        (Asset.kind, kind),
        (Asset.look, look),
        (Asset.origin, origin),
    ):
        if value:
            query = query.where(column == value)
            tally = tally.where(column == value)
    if q:
        query = query.where(Asset.name.ilike(f"%{q}%"))
        tally = tally.where(Asset.name.ilike(f"%{q}%"))
    if skill:
        made = select(SkillRun.asset_seq).where(SkillRun.skill == skill)
        query = query.where(Asset.seq.in_(made))
        tally = tally.where(Asset.seq.in_(made))
    total = (await session.execute(tally)).scalar_one()
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    seqs = [row.seq for row in rows]
    stored = await _files(session, seqs)
    previews = {seq: _preview(stored.get(seq, [])) for seq in seqs}
    building = await _building(session, seqs)
    skills = await _skills(session, seqs)
    return {
        "assets": [_row(row, building, previews, skills) for row in rows],
        "total": total,
    }


async def _get(session, seq):
    found = await session.get(Asset, seq)
    if found is None:
        raise errors.Missing(f"no asset {seq}")
    return found


async def _skill_runs(session, seq):
    return (
        (
            await session.execute(
                select(SkillRun)
                .where(SkillRun.asset_seq == seq)
                .order_by(SkillRun.seq.desc())
            )
        )
        .scalars()
        .all()
    )


def _versions(rows):
    grouped: dict = {}
    for row in rows:
        grouped.setdefault(row.version, []).append(row)
    return [
        {
            "version": version,
            "note": next((row.note for row in kept if row.note), None),
            "created_at": max(row.created_at for row in kept).isoformat(),
            "files": [
                files.listed(
                    where(row.asset_seq, row.version),
                    row.path,
                    row.media_type,
                    row.bytes,
                    file_url(row.asset_seq, row.path),
                )
                for row in kept
            ],
        }
        for version, kept in sorted(grouped.items(), reverse=True)
    ]


def _feedback(seq):
    return store.read_text(FEEDBACK.format(seq=seq))


async def detail(session, seq):
    asset = await _get(session, seq)
    ran = await _skill_runs(session, seq)
    stored = (await _files(session, [seq])).get(seq, [])
    claims = (
        (
            await session.execute(
                select(ProposalClaim)
                .where(ProposalClaim.proposal_seq == asset.proposal_seq)
                .order_by(ProposalClaim.id)
            )
        )
        .scalars()
        .all()
    )
    evidence = (
        (
            await session.execute(
                select(ProposalEvidence)
                .where(ProposalEvidence.proposal_seq == asset.proposal_seq)
                .order_by(ProposalEvidence.id)
            )
        )
        .scalars()
        .all()
    )
    return {
        **_row(
            asset,
            await _building(session, [seq]),
            {seq: _preview(stored)},
            {seq: ran[0].skill} if ran else {},
        ),
        "ancestor_ref": asset.ancestor_ref,
        "skill_sha": ran[0].skill_sha if ran else "",
        "read": list(dict.fromkeys(f"{row.kind}: {row.ref}" for row in evidence)),
        "claims": [
            {
                "text": row.text,
                "source_kind": row.source_kind,
                "source_ref": row.source_ref,
                "verified": row.verified,
            }
            for row in claims
        ],
        "versions": _versions(stored),
        "feedback": _feedback(seq),
        "skill_run_seq": ran[0].seq if ran else None,
    }


async def version_files(session, seq):
    stored = (await _files(session, [seq])).get(seq, [])
    newest = max((row.version for row in stored), default=0)
    return [
        files.listed(
            where(seq, row.version),
            row.path,
            row.media_type,
            row.bytes,
            file_url(seq, row.path),
        )
        for row in stored
        if row.version == newest
    ]


async def file_bytes(session, seq, path):
    if files.refuses(path):
        raise errors.Refused(f"{path!r} climbs out of the media store")
    found = (
        (
            await session.execute(
                select(AssetFile).where(
                    AssetFile.asset_seq == seq, AssetFile.path == path
                )
            )
        )
        .scalars()
        .first()
    )
    if found is None:
        raise errors.Missing(f"asset {seq} holds no {path!r}")
    try:
        return files.read(where(seq, found.version), path), found.media_type
    except media.MediaError as exc:
        raise errors.Missing(f"the media store has no {path!r}") from exc


async def rebuild(session, seq, note):
    asset = await _get(session, seq)
    ran = await _skill_runs(session, seq)
    if not ran:
        raise errors.Refused(f"nothing has ever run for asset {seq}")
    return await runs.start(
        session, skill=ran[0].skill, mode="build", input=note, asset_seq=asset.seq
    )


async def feedback(session, seq, text):
    await _get(session, seq)
    store.write_text(FEEDBACK.format(seq=seq), text)
    return await detail(session, seq)
