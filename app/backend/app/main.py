from fastapi import FastAPI

app = FastAPI(title="OS v0")


@app.get("/api/health")
async def health():
    return {"status": "ok"}
