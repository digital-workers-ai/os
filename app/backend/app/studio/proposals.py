from sqlalchemy import func, select

from app import clock, media
from app.engine import calendar as spec
from app.models import (
    Asset,
    Proposal,
    ProposalClaim,
    ProposalDraft,
    ProposalEvidence,
    SkillRun,
)
from app.studio import errors, files, runs

STATUSES = ("open", "approved", "rejected", "built")

ANCESTOR = "competitor_ad"

DRAFT_VERSION = 1


def where(seq):
    return ("proposals", seq, DRAFT_VERSION)


def draft_url(seq, path):
    return f"/api/studio/proposals/{seq}/drafts/{path}"


def _summary(rows):
    counted: dict = {}
    for row in rows:
        counted[row.ref] = counted.get(row.ref, 0) + 1
    return " · ".join(
        ref if seen == 1 else f"{ref} ×{seen}" for ref, seen in counted.items()
    )


def _row(proposal, claims, evidence):
    verified, total = claims.get(proposal.seq, (0, 0))
    return {
        "seq": proposal.seq,
        "kind": proposal.kind,
        "title": proposal.title,
        "slot_date": None
        if proposal.slot_date is None
        else proposal.slot_date.isoformat(),
        "slot_name": proposal.slot_name,
        "reactive": proposal.reactive,
        "skill": proposal.skill,
        "skill_sha": proposal.skill_sha,
        "status": proposal.status,
        "created_at": proposal.created_at.isoformat(),
        "claims_verified": verified,
        "claims_total": total,
        "evidence_summary": _summary(evidence.get(proposal.seq, [])),
    }


async def _claims(session, seqs):
    rows = (
        await session.execute(
            select(
                ProposalClaim.proposal_seq,
                func.count().filter(ProposalClaim.verified),
                func.count(),
            )
            .where(ProposalClaim.proposal_seq.in_(seqs))
            .group_by(ProposalClaim.proposal_seq)
        )
    ).all()
    return {seq: (verified, total) for seq, verified, total in rows}


async def _evidence(session, seqs):
    rows = (
        (
            await session.execute(
                select(ProposalEvidence)
                .where(ProposalEvidence.proposal_seq.in_(seqs))
                .order_by(ProposalEvidence.id)
            )
        )
        .scalars()
        .all()
    )
    found: dict = {}
    for row in rows:
        found.setdefault(row.proposal_seq, []).append(row)
    return found


async def listing(session, status=None, kind=None, slot=None, limit=50, offset=0):
    query = select(Proposal).order_by(Proposal.seq.desc())
    tally = select(Proposal.status, func.count()).group_by(Proposal.status)
    if kind:
        query = query.where(Proposal.kind == kind)
        tally = tally.where(Proposal.kind == kind)
    if slot:
        query = query.where(Proposal.slot_name == slot)
        tally = tally.where(Proposal.slot_name == slot)
    counted = dict((await session.execute(tally)).all())
    if status:
        query = query.where(Proposal.status == status)
    rows = (await session.execute(query.limit(limit).offset(offset))).scalars().all()
    seqs = [row.seq for row in rows]
    claims = await _claims(session, seqs)
    evidence = await _evidence(session, seqs)
    return {
        "proposals": [_row(row, claims, evidence) for row in rows],
        "counts": {name: counted.get(name, 0) for name in STATUSES},
    }


async def _get(session, seq):
    found = await session.get(Proposal, seq)
    if found is None:
        raise errors.Missing(f"no proposal {seq}")
    return found


async def _open(session, seq):
    found = await _get(session, seq)
    if found.status != "open":
        raise errors.Refused(f"proposal {seq} was already {found.status}")
    return found


async def _drafts(session, seq):
    return (
        (
            await session.execute(
                select(ProposalDraft)
                .where(ProposalDraft.proposal_seq == seq)
                .order_by(ProposalDraft.path)
            )
        )
        .scalars()
        .all()
    )


async def draft_files(session, seq):
    return [
        files.listed(
            where(seq), row.path, row.media_type, row.bytes, draft_url(seq, row.path)
        )
        for row in await _drafts(session, seq)
    ]


async def _runs(session, seq):
    return (
        (
            await session.execute(
                select(SkillRun)
                .where(SkillRun.proposal_seq == seq)
                .order_by(SkillRun.seq.desc())
            )
        )
        .scalars()
        .all()
    )


