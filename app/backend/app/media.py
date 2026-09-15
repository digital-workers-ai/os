import re
from pathlib import Path

from app.config import settings

KINDS = ("proposals", "assets", "runs")

MAX_FILE_BYTES = 32 * 1024 * 1024

MAX_FILES_PER_RUN = 24

MAX_PATH_CHARS = 120

SEGMENT = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*\Z")

MEDIA_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".yaml": "text/yaml",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}

PLAIN_TYPE = "application/octet-stream"

READABLE = ("text/", "application/json")


class MediaError(RuntimeError):
    pass


def root() -> Path:
    return Path(settings.MEDIA_DIR)


def _whole(value, what: str) -> str:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise MediaError(f"{what} {value!r} is not a whole number") from None
    if number < 1:
        raise MediaError(f"{what} {value!r} is not a positive number")
    return str(number)


def relative(path) -> str:
    text = str(path)
    if not text:
        raise MediaError("a file with no name cannot be written")
    if len(text) > MAX_PATH_CHARS:
        raise MediaError(f"{text[:40]!r} is too long for a file name")
    segments = text.split("/")
    for segment in segments:
        if not SEGMENT.match(segment):
            raise MediaError(
                f"{text!r} is not a plain relative path — a file is named in "
                "letters, digits, dots, dashes and underscores, and lives "
                "inside its own run"
            )
    return "/".join(segments)


def run_dir(kind, seq, version) -> Path:
    if kind not in KINDS:
        raise MediaError(f"{kind!r} is not a kind of run — known: {list(KINDS)}")
    return root() / kind / _whole(seq, "seq") / _whole(version, "version")


def path_for(kind, seq, version, path) -> Path:
    directory = run_dir(kind, seq, version)
    target = (directory / relative(path)).resolve()
    if directory.resolve() not in target.parents:
        raise MediaError(f"{str(path)!r} resolves outside the media store")
    return target


def media_type(path) -> str:
    return MEDIA_TYPES.get(Path(str(path)).suffix.lower(), PLAIN_TYPE)


def readable(kind: str) -> bool:
    return kind.startswith(READABLE)


def write(kind, seq, version, path, data) -> dict:
    if isinstance(data, str):
        payload = data.encode()
    elif isinstance(data, bytes | bytearray):
        payload = bytes(data)
    else:
        raise MediaError(f"{type(data).__name__} is neither text or bytes")
    if len(payload) > MAX_FILE_BYTES:
        raise MediaError(
            f"{str(path)!r} is {len(payload)} bytes, over the "
            f"{MAX_FILE_BYTES} a single file may be"
        )
    target = path_for(kind, seq, version, path)
    if not target.exists() and len(listing(kind, seq, version)) >= MAX_FILES_PER_RUN:
        raise MediaError(
            f"this run has already written {MAX_FILES_PER_RUN} files, which is "
            "all one run may write"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return {
        "path": relative(path),
        "media_type": media_type(path),
        "bytes": len(payload),
    }


def read(kind, seq, version, path) -> bytes:
    target = path_for(kind, seq, version, path)
    if not target.is_file():
        raise MediaError(f"no file at {str(path)!r} in this run")
    return target.read_bytes()


def listing(kind, seq, version) -> list[dict]:
    directory = run_dir(kind, seq, version)
    if not directory.is_dir():
        return []
    return [
        {
            "path": str(found.relative_to(directory)),
            "media_type": media_type(found),
            "bytes": found.stat().st_size,
        }
        for found in sorted(directory.rglob("*"))
        if found.is_file()
    ]
