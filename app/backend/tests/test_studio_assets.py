import pytest

from app import media
from app.config import settings
from app.models import (
    Asset,
    AssetClaim,
    AssetEvidence,
    AssetFile,
    AssetVersion,
    SkillRun,
)
from app.skills import runner
from app.studio import Missing, assets

SHA = "a" * 64
ROW_KEYS = {
    "seq",
    "name",
    "kind",
    "skill",
    "look",
    "ratio",
    "origin",
    "slot_date",
    "slot_name",
    "status",
    "version",
    "preview",
    "created_at",
}
DETAIL_KEYS = ROW_KEYS | {"versions", "claims", "evidence", "feedback", "skill_run_seq"}
FILE_KEYS = {"path", "media_type", "bytes", "url", "text"}


@pytest.fixture(autouse=True)
def media_root(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path))
    return tmp_path


async def _stored(session, row):
    session.add(row)
    await session.flush()
    await session.refresh(row)
    return row


async def _version(session, asset, version, note):
    return await _stored(
        session, AssetVersion(asset_seq=asset.seq, version=version, note=note)
    )


async def _asset(session, **overrides):
    fields = {
        "name": "Three numbers from the quarter",
        "kind": "post",
        "skill": "dw-post",
        "origin": "chat",
    }
    asset = await _stored(session, Asset(**{**fields, **overrides}))
    await _version(session, asset, 1, asset.name)
    return asset


async def _file(session, asset, version, path, data):
    written = media.write(asset.seq, version, path, data)
    return await _stored(
        session, AssetFile(asset_seq=asset.seq, version=version, **written)
    )


async def _run(session, asset, status="ok"):
    return await _stored(
        session,
        SkillRun(
            skill=asset.skill,
            skill_sha=SHA,
            caller="chat",
            asset_seq=asset.seq,
            version=1,
            status=status,
        ),
    )


@pytest.fixture
def opened(monkeypatch):
    asks = []

    async def fake_open_run(session, ask):
        asks.append(ask)
        run = await _stored(
            session,
            SkillRun(
                skill=ask.skill,
                skill_sha=SHA,
                caller=ask.caller,
                asset_seq=ask.asset_seq,
                version=2,
                status="running",
            ),
        )
        return runner.Started(skill_run=run.seq, asset_seq=ask.asset_seq, version=2)

    monkeypatch.setattr(runner, "open_run", fake_open_run)
    return asks


class TestListing:
    async def test_an_empty_library_is_no_assets_and_a_total_of_zero(self, session):
        assert await assets.listing(session) == {"assets": [], "total": 0}

    async def test_rows_carry_the_contract_keys_newest_first(self, session):
        first = await _asset(session, name="First")
        second = await _asset(session, name="Second")
        body = await assets.listing(session)
        assert [row["seq"] for row in body["assets"]] == [second.seq, first.seq]
        assert body["total"] == 2
        for row in body["assets"]:
            assert set(row) == ROW_KEYS

    async def test_each_filter_narrows_the_page_and_the_total(self, session):
        await _asset(session, kind="post", look="stat-card", origin="chat")
        await _asset(session, kind="image", look="quote-card", origin="marketer")
        await _asset(session, kind="image", look="stat-card", origin="mcp")
        assert (await assets.listing(session, kind="image"))["total"] == 2
        assert (await assets.listing(session, look="stat-card"))["total"] == 2
        assert (await assets.listing(session, origin="mcp"))["total"] == 1
        both = await assets.listing(session, kind="image", look="stat-card")
        assert [row["origin"] for row in both["assets"]] == ["mcp"]
        assert both["total"] == 1

    async def test_q_is_a_case_insensitive_substring_of_the_name(self, session):
        await _asset(session, name="Why churn fell")
        await _asset(session, name="Three numbers")
        found = await assets.listing(session, q="CHURN")
        assert [row["name"] for row in found["assets"]] == ["Why churn fell"]
        assert found["total"] == 1

    async def test_q_wildcards_are_letters_not_patterns(self, session):
        await _asset(session, name="a_b")
        await _asset(session, name="axb")
        assert (await assets.listing(session, q="a_b"))["total"] == 1
        assert (await assets.listing(session, q="%"))["total"] == 0

    async def test_limit_and_offset_page_while_the_total_stays_whole(self, session):
        for n in range(3):
            await _asset(session, name=f"Asset {n}")
        page = await assets.listing(session, limit=1, offset=1)
        assert [row["name"] for row in page["assets"]] == ["Asset 1"]
        assert page["total"] == 3


