from fastapi import HTTPException

from app.api.routers import looks as router
from app.engine import looks

ROW_KEYS = ("name", "medium", "ratios", "slots")
NOT_FOUND = {404: {"description": "no such look"}}


def _row(manifest) -> dict:
    row = {key: manifest[key] for key in ROW_KEYS}
    if manifest["medium"] == "carousel":
        row["slides"] = manifest["slides"]
    return row


@router.get("/looks")
async def list_looks():
    return {"looks": [_row(looks.load(name)) for name in looks.names()]}


@router.get("/looks/{name}", responses=NOT_FOUND)
async def get_look(name: str):
    try:
        manifest = looks.read(name)
    except looks.LookError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        **_row(manifest),
        "sample": manifest["sample"],
        "layouts": manifest["layouts"],
    }
