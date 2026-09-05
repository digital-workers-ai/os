from app.api.routers import mcp as router
from app.mcp import PATH, server


@router.get("")
async def describe():
    return {
        "path": PATH,
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
