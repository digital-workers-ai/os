import base64
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from app.engine import brand, looks
from app.render.client import RenderError

FONT_TYPE = "font/woff2"
LOGO_TYPE = "image/svg+xml"
PICTURE_TYPE = "image/png"
CARD = "card.html.j2"


def _uri(media_type: str, data: bytes) -> str:
    return f"data:{media_type};base64,{base64.b64encode(data).decode()}"


def _where(look, part) -> str:
    return f"look {look!r}" if part is None else f"look {look!r} {part}"


def fit(look, content, part=None) -> dict:
    limits = looks.limits(look, part)
    where = _where(look, part)
    if not isinstance(content, dict):
        raise RenderError(f"{where}: content must be a mapping of slot to text")
    for name in content:
        if name not in limits:
            raise RenderError(
                f"{where} has no slot named {name!r}; its slots are {list(limits)}"
            )
    slots = {}
    for name, maximum in limits.items():
        text = content.get(name)
        if not isinstance(text, str) or not text.strip():
            raise RenderError(
                f"{where}: slot {name!r} is missing, and every slot gets text"
            )
        if len(text) > maximum:
            raise RenderError(
                f"{where}: slot {name!r} runs {len(text)} characters, past its max "
                f"of {maximum}"
            )
        slots[name] = text
    return slots


def assets_uri() -> dict:
    tokens = brand.tokens()
    return {
        "fonts": {
            name: _uri(FONT_TYPE, brand.asset_bytes(Path(path).name))
            for name, path in tokens["fonts"].items()
        },
        "logo": _uri(LOGO_TYPE, brand.asset_bytes(Path(tokens["logo"]).name)),
    }


def html(look, slots, ratio, picture, part=None, page=None, pages=None) -> str:
    width, height = looks.frame(ratio)
    environment = Environment(
        loader=FileSystemLoader(looks.DEFAULT_LOOKS / look),
        autoescape=True,
        undefined=StrictUndefined,
    )
    context = {
        "slots": slots,
        "width": width,
        "height": height,
        "tokens": brand.tokens(),
        "picture": _uri(PICTURE_TYPE, picture) if picture else "",
        **assets_uri(),
    }
    if page is not None:
        context.update(page=page, pages=pages)
    template = CARD if part is None else f"{part}.html.j2"
    return environment.get_template(template).render(context)


def _frame(look, ratio) -> tuple[int, int]:
    ratios = looks.load(look)["ratios"]
    if ratio not in ratios:
        raise RenderError(
            f"look {look!r} does not render {ratio!r}; it renders {ratios}"
        )
    return looks.frame(ratio)


async def render(look, content, ratio, picture, client) -> bytes:
    slots = fit(look, content)
    width, height = _frame(look, ratio)
    return await client.shot(html(look, slots, ratio, picture), width, height)


async def render_slides(look, content, ratio, client) -> list[bytes]:
    if not isinstance(content, dict):
        raise RenderError(
            f"look {look!r}: content must be a mapping of cover, slides and closing"
        )
    manifest = looks.load(look)
    if manifest["medium"] != "carousel":
        raise RenderError(f"look {look!r} is an image look, not a carousel")
    low, high = manifest["slides"]["min"], manifest["slides"]["max"]
    slides = content.get("slides")
    if not isinstance(slides, list):
        raise RenderError(
            f"look {look!r}: slides must be a list of {low} to {high} slide mappings"
        )
    if not low <= len(slides) <= high:
        raise RenderError(
            f"look {look!r} takes {low} to {high} slides, not {len(slides)}"
        )
    pages = [("cover", fit(look, content.get("cover"), "cover"))]
    pages += [("slide", fit(look, slide, "slide")) for slide in slides]
    pages.append(("closing", fit(look, content.get("closing"), "closing")))
    width, height = _frame(look, ratio)
    shots = []
    for number, (part, slots) in enumerate(pages, 1):
        page = html(look, slots, ratio, None, part, number, len(pages))
        shots.append(await client.shot(page, width, height))
    return shots
