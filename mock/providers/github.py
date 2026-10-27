import itertools

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

TOKEN = "Bearer mock_github_token"
NUMBERS = itertools.count(1)


@router.post("/repos/{owner}/{repo}/issues", status_code=201)
async def create_issue(owner: str, repo: str, request: Request):
    if request.headers.get("authorization") != TOKEN:
        return JSONResponse(
            status_code=401,
            content={
                "message": "Bad credentials",
                "documentation_url": "https://docs.github.com/rest",
                "status": "401",
            },
        )
    issue = await request.json()
    number = next(NUMBERS)
    return {
        "number": number,
        "html_url": f"https://github.com/{owner}/{repo}/issues/{number}",
        "labels": [{"name": label} for label in issue.get("labels", [])],
    }