class TestDetail:
    async def test_an_unknown_asset_is_missing(self, session):
        with pytest.raises(Missing, match="404"):
            await assets.detail(session, 404)

    async def test_the_detail_extends_the_row_with_versions_newest_first(self, session):
        asset = await _asset(session)
        await _file(session, asset, 1, "post.md", "# One\n")
        second = await _version(session, asset, 2, "Make it shorter")
        await _file(session, asset, 2, "post.md", "# Two\n")
        await _file(session, asset, 2, "image.png", b"\x89PNG")
        body = await assets.detail(session, asset.seq)
        assert set(body) == DETAIL_KEYS
        assert body["seq"] == asset.seq
        assert body["version"] == 2
        assert [v["version"] for v in body["versions"]] == [2, 1]
        newest, oldest = body["versions"]
        assert newest["note"] == "Make it shorter"
        assert newest["created_at"] == second.created_at.isoformat()
        assert [f["path"] for f in newest["files"]] == ["image.png", "post.md"]
        assert [f["path"] for f in oldest["files"]] == ["post.md"]
        assert oldest["files"][0]["url"] == (
            f"/api/assets/{asset.seq}/versions/1/files/post.md"
        )
        for file in newest["files"]:
            assert set(file) == FILE_KEYS

    async def test_claims_and_evidence_carry_their_version(self, session):
        asset = await _asset(session)
        await _version(session, asset, 2, "Again")
        session.add_all(
            [
                AssetClaim(
                    asset_seq=asset.seq,
                    version=2,
                    text="Everyone loves it",
                    source_kind="none",
                    verified=False,
                ),
                AssetClaim(
                    asset_seq=asset.seq,
                    version=1,
                    text="MRR is 17,147",
                    source_kind="proof",
                    source_ref="mrr",
                    verified=True,
                ),
                AssetEvidence(
                    asset_seq=asset.seq,
                    version=2,
                    kind="proof",
                    ref="mrr",
                    detail="17,147",
                ),
                AssetEvidence(
                    asset_seq=asset.seq,
                    version=1,
                    kind="brand",
                    ref="voice.md",
                    detail="how it sounds",
                ),
            ]
        )
        await session.flush()
        body = await assets.detail(session, asset.seq)
        assert body["claims"] == [
            {
                "version": 1,
                "text": "MRR is 17,147",
                "source_kind": "proof",
                "source_ref": "mrr",
                "verified": True,
            },
            {
                "version": 2,
                "text": "Everyone loves it",
                "source_kind": "none",
                "source_ref": None,
                "verified": False,
            },
        ]
        assert body["evidence"] == [
            {
                "version": 1,
                "kind": "brand",
                "ref": "voice.md",
                "detail": "how it sounds",
            },
            {"version": 2, "kind": "proof", "ref": "mrr", "detail": "17,147"},
        ]

    async def test_the_newest_run_names_the_skill_run_seq(self, session):
        asset = await _asset(session)
        assert (await assets.detail(session, asset.seq))["skill_run_seq"] is None
        await _run(session, asset)
        newest = await _run(session, asset, status="running")
        body = await assets.detail(session, asset.seq)
        assert body["skill_run_seq"] == newest.seq
        assert body["status"] == "running"

    async def test_feedback_rides_along(self, session):
        asset = await _asset(session, feedback="Shorter next time")
        assert (await assets.detail(session, asset.seq))["feedback"] == (
            "Shorter next time"
        )


