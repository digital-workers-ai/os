import time

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.middleware import Middleware
from fastmcp.tools import Tool, ToolResult
from mcp.types import ToolAnnotations
from sqlalchemy import select

from app.caches import DEFINITIONS_DIR
from app.coaching import briefer
from app.conversation import agent
from app.db import async_session
from app.engine import brand, looks
from app.models import Asset, AssetFile, McpCall
from app.skills import catalog, runner
from app.studio import Missing, assets, rows

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
    "derived": "the cross-entity facts the rebuild computes, as declared rollups",
    "spy": "the brand, the competitors and the queries Spy tracks",
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


ASK = {
    "type": "object",
    "properties": {
        "ask": {"type": "string"},
        "look": {"type": "string"},
        "ratio": {"type": "string"},
    },
    "required": ["ask"],
}


class StudioTool(Tool):
    async def run(self, arguments: dict) -> ToolResult:
        ask = runner.Ask(
            self.name.replace("_", "-"),
            caller="mcp",
            input=arguments["ask"],
            look=arguments.get("look"),
            ratio=arguments.get("ratio"),
        )
        async with async_session() as session:
            try:
                started = await runner.open_run(session, ask)
            except runner.SkillError as exc:
                raise ToolError(str(exc)) from exc
            result = await runner.execute(session, started.skill_run, ask)
            [row] = await rows.asset_rows(
                session, [await session.get(Asset, started.asset_seq)]
            )
            files = await session.scalars(
                select(AssetFile)
                .where(
                    AssetFile.asset_seq == started.asset_seq,
                    AssetFile.version == started.version,
                )
                .order_by(AssetFile.path)
            )
            payload = {
                **row,
                "files": [
                    rows.file_row(started.asset_seq, started.version, file)
                    for file in files
                ],
                "status": result["status"],
            }
        return ToolResult(structured_content=payload)


async def _assets_list(session, **narrowing) -> dict:
    return await assets.listing(session, **narrowing)


async def _assets_read(session, seq) -> dict:
    try:
        return await assets.detail(session, seq)
    except Missing as exc:
        raise ToolError(str(exc)) from exc


async def _brand_read(session, name) -> dict:
    try:
        front, body = brand.read(name)
    except brand.BrandError as exc:
        raise ToolError(str(exc)) from exc
    return {"file": name, "front": front, "body": body}


async def _looks_read(session, name) -> dict:
    try:
        return looks.read(name)
    except looks.LookError as exc:
        raise ToolError(str(exc)) from exc


def _properties(**types) -> dict:
    return {name: {"type": kind} for name, kind in types.items()}


READS = {
    "assets_list": (
        _assets_list,
        "The assets Studio has made, newest first, narrowed by kind, look, origin "
        "or a word of the name.",
        {
            "type": "object",
            "properties": _properties(
                kind="string",
                look="string",
                origin="string",
                q="string",
                limit="integer",
            ),
        },
    ),
    "assets_read": (
        _assets_read,
        "One asset with every version, its files, its claims, its evidence and "
        "its feedback.",
        {
            "type": "object",
            "properties": _properties(seq="integer"),
            "required": ["seq"],
        },
    ),
    "brand_read": (
        _brand_read,
        "One brand file by name, as its front matter and its body.",
        {
            "type": "object",
            "properties": _properties(name="string"),
            "required": ["name"],
        },
    ),
    "looks_read": (
        _looks_read,
        "One look by name: its manifest, its sample content and its layouts.",
        {
            "type": "object",
            "properties": _properties(name="string"),
            "required": ["name"],
        },
    ),
}


class StudioReadTool(Tool):
    async def run(self, arguments: dict) -> ToolResult:
        handler = READS[self.name][0]
        async with async_session() as session:
            payload = await handler(session, **arguments)
        return ToolResult(structured_content=payload)


for skill in catalog.names():
    server.add_tool(
        StudioTool(
            name=skill.replace("-", "_"),
            description=catalog.load(skill).description,
            parameters=ASK,
        )
    )

for name, (_handler, description, parameters) in READS.items():
    server.add_tool(
        StudioReadTool(
            name=name,
            description=description,
            parameters=parameters,
            annotations=READ_ONLY,
        )
    )

http_app = server.http_app(path=PATH)
