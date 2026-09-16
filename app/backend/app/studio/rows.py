from dataclasses import dataclass

from sqlalchemy import func, select, tuple_

from app import media
from app.models import AssetFile, AssetVersion, SkillRun

MAX_TEXT_BYTES = 256 * 1024
FIRST_VERSION = 1
NO_RUN_STATUS = "ok"


def _iso(value):
    return None if value is None else value.isoformat()


def skill_run_row(run) -> dict:
    return {
        "seq": run.seq,
        "skill": run.skill,
        "skill_sha": run.skill_sha,
        "caller": run.caller,
        "asset_seq": run.asset_seq,
        "version": run.version,
        "stage": run.stage,
        "status": run.status,
        "error": run.error,
        "model": run.model,
        "tokens_in": run.tokens_in,
        "tokens_out": run.tokens_out,
        "duration_ms": run.duration_ms,
        "started_at": run.started_at.isoformat(),
        "finished_at": _iso(run.finished_at),
    }


def agent_run_row(run) -> dict:
    return {
        "seq": run.seq,
        "agent": run.agent,
        "trigger": run.trigger,
        "read_detail": run.read_detail,
        "made": run.made,
        "duration_ms": run.duration_ms,
        "ok": run.ok,
        "error": run.error,
        "created_at": run.created_at.isoformat(),
    }


def asset_row(asset, *, status, version, preview) -> dict:
    return {
        "seq": asset.seq,
        "name": asset.name,
        "kind": asset.kind,
        "skill": asset.skill,
        "look": asset.look,
        "ratio": asset.ratio,
        "origin": asset.origin,
        "slot_date": _iso(asset.slot_date),
        "slot_name": asset.slot_name,
        "status": status,
        "version": version,
        "preview": preview,
        "created_at": asset.created_at.isoformat(),
    }


def file_url(asset_seq, version, path) -> str:
    return f"/api/assets/{asset_seq}/versions/{version}/files/{path}"


def file_row(asset_seq, version, file) -> dict:
    text = None
    if media.readable(file.media_type) and file.bytes < MAX_TEXT_BYTES:
        text = media.read(asset_seq, version, file.path).decode("utf-8", "replace")
    return {
        "path": file.path,
        "media_type": file.media_type,
        "bytes": file.bytes,
        "url": file_url(asset_seq, version, file.path),
        "text": text,
    }


async def _versions(session, seqs) -> dict:
    found = await session.execute(
        select(AssetVersion.asset_seq, func.max(AssetVersion.version))
        .where(AssetVersion.asset_seq.in_(seqs))
        .group_by(AssetVersion.asset_seq)
    )
    newest = dict(found.all())
    return {seq: newest.get(seq, FIRST_VERSION) for seq in seqs}


async def _statuses(session, seqs) -> dict:
    found = await session.execute(
        select(SkillRun.asset_seq, SkillRun.status)
        .distinct(SkillRun.asset_seq)
        .where(SkillRun.asset_seq.in_(seqs))
        .order_by(SkillRun.asset_seq, SkillRun.seq.desc())
    )
    return dict(found.all())


async def _files(session, versions) -> dict:
    found = await session.execute(
        select(AssetFile)
        .where(tuple_(AssetFile.asset_seq, AssetFile.version).in_(versions.items()))
        .order_by(AssetFile.asset_seq, AssetFile.path)
    )
    files: dict = {}
    for file in found.scalars():
        files.setdefault(file.asset_seq, []).append(file)
    return files


@dataclass(frozen=True)
class Lookup:
    versions: dict
    statuses: dict
    files: dict

    @classmethod
    async def load(cls, session, seqs):
        if not seqs:
            return cls({}, {}, {})
        versions = await _versions(session, seqs)
        return cls(
            versions, await _statuses(session, seqs), await _files(session, versions)
        )

    def version(self, seq) -> int:
        return self.versions.get(seq, FIRST_VERSION)

    def status(self, seq) -> str:
        return self.statuses.get(seq, NO_RUN_STATUS)

    def first(self, seq, prefix):
        files = self.files.get(seq, ())
        return next((f for f in files if f.media_type.startswith(prefix)), None)

    def preview(self, seq):
        image = self.first(seq, "image/")
        return None if image is None else file_url(seq, self.version(seq), image.path)

    def row(self, asset) -> dict:
        seq = asset.seq
        return asset_row(
            asset,
            status=self.status(seq),
            version=self.version(seq),
            preview=self.preview(seq),
        )


async def asset_rows(session, assets) -> list[dict]:
    lookup = await Lookup.load(session, [asset.seq for asset in assets])
    return [lookup.row(asset) for asset in assets]
