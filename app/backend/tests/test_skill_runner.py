import sys
import types
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app import llm, media
from app.config import settings
from app.models import (
    Asset,
    AssetFile,
    EntityCanonical,
    FactCurrent,
    Proposal,
    ProposalClaim,
    ProposalDraft,
    ProposalEvidence,
    SkillRun,
    SkillRunToolCall,
)
from app.skills import catalog, runner, toolbelt

SKILL = """---
name: dw-post
description: One post, said once.
---

# Skill: Post

One LinkedIn post, from the company's own proof.

## Modes

**draft** is the daily run. **build** runs after approval. **chat** is MCP.

## Rules

- One idea.

## Lessons

- Never lead with a statistic (#209, 2026-09-12).
"""

SEEN = datetime(2026, 8, 1, tzinfo=UTC)


class Text:
    type = "text"

    def __init__(self, text):
        self.text = text


class ToolUse:
    type = "tool_use"

    def __init__(self, name, tool_input=None, call_id="call-1"):
        self.name, self.input, self.id = name, tool_input or {}, call_id


class Usage:
    def __init__(self, input_tokens=120, output_tokens=40):
        self.input_tokens, self.output_tokens = input_tokens, output_tokens


class Reply:
    def __init__(self, *content, stop_reason="end_turn", usage=None):
        self.content = list(content)
        self.stop_reason, self.model = stop_reason, "claude-test"
        self.usage = usage or Usage()


class ScriptedModel:
    def __init__(self, *replies, raises=None):
        self.replies, self.raises = list(replies), raises
        self.sent = []

    class _Messages:
        def __init__(self, outer):
            self.outer = outer

        async def create(self, **kwargs):
            self.outer.sent.append(kwargs)
            if self.outer.raises:
                raise self.outer.raises
            replies = self.outer.replies
            return replies.pop(0) if len(replies) > 1 else replies[0]

    @property
    def messages(self):
        return self._Messages(self)


def writes(*files, answer="done"):
    calls = [
        ToolUse("files_write", {"path": path, "text": text}, f"call-{n}")
        for n, (path, text) in enumerate(files)
    ]
    return ScriptedModel(Reply(*calls), Reply(Text(answer)))


@pytest.fixture
def studio(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "STUDIO_ENABLED", True)
    monkeypatch.setattr(settings, "MEDIA_DIR", str(tmp_path / "media"))
    skills = tmp_path / "skills"
    (skills / "dw-post").mkdir(parents=True)
    (skills / "dw-post" / "SKILL.md").write_text(SKILL)
    monkeypatch.setattr(catalog, "SKILLS_DIR", skills)
    return skills


@pytest.fixture
def provide(monkeypatch):
    def install(dotted, **attributes):
        module = types.ModuleType(dotted)
        for key, value in attributes.items():
            setattr(module, key, value)
        parent_name, _, leaf = dotted.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is None:
            parent = types.ModuleType(parent_name)
            monkeypatch.setitem(sys.modules, parent_name, parent)
        monkeypatch.setattr(parent, leaf, module, raising=False)
        monkeypatch.setitem(sys.modules, dotted, module)
        return module

    return install


@pytest.fixture
def bench(session, studio):
    return toolbelt.Bench(session=session, run_seq=1, mode="build", kind="runs", seq=1)


@pytest.fixture
async def skill_run(session):
    row = SkillRun(
        skill="dw-post",
        skill_sha="a" * 64,
        mode="build",
        caller="studio",
        status="running",
    )
    session.add(row)
    await session.flush()
    return row


async def calls_of(session):
    rows = (
        (await session.execute(select(SkillRunToolCall).order_by(SkillRunToolCall.id)))
        .scalars()
        .all()
    )
    return [(row.tool, row.ok) for row in rows]


