from fastapi import Depends
from sqlalchemy import func, select

from app.api.routers import mcp as router
from app.config import settings
from app.db import get_session
from app.mcp import PATH, server
from app.models import McpCall


@router.get("")
async def describe():
    return {
        "url": f"{settings.PUBLIC_URL}{PATH}",
        "auth": "google" if settings.AUTH_ENABLED else "open",
        "tools": [
            {"name": tool.name, "description": tool.description}
            for tool in await server.list_tools()
        ],
        "resources": [
            {
                "uri": str(resource.uri),
                "name": resource.name,
                "description": resource.description,
            }
            for resource in await server.list_resources()
        ],
        "prompts": [
            {"name": prompt.name, "description": prompt.description}
            for prompt in await server.list_prompts()
        ],
    }


@router.get("/calls")
async def callers(session=Depends(get_session)):
    last_at = func.max(McpCall.created_at)
    query = (
        select(
            McpCall.subject,
            McpCall.name,
            func.count().label("calls"),
            func.count().filter(McpCall.ok.is_(False)).label("failed"),
            last_at.label("last_at"),
        )
        .group_by(McpCall.subject, McpCall.name)
        .order_by(last_at.desc())
    )
    return [
        {
            "subject": row.subject,
            "name": row.name,
            "calls": row.calls,
            "failed": row.failed,
            "last_at": row.last_at.isoformat(),
        }
        for row in await session.execute(query)
    ]
