import hashlib

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()

KEY = "Token mock_deepgram_key"
TRANSCRIPTS = {
    "417299b92923b8cbedaa185a7d5df8975c416d6324350c966a90d79825ab160b": (
        "walk-in cooler, 37"
    ),
    "6b16a75d37f896abac35da8796d20d26e2ad8e5393df515d06cfa3161c2a22d7": (
        "three, three two four, bleeding on the two"
    ),
}
SECONDS_PER_WORD = 0.4


def _words(transcript):
    return [
        {
            "word": spoken.strip(",.").lower(),
            "start": round(index * SECONDS_PER_WORD, 2),
            "end": round((index + 1) * SECONDS_PER_WORD, 2),
            "confidence": 0.98,
            "punctuated_word": spoken,
        }
        for index, spoken in enumerate(transcript.split())
    ]


@router.post("/v1/listen")
async def listen(request: Request):
    if request.headers.get("authorization") != KEY:
        return JSONResponse(
            status_code=401,
            content={"err_code": "INVALID_AUTH", "err_msg": "Invalid credentials."},
        )
    audio = await request.body()
    transcript = TRANSCRIPTS.get(hashlib.sha256(audio).hexdigest(), "")
    alternative = {
        "transcript": transcript,
        "confidence": 0.98 if transcript else 0.0,
        "words": _words(transcript),
    }
    return {"results": {"channels": [{"alternatives": [alternative]}]}}
