from datetime import timedelta

from sqlalchemy import select

from app import clock
from app.models import (
    Asset,
    AssetFile,
    Proposal,
    ProposalDraft,
    ProposalEvidence,
    SkillRun,
)
from app.studio import proposals, store

LAYOUT = "canvas-layout.json"

DEFAULT_DAYS = 90

MEDIA_KINDS = (("image/", "image"), ("video/", "video"), ("text/html", "html"))

RANKS = {"ancestor": 0, "draft": 1, "file": 2}


def _kind(media_type):
    for prefix, kind in MEDIA_KINDS:
        if media_type.startswith(prefix):
            return kind
    return "document"


def _node(node_id, group, day, label, media_type, url, asset_seq, proposal_seq, skill):
    return {
        "id": node_id,
        "group": group,
        "date": day,
        "kind": _kind(media_type) if media_type else "ancestor",
        "skill": skill,
        "label": label,
        "media_type": media_type,
        "url": url,
        "asset_seq": asset_seq,
        "proposal_seq": proposal_seq,
    }


def _order(node):
    return (node["date"], node["group"], RANKS[node["id"].split(":", 1)[0]], node["id"])


def _proposal_group(proposal):
    return f"#{proposal.seq} {proposal.slot_name or proposal.kind}"


def _asset_group(asset, proposal, skills):
    if proposal is not None:
        return _proposal_group(proposal)
    if asset.seq in skills:
        return f"chat · {skills[asset.seq]}"
    return "chat"


async def _all(session, model, *order_by):
    return (await session.execute(select(model).order_by(*order_by))).scalars().all()


async def _skills(session):
    rows = (
        await session.execute(
            select(SkillRun.asset_seq, SkillRun.skill)
            .where(SkillRun.asset_seq.is_not(None))
            .order_by(SkillRun.seq.desc())
        )
    ).all()
    skills: dict = {}
    for asset_seq, skill in rows:
        skills.setdefault(asset_seq, skill)
    return skills


async def _ancestor_refs(session):
    rows = (
        await session.execute(
            select(ProposalEvidence.proposal_seq, ProposalEvidence.ref)
            .where(ProposalEvidence.kind == proposals.ANCESTOR)
            .order_by(ProposalEvidence.id)
        )
    ).all()
    refs: dict = {}
    for seq, ref in rows:
        refs.setdefault(seq, ref)
    return refs


def _window(frm, to):
    today = clock.now().date()
    return (
        frm or (today - timedelta(days=DEFAULT_DAYS)).isoformat(),
        to or today.isoformat(),
    )


def _shown(node, start, end, kind, skill):
    return (
        start <= node["date"] <= end
        and (not kind or node["kind"] == kind)
        and (not skill or node["skill"] == skill)
    )


async def graph(session, frm=None, to=None, kind=None, skill=None):
    start, end = _window(frm, to)
    by_seq = {row.seq: row for row in await _all(session, Proposal, Proposal.seq)}
    assets = {row.seq: row for row in await _all(session, Asset, Asset.seq)}
    skills = await _skills(session)
    nodes = []
    first_draft: dict = {}
    first_file: dict = {}
    versions: dict = {}

    for row in await _all(
        session, ProposalDraft, ProposalDraft.proposal_seq, ProposalDraft.path
    ):
        proposal = by_seq[row.proposal_seq]
        node = _node(
            f"draft:{row.proposal_seq}:{row.path}",
            _proposal_group(proposal),
            proposal.created_at.date().isoformat(),
            row.path.rsplit("/", 1)[-1],
            row.media_type,
            proposals.draft_url(row.proposal_seq, row.path),
            None,
            row.proposal_seq,
            proposal.skill,
        )
        nodes.append(node)
        first_draft.setdefault(row.proposal_seq, node["id"])

    for row in await _all(
        session, AssetFile, AssetFile.asset_seq, AssetFile.version, AssetFile.path
    ):
        asset = assets[row.asset_seq]
        node = _node(
            f"file:{row.asset_seq}:{row.version}:{row.path}",
            _asset_group(asset, by_seq.get(asset.proposal_seq), skills),
            row.created_at.date().isoformat(),
            row.path.rsplit("/", 1)[-1],
            row.media_type,
            f"/api/assets/{row.asset_seq}/files/{row.path}",
            row.asset_seq,
            asset.proposal_seq,
            skills.get(row.asset_seq),
        )
        nodes.append(node)
        first_file.setdefault(row.asset_seq, node["id"])
        versions.setdefault((row.asset_seq, row.version), node["id"])

    edges = _lineage(assets, first_draft, first_file, versions)
    for seq, ref in (await _ancestor_refs(session)).items():
        proposal = by_seq[seq]
        group = _proposal_group(proposal)
        nodes.append(
            _node(
                f"ancestor:{group}:{ref}",
                group,
                proposal.created_at.date().isoformat(),
                ref,
                "",
                None,
                None,
                seq,
                proposal.skill,
            )
        )
        edges.append(
            {
                "from": f"ancestor:{group}:{ref}",
                "to": first_draft.get(seq),
                "rel": "ancestor",
            }
        )
    for asset in assets.values():
        if asset.ancestor_ref is None or asset.proposal_seq is not None:
            continue
        group = _asset_group(asset, None, skills)
        nodes.append(
            _node(
                f"ancestor:{group}:{asset.ancestor_ref}",
                group,
                asset.created_at.date().isoformat(),
                asset.ancestor_ref,
                "",
                None,
                asset.seq,
                None,
                skills.get(asset.seq),
            )
        )
        edges.append(
            {
                "from": f"ancestor:{group}:{asset.ancestor_ref}",
                "to": first_file.get(asset.seq),
                "rel": "ancestor",
            }
        )

    shown = sorted(
        (node for node in nodes if _shown(node, start, end, kind, skill)), key=_order
    )
    ids = {node["id"] for node in shown}
    positions, frames = saved()
    return {
        "nodes": shown,
        "edges": [edge for edge in edges if edge["from"] in ids and edge["to"] in ids],
        "frames": frames,
        "layout": positions,
    }


def _lineage(assets, first_draft, first_file, versions):
    edges = []
    for asset in assets.values():
        target = first_file.get(asset.seq)
        source = first_draft.get(asset.proposal_seq)
        if target is not None and source is not None:
            edges.append({"from": source, "to": target, "rel": "draft"})
        numbered = sorted(version for (seq, version) in versions if seq == asset.seq)
        for before, after in zip(numbered, numbered[1:], strict=False):
            edges.append(
                {
                    "from": versions[(asset.seq, before)],
                    "to": versions[(asset.seq, after)],
                    "rel": "build",
                }
            )
    return edges


def saved():
    doc = store.read_json(LAYOUT)
    return doc.get("layout", {}), doc.get("frames", [])


def save_layout(positions, frames):
    store.write_json(LAYOUT, {"layout": positions, "frames": frames})
