import json
from contextlib import asynccontextmanager

import httpx
import pytest_asyncio
from fastmcp import Client
from sqlalchemy import select

from app import main, mcp
from app.caches import DEFINITIONS_DIR
from app.coaching import briefer
from app.conversation import agent
from app.models import McpCall

TOOLS = {
    "get_metrics",
    "get_goals",
    "get_findings",
    "entity_counts",
    "find_entities",
    "get_entity",
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
    async def test_the_six_agent_tools_are_served_read_only(self, client):
        tools = await client.list_tools()
        assert {tool.name for tool in tools} == TOOLS
        assert {tool.name: tool.description for tool in tools} == {
            spec["name"]: spec["description"] for spec in agent.TOOLS
        }
        for tool in tools:
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


class TestResources:
    async def test_the_eight_definition_files_are_resources(self, client):
        resources = await client.list_resources()
        assert {str(resource.uri) for resource in resources} == URIS
        assert {resource.mime_type for resource in resources} == {"application/yaml"}

    async def test_reading_one_returns_the_file_text(self, client):
        [content] = await client.read_resource("definitions://metrics")
        assert content.mime_type == "application/yaml"
        assert content.text == (DEFINITIONS_DIR / "metrics.yaml").read_text()
        assert content.text.startswith("mrr:\n")


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
            6,
            8,
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
