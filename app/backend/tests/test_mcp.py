import json
from contextlib import asynccontextmanager
from types import SimpleNamespace

import httpx
import pytest_asyncio
from fastmcp import Client
from sqlalchemy import select

from app import main, mcp
from app.caches import DEFINITIONS_DIR
from app.coaching import briefer
from app.conversation import agent
from app.engine import brand, looks
from app.models import Asset, AssetFile, McpCall
from app.skills import catalog

AGENT_TOOLS = {
    "get_metrics",
    "get_goals",
    "get_findings",
    "entity_counts",
    "find_entities",
    "get_entity",
    "slice_metric",
}
SKILL_TOOLS = {"dw_post", "dw_newsletter", "dw_blog", "dw_image", "dw_carousel"}
READ_TOOLS = {"assets_list", "assets_read", "brand_read", "looks_read"}
TOOLS = AGENT_TOOLS | SKILL_TOOLS | READ_TOOLS
ASK = {
    "type": "object",
    "properties": {
        "ask": {"type": "string"},
        "look": {"type": "string"},
        "ratio": {"type": "string"},
    },
    "required": ["ask"],
}
DEFINITIONS = (
    "ontology",
    "mappings",
    "transforms",
    "synonyms",
    "metrics",
    "rules",
    "goals",
    "enrichment",
    "derived",
    "spy",
)
URIS = {f"definitions://{name}" for name in DEFINITIONS}
READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}
INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}
MCP_HEADERS = {
    "Accept": "application/json, text/event-stream",
    "MCP-Protocol-Version": "2025-06-18",
}


@pytest_asyncio.fixture
async def client(session, sessionmaker_for_test, monkeypatch):
    monkeypatch.setattr(mcp, "async_session", sessionmaker_for_test)
    async with Client(mcp.server) as client:
        yield client


@asynccontextmanager
async def served():
    async with main.lifespan(main.app):
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://backend"
        ) as api:
            yield api


async def _logged(session) -> list[tuple]:
    rows = (
        (await session.execute(select(McpCall).order_by(McpCall.seq))).scalars().all()
    )
    assert all(row.duration_ms >= 0 and row.created_at for row in rows)
    return [(row.kind, row.name, row.ok, row.arguments, row.error) for row in rows]


class TestTools:
    async def test_the_seven_agent_tools_are_served_read_only(self, client):
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == TOOLS
        served = {tool.name: tool for tool in tools if tool.name in AGENT_TOOLS}
        assert {name: tool.description for name, tool in served.items()} == {
            spec["name"]: spec["description"] for spec in agent.TOOLS
        }
        for tool in served.values():
            wire = tool.annotations.model_dump(by_alias=True, exclude_none=True)
            assert wire == READ_ONLY, tool.name

    async def test_each_tool_answers_what_the_agent_function_answers(
        self, client, session, canonical
    ):
        company = await canonical("company", {"name": "Acme", "domain": "acme.io"})
        await session.commit()
        calls = {
            "get_metrics": {"name": "mrr"},
            "get_goals": {},
            "get_findings": {},
            "entity_counts": {},
            "find_entities": {"entity_type": "company", "name": "Acme"},
            "get_entity": {"canonical_id": str(company)},
            "slice_metric": {"metric": "mrr"},
        }
        for name, arguments in calls.items():
            direct = await agent.HANDLERS[name](session, **arguments)
            expected = json.loads(json.dumps(direct))
            result = await client.call_tool(name, arguments)
            assert set(result.structured_content) == set(expected), name
            assert result.structured_content == expected, name

    async def test_a_failing_tool_is_an_error_result_and_a_failed_row(
        self, client, session, monkeypatch
    ):
        async def broken(session):
            raise RuntimeError("the goals engine is down")

        monkeypatch.setitem(agent.HANDLERS, "get_goals", broken)
        result = await client.call_tool("get_goals", {}, raise_on_error=False)
        assert result.is_error
        assert "the goals engine is down" in result.content[0].text
        [(kind, name, ok, arguments, error)] = await _logged(session)
        assert (kind, name, ok, arguments) == ("tool", "get_goals", False, {})
        assert "the goals engine is down" in error


async def _asset_with_files(session) -> Asset:
    asset = Asset(name="Three numbers", kind="post", skill="dw-post", origin="mcp")
    session.add(asset)
    await session.flush()
    for version, path, media_type, size in (
        (1, "post.md", "text/markdown", 800),
        (2, "post.md", "text/markdown", 640),
        (2, "image.png", "image/png", 348211),
    ):
        session.add(
            AssetFile(
                asset_seq=asset.seq,
                version=version,
                path=path,
                media_type=media_type,
                bytes=size,
            )
        )
    await session.commit()
    return asset


