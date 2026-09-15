from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from seeds.helpers import require_bearer
from seeds.world import (
    ANSWER_ENGINES,
    COMPETITORS,
    OUR_BRAND,
    TRACKED_PROMPTS,
)

router = APIRouter()

_CHECKED_AT = "2026-09-14T05:45:00Z"
_US = "us"

_NAMED = {
    ("best ai ugc ad tool", "chatgpt"): ("k1", "k3", "k2"),
    ("best ai ugc ad tool", "perplexity"): ("k1", "k2"),
    ("best ai ugc ad tool", "gemini"): ("k3", "k1"),
    ("best ai ugc ad tool", "aio"): ("k1",),
    ("ugc ads without creators", "chatgpt"): ("k1", "k3", _US),
    ("ugc ads without creators", "perplexity"): ("k2", _US),
    ("ugc ads without creators", "gemini"): ("k1", "k2"),
    ("ugc ads without creators", "aio"): ("k3",),
    ("how do i make video ads with ai", "chatgpt"): ("k1", "k2"),
    ("how do i make video ads with ai", "perplexity"): ("k1",),
    ("how do i make video ads with ai", "gemini"): ("k1",),
    ("how do i make video ads with ai", "aio"): (),
}

_CITED_PATH = {
    ("best ai ugc ad tool", "k1"): "/",
    ("best ai ugc ad tool", "k2"): "/pricing",
    ("best ai ugc ad tool", "k3"): "/",
    ("best ai ugc ad tool", _US): "/ugc",
    ("ugc ads without creators", "k1"): "/blog/what-a-creator-brief-costs",
    ("ugc ads without creators", "k2"): "/",
    ("ugc ads without creators", "k3"): "/how-it-works",
    ("ugc ads without creators", _US): "/ugc",
    ("how do i make video ads with ai", "k1"): "/how-it-works",
    ("how do i make video ads with ai", "k2"): "/how-it-works",
    ("how do i make video ads with ai", "k3"): "/how-it-works",
    ("how do i make video ads with ai", _US): "/ai-ads-without-a-studio",
}

_BRANDS = [(_US, OUR_BRAND.name, OUR_BRAND.domain)] + [
    (k.id, k.name, k.domain) for k in COMPETITORS
]


def _error(status, code, message):
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _mention(prompt, named, key, name, domain):
    if key not in named:
        return {"brand": name, "domain": domain, "mentioned": "no", "cited_url": "", "rank": 0}
    return {
        "brand": name,
        "domain": domain,
        "mentioned": "yes",
        "cited_url": f"https://{domain}{_CITED_PATH[(prompt, key)]}",
        "rank": named.index(key) + 1,
    }


@router.get("/v1/mentions")
async def mentions(request: Request, prompt: str = Query(...), engine: str = Query(...)):
    require_bearer(request)
    if prompt not in TRACKED_PROMPTS:
        return _error(404, "prompt_not_tracked", f"Prompt '{prompt}' is not in the tracked set.")
    if engine not in ANSWER_ENGINES:
        return _error(
            404,
            "engine_not_supported",
            f"Engine '{engine}' is not one of {', '.join(ANSWER_ENGINES)}.",
        )
    named = _NAMED[(prompt, engine)]
    return {
        "prompt": prompt,
        "engine": engine,
        "checked_at": _CHECKED_AT,
        "mentions": [_mention(prompt, named, *brand) for brand in _BRANDS],
        "next": None,
    }
