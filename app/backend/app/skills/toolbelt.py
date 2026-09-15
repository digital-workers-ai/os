import inspect
import time
from dataclasses import dataclass, field

from sqlalchemy import func, select

from app import media
from app.engine import brand, calendar
from app.models import Asset, AssetFile, FactCurrent, SkillRunToolCall

DRAFT = "draft"

MEETING = "meeting"

TRANSCRIPT = "transcript"

NAME = "name"

MAX_DETAIL_CHARS = 200

MAX_LISTED = 20

FENCE_OPEN, FENCE_CLOSE = "<studio_data>", "</studio_data>"

NO_BACKGROUND_ON_A_DRAFT = (
    "image.render generates a background only on a build — a draft renders "
    "flat, which costs nothing. Say in build.md what the background would "
    "cost, and render this variant without one."
)


class ToolRefused(RuntimeError):
    pass


@dataclass
class Bench:
    session: object
    run_seq: int
    mode: str
    kind: str
    seq: int
    version: int = 1
    written: list = field(default_factory=list)
    renders: dict = field(default_factory=dict)
    read: list = field(default_factory=list)
    stage: str | None = None


async def _settled(value):
    return await value if inspect.isawaitable(value) else value


def _noted(bench: Bench, kind: str, ref: str, detail: str) -> None:
    if not any(row["ref"] == ref for row in bench.read):
        bench.read.append({"kind": kind, "ref": ref, "detail": detail})


async def brand_read(bench: Bench, name: str = "") -> dict:
    known = brand.files()
    if name not in known:
        raise ToolRefused(f"no brand file named {name!r} — the files are {known}")
    front, body = brand.read(name)
    _noted(bench, "brand", f"{name}.md", "read for voice, proof, pillars or language")
    return {"file": f"{name}.md", "front": front, "body": body}


async def brand_list(bench: Bench) -> dict:
    return {"files": brand.files()}


async def swipe_read(bench: Bench, id: str = "") -> dict:
    from app.studio import swipe

    item = await _settled(swipe.read(bench.session, str(id)))
    _noted(bench, "competitor_ad", f"swipe/{id}", "the competitor item it answers")
    return {"item": item}


async def swipe_search(
    bench: Bench,
    competitor: str = "",
    platform: str = "",
    angle: str = "",
    hook: str = "",
    sort: str = "",
    limit: int = MAX_LISTED,
) -> dict:
    from app.studio import swipe

    filters = {
        key: value
        for key, value in (
            ("competitor", competitor),
            ("platform", platform),
            ("angle", angle),
            ("hook", hook),
            ("sort", sort),
        )
        if value
    }
    items = await _settled(swipe.search(bench.session, limit=int(limit), **filters))
    return {"items": items}


async def calendar_read(bench: Bench, slot: str = "") -> dict:
    slots = calendar.slots()
    if not slot:
        return {"slots": slots}
    if slot not in slots:
        raise ToolRefused(f"no slot named {slot!r} — the slots are {sorted(slots)}")
    return {"slot": slot, **slots[slot]}


async def looks_read(bench: Bench, name: str = "") -> dict:
    from app.engine import looks

    return {"look": await _settled(looks.read(name))}


async def assets_read(bench: Bench, seq: int = 0) -> dict:
    asset = (
        (await bench.session.execute(select(Asset).where(Asset.seq == int(seq))))
        .scalars()
        .first()
    )
    if asset is None:
        raise ToolRefused(f"no asset numbered {seq} is in the library")
    version = (
        await bench.session.execute(
            select(func.max(AssetFile.version)).where(AssetFile.asset_seq == asset.seq)
        )
    ).scalar() or 1
    files = media.listing("assets", asset.seq, version)
    _noted(bench, "asset", f"asset/{asset.seq}", "an asset this one is built from")
    return {
        "asset": {
            "seq": asset.seq,
            "name": asset.name,
            "kind": asset.kind,
            "look": asset.look,
            "ancestor_ref": asset.ancestor_ref,
            "version": version,
        },
        "files": files,
        "text": {
            file["path"]: media.read("assets", asset.seq, version, file["path"]).decode(
                errors="replace"
            )
            for file in files
            if media.readable(file["media_type"])
        },
    }


async def transcript_read(bench: Bench, ref: str = "") -> dict:
    names = select(FactCurrent.canonical_id, FactCurrent.value).where(
        FactCurrent.entity_type == MEETING, FactCurrent.attr == NAME
    )
    if not ref:
        rows = (await bench.session.execute(names.limit(MAX_LISTED))).all()
        return {
            "transcripts": [
                {"id": str(canonical_id), "name": name} for canonical_id, name in rows
            ]
        }
    known = dict((await bench.session.execute(names)).all())
    matching = [
        canonical_id
        for canonical_id, name in known.items()
        if str(canonical_id) == ref or name == ref
    ]
    if not matching:
        raise ToolRefused(
            f"no call named {ref!r} — call transcript.read with no ref for the "
            "calls it can open"
        )
    body = (
        (
            await bench.session.execute(
                select(FactCurrent.value).where(
                    FactCurrent.canonical_id == matching[0],
                    FactCurrent.attr == TRANSCRIPT,
                )
            )
        )
        .scalars()
        .first()
    )
    if body is None:
        raise ToolRefused(f"the call {ref!r} carries no transcript")
    _noted(bench, TRANSCRIPT, f"meeting/{matching[0]}", "a line quoted from the call")
    return {"id": str(matching[0]), "name": known[matching[0]], "transcript": body}


def _handle(bench: Bench, name: str, payload: bytes) -> dict:
    handle = f"render-{len(bench.renders) + 1}"
    bench.renders[handle] = payload
    return {"render": handle, "name": name, "bytes": len(payload)}