def _file_url(file) -> str:
    return f"/api/assets/{file.asset_seq}/versions/{file.version}/files/{file.path}"


class TestStudioTools:
    async def test_one_tool_per_content_skill_and_four_reads(self, client):
        tools = {tool.name: tool for tool in await client.list_tools()}
        assert {name for name in tools if name.startswith("dw_")} == SKILL_TOOLS
        for name in SKILL_TOOLS:
            skill = catalog.load(name.replace("_", "-", 1))
            assert tools[name].description == skill.description
            assert tools[name].input_schema == ASK
            assert tools[name].annotations is None
        for name in READ_TOOLS:
            wire = tools[name].annotations.model_dump(by_alias=True, exclude_none=True)
            assert wire == READ_ONLY, name
            assert tools[name].description.endswith("."), name

    async def test_a_skill_tool_runs_the_runner_and_returns_the_asset_with_files(
        self, client, session, monkeypatch
    ):
        asset = await _asset_with_files(session)
        asks: list = []
        executed: list = []

        async def open_run(session, ask):
            asks.append(ask)
            return SimpleNamespace(skill_run=7, asset_seq=asset.seq, version=2)

        async def execute(session, seq, ask):
            executed.append(seq)
            return {"status": "held"}

        async def asset_rows(session, assets):
            return [{"seq": a.seq, "name": a.name, "kind": a.kind} for a in assets]

        def file_row(asset_seq, version, file):
            assert (asset_seq, version) == (file.asset_seq, file.version)
            return {"path": file.path, "bytes": file.bytes, "url": _file_url(file)}

        monkeypatch.setattr(mcp.runner, "open_run", open_run)
        monkeypatch.setattr(mcp.runner, "execute", execute)
        monkeypatch.setattr(mcp.rows, "asset_rows", asset_rows)
        monkeypatch.setattr(mcp.rows, "file_row", file_row)

        result = await client.call_tool(
            "dw_post", {"ask": "Three numbers", "look": "stat-card", "ratio": "1:1"}
        )
        assert result.structured_content == {
            "seq": asset.seq,
            "name": "Three numbers",
            "kind": "post",
            "files": [
                {
                    "path": "image.png",
                    "bytes": 348211,
                    "url": f"/api/assets/{asset.seq}/versions/2/files/image.png",
                },
                {
                    "path": "post.md",
                    "bytes": 640,
                    "url": f"/api/assets/{asset.seq}/versions/2/files/post.md",
                },
            ],
            "status": "held",
        }
        [ask] = asks
        assert (ask.skill, ask.caller, ask.input) == ("dw-post", "mcp", "Three numbers")
        assert (ask.look, ask.ratio) == ("stat-card", "1:1")
        assert executed == [7]

        await client.call_tool("dw_carousel", {"ask": "Five slides on churn"})
        assert (asks[-1].skill, asks[-1].look, asks[-1].ratio) == (
            "dw-carousel",
            None,
            None,
        )

    async def test_a_refused_run_is_a_tool_error(self, client, session, monkeypatch):
        executed: list = []

        async def open_run(session, ask):
            raise mcp.runner.SkillError("STUDIO_ENABLED is off")

        async def execute(session, seq, ask):
            executed.append(seq)

        monkeypatch.setattr(mcp.runner, "open_run", open_run)
        monkeypatch.setattr(mcp.runner, "execute", execute)
        result = await client.call_tool(
            "dw_post", {"ask": "Three numbers"}, raise_on_error=False
        )
        assert result.is_error
        assert "STUDIO_ENABLED is off" in result.content[0].text
        assert executed == []
        [(kind, name, ok, arguments, error)] = await _logged(session)
        assert (kind, name, ok, arguments) == (
            "tool",
            "dw_post",
            False,
            {"ask": "Three numbers"},
        )
        assert "STUDIO_ENABLED is off" in error

    async def test_assets_list_answers_the_listing(self, client, monkeypatch):
        asked: list = []

        async def listing(session, **narrowing):
            asked.append(narrowing)
            return {"assets": [{"seq": 1, "name": "Three numbers"}], "total": 1}

        monkeypatch.setattr(mcp.assets, "listing", listing)
        result = await client.call_tool(
            "assets_list", {"kind": "post", "q": "numbers", "limit": 5}
        )
        assert result.structured_content == {
            "assets": [{"seq": 1, "name": "Three numbers"}],
            "total": 1,
        }
        assert asked == [{"kind": "post", "q": "numbers", "limit": 5}]

    async def test_assets_read_answers_the_detail_and_errors_when_missing(
        self, client, monkeypatch
    ):
        async def detail(session, seq):
            if seq == 9:
                raise mcp.Missing("no asset 9")
            return {"seq": seq, "versions": []}

        monkeypatch.setattr(mcp.assets, "detail", detail)
        result = await client.call_tool("assets_read", {"seq": 3})
        assert result.structured_content == {"seq": 3, "versions": []}
        missing = await client.call_tool(
            "assets_read", {"seq": 9}, raise_on_error=False
        )
        assert missing.is_error
        assert "no asset 9" in missing.content[0].text

    async def test_brand_read_answers_the_file_and_errors_on_an_unknown_name(
        self, client
    ):
        front, body = brand.read("voice.md")
        result = await client.call_tool("brand_read", {"name": "voice.md"})
        assert result.structured_content == json.loads(
            json.dumps({"file": "voice.md", "front": front, "body": body}, default=str)
        )
        unknown = await client.call_tool(
            "brand_read", {"name": "nope.md"}, raise_on_error=False
        )
        assert unknown.is_error
        assert "no brand file named 'nope.md'" in unknown.content[0].text

    async def test_looks_read_answers_the_look_and_errors_on_an_unknown_name(
        self, client
    ):
        result = await client.call_tool("looks_read", {"name": "stat-card"})
        assert result.structured_content == json.loads(
            json.dumps(looks.read("stat-card"), default=str)
        )
        unknown = await client.call_tool(
            "looks_read", {"name": "nope"}, raise_on_error=False
        )
        assert unknown.is_error
        assert "no look named 'nope'" in unknown.content[0].text


