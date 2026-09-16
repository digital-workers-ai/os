import base64
import hashlib
import re
from datetime import timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from seeds import world

router = APIRouter()

_MODELS = {
    "claude-haiku-4-5": "claude-haiku-4-5-20251001",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
}
_PREAMBLE = "I'll search for current information to answer this."
_CITED_TEXT_LIMIT = 150


def _digest(*parts):
    return hashlib.sha256("|".join(parts).encode()).digest()


def _token(*parts, length=24):
    return _digest(*parts).hex()[:length]


def _blob(*parts, repeat=1):
    return base64.b64encode(_digest(*parts) * repeat).decode()


def _error(status, kind, message):
    return JSONResponse(
        status_code=status,
        content={
            "type": "error",
            "error": {"type": kind, "message": message},
            "request_id": "req_01" + _token(kind, message, length=22),
        },
    )


def _query(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            if isinstance(content, list):
                return " ".join(
                    p.get("text", "") for p in content if p.get("type") == "text"
                ).strip()
            return (content or "").strip()
    return ""


def _company_for(url):
    host = urlparse(url).netloc.removeprefix("www.")
    return next(
        (
            c
            for c in world.SPY_COMPANIES
            if host == c["domain"] or host.endswith("." + c["domain"])
        ),
        None,
    )


def _names(source):
    company = _company_for(source["url"])
    return [company["name"], *company["aliases"]] if company else []


def _result(seed, source):
    day = world.SPY_ANCHOR - timedelta(days=_digest(seed, source["url"])[0] % 90)
    return {
        "type": "web_search_result",
        "title": source["title"],
        "url": source["url"],
        "encrypted_content": _blob(seed, source["url"], repeat=32),
        "page_age": f"{day:%B} {day.day}, {day.year}",
    }


def _quote(sentence, source):
    text = f"{source['title']}\n\n{sentence}"
    return text if len(text) <= _CITED_TEXT_LIMIT else text[:_CITED_TEXT_LIMIT] + "..."


def _citation(seed, sentence, source):
    return {
        "type": "web_search_result_location",
        "cited_text": _quote(sentence, source),
        "url": source["url"],
        "title": source["title"],
        "encrypted_index": _blob(seed, sentence, source["url"], repeat=5),
    }


def _cited(sentence, sources):
    return [
        s
        for s in sources
        if any(re.search(rf"\b{re.escape(n)}\b", sentence) for n in _names(s))
    ]


def _answer_blocks(seed, text, sources):
    blocks, plain = [], ""
    for piece in re.split(r"((?<=[.!?])\s+)", text):
        cited = _cited(piece, sources)
        if not cited:
            plain += piece
            continue
        if plain:
            blocks.append({"type": "text", "text": plain})
            plain = ""
        blocks.append(
            {
                "citations": [_citation(seed, piece, s) for s in cited],
                "type": "text",
                "text": piece,
            }
        )
    if plain:
        blocks.append({"type": "text", "text": plain})
    return blocks


def _usage(seed, text):
    return {
        "input_tokens": 3000 + _digest(seed, "input")[0] * 8,
        "cache_creation_input_tokens": 0,
        "cache_read_input_tokens": 0,
        "cache_creation": {
            "ephemeral_5m_input_tokens": 0,
            "ephemeral_1h_input_tokens": 0,
        },
        "output_tokens": len(text) // 4 + 40,
        "service_tier": "standard",
        "inference_geo": "not_available",
        "server_tool_use": {"web_search_requests": 1, "web_fetch_requests": 0},
    }


@router.post("/v1/messages")
async def create_message(request: Request):
    if not request.headers.get("x-api-key"):
        return _error(401, "authentication_error", "x-api-key header is required")
    if not request.headers.get("anthropic-version"):
        return _error(
            400, "invalid_request_error", "anthropic-version: header is required"
        )
    body = await request.json()
    requested = body.get("model") or ""
    if requested not in _MODELS:
        return _error(404, "not_found_error", f"model: {requested}")
    model = _MODELS[requested]
    query = _query(body.get("messages") or [])
    answer = world.spy_answer("claude", query)
    seed = f"{model}|{query}"
    tool_id = "srvtoolu_01" + _token(seed, "tool")
    content = [
        {"type": "text", "text": _PREAMBLE},
        {
            "type": "server_tool_use",
            "id": tool_id,
            "name": "web_search",
            "input": {"query": f"{query} {world.SPY_ANCHOR.year}"},
        },
        {
            "type": "web_search_tool_result",
            "tool_use_id": tool_id,
            "content": [_result(seed, source) for source in answer["sources"]],
            "caller": {"type": "direct"},
        },
        *_answer_blocks(seed, answer["text"], answer["sources"]),
    ]
    return {
        "model": model,
        "id": "msg_01" + _token(seed, "message"),
        "type": "message",
        "role": "assistant",
        "content": content,
        "container": None,
        "stop_reason": "end_turn",
        "stop_sequence": None,
        "stop_details": None,
        "usage": _usage(seed, answer["text"]),
    }
