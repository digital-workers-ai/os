import uuid
from datetime import UTC, date, datetime

from app import media
from app.config import settings
from app.models import AgentRun, Asset, AssetFile, AssetVersion, SkillRun
from app.studio import rows

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
LATER = datetime(2026, 9, 4, 12, 30, tzinfo=UTC)
SHA = "b" * 64


async def _stored(session, row):
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _asset(session, **overrides):
    fields = {
        "name": "Three numbers",
        "kind": "post",
        "skill": "dw-post",
        "origin": "chat",
    }
    return await _stored(session, Asset(**{**fields, **overrides}))


async def _run(session, asset, status="ok"):
    return await _stored(
        session,
        SkillRun(
            skill="dw-post",
            skill_sha=SHA,
            caller="chat",
            asset_seq=asset.seq,
            status=status,
        ),
    )


async def _version(session, asset, version):
    return await _stored(
        session, AssetVersion(asset_seq=asset.seq, version=version, note=f"v{version}")
    )


async def _file(session, asset, version, path, media_type, size=10):
    return await _stored(
        session,
        AssetFile(
            asset_seq=asset.seq,
            version=version,
            path=path,
            media_type=media_type,
            bytes=size,
        ),
    )


class TestSkillRunRow:
    def test_carries_every_wire_field(self):
        run = SkillRun(
            seq=7,
            skill="dw-post",
            skill_sha=SHA,
            caller="marketer",
            asset_seq=3,
            version=2,
            stage="painting",
            status="ok",
            error=None,
            model="claude-opus-5",
            tokens_in=120,
            tokens_out=40,
            duration_ms=900,
            started_at=NOW,
            finished_at=LATER,
        )
        assert rows.skill_run_row(run) == {
            "seq": 7,
            "skill": "dw-post",
            "skill_sha": SHA,
            "caller": "marketer",
            "asset_seq": 3,
            "version": 2,
            "stage": "painting",
            "status": "ok",
            "error": None,
            "model": "claude-opus-5",
            "tokens_in": 120,
            "tokens_out": 40,
            "duration_ms": 900,
            "started_at": "2026-09-04T12:00:00+00:00",
            "finished_at": "2026-09-04T12:30:00+00:00",
        }

    def test_a_running_run_has_no_finish(self):
        run = SkillRun(
            seq=1,
            skill="dw-post",
            skill_sha=SHA,
            caller="chat",
            status="running",
            tokens_in=0,
            tokens_out=0,
            duration_ms=0,
            started_at=NOW,
        )
        row = rows.skill_run_row(run)
        assert row["finished_at"] is None
        assert (row["asset_seq"], row["version"], row["stage"], row["error"]) == (
            None,
            None,
            None,
            None,
        )


class TestAgentRunRow:
    def test_carries_every_wire_field(self):
        run = AgentRun(
            seq=2,
            agent="marketer",
            trigger="daily",
            read_detail="14 days, 4 slots, 2 empty",
            made=2,
            duration_ms=90000,
            ok=False,
            error="SkillError: dw-post unknown",
            created_at=NOW,
        )
        assert rows.agent_run_row(run) == {
            "seq": 2,
            "agent": "marketer",
            "trigger": "daily",
            "read_detail": "14 days, 4 slots, 2 empty",
            "made": 2,
            "duration_ms": 90000,
            "ok": False,
            "error": "SkillError: dw-post unknown",
            "created_at": "2026-09-04T12:00:00+00:00",
        }


class TestAssetRow:
    def test_carries_every_wire_field(self):
        asset = Asset(
            seq=5,
            name="Why churn fell",
            kind="post",
            skill="dw-post",
            look="stat-card",
            ratio="1:1",
            origin="marketer",
            slot_date=date(2026, 9, 4),
            slot_name="linkedin_post",
            created_at=NOW,
        )
        preview = "/api/assets/5/versions/3/files/a.png"
        row = rows.asset_row(asset, status="held", version=3, preview=preview)
        assert row == {
            "seq": 5,
            "name": "Why churn fell",
            "kind": "post",
            "skill": "dw-post",
            "look": "stat-card",
            "ratio": "1:1",
            "origin": "marketer",
            "slot_date": "2026-09-04",
            "slot_name": "linkedin_post",
            "status": "held",
            "version": 3,
            "preview": preview,
            "created_at": "2026-09-04T12:00:00+00:00",
        }

    def test_an_unslotted_asset_has_null_slot_fields(self):
        asset = Asset(
            seq=1, name="x", kind="blog", skill="dw-blog", origin="chat", created_at=NOW
        )
        row = rows.asset_row(asset, status="ok", version=1, preview=None)
        assert (row["slot_date"], row["slot_name"], row["look"], row["ratio"]) == (
            None,
            None,
            None,
            None,
        )
        assert row["preview"] is None


