import time

from fastmcp import FastMCP
from fastmcp.server.middleware import Middleware
from fastmcp.tools import Tool, ToolResult
from mcp.types import ToolAnnotations

from app.caches import DEFINITIONS_DIR
from app.coaching import briefer
from app.conversation import agent
from app.db import async_session
from app.models import McpCall

PATH = "/mcp"

READ_ONLY = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)

DEFINITIONS = {
    "ontology": "what entities exist and what typed attributes each may have",
    "mappings": "one line per raw field worth keeping: source.object.path → attribute",
    "transforms": "which normalizer each attribute's values pass through",
    "synonyms": "which provider spellings fold to one canonical status",
    "metrics": "the numbers the estate answers with, as declared aggregates",
    "rules": "the conditions worth a human's attention, as declared predicates",
    "goals": "the targets the business holds itself to, judged by strategies",
    "enrichment": "the questions a model may ask of declared texts, as readings",
}


class AgentTool(Tool):
    async def run(self, arguments: dict) -> ToolResult:
        async with async_session() as session:
            payload = await agent.HANDLERS[self.name](session, **arguments)
        return ToolResult(structured_content=payload)


class CallLog(Middleware):
    async def on_call_tool(self, context, call_next):
        request = context.message
        return await self._record(
            "tool", request.name, request.arguments or {}, context, call_next
        )

    async def on_read_resource(self, context, call_next):
        return await self._record(
            "resource", context.message.uri, {}, context, call_next
        )

    async def on_get_prompt(self, context, call_next):
        request = context.message
        return await self._record(
            "prompt", request.name, request.arguments or {}, context, call_next
        )

    async def _record(self, kind, name, arguments, context, call_next):
        started = time.monotonic()
        row = McpCall(kind=kind, name=name, arguments=arguments, ok=False)
        try:
            result = await call_next(context)
            row.ok = True
            return result
        except Exception as exc:
            row.error = str(exc)
            raise
        finally:
            row.duration_ms = int((time.monotonic() - started) * 1000)
            async with async_session() as session:
                session.add(row)
                await session.commit()


server = FastMCP("os", middleware=[CallLog()])

for spec in agent.TOOLS:
    server.add_tool(
        AgentTool(
            name=spec["name"],
            description=spec["description"],
            parameters=spec["input_schema"],
            annotations=READ_ONLY,
        )
    )


def _definition(name: str):
    def read() -> str:
        return (DEFINITIONS_DIR / f"{name}.yaml").read_text()

    return read


for name, description in DEFINITIONS.items():
    server.resource(
        f"definitions://{name}",
        name=name,
        description=description,
        mime_type="application/yaml",
    )(_definition(name))


def _briefing(role: str):
    def brief() -> str:
        return briefer.prompt_body(role)

    return brief


for role in briefer.roles():
    server.prompt(
        _briefing(role),
        name=f"briefing_{role}",
        description=f"The {role} briefing prompt, as the coaching layer sends it",
    )

http_app = server.http_app(path=PATH)