class TestFileBytes:
    @pytest.mark.parametrize("path", ["/etc/passwd", "../1/post.md", "a/../b", ".."])
    async def test_a_path_that_climbs_is_refused_before_any_lookup(self, session, path):
        with pytest.raises(assets.Refused, match="climb"):
            await assets.file_bytes(session, 1, 1, path)

    async def test_no_file_row_is_missing(self, session):
        asset = await _asset(session)
        with pytest.raises(Missing, match="post.md"):
            await assets.file_bytes(session, asset.seq, 1, "post.md")

    async def test_a_row_whose_bytes_left_the_store_is_missing(
        self, session, media_root
    ):
        asset = await _asset(session)
        await _file(session, asset, 1, "post.md", "# One\n")
        (media_root / "assets" / str(asset.seq) / "1" / "post.md").unlink()
        with pytest.raises(Missing, match="post.md"):
            await assets.file_bytes(session, asset.seq, 1, "post.md")

    async def test_the_bytes_come_back_with_the_media_type(self, session):
        asset = await _asset(session)
        await _file(session, asset, 1, "slides/slide-01.png", b"\x89PNG")
        found = await assets.file_bytes(session, asset.seq, 1, "slides/slide-01.png")
        assert found == (b"\x89PNG", "image/png")


class TestEdit:
    async def test_an_unknown_asset_is_missing(self, session, opened):
        with pytest.raises(Missing, match="404"):
            await assets.edit(session, 404, "Shorter")
        assert opened == []

    async def test_an_edit_opens_a_chat_run_on_the_asset_with_its_look_and_ratio(
        self, session, opened
    ):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        started, ask = await assets.edit(session, asset.seq, "Make it shorter")
        assert opened == [ask]
        assert (ask.skill, ask.caller, ask.input) == (
            "dw-post",
            "chat",
            "Make it shorter",
        )
        assert (ask.look, ask.ratio, ask.asset_seq) == ("stat-card", "1:1", asset.seq)
        assert (ask.slot_date, ask.slot_name) == (None, None)
        assert started.version == 2
        run = await session.get(SkillRun, started.skill_run)
        assert (run.asset_seq, run.status) == (asset.seq, "running")


class TestResize:
    async def test_an_unknown_asset_is_missing(self, session, opened):
        with pytest.raises(Missing, match="404"):
            await assets.resize(session, 404, "9:16")
        assert opened == []

    async def test_a_ratio_outside_the_frames_is_refused(self, session, opened):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        with pytest.raises(assets.Refused, match="3:2"):
            await assets.resize(session, asset.seq, "3:2")
        assert opened == []

    async def test_an_asset_without_a_look_has_no_image_to_remake(
        self, session, opened
    ):
        asset = await _asset(session)
        with pytest.raises(assets.Refused, match="look"):
            await assets.resize(session, asset.seq, "9:16")
        assert opened == []

    async def test_a_resize_is_an_edit_at_the_new_ratio(self, session, opened):
        asset = await _asset(session, look="stat-card", ratio="1:1")
        started, ask = await assets.resize(session, asset.seq, "9:16")
        assert opened == [ask]
        assert (ask.input, ask.look, ask.ratio) == (
            "Remake this at 9:16",
            "stat-card",
            "9:16",
        )
        assert (ask.caller, ask.asset_seq) == ("chat", asset.seq)
        assert started.version == 2


class TestFeedback:
    async def test_an_unknown_asset_is_missing(self, session):
        with pytest.raises(Missing, match="404"):
            await assets.feedback(session, 404, "Shorter")

    async def test_feedback_is_stored_and_the_detail_comes_back(self, session):
        asset = await _asset(session)
        body = await assets.feedback(session, asset.seq, "Shorter next time")
        assert body["feedback"] == "Shorter next time"
        assert set(body) == DETAIL_KEYS
        assert (await session.get(Asset, asset.seq)).feedback == "Shorter next time"
