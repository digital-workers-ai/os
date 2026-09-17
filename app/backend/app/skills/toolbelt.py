import json
import time
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import media
from app.engine import brand, calendar, looks
from app.models import Asset, AssetVersion, FactCurrent, SkillRunToolCall
from app.render import image
from app.render.client import Painter, Render, RenderError

FENCE_OPEN, FENCE_CLOSE = "<studio_data>", "</studio_data>"
DETAIL_CHARS = 200
TOOL_CHARS = 64
MEETING, NAME, TRANSCRIPT = "meeting", "name", "transcript"


class ToolRefused(RuntimeError):
    pass


@dataclass
class Bench:
    session: AsyncSession
    run_seq: int
    asset_seq: int
    version: int
    painter: Painter = field(default_factory=Painter)
    renderer: Render = field(default_factory=Render)
    written: list = field(default_factory=list)
    renders: dict = field(default_factory=dict)
    pictures: dict = field(default_factory=dict)
    read: list = field(default_factory=list)
    stage: str | None = None


def _note(bench: Bench, kind: str, ref: str, detail: str) -> None:
    if all((item["kind"], item["ref"]) != (kind, ref) for item in bench.read):
        bench.read.append({"kind": kind, "ref": ref, "detail": detail})


def _keep(bench: Bench, png: bytes) -> str:
    handle = f"render-{len(bench.renders) + 1}"
    bench.renders[handle] = png
    return handle


async def brand_list(bench) -> dict:
    return {
        "files": brand.files(),
        "assets": [asset["name"] for asset in brand.assets()],
    }


async def brand_read(bench, name="") -> dict:
    file = str(name)
    file = file if file.endswith(".md") else f"{file}.md"
    front, body = brand.read(file)
    _note(bench, "brand", file, str(front.get("title") or file))
    return {"file": file, "front": front, "body": body}


async def brand_assets(bench) -> dict:
    return {
        "assets": [
            {
                "name": asset["name"],
                "media_type": asset["media_type"],
                "bytes": asset["bytes"],
            }
            for asset in brand.assets()
        ]
    }


async def calendar_read(bench, slot="") -> dict:
    slots = calendar.slots()
    if not slot:
        return {"slots": slots}
    if slot not in slots:
        raise ToolRefused(f"no slot named {slot!r}; the calendar has {sorted(slots)}")
    return {"slot": slot, **slots[slot]}


async def looks_read(bench, name="") -> dict:
    return looks.read(str(name))


async def assets_read(bench, seq=None) -> dict:
    try:
        number = int(seq)
    except (TypeError, ValueError):
        raise ToolRefused(f"seq {seq!r} is not an asset number") from None
    asset = await bench.session.get(Asset, number)
    if asset is None:
        raise ToolRefused(
            f"no asset {number}; assets.read takes the seq of an earlier asset"
        )
    query = (
        select(AssetVersion.version)
        .where(AssetVersion.asset_seq == number)
        .order_by(AssetVersion.version.desc())
    )
    versions = [
        version
        for version in (await bench.session.execute(query)).scalars()
        if (number, version) != (bench.asset_seq, bench.version)
    ]
    if not versions:
        raise ToolRefused(f"asset {number} has no earlier version to read")
    version = versions[0]
    files = []
    for entry in media.listing(number, version):
        if media.readable(entry["media_type"]):
            data = media.read(number, version, entry["path"])
            entry["text"] = data.decode(errors="replace")
        files.append(entry)
    _note(bench, "asset", str(number), f"{asset.name}, version {version}")
    return {
        "seq": number,
        "name": asset.name,
        "kind": asset.kind,
        "look": asset.look,
        "ratio": asset.ratio,
        "version": version,
        "files": files,
    }


def _meetings(attr: str):
    return select(FactCurrent.canonical_id, FactCurrent.value).where(
        FactCurrent.entity_type == MEETING, FactCurrent.attr == attr
    )


async def transcript_read(bench, ref="") -> dict:
    session = bench.session
    if not ref:
        listing = _meetings(NAME).order_by(FactCurrent.value)
        rows = (await session.execute(listing)).all()
        return {"meetings": [{"ref": str(cid), "name": name} for cid, name in rows]}
    ref = str(ref)
    try:
        named = _meetings(NAME).where(FactCurrent.canonical_id == uuid.UUID(ref))
    except ValueError:
        named = _meetings(NAME).where(FactCurrent.value == ref)
    row = (await session.execute(named.limit(1))).first()
    if row is None:
        raise ToolRefused(
            f"no meeting {ref!r}; transcript.read with no ref lists the meetings"
        )
    cid, name = row
    body = select(FactCurrent.value).where(
        FactCurrent.canonical_id == cid, FactCurrent.attr == TRANSCRIPT
    )
    transcript = (await session.execute(body)).scalar()
    if transcript is None:
        raise ToolRefused(f"meeting {name!r} has no transcript on file")
    _note(bench, "transcript", str(cid), name)
    return {"ref": str(cid), "name": name, "transcript": transcript}


async def image_paint(bench, prompt="", ratio="") -> dict:
    if not str(prompt).strip():
        raise ToolRefused("image.paint needs a prompt that describes the scene")
    picture = await bench.painter.picture(str(prompt), str(ratio))
    handle = f"picture-{len(bench.pictures) + 1}"
    bench.pictures[handle] = picture
    return {"picture": handle}


