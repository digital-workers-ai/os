from app.config import settings
from app.sources import util
from app.sources.client import ConnectorError

SOURCE = "github"


class GitHubError(RuntimeError):
    pass


async def file_issue(title, body, labels=("app",)) -> dict:
    api = util.client_for(SOURCE)
    try:
        issue = await api.post(
            f"/repos/{settings.GITHUB_REPOSITORY}/issues",
            json={"title": title, "body": body, "labels": list(labels)},
        )
    except ConnectorError as exc:
        raise GitHubError(str(exc)) from exc
    return {"number": issue["number"], "url": issue["html_url"]}