async def image_render(
    bench: Bench,
    look: str = "",
    fields: dict | None = None,
    size: str = "",
    background: str = "",
) -> dict:
    if bench.mode == DRAFT and background:
        raise ToolRefused(NO_BACKGROUND_ON_A_DRAFT)
    from app.render import image

    rendered = await _settled(
        image.render(look=look, fields=fields or {}, size=size, background=background)
    )
    return {
        **_handle(bench, "image.png", rendered),
        "detail": "pass the handle to files.write to keep it",
    }


async def files_write(
    bench: Bench, path: str = "", text: str | None = None, render: str = ""
) -> dict:
    if (text is None) == (not render):
        raise ToolRefused("files.write takes exactly one of text or a render handle")
    if render:
        if render not in bench.renders:
            raise ToolRefused(
                f"no render named {render!r} — image.render hands back the "
                "handle it made"
            )
        data = bench.renders.pop(render)
    else:
        data = str(text)
    written = media.write(bench.kind, bench.seq, bench.version, path, data)
    bench.written = [
        file for file in bench.written if file["path"] != written["path"]
    ] + [written]
    return written


HANDLERS = {
    "brand.read": brand_read,
    "brand.list": brand_list,
    "swipe.read": swipe_read,
    "swipe.search": swipe_search,
    "calendar.read": calendar_read,
    "looks.read": looks_read,
    "assets.read": assets_read,
    "transcript.read": transcript_read,
    "image.render": image_render,
    "files.write": files_write,
}

STAGES = {
    "brand.read": "reading",
    "brand.list": "reading",
    "swipe.read": "reading",
    "swipe.search": "reading",
    "calendar.read": "reading",
    "looks.read": "reading",
    "assets.read": "reading",
    "transcript.read": "reading",
    "image.render": "rendering",
    "files.write": "writing",
}

TOOLS = (
    (
        "brand.read",
        "One brand file in full: voice, pillars, audiences, objections, "
        "language or proof. Numbers may only come from proof.",
        {"name": {"type": "string"}},
    ),
    (
        "brand.list",
        "The brand files this company keeps.",
        {},
    ),
    (
        "swipe.read",
        "One competitor item as it arrived: its creative, copy, how long it "
        "has run, and its labels with the quote each was read from.",
        {"id": {"type": "string"}},
    ),
    (
        "swipe.search",
        "The swipe file: competitor ads and posts filtered by competitor, "
        "platform, angle or hook, and sorted — days_running is the one that "
        "says an angle is working rather than being tested.",
        {
            "competitor": {"type": "string"},
            "platform": {"type": "string"},
            "angle": {"type": "string"},
            "hook": {"type": "string"},
            "sort": {"type": "string"},
            "limit": {"type": "integer"},
        },
    ),
    (
        "calendar.read",
        "The publishing calendar: every slot with its cadence, kind, look and "
        "theme, or one slot by name.",
        {"slot": {"type": "string"}},
    ),
    (
        "looks.read",
        "One look: the slots its card holds, the character limit measured "
        "for each, and the ratio it sets.",
        {"name": {"type": "string"}},
    ),
    (
        "assets.read",
        "One asset already in the library, with the text of its latest files.",
        {"seq": {"type": "integer"}},
    ),
    (
        "transcript.read",
        "One call transcript by id or by name; called with no ref it names the "
        "calls it can open.",
        {"ref": {"type": "string"}},
    ),
    (
        "image.render",
        "Render one image on a look: the field values as HTML inside the "
        "look's measured limits. A generated background is paid for, so a "
        "draft renders flat and passes no background.",
        {
            "look": {"type": "string"},
            "fields": {"type": "object"},
            "size": {"type": "string"},
            "background": {"type": "string"},
        },
    ),
    (
        "files.write",
        "Keep one file. This is the only way a run produces anything: take "
        "either text, or the handle a render handed back.",
        {
            "path": {"type": "string"},
            "text": {"type": "string"},
            "render": {"type": "string"},
        },
    ),
)


def wire(name: str) -> str:
    return name.replace(".", "_")


def dotted(name: str) -> str:
    return name.replace("_", ".", 1)


def schemas() -> list[dict]:
    return [
        {
            "name": wire(name),
            "description": description,
            "input_schema": {"type": "object", "properties": properties},
        }
        for name, description, properties in TOOLS
    ]


async def _record(bench: Bench, tool: str, ok: bool, started: float, detail: str):
    bench.session.add(
        SkillRunToolCall(
            skill_run_seq=bench.run_seq,
            tool=tool,
            ok=ok,
            duration_ms=int((time.monotonic() - started) * 1000),
            detail=detail[:MAX_DETAIL_CHARS] or None,
        )
    )
    await bench.session.commit()


def _asked(arguments: dict) -> str:
    return ", ".join(f"{key}={value}" for key, value in sorted(arguments.items()))


async def call(bench: Bench, tool: str, arguments: dict | None) -> dict:
    started = time.monotonic()
    handler = HANDLERS.get(tool)
    if handler is None:
        payload, ok, detail = (
            {"error": f"no tool named {tool!r} — the toolbelt is fixed"},
            False,
            f"no tool named {tool!r}",
        )
    else:
        try:
            payload = await handler(bench, **(arguments or {}))
            ok, detail = True, _asked(arguments or {})
        except Exception as exc:
            payload = {"error": f"{type(exc).__name__}: {exc}"}
            ok, detail = False, f"{type(exc).__name__}: {exc}"
    bench.stage = STAGES.get(tool, bench.stage)
    await _record(bench, tool, ok, started, detail)
    return payload