async def image_render(bench, look="", fields=None, ratio="", picture="") -> dict:
    scene = None
    if picture:
        if picture not in bench.pictures:
            raise ToolRefused(
                f"no picture {picture!r}; image.paint returns the handle to pass here"
            )
        scene = bench.pictures[picture]
    png = await image.render(str(look), fields, str(ratio), scene, bench.renderer)
    return {"render": _keep(bench, png)}


async def carousel_render(bench, look="", content=None, ratio="") -> dict:
    pngs = await image.render_slides(str(look), content, str(ratio), bench.renderer)
    return {"renders": [_keep(bench, png) for png in pngs]}


async def files_write(bench, path="", text=None, render="") -> dict:
    if (text is None) == (not render):
        raise ToolRefused("files.write takes exactly one of text or render")
    if render:
        if render not in bench.renders:
            raise ToolRefused(
                f"no render {render!r}; image.render and carousel.render return "
                "the handles to write"
            )
        data = bench.renders[render]
    else:
        data = str(text)
    written = media.write(bench.asset_seq, bench.version, str(path), data)
    for index, item in enumerate(bench.written):
        if item["path"] == written["path"]:
            bench.written[index] = written
            break
    else:
        bench.written.append(written)
    return written


TOOLS = (
    ("brand.list", "The brand files and the brand assets, by name.", {}),
    (
        "brand.read",
        "One brand file: its front matter and its body. Name it with or without "
        ".md: brand-brain, voice, pillars, audiences, objections, language, proof.",
        {"name": {"type": "string"}},
    ),
    ("brand.assets", "The brand's logo and fonts: name, media type and size.", {}),
    (
        "calendar.read",
        "Every calendar slot, or one slot by name.",
        {"slot": {"type": "string"}},
    ),
    (
        "looks.read",
        "One look: its slots and each slot's max, the ratios it renders, the "
        "sample content and the layouts.",
        {"name": {"type": "string"}},
    ),
    (
        "assets.read",
        "An earlier asset's latest version: its files, with the text of the "
        "readable ones.",
        {"seq": {"type": "integer"}},
    ),
    (
        "transcript.read",
        "The meetings on file, or one meeting's transcript by ref or exact name.",
        {"ref": {"type": "string"}},
    ),
    (
        "image.paint",
        "Paint a wordless picture at the ratio. Returns a picture handle for "
        "image.render.",
        {"prompt": {"type": "string"}, "ratio": {"type": "string"}},
    ),
    (
        "image.render",
        "Compose the look's card from the fields, over the picture when one is "
        "given, at the ratio. Returns a render handle for files.write.",
        {
            "look": {"type": "string"},
            "fields": {"type": "object"},
            "ratio": {"type": "string"},
            "picture": {"type": "string"},
        },
    ),
    (
        "carousel.render",
        "Render every page of a carousel from its content: cover, slides and "
        "closing. Returns one render handle per page, in order.",
        {
            "look": {"type": "string"},
            "content": {"type": "object"},
            "ratio": {"type": "string"},
        },
    ),
    (
        "files.write",
        "Write one file of the asset: text, or one render handle. Exactly one "
        "of the two.",
        {
            "path": {"type": "string"},
            "text": {"type": "string"},
            "render": {"type": "string"},
        },
    ),
)

HANDLERS = {
    "brand.list": brand_list,
    "brand.read": brand_read,
    "brand.assets": brand_assets,
    "calendar.read": calendar_read,
    "looks.read": looks_read,
    "assets.read": assets_read,
    "transcript.read": transcript_read,
    "image.paint": image_paint,
    "image.render": image_render,
    "carousel.render": carousel_render,
    "files.write": files_write,
}

STAGES = {
    "brand.list": "reading",
    "brand.read": "reading",
    "brand.assets": "reading",
    "calendar.read": "reading",
    "looks.read": "reading",
    "assets.read": "reading",
    "transcript.read": "reading",
    "image.paint": "painting",
    "image.render": "rendering",
    "carousel.render": "rendering",
    "files.write": "writing",
}

WIRE = {name.replace(".", "_"): name for name, _description, _properties in TOOLS}


def schemas() -> list[dict]:
    return [
        {
            "name": name.replace(".", "_"),
            "description": description,
            "input_schema": {"type": "object", "properties": properties},
        }
        for name, description, properties in TOOLS
    ]


def dotted(name: str) -> str:
    return WIRE.get(name, name)


def _summary(arguments) -> str:
    return json.dumps(arguments or {}, default=str)[:DETAIL_CHARS]


async def call(bench: Bench, tool: str, arguments) -> dict:
    name = dotted(tool)
    handler = HANDLERS.get(name)
    started = time.monotonic()
    if handler is None:
        payload = {
            "error": f"no tool named {tool!r}: the toolbelt is fixed at "
            f"{', '.join(HANDLERS)}"
        }
    else:
        bench.stage = STAGES[name]
        try:
            payload = await handler(bench, **(arguments or {}))
        except TypeError as exc:
            payload = {"error": f"bad arguments for {name}: {exc}"}
        except (ToolRefused, RenderError, media.MediaError, ValueError) as exc:
            payload = {"error": str(exc)}
    ok = "error" not in payload
    bench.session.add(
        SkillRunToolCall(
            skill_run_seq=bench.run_seq,
            tool=str(tool)[:TOOL_CHARS],
            ok=ok,
            duration_ms=int((time.monotonic() - started) * 1000),
            detail=_summary(arguments) if ok else payload["error"],
        )
    )
    await bench.session.flush()
    return payload
