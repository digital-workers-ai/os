from fastapi import HTTPException

from app.api.routers import brand as router
from app.engine import brand

SUFFIX = ".md"
NOT_FOUND = {404: {"description": "no such brand file"}}


@router.get("/brand")
async def get_brand():
    return {
        "files": [name.removesuffix(SUFFIX) for name in brand.files()],
        "tokens": brand.tokens(),
        "assets": brand.assets(),
    }


@router.get("/brand/{name}", responses=NOT_FOUND)
async def get_brand_file(name: str):
    file = f"{name}{SUFFIX}"
    try:
        front, body = brand.read(file)
    except brand.BrandError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"file": file, "front": front, "body": body}
