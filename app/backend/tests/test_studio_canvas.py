from datetime import UTC, date, datetime, timedelta

from app.models import Asset, AssetFile, AssetVersion, SkillRun
from app.studio import canvas

NOW = datetime(2026, 9, 4, 12, tzinfo=UTC)
TODAY = date(2026, 9, 4)
SHA = "e" * 64


async def _asset(session, created_at=NOW, **overrides):
    fields = {
        "name": "Made",
        "kind": "post",
        "skill": "dw-linkedin-post",
        "origin": "chat",
        "created_at": created_at,
    }
    asset = Asset(**{**fields, **overrides})
    session.add(asset)
    await session.flush()
    return asset


async def _file(session, asset, version, path, media_type):
    session.add(
        AssetFile(
            asset_seq=asset.seq,
            version=version,
            path=path,
            media_type=media_type,
            bytes=1,
        )
    )
    await session.flush()


def _at(day, **at):
    return datetime.combine(day, datetime.min.time(), tzinfo=UTC) + timedelta(**at)


class TestNodes:
    async def test_no_assets_is_no_nodes(self, session):
        assert await canvas.nodes(session) == []

    async def test_a_node_carries_the_wire_shape_with_its_image(self, session):
        asset = await _asset(
            session, look="stat-card", ratio="1:1", origin="marketer", name="Numbers"
        )
        session.add(AssetVersion(asset_seq=asset.seq, version=2, note="again"))
        session.add(
            SkillRun(
                skill="dw-linkedin-post",
                skill_sha=SHA,
                caller="marketer",
                asset_seq=asset.seq,
                status="held",
            )
        )
        await _file(session, asset, 2, "post.md", "text/markdown")
        await _file(session, asset, 2, "image.png", "image/png")
        [node] = await canvas.nodes(session)
        assert node == {
            "id": f"asset:{asset.seq}",
            "asset_seq": asset.seq,
            "version": 2,
            "date": "2026-09-04",
            "kind": "post",
            "label": "Numbers",
            "media_type": "image/png",
            "url": f"/api/assets/{asset.seq}/versions/2/files/image.png",
            "origin": "marketer",
            "skill": "dw-linkedin-post",
            "look": "stat-card",
            "status": "held",
        }

    async def test_a_text_only_asset_links_its_first_text_file(self, session):
        asset = await _asset(session, kind="blog", skill="dw-blog")
        await _file(session, asset, 1, "post.md", "text/markdown")
        await _file(session, asset, 1, "claims.md", "text/markdown")
        [node] = await canvas.nodes(session)
        assert node["url"] == f"/api/assets/{asset.seq}/versions/1/files/claims.md"
        assert node["media_type"] == "text/markdown"

    async def test_an_asset_without_files_has_no_url(self, session):
        await _asset(session)
        [node] = await canvas.nodes(session)
        assert (node["url"], node["media_type"], node["version"], node["status"]) == (
            None,
            "",
            1,
            "ok",
        )

    async def test_nodes_come_newest_first(self, session):
        older = await _asset(session, NOW - timedelta(days=1))
        newer = await _asset(session, NOW)
        nodes = await canvas.nodes(session)
        assert [node["asset_seq"] for node in nodes] == [newer.seq, older.seq]

    async def test_the_default_range_is_the_last_ninety_days(self, session):
        await _asset(session, _at(TODAY - timedelta(days=91)))
        edge = await _asset(session, _at(TODAY - timedelta(days=90)))
        nodes = await canvas.nodes(session)
        assert [node["asset_seq"] for node in nodes] == [edge.seq]

    async def test_a_range_is_inclusive_of_both_days(self, session):
        await _asset(session, _at(date(2026, 9, 1), microseconds=-1))
        first = await _asset(session, _at(date(2026, 9, 1)))
        last = await _asset(session, _at(date(2026, 9, 3), hours=23, minutes=59))
        await _asset(session, _at(date(2026, 9, 4)))
        nodes = await canvas.nodes(session, date(2026, 9, 1), date(2026, 9, 3))
        assert [node["asset_seq"] for node in nodes] == [last.seq, first.seq]

    async def test_only_to_given_reaches_ninety_days_back(self, session):
        await _asset(session, _at(date(2026, 9, 1)))
        old = await _asset(session, _at(date(2026, 8, 30)))
        nodes = await canvas.nodes(session, to=date(2026, 8, 31))
        assert [node["asset_seq"] for node in nodes] == [old.seq]

    async def test_a_to_at_the_dawn_of_time_does_not_overflow(self, session):
        assert await canvas.nodes(session, to=date(1, 1, 10)) == []

    async def test_only_from_given_reaches_today(self, session):
        recent = await _asset(session, NOW)
        await _asset(session, _at(date(2026, 9, 2)))
        nodes = await canvas.nodes(session, frm=date(2026, 9, 3))
        assert [node["asset_seq"] for node in nodes] == [recent.seq]

    async def test_kind_narrows(self, session):
        await _asset(session, kind="post")
        blog = await _asset(session, kind="blog", skill="dw-blog")
        nodes = await canvas.nodes(session, kind="blog")
        assert [node["asset_seq"] for node in nodes] == [blog.seq]