class TestFileRow:
    def _file(self, path, media_type, size):
        return AssetFile(
            id=uuid.uuid4(),
            asset_seq=4,
            version=2,
            path=path,
            media_type=media_type,
            bytes=size,
        )

    def test_readable_text_under_the_limit_is_decoded(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
        media.write(4, 2, "post.md", "# Hello\n")
        row = rows.file_row(4, 2, self._file("post.md", "text/markdown", 8))
        assert row == {
            "path": "post.md",
            "media_type": "text/markdown",
            "bytes": 8,
            "url": "/api/assets/4/versions/2/files/post.md",
            "text": "# Hello\n",
        }

    def test_an_image_carries_no_text_and_is_never_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
        row = rows.file_row(4, 2, self._file("image.png", "image/png", 348211))
        assert row["text"] is None
        assert row["url"] == "/api/assets/4/versions/2/files/image.png"

    def test_readable_text_at_the_limit_is_not_read(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
        row = rows.file_row(4, 2, self._file("big.md", "text/markdown", 256 * 1024))
        assert row["text"] is None

    def test_bytes_that_are_not_utf8_are_replaced(self, tmp_path, monkeypatch):
        monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
        media.write(4, 2, "odd.txt", b"a\xffb")
        row = rows.file_row(4, 2, self._file("odd.txt", "text/plain", 3))
        assert row["text"] == "a�b"


class TestAssetRows:
    async def test_no_assets_means_no_query_at_all(self, session, count_queries):
        with count_queries() as counter:
            assert await rows.asset_rows(session, []) == []
        assert counter.total == 0

    async def test_three_queries_serve_any_number_of_assets(
        self, session, count_queries
    ):
        assets = [await _asset(session) for _ in range(5)]
        for asset in assets:
            await _version(session, asset, 1)
            await _run(session, asset)
            await _file(session, asset, 1, "image.png", "image/png")
        with count_queries() as counter:
            served = await rows.asset_rows(session, assets)
        assert counter.total == 3
        assert len(served) == 5

    async def test_defaults_are_version_one_status_ok_and_no_preview(self, session):
        asset = await _asset(session)
        [row] = await rows.asset_rows(session, [asset])
        assert (row["version"], row["status"], row["preview"]) == (1, "ok", None)

    async def test_version_is_the_highest_version_row(self, session):
        asset = await _asset(session)
        for version in (1, 2, 3):
            await _version(session, asset, version)
        [row] = await rows.asset_rows(session, [asset])
        assert row["version"] == 3

    async def test_status_is_the_newest_runs_status(self, session):
        asset = await _asset(session)
        other = await _asset(session)
        await _run(session, asset, "ok")
        await _run(session, asset, "running")
        await _run(session, other, "failed")
        first, second = await rows.asset_rows(session, [asset, other])
        assert (first["status"], second["status"]) == ("running", "failed")

    async def test_preview_is_the_first_image_of_the_newest_version_by_path(
        self, session
    ):
        asset = await _asset(session)
        await _version(session, asset, 1)
        await _version(session, asset, 2)
        await _file(session, asset, 1, "a.png", "image/png")
        await _file(session, asset, 2, "z.png", "image/png")
        await _file(session, asset, 2, "b.jpg", "image/jpeg")
        await _file(session, asset, 2, "a.md", "text/markdown")
        [row] = await rows.asset_rows(session, [asset])
        assert row["preview"] == "/api/assets/1/versions/2/files/b.jpg"

    async def test_a_newest_version_without_an_image_has_no_preview(self, session):
        asset = await _asset(session)
        await _version(session, asset, 1)
        await _version(session, asset, 2)
        await _file(session, asset, 1, "image.png", "image/png")
        await _file(session, asset, 2, "post.md", "text/markdown")
        [row] = await rows.asset_rows(session, [asset])
        assert row["preview"] is None

    async def test_an_unversioned_asset_previews_its_version_one_files(self, session):
        asset = await _asset(session)
        await _file(session, asset, 1, "image.png", "image/png")
        [row] = await rows.asset_rows(session, [asset])
        assert row["preview"] == "/api/assets/1/versions/1/files/image.png"

    async def test_rows_keep_the_order_given(self, session):
        first = await _asset(session, name="first")
        second = await _asset(session, name="second")
        served = await rows.asset_rows(session, [second, first])
        assert [row["name"] for row in served] == ["second", "first"]


class TestLookup:
    async def test_first_finds_the_first_file_by_prefix_or_nothing(self, session):
        asset = await _asset(session)
        await _file(session, asset, 1, "post.md", "text/markdown")
        await _file(session, asset, 1, "notes.txt", "text/plain")
        lookup = await rows.Lookup.load(session, [asset.seq])
        assert lookup.first(asset.seq, "text/").path == "notes.txt"
        assert lookup.first(asset.seq, "image/") is None
        assert lookup.first(999, "text/") is None

    async def test_an_empty_lookup_answers_the_defaults(self, session):
        lookup = await rows.Lookup.load(session, [])
        assert (lookup.version(1), lookup.status(1), lookup.preview(1)) == (
            1,
            "ok",
            None,
        )