class TestTheToolbeltReads:
    async def test_brand_read_returns_the_file_and_records_the_call(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        payload = await toolbelt.call(bench, "brand.read", {"name": "voice"})
        assert payload["body"].strip()
        assert await calls_of(session) == [("brand.read", True)]

    async def test_a_file_read_twice_is_one_line_in_the_manifest(
        self, bench, skill_run
    ):
        bench.run_seq = skill_run.seq
        await toolbelt.call(bench, "brand.read", {"name": "voice"})
        await toolbelt.call(bench, "brand.read", {"name": "voice"})
        assert [row["ref"] for row in bench.read] == ["voice.md"]

    async def test_brand_read_of_a_file_that_is_not_ours_is_refused(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        payload = await toolbelt.call(bench, "brand.read", {"name": "passwords"})
        assert "error" in payload
        assert await calls_of(session) == [("brand.read", False)]

    async def test_brand_list_names_the_files(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert "voice" in (await toolbelt.call(bench, "brand.list", {}))["files"]

    async def test_calendar_read_returns_every_slot(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert (await toolbelt.call(bench, "calendar.read", {}))["slots"]

    async def test_calendar_read_returns_one_slot_by_name(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        from app.engine import calendar

        name = sorted(calendar.slots())[0]
        assert (await toolbelt.call(bench, "calendar.read", {"slot": name}))[
            "slot"
        ] == name

    async def test_calendar_read_of_an_unknown_slot_is_refused(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert "error" in await toolbelt.call(bench, "calendar.read", {"slot": "never"})

    async def test_looks_read_reaches_the_looks_module(self, bench, skill_run, provide):
        bench.run_seq = skill_run.seq
        provide("app.engine.looks", read=lambda name: {"name": name, "fields": []})
        assert (await toolbelt.call(bench, "looks.read", {"name": "soda"}))["look"] == {
            "name": "soda",
            "fields": [],
        }

    async def test_a_module_that_is_not_there_yet_fails_the_call(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        payload = await toolbelt.call(bench, "swipe.read", {"id": "8821"})
        assert "error" in payload
        assert await calls_of(session) == [("swipe.read", False)]

    async def test_swipe_read_and_search_reach_the_swipe_module(
        self, bench, skill_run, provide
    ):
        bench.run_seq = skill_run.seq

        async def read(session, item_id):
            return {"id": item_id, "headline": "theirs"}

        async def search(session, **filters):
            return [{"id": "1", **filters}]

        provide("app.studio.swipe", read=read, search=search)
        assert (await toolbelt.call(bench, "swipe.read", {"id": "8821"}))["item"] == {
            "id": "8821",
            "headline": "theirs",
        }
        found = await toolbelt.call(
            bench, "swipe.search", {"competitor": "acme", "sort": "days_running"}
        )
        assert found["items"] == [
            {"id": "1", "competitor": "acme", "sort": "days_running", "limit": 20}
        ]

    async def test_assets_read_returns_an_asset_and_its_text(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        asset = Asset(name="Older post", kind="post", origin="chat")
        session.add(asset)
        await session.flush()
        media.write("assets", asset.seq, 1, "post.md", "the older words")
        session.add(
            AssetFile(
                asset_seq=asset.seq,
                version=1,
                path="post.md",
                media_type="text/markdown",
                bytes=15,
            )
        )
        await session.flush()
        payload = await toolbelt.call(bench, "assets.read", {"seq": asset.seq})
        assert payload["asset"]["name"] == "Older post"
        assert payload["text"] == {"post.md": "the older words"}

    async def test_assets_read_leaves_the_bytes_of_a_rendered_file_alone(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        asset = Asset(name="Older image", kind="image", origin="chat")
        session.add(asset)
        await session.flush()
        media.write("assets", asset.seq, 1, "v1.png", b"pixels")
        payload = await toolbelt.call(bench, "assets.read", {"seq": asset.seq})
        assert payload["files"] == [
            {"path": "v1.png", "media_type": "image/png", "bytes": 6}
        ]
        assert payload["text"] == {}

    async def test_a_call_with_no_transcript_is_refused(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        canonical_id = uuid.uuid5(uuid.NAMESPACE_URL, "meeting|silent")
        session.add(
            EntityCanonical(
                canonical_id=canonical_id,
                entity_type="meeting",
                anchor_key="zoom|meeting|silent",
                minted_seq=1,
                member_count=1,
            )
        )
        session.add(
            FactCurrent(
                id=uuid.uuid5(uuid.NAMESPACE_URL, "silent|name"),
                canonical_id=canonical_id,
                entity_type="meeting",
                attr="name",
                value="Silent call",
                observed_at=SEEN,
            )
        )
        await session.flush()
        assert (
            "carries no transcript"
            in (await toolbelt.call(bench, "transcript.read", {"ref": "Silent call"}))[
                "error"
            ]
        )

    async def test_assets_read_of_an_asset_that_is_not_there_is_refused(
        self, bench, skill_run
    ):
        bench.run_seq = skill_run.seq
        assert "error" in await toolbelt.call(bench, "assets.read", {"seq": 404})

    async def test_transcript_read_lists_the_calls_it_can_open(
        self, bench, skill_run, session, meeting
    ):
        bench.run_seq = skill_run.seq
        await meeting("Acme intro", "we lose four hours a week to reporting")
        payload = await toolbelt.call(bench, "transcript.read", {})
        assert [row["name"] for row in payload["transcripts"]] == ["Acme intro"]

    async def test_transcript_read_returns_one_call_by_name(
        self, bench, skill_run, meeting
    ):
        bench.run_seq = skill_run.seq
        await meeting("Acme intro", "we lose four hours a week")
        payload = await toolbelt.call(bench, "transcript.read", {"ref": "Acme intro"})
        assert payload["transcript"] == "we lose four hours a week"

    async def test_transcript_read_returns_one_call_by_id(
        self, bench, skill_run, meeting
    ):
        bench.run_seq = skill_run.seq
        canonical_id = await meeting("Acme intro", "four hours a week")
        payload = await toolbelt.call(
            bench, "transcript.read", {"ref": str(canonical_id)}
        )
        assert payload["transcript"] == "four hours a week"

    async def test_transcript_read_of_a_call_that_is_not_there_is_refused(
        self, bench, skill_run
    ):
        bench.run_seq = skill_run.seq
        assert "error" in await toolbelt.call(
            bench, "transcript.read", {"ref": "no such call"}
        )


class TestWhatADraftMayNotSpend:
    async def test_a_draft_renders_an_image_flat_because_that_costs_nothing(
        self, bench, skill_run, session, provide
    ):
        bench.run_seq, bench.mode = skill_run.seq, "draft"
        provide("app.render.image", render=lambda **kwargs: b"pixels")
        payload = await toolbelt.call(bench, "image.render", {"look": "soda"})
        assert payload["bytes"] == 6
        assert await calls_of(session) == [("image.render", True)]

    async def test_a_draft_may_not_pay_for_a_generated_background(
        self, bench, skill_run, session, provide
    ):
        bench.run_seq, bench.mode = skill_run.seq, "draft"
        provide("app.render.image", render=lambda **kwargs: b"pixels")
        payload = await toolbelt.call(
            bench, "image.render", {"look": "soda", "background": "a lit desk"}
        )
        assert "only on a build" in payload["error"]
        assert await calls_of(session) == [("image.render", False)]

    async def test_video_render_refuses_on_a_draft(self, bench, skill_run):
        bench.run_seq, bench.mode = skill_run.seq, "draft"
        assert (
            "never pays"
            in (await toolbelt.call(bench, "video.render", {"look": "aios"}))["error"]
        )

    async def test_video_plan_costs_nothing_so_a_draft_may_call_it(
        self, bench, skill_run, provide
    ):
        bench.run_seq, bench.mode = skill_run.seq, "draft"
        provide("app.render.video", plan=lambda look, content: ["scene 2 is too long"])
        payload = await toolbelt.call(
            bench, "video.plan", {"look": "aios", "content": "scenes: []"}
        )
        assert payload == {"ok": False, "problems": ["scene 2 is too long"]}

    async def test_a_build_renders_an_image_and_hands_back_a_handle(
        self, bench, skill_run, provide
    ):
        bench.run_seq = skill_run.seq
        provide("app.render.image", render=lambda **kwargs: b"pixels")
        payload = await toolbelt.call(
            bench, "image.render", {"look": "soda", "fields": {"headline": "hi"}}
        )
        assert payload["bytes"] == 6
        assert bench.renders[payload["render"]] == b"pixels"

    async def test_a_renderer_that_answers_later_is_awaited(
        self, bench, skill_run, provide
    ):
        bench.run_seq = skill_run.seq

        async def render(**kwargs):
            return b"pixels"

        provide("app.render.image", render=render)
        assert (await toolbelt.call(bench, "image.render", {"look": "soda"}))[
            "bytes"
        ] == 6

    async def test_a_build_renders_a_video_and_hands_back_every_file(
        self, bench, skill_run, provide
    ):
        bench.run_seq = skill_run.seq
        provide(
            "app.render.video",
            render=lambda **kwargs: {"video.mp4": b"mp4", "composition.json": b"{}"},
        )
        payload = await toolbelt.call(bench, "video.render", {"look": "aios"})
        assert [file["name"] for file in payload["renders"]] == [
            "composition.json",
            "video.mp4",
        ]
        assert len(bench.renders) == 2


class TestTheOnlyWayOut:
    async def test_files_write_puts_text_in_the_store(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        written = await toolbelt.call(
            bench, "files.write", {"path": "post.md", "text": "the words"}
        )
        assert written == {
            "path": "post.md",
            "media_type": "text/markdown",
            "bytes": 9,
        }
        assert media.read("runs", 1, 1, "post.md") == b"the words"

    async def test_files_write_keeps_a_render(self, bench, skill_run, provide):
        bench.run_seq = skill_run.seq
        provide("app.render.image", render=lambda **kwargs: b"pixels")
        rendered = await toolbelt.call(bench, "image.render", {"look": "soda"})
        handle = rendered["render"]
        written = await toolbelt.call(
            bench, "files.write", {"path": "v1.png", "render": handle}
        )
        assert written["bytes"] == 6
        assert bench.renders == {}

    async def test_files_write_takes_one_of_text_or_a_render(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert (
            "exactly one"
            in (await toolbelt.call(bench, "files.write", {"path": "post.md"}))["error"]
        )
        assert (
            "exactly one"
            in (
                await toolbelt.call(
                    bench, "files.write", {"path": "p.md", "text": "a", "render": "r"}
                )
            )["error"]
        )

    async def test_files_write_refuses_a_handle_it_never_gave(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert (
            "no render named"
            in (
                await toolbelt.call(
                    bench, "files.write", {"path": "v1.png", "render": "render-9"}
                )
            )["error"]
        )

    async def test_files_write_refuses_a_path_that_leaves_the_store(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        payload = await toolbelt.call(
            bench, "files.write", {"path": "../escape.md", "text": "a"}
        )
        assert "error" in payload
        assert await calls_of(session) == [("files.write", False)]

    async def test_a_second_write_replaces_the_first_in_the_manifest(
        self, bench, skill_run
    ):
        bench.run_seq = skill_run.seq
        await toolbelt.call(bench, "files.write", {"path": "post.md", "text": "one"})
        await toolbelt.call(bench, "files.write", {"path": "post.md", "text": "two"})
        assert [file["path"] for file in bench.written] == ["post.md"]


class TestTheToolbeltItself:
    async def test_a_tool_that_does_not_exist_is_refused(self, bench, skill_run):
        bench.run_seq = skill_run.seq
        assert "no tool named" in (await toolbelt.call(bench, "shell.run", {}))["error"]

    async def test_an_argument_the_tool_does_not_take_fails_the_call(
        self, bench, skill_run, session
    ):
        bench.run_seq = skill_run.seq
        payload = await toolbelt.call(bench, "brand.list", {"sudo": True})
        assert "error" in payload
        assert await calls_of(session) == [("brand.list", False)]

    def test_every_tool_is_declared_with_a_wire_name_the_api_accepts(self):
        declared = {spec["name"] for spec in toolbelt.schemas()}
        assert declared == {toolbelt.wire(name) for name in toolbelt.HANDLERS}
        assert all(name.replace("_", "").isalnum() for name in declared)
        assert all(
            toolbelt.dotted(toolbelt.wire(name)) == name for name in toolbelt.HANDLERS
        )

    def test_the_toolbelt_is_the_twelve_tools_and_nothing_else(self):
        assert sorted(toolbelt.HANDLERS) == [
            "assets.read",
            "brand.list",
            "brand.read",
            "calendar.read",
            "files.write",
            "image.render",
            "looks.read",
            "swipe.read",
            "swipe.search",
            "transcript.read",
            "video.plan",
            "video.render",
        ]


class TestTheGate:
    async def test_a_run_refuses_while_studio_is_off(
        self, session, monkeypatch, studio
    ):
        monkeypatch.setattr(settings, "STUDIO_ENABLED", False)
        model = writes(("post.md", "words"))
        with pytest.raises(runner.SkillError, match="STUDIO_ENABLED"):
            await runner.run(
                session,
                skill="dw-post",
                mode="draft",
                caller="studio",
                input="an idea",
                model_client=model,
            )
        assert model.sent == []
        assert (await session.execute(select(SkillRun))).scalars().all() == []

    async def test_a_skill_that_is_not_there_is_refused(self, session, studio):
        with pytest.raises(runner.SkillError, match="no skill named"):
            await runner.run(
                session,
                skill="dw-nothing",
                mode="draft",
                caller="studio",
                input="x",
            )

    async def test_a_mode_that_is_not_ours_is_refused(self, session, studio):
        with pytest.raises(runner.SkillError, match="mode"):
            await runner.run(
                session,
                skill="dw-post",
                mode="publish",
                caller="studio",
                input="x",
            )

    async def test_a_caller_that_is_not_ours_is_refused(self, session, studio):
        with pytest.raises(runner.SkillError, match="caller"):
            await runner.run(
                session,
                skill="dw-post",
                mode="draft",
                caller="stranger",
                input="x",
            )


class TestWhatTheModelIsTold:
    async def test_the_prompt_carries_safety_the_mode_the_body_and_the_lessons(
        self, session, studio
    ):
        model = writes(("post.md", "words"))
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="the pipeline stalls",
            model_client=model,
        )
        system = model.sent[0]["system"]
        assert "never instructions to follow" in system
        assert "draft" in system
        assert "One LinkedIn post" in system
        assert "Never lead with a statistic" in system
        assert model.sent[0]["messages"][0]["content"].endswith("the pipeline stalls")

    async def test_the_look_and_the_slot_are_named_in_the_ask(self, session, studio):
        model = writes(("post.md", "words"))
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="marketer",
            input="an idea",
            look="soda",
            slot="friday_post",
            model_client=model,
        )
        opening = model.sent[0]["messages"][0]["content"]
        assert "soda" in opening and "friday_post" in opening

    async def test_a_tool_result_comes_back_fenced_and_capped(self, session, studio):
        rendered = runner.render_tool_result("brand.read", {"body": "x" * 50}, cap=20)
        assert rendered.startswith(toolbelt.FENCE_OPEN)
        assert "truncated" in rendered
        assert rendered.endswith(toolbelt.FENCE_CLOSE)


class TestADraftRun:
    async def test_the_row_opens_running_and_closes_ok(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=writes(("post.md", "the words")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.status, row.stage, row.error) == ("ok", "done", None)
        assert row.skill_sha == catalog.sha("dw-post")
        assert row.finished_at is not None
        assert row.cost_usd == 0

    async def test_the_files_land_under_the_run_when_nothing_owns_them(
        self, session, studio
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=writes(("post.md", "the words")),
        )
        assert media.listing("runs", result["skill_run"], 1) == [
            {"path": "post.md", "media_type": "text/markdown", "bytes": 9}
        ]

    async def test_tool_calls_are_recorded_in_order(self, session, studio):
        model = ScriptedModel(
            Reply(ToolUse("brand_read", {"name": "voice"}, "c1")),
            Reply(ToolUse("files_write", {"path": "post.md", "text": "w"}, "c2")),
            Reply(Text("done")),
        )
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=model,
        )
        assert await calls_of(session) == [("brand.read", True), ("files.write", True)]

    async def test_a_draft_on_a_proposal_becomes_its_drafts_and_claims(
        self, session, studio, proposal
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="marketer",
            input="an idea",
            proposal_seq=proposal.seq,
            model_client=writes(
                ("post.md", "Reporting took four hours."),
                (
                    "claims.md",
                    "# claims\n\nReporting took four hours. | proof | brand/proof.md",
                ),
                ("build.md", "Two images, about a dollar."),
            ),
        )
        drafts = (
            (await session.execute(select(ProposalDraft).order_by(ProposalDraft.path)))
            .scalars()
            .all()
        )
        assert [draft.path for draft in drafts] == [
            "build.md",
            "claims.md",
            "post.md",
        ]
        claims = (await session.execute(select(ProposalClaim))).scalars().all()
        assert [(c.text, c.source_kind, c.source_ref, c.verified) for c in claims] == [
            ("Reporting took four hours.", "proof", "brand/proof.md", True)
        ]
        assert (await session.get(SkillRun, result["skill_run"])).stage == "done"

    async def test_a_redo_replaces_the_drafts_of_the_last_one(
        self, session, studio, proposal
    ):
        for text in ("first words", "second words"):
            await runner.run(
                session,
                skill="dw-post",
                mode="draft",
                caller="studio",
                input="an idea",
                proposal_seq=proposal.seq,
                model_client=writes(("post.md", text)),
            )
        drafts = (await session.execute(select(ProposalDraft))).scalars().all()
        assert [(d.path, d.bytes) for d in drafts] == [("post.md", 12)]
        assert media.read("proposals", proposal.seq, 1, "post.md") == b"second words"

    async def test_what_was_read_becomes_evidence(self, session, studio, proposal):
        model = ScriptedModel(
            Reply(ToolUse("brand_read", {"name": "voice"}, "c1")),
            Reply(ToolUse("files_write", {"path": "post.md", "text": "w"}, "c2")),
            Reply(Text("done")),
        )
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            proposal_seq=proposal.seq,
            model_client=model,
        )
        evidence = (await session.execute(select(ProposalEvidence))).scalars().all()
        assert [(row.kind, row.ref) for row in evidence] == [("brand", "voice.md")]
        assert evidence[0].detail


class TestAHeldDraft:
    async def test_held_ends_ok_with_the_sentence_recorded(
        self, session, studio, proposal
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="marketer",
            input="an idea",
            proposal_seq=proposal.seq,
            model_client=writes(
                (
                    "held.md",
                    "No proof for this:\n\n- Reporting takes four hours.\n",
                ),
            ),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.status, row.stage, row.error) == ("ok", "held", None)
        claims = (await session.execute(select(ProposalClaim))).scalars().all()
        assert [(c.text, c.source_ref, c.verified) for c in claims] == [
            ("Reporting takes four hours.", None, False)
        ]
        assert result["held"] is True

    async def test_a_claim_with_no_source_holds_the_draft_the_same_way(
        self, session, studio, proposal
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="marketer",
            input="an idea",
            proposal_seq=proposal.seq,
            model_client=writes(
                ("post.md", "We are the fastest."),
                (
                    "claims.md",
                    "We are the fastest.\nReporting took four hours. | proof",
                ),
            ),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.status, row.stage) == ("ok", "held")
        claims = (
            (await session.execute(select(ProposalClaim).order_by(ProposalClaim.id)))
            .scalars()
            .all()
        )
        assert [(c.source_kind, c.verified) for c in claims] == [
            ("none", False),
            ("proof", False),
        ]

    async def test_a_held_chat_run_still_keeps_the_asset(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="chat",
            caller="mcp",
            input="an idea",
            model_client=writes(("held.md", "- No number for this.\n")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.status, row.stage) == ("ok", "held")
        assert (await session.get(Asset, row.asset_seq)).origin == "chat"


class TestABuildRun:
    async def test_a_build_becomes_an_asset_with_its_files(
        self, session, studio, proposal
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="build",
            caller="studio",
            input="the approved words",
            proposal_seq=proposal.seq,
            model_client=writes(("post.md", "the words")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        asset = await session.get(Asset, row.asset_seq)
        assert (asset.name, asset.kind, asset.origin) == (
            "Why the pipeline stalls",
            "post",
            "proposal",
        )
        assert asset.proposal_seq == proposal.seq
        files = (await session.execute(select(AssetFile))).scalars().all()
        assert [(f.version, f.path, f.bytes) for f in files] == [(1, "post.md", 9)]
        assert media.read("assets", asset.seq, 1, "post.md") == b"the words"

    async def test_a_chat_build_is_named_from_the_ask(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="chat",
            caller="mcp",
            input="a post about onboarding\nin our voice",
            model_client=writes(("post.md", "the words")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        asset = await session.get(Asset, row.asset_seq)
        assert (asset.name, asset.origin, asset.proposal_seq) == (
            "a post about onboarding",
            "chat",
            None,
        )

    async def test_a_rebuild_writes_the_next_version_with_the_note(
        self, session, studio
    ):
        first = await runner.run(
            session,
            skill="dw-post",
            mode="chat",
            caller="mcp",
            input="an idea",
            model_client=writes(("post.md", "the words")),
        )
        asset_seq = (await session.get(SkillRun, first["skill_run"])).asset_seq
        await runner.run(
            session,
            skill="dw-post",
            mode="build",
            caller="studio",
            input="shorter hook",
            asset_seq=asset_seq,
            model_client=writes(("post.md", "tighter words")),
        )
        files = (
            (await session.execute(select(AssetFile).order_by(AssetFile.version)))
            .scalars()
            .all()
        )
        assert [(f.version, f.note) for f in files] == [
            (1, None),
            (2, "shorter hook"),
        ]
        assert media.read("assets", asset_seq, 2, "post.md") == b"tighter words"

    async def test_a_remix_records_the_ancestor_it_came_from(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="chat",
            caller="mcp",
            input="remix 8821",
            model_client=writes(
                ("remix.md", "# remix\nancestor: swipe/8821\n\nKept: the shape.\n"),
                ("post.md", "ours"),
            ),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (await session.get(Asset, row.asset_seq)).ancestor_ref == "swipe/8821"

    async def test_a_remix_on_a_proposal_files_the_ancestor_as_evidence(
        self, session, studio, proposal
    ):
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="marketer",
            input="remix 8821",
            proposal_seq=proposal.seq,
            model_client=writes(("remix.md", "ancestor: swipe/8821\n")),
        )
        evidence = (await session.execute(select(ProposalEvidence))).scalars().all()
        assert [(row.kind, row.ref) for row in evidence] == [
            ("competitor_ad", "swipe/8821")
        ]

    async def test_an_ask_with_no_words_is_named_after_the_skill(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="chat",
            caller="mcp",
            input="   ",
            model_client=writes(("post.md", "w")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (await session.get(Asset, row.asset_seq)).name == "dw-post chat"

    async def test_a_skill_that_makes_no_kind_of_asset_is_refused(
        self, session, studio
    ):
        (studio / "dw-oddity").mkdir()
        (studio / "dw-oddity" / "SKILL.md").write_text(SKILL)
        with pytest.raises(runner.SkillError, match="no kind of asset"):
            await runner.run(
                session,
                skill="dw-oddity",
                mode="chat",
                caller="mcp",
                input="an idea",
            )

    async def test_a_build_on_a_proposal_that_is_not_there_is_refused(
        self, session, studio
    ):
        with pytest.raises(runner.SkillError, match="proposal"):
            await runner.run(
                session,
                skill="dw-post",
                mode="build",
                caller="studio",
                input="x",
                proposal_seq=404,
            )

    async def test_a_rebuild_of_an_asset_that_is_not_there_is_refused(
        self, session, studio
    ):
        with pytest.raises(runner.SkillError, match="asset"):
            await runner.run(
                session,
                skill="dw-post",
                mode="build",
                caller="studio",
                input="x",
                asset_seq=404,
            )


class TestWhenItGoesWrong:
    async def test_a_model_error_fails_the_run_and_leaves_the_row(
        self, session, studio
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=ScriptedModel(raises=llm.LLMError("APIError: down")),
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.status, row.error) == ("failed", "APIError: down")
        assert row.finished_at is not None

    async def test_a_model_that_declines_fails_the_run(self, session, studio):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=ScriptedModel(Reply(Text("no"), stop_reason="refusal")),
        )
        assert (await session.get(SkillRun, result["skill_run"])).error == (
            "the model declined to run the skill"
        )

    async def test_anything_else_that_breaks_fails_the_run_by_name(
        self, session, studio
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=ScriptedModel(raises=RuntimeError("the socket closed")),
        )
        assert (await session.get(SkillRun, result["skill_run"])).error == (
            "RuntimeError: the socket closed"
        )

    async def test_a_model_that_never_stops_is_cut_off_at_the_turn_cap(
        self, session, studio, monkeypatch
    ):
        monkeypatch.setattr(runner, "MAX_TURNS", 3)
        model = ScriptedModel(
            Reply(ToolUse("brand_list", {}, "c1")),
        )
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=model,
        )
        row = await session.get(SkillRun, result["skill_run"])
        assert row.status == "failed"
        assert "3 turns" in row.error
        assert len(model.sent) == 3

    async def test_the_files_a_failed_run_wrote_are_still_recorded(
        self, session, studio, proposal, monkeypatch
    ):
        monkeypatch.setattr(runner, "MAX_TURNS", 1)
        await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            proposal_seq=proposal.seq,
            model_client=ScriptedModel(
                Reply(ToolUse("files_write", {"path": "post.md", "text": "w"}, "c1"))
            ),
        )
        drafts = (await session.execute(select(ProposalDraft))).scalars().all()
        assert [draft.path for draft in drafts] == ["post.md"]


class TestWhatARunCosts:
    async def test_tokens_and_the_model_are_recorded_and_cost_left_at_zero(
        self, session, studio
    ):
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=ScriptedModel(
                Reply(ToolUse("brand_list", {}, "c1"), usage=Usage(100, 20)),
                Reply(Text("done"), usage=Usage(200, 30)),
            ),
        )
        assert result["tokens"] == {"input": 300, "output": 50}
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.tokens_in, row.tokens_out) == (300, 50)
        assert (row.model, row.cost_usd) == ("claude-test", 0)

    async def test_a_reply_that_reports_no_usage_still_closes_the_run(
        self, session, studio
    ):
        reply = Reply(Text("done"))
        reply.usage, reply.model = None, None
        result = await runner.run(
            session,
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
            model_client=ScriptedModel(reply),
        )
        assert result["tokens"] == {"input": 0, "output": 0}
        row = await session.get(SkillRun, result["skill_run"])
        assert (row.tokens_in, row.tokens_out) == (0, 0)
        assert row.model == settings.SKILL_MODEL


class TestRunningItInTheBackground:
    async def test_the_detached_run_opens_its_own_session(
        self, session, studio, sessionmaker_for_test, monkeypatch
    ):
        monkeypatch.setattr(runner, "async_session", sessionmaker_for_test)
        ask = runner.Ask(
            skill="dw-post",
            mode="draft",
            caller="studio",
            input="an idea",
        )
        seq = await runner.open_run(session, ask)
        await runner.execute_detached(seq, ask, model_client=writes(("post.md", "w")))
        await session.refresh(await session.get(SkillRun, seq))
        assert (await session.get(SkillRun, seq)).status == "ok"


@pytest.fixture
async def proposal(session):
    row = Proposal(
        kind="post",
        title="Why the pipeline stalls",
        skill="dw-post",
        skill_sha="a" * 64,
        status="open",
    )
    session.add(row)
    await session.flush()
    return row


@pytest.fixture
def meeting(session):
    async def _make(name: str, transcript: str):
        canonical_id = uuid.uuid5(uuid.NAMESPACE_URL, f"meeting|{name}")
        session.add(
            EntityCanonical(
                canonical_id=canonical_id,
                entity_type="meeting",
                anchor_key=f"zoom|meeting|{name}",
                minted_seq=1,
                member_count=1,
            )
        )
        for attr, value in (("name", name), ("transcript", transcript)):
            session.add(
                FactCurrent(
                    id=uuid.uuid5(uuid.NAMESPACE_URL, f"{name}|{attr}"),
                    canonical_id=canonical_id,
                    entity_type="meeting",
                    attr=attr,
                    value=value,
                    observed_at=SEEN,
                )
            )
        await session.flush()
        return canonical_id

    return _make
