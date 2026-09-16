import hashlib
import re
from datetime import datetime, time, timezone
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from seeds import world

router = APIRouter()

_MODELS = {
    "openai/gpt-5.6-luna": ("chatgpt", "OpenAI", "completed", "default"),
    "perplexity/sonar": ("perplexity", "Perplexity", "stop", None),
    "google/gemini-3.5-flash-lite": ("gemini", "Google", "STOP", "default"),
}

_RATES = {
    "chatgpt": (0.20, 1.20, 0.01),
    "perplexity": (1.00, 1.00, 0.005),
    "gemini": (0.30, 2.50, 0.014),
}

_REDIRECT = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/"


def _error(status, message, **extra):
    return JSONResponse(
        status_code=status,
        content={"error": {"message": message, "code": status}, **extra},
    )


def _companies():
    return [world.SPY_BRAND, *world.SPY_COMPETITORS]


def _company_for(url):
    host = urlparse(url).netloc.removeprefix("www.")
    return next(
        (
            c
            for c in _companies()
            if host == c["domain"] or host.endswith("." + c["domain"])
        ),
        None,
    )


def _sentence(text, start, end):
    left = max(text.rfind(". ", 0, start), text.rfind("\n", 0, start))
    left = 0 if left < 0 else left + (2 if text[left] == "." else 1)
    stops = [i for i in (text.find(". ", end), text.find("\n", end)) if i >= 0]
    right = min(stops) if stops else len(text)
    if right < len(text) and text[right] == ".":
        right += 1
    return left, right


def _span(text, source):
    company = _company_for(source["url"])
    names = (
        [company["name"], *company["aliases"]]
        if company
        else [c["name"] for c in _companies()]
    )
    for name in names:
        hit = re.search(rf"\b{re.escape(name)}\b", text)
        if hit:
            return _sentence(text, hit.start(), hit.end())
    return 0, 0


def _citation(engine, text, source):
    start, end = _span(text, source)
    url, title = source["url"], source["title"]
    if engine == "chatgpt":
        url = url + ("&" if "?" in url else "?") + "utm_source=openai"
    if engine == "gemini":
        title = urlparse(source["url"]).netloc.removeprefix("www.")
        url = _REDIRECT + hashlib.sha256(source["url"].encode()).hexdigest()
    return {
        "type": "url_citation",
        "url_citation": {
            "url": url,
            "title": title,
            "start_index": start,
            "end_index": end,
        },
    }


def _usage(engine, prompt, completion, searches):
    rate_in, rate_out, fee = _RATES[engine]
    cost = prompt * rate_in / 1e6 + completion * rate_out / 1e6 + fee * searches
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": prompt + completion,
        "cost": round(cost, 8),
        "is_byok": False,
    }


def _completion(model, engine, seed, content, annotations, prompt_tokens, searches):
    _, provider, native_finish, service_tier = _MODELS[model]
    created = int(
        datetime.combine(world.SPY_ANCHOR, time(12), tzinfo=timezone.utc).timestamp()
    )
    message = {
        "role": "assistant",
        "content": content,
        "refusal": None,
        "reasoning": None,
    }
    if annotations is not None:
        message["annotations"] = annotations
    return {
        "id": f"gen-{created}-{hashlib.md5(seed.encode()).hexdigest()[:20]}",
        "object": "chat.completion",
        "created": created,
        "model": model,
        "provider": provider,
        "system_fingerprint": None,
        "service_tier": service_tier,
        "choices": [
            {
                "index": 0,
                "logprobs": None,
                "finish_reason": "stop",
                "native_finish_reason": native_finish,
                "message": message,
            }
        ],
        "usage": _usage(engine, prompt_tokens, len(content) // 4 + 1, searches),
    }


def _creative_id(image):
    for company in world.SPY_COMPETITORS:
        for ad in world.spy_ads(company["google_advertiser_id"]):
            if ad.get("image") == image:
                return ad["ad_creative_id"]
    return urlparse(image).path.rstrip("/").rsplit("/", 1)[-1]


def _user_parts(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return (
                content
                if isinstance(content, list)
                else [{"type": "text", "text": content or ""}]
            )
    return []


@router.post("/api/v1/chat/completions")
async def chat_completions(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer ") or len(auth) <= 7:
        return _error(401, "No cookie auth credentials found")
    body = await request.json()
    requested = body.get("model") or ""
    model = requested.split(":")[0]
    if model not in _MODELS:
        return _error(400, f"{requested} is not a valid model ID", user_id="user_mock")
    engine = _MODELS[model][0]
    parts = _user_parts(body.get("messages") or [])
    image = next(
        (p["image_url"]["url"] for p in parts if p.get("type") == "image_url"), None
    )
    if image:
        text = world.spy_ad_text(_creative_id(image))
        return _completion(model, engine, f"{model}|{image}", text, None, 425, 0)
    query = " ".join(
        p.get("text", "") for p in parts if p.get("type") == "text"
    ).strip()
    answer = world.spy_answer(engine, query)
    text = answer["text"]
    annotations = [_citation(engine, text, source) for source in answer["sources"]]
    return _completion(
        model, engine, f"{model}|{query}", text, annotations, 6 + len(query) // 4, 1
    )