async def detail(session, seq):
    found = await _get(session, seq)
    claims = (
        (
            await session.execute(
                select(ProposalClaim)
                .where(ProposalClaim.proposal_seq == seq)
                .order_by(ProposalClaim.id)
            )
        )
        .scalars()
        .all()
    )
    evidence = (await _evidence(session, [seq])).get(seq, [])
    runs = await _runs(session, seq)
    built = next((run for run in runs if run.mode == "build"), None)
    asset = (
        (
            await session.execute(
                select(Asset.seq)
                .where(Asset.proposal_seq == seq)
                .order_by(Asset.seq.desc())
            )
        )
        .scalars()
        .first()
    )
    slot = spec.slots().get(found.slot_name, {})
    return {
        **_row(
            found,
            {seq: (sum(1 for claim in claims if claim.verified), len(claims))},
            {seq: evidence},
        ),
        "reason": found.reason,
        "note": found.note,
        "decided_at": None
        if found.decided_at is None
        else found.decided_at.isoformat(),
        "look": slot.get("look"),
        "theme": slot.get("theme"),
        "ancestor_ref": next(
            (row.ref for row in evidence if row.kind == ANCESTOR), None
        ),
        "drafts": await draft_files(session, seq),
        "evidence": [
            {"kind": row.kind, "ref": row.ref, "detail": row.detail} for row in evidence
        ],
        "claims": [
            {
                "text": row.text,
                "source_kind": row.source_kind,
                "source_ref": row.source_ref,
                "verified": row.verified,
            }
            for row in claims
        ],
        "read": list(dict.fromkeys(f"{row.kind}: {row.ref}" for row in evidence)),
        "build_cost": _spent(built),
        "asset_seq": asset,
        "skill_run_seq": runs[0].seq if runs else None,
    }


async def create(
    session,
    *,
    kind,
    title,
    skill,
    skill_sha,
    slot_date=None,
    slot_name=None,
    reactive=False,
    evidence=(),
    claims=(),
    drafts=(),
):
    made = Proposal(
        kind=kind,
        title=title,
        skill=skill,
        skill_sha=skill_sha,
        slot_date=slot_date,
        slot_name=slot_name,
        reactive=reactive,
        status="open",
        created_at=clock.now(),
    )
    session.add(made)
    await session.flush()
    for row in evidence:
        session.add(ProposalEvidence(proposal_seq=made.seq, **row))
    for row in claims:
        session.add(ProposalClaim(proposal_seq=made.seq, **row))
    for row in drafts:
        session.add(ProposalDraft(proposal_seq=made.seq, **row))
    await session.flush()
    return made


def _spent(run):
    if run is None or not run.tokens_in + run.tokens_out:
        return None
    return f"{run.tokens_in + run.tokens_out:,} tokens"


def _build_ask(variants):
    if not variants:
        return "Build the draft a person approved."
    return "Build the draft a person approved, these variants only: " + ", ".join(
        variants
    )


async def approve(session, seq, variants):
    found = await _open(session, seq)
    found.status = "approved"
    found.decided_at = clock.now()
    await session.flush()
    return await runs.start(
        session,
        skill=found.skill,
        mode="build",
        input=_build_ask(variants),
        proposal_seq=found.seq,
    )


async def reject(session, seq, reason):
    found = await _open(session, seq)
    found.status = "rejected"
    found.reason = reason
    found.decided_at = clock.now()
    await session.flush()
    return await detail(session, seq)


async def redo(session, seq, note):
    found = await _open(session, seq)
    found.note = note
    await session.flush()
    return await runs.start(
        session, skill=found.skill, mode="draft", input=note, proposal_seq=found.seq
    )


async def _draft(session, seq, path):
    found = (
        (
            await session.execute(
                select(ProposalDraft).where(
                    ProposalDraft.proposal_seq == seq, ProposalDraft.path == path
                )
            )
        )
        .scalars()
        .first()
    )
    if found is None:
        raise errors.Missing(f"proposal {seq} drafted no {path!r}")
    return found


async def edit_draft(session, seq, path, text):
    await _get(session, seq)
    found = await _draft(session, seq, path)
    written = media.write(*where(seq), path, text.encode())
    found.bytes = written["bytes"]
    await session.flush()
    return await detail(session, seq)


async def draft_bytes(session, seq, path):
    if files.refuses(path):
        raise errors.Refused(f"{path!r} climbs out of the media store")
    found = await _draft(session, seq, path)
    try:
        return files.read(where(seq), path), found.media_type
    except media.MediaError as exc:
        raise errors.Missing(f"the media store has no {path!r}") from exc
