from fastapi import Depends

from app.api.routers import metrics as router
from app.db import get_session
from app.engine import mappings, metrics


@router.get("")
async def get_metrics(session=Depends(get_session)):
    values = await metrics.evaluate(session)
    lineage = metrics.provenance(metrics.load_definitions(), mappings.load())
    for name, row in values.items():
        row.update(lineage.get(name, {}))
    return {"metrics": values}