class TestResources:
    async def test_the_ten_definition_files_are_resources(self, client):
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources} == URIS
        assert {resource.mime_type for resource in resources} == {"application/yaml"}

    async def test_reading_one_returns_the_file_text(self, client):
        [content] = await client.read_resource("definitions://metrics")
        assert content.mime_type == "application/yaml"
        assert content.text == (DEFINITIONS_DIR / "metrics.yaml").read_text()
        assert content.text.startswith("mrr:\n")

    async def test_the_spy_definition_is_a_resource_too(self, client):
        [content] = await client.read_resource("definitions://spy")
        assert content.mime_type == "application/yaml"
        assert content.text == (DEFINITIONS_DIR / "spy.yaml").read_text()
        assert content.text.startswith("brand:\n")


class TestPrompts:
    async def test_every_role_is_a_prompt(self, client):
        names = {prompt.name for prompt in await client.list_prompts()}
        assert {"briefing_ceo", "briefing_head_of_sales"} <= names
        assert names == {f"briefing_{role}" for role in briefer.roles()}

    async def test_getting_one_yields_the_body_as_one_user_message(self, client):
        rendered = await client.get_prompt("briefing_ceo")
        [message] = rendered.messages
        text = message.content.text
        assert message.role == "user"
        assert text.startswith(
            "You are writing a short daily briefing for the chief executive"
        )
        assert "---" not in text
        assert text == briefer.prompt_body("ceo")


class TestCallLog:
    async def test_every_call_leaves_a_row(self, client, session):
        arguments = {"entity_type": "company", "limit": 3}
        await client.call_tool("find_entities", arguments)
        await client.read_resource("definitions://goals")
        await client.get_prompt("briefing_head_of_sales")
        assert await _logged(session) == [
            ("tool", "find_entities", True, arguments, None),
            ("resource", "definitions://goals", True, {}, None),
            ("prompt", "briefing_head_of_sales", True, {}, None),
        ]


class TestHttp:
    async def test_the_api_describes_the_server(self):
        assert main.app.title == "OS"
        async with served() as api:
            body = (await api.get("/api/mcp")).json()
        assert body["path"] == "/mcp"
        assert {tool["name"] for tool in body["tools"]} == TOOLS
        assert {resource["uri"] for resource in body["resources"]} == URIS
        assert {prompt["name"] for prompt in body["prompts"]} == {
            "briefing_ceo",
            "briefing_head_of_sales",
        }
        assert all(tool["description"] for tool in body["tools"])
        assert all(r["name"] and r["description"] for r in body["resources"])
        assert all(prompt["description"] for prompt in body["prompts"])
        assert (len(body["tools"]), len(body["resources"]), len(body["prompts"])) == (
            16,
            10,
            2,
        )

    async def test_the_endpoint_answers_inside_the_app(self):
        async with served() as api:
            response = await api.post("/mcp", json=INITIALIZE, headers=MCP_HEADERS)
        assert response.status_code == 200
        [data] = [
            line.removeprefix("data: ")
            for line in response.text.splitlines()
            if line.startswith("data: ")
        ]
        assert json.loads(data)["result"]["serverInfo"]["name"] == "os"
