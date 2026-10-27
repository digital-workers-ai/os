import httpx

from app.config import settings
from app.sources import client, creds

TIMEOUT = 30.0


class TranscribeError(RuntimeError):
    pass


def _field_terms(fields):
    for field in fields:
        yield field.name
        yield from (label for label, _ in field.labels)
        yield from _field_terms(field.fields)


def _template_terms(template):
    if template is None:
        return []
    if template.kind == "grid":
        return [
            template.rows["name"],
            *_field_terms(template.rows["fields"]),
            template.columns["name"],
            *_field_terms(template.cells["fields"]),
        ]
    sections = [
        term
        for section, items in template.sections.items()
        for term in (section, *items)
    ]
    return [*sections, *_field_terms(template.items["fields"])]


def keyterms(app) -> list[str]:
    terms = [*_field_terms(app.fields), *_template_terms(app.template)]
    return list(dict.fromkeys(term.replace("_", " ") for term in terms))


async def transcribe(app, audio: bytes, media_type: str) -> str:
    if not settings.TRANSCRIBE_ENABLED:
        raise TranscribeError("transcribing is off: set TRANSCRIBE_ENABLED")
    deepgram = creds.credentials_for("deepgram")
    params = [
        ("model", settings.TRANSCRIBE_MODEL),
        ("language", "en"),
        ("smart_format", "true"),
        *(("keyterm", term) for term in keyterms(app)),
    ]
    try:
        async with httpx.AsyncClient(
            timeout=TIMEOUT, transport=client._transport
        ) as http:
            response = await http.post(
                f"{deepgram.base_url}/v1/listen",
                params=params,
                content=audio,
                headers={**deepgram.headers, "Content-Type": media_type},
            )
    except httpx.HTTPError as exc:
        raise TranscribeError(f"Deepgram unreachable: {type(exc).__name__}") from exc
    if response.status_code >= 400:
        raise TranscribeError(f"Deepgram answered {response.status_code}")
    try:
        channel = response.json()["results"]["channels"][0]
        return channel["alternatives"][0]["transcript"]
    except (LookupError, TypeError, ValueError) as exc:
        raise TranscribeError("Deepgram answered with no transcript") from exc
