from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from app.engine import looks
from app.render.browser import screenshot
from app.render.clients import Browser, Painter, RenderError

HTML = "card.html"

PNG = "card.png"

BACKGROUND = "background.png"

PROMPT_SLOT = "background_prompt"

DRAFT_SCALE = 0.5

STAGES = ("fit", "ground", "compose", "shoot")


def fit(look: str, content: dict, looks_dir=None) -> dict:
    allowed = looks.limits(look, looks_dir)
    unknown = sorted(set(content) - set(allowed) - {PROMPT_SLOT})
    if unknown:
        raise RenderError(
            f"look {look!r} draws no {', '.join(unknown)} — copy written into a "
            "slot the card has no room for would never appear"
        )
    slots = {}
    for slot, ceiling in allowed.items():
        written = content.get(slot)
        if not isinstance(written, str):
            raise RenderError(f"look {look!r} needs a {slot!r} and none was written")
        if len(written) > ceiling:
            raise RenderError(
                f"look {look!r}: {slot!r} holds {ceiling} characters and this is "
                f"{len(written)} — {written!r}"
            )
        slots[slot] = written
    return slots


async def render(
    look: str,
    content: dict,
    out_dir,
    *,
    draft: bool,
    looks_dir=None,
    browser=None,
    painter=None,
    progress=None,
) -> Path:
    def report(stage):
        if progress:
            progress(stage)

    report(STAGES[0])
    slots = fit(look, content, looks_dir)
    width, height = looks.frame(look, looks_dir)
    if draft:
        width, height = int(width * DRAFT_SCALE), int(height * DRAFT_SCALE)

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    report(STAGES[1])
    ground = None
    wanted = content.get(PROMPT_SLOT)
    if wanted and not draft:
        painter = painter or Painter()
        (out_dir / BACKGROUND).write_bytes(
            await painter.background(wanted, width=width, height=height)
        )
        ground = BACKGROUND

    report(STAGES[2])
    environment = Environment(
        loader=FileSystemLoader(looks.directory(look, looks_dir)),
        keep_trailing_newline=True,
        autoescape=True,
    )
    page = out_dir / HTML
    page.write_text(
        environment.get_template(looks.IMAGE_TEMPLATE).render(
            slots=slots, width=width, height=height, background=ground, draft=draft
        )
    )

    report(STAGES[3])
    return screenshot(
        page, out_dir / PNG, width=width, height=height, client=browser or Browser()
    )
