import re
from pathlib import Path

from app.config import settings

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_FILES_PER_VERSION = 24
MAX_PATH_CHARS = 120
SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
MEDIA_TYPES = {
    ".md": "text/markdown",
    ".txt": "text/plain",
    ".html": "text/html",
    ".yaml": "text/yaml",
    ".json": "application/json",
    ".png": "image/png",
    ".jpg": "image/jpeg",
}
BYTE_STREAM = "application/octet-stream"


class MediaError(RuntimeError):
    pass


def relative(path: str) -> str:
    if len(path) > MAX_PATH_CHARS:
        raise MediaError(
            f"a path of {len(path)} characters is over the {MAX_PATH_CHARS} a file "
            "may carry: a name that long is prose that belongs inside the file"
        )
    for segment in path.split("/"):
        if segment == "..":
            raise MediaError(
                f"{path!r} climbs with '..', which could reach a file outside "
                "the version it belongs to"
            )
        if not SEGMENT.fullmatch(segment):
            raise MediaError(
                f"{path!r} has the segment {segment!r}: a segment starts with a "
                "letter or digit and carries only letters, digits, '.', '_' and "
                "'-', so a path names one place under its version and nothing else"
            )
    return path


def media_type(path: str) -> str:
    return MEDIA_TYPES.get(Path(path).suffix, BYTE_STREAM)


def readable(media_type: str) -> bool:
    return media_type.startswith("text/") or media_type == "application/json"


def _version_dir(seq: int, version: int) -> Path:
    return Path(settings.MEDIA_DIR) / "assets" / str(seq) / str(version)


def _files(base: Path) -> list[Path]:
    return [file for file in base.rglob("*") if file.is_file()]


def _entry(base: Path, file: Path) -> dict:
    path = file.relative_to(base).as_posix()
    return {"path": path, "media_type": media_type(path), "bytes": file.stat().st_size}


def write(seq: int, version: int, path: str, data: str | bytes) -> dict:
    path = relative(path)
    if isinstance(data, str):
        data = data.encode()
    if len(data) > MAX_FILE_BYTES:
        raise MediaError(
            f"{path!r} is {len(data)} bytes, over the {MAX_FILE_BYTES} a file may "
            "weigh: nothing a skill makes is that large, so this is a run gone wrong"
        )
    base = _version_dir(seq, version)
    target = base / path
    if not target.exists() and len(_files(base)) >= MAX_FILES_PER_VERSION:
        raise MediaError(
            f"asset {seq} version {version} already holds {MAX_FILES_PER_VERSION} "
            "files, and a run that writes more is looping rather than finishing"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"path": path, "media_type": media_type(path), "bytes": len(data)}


def read(seq: int, version: int, path: str) -> bytes:
    path = relative(path)
    target = _version_dir(seq, version) / path
    if not target.is_file():
        raise MediaError(
            f"asset {seq} version {version} has no file {path!r}; the asset_file "
            "row and the media store disagree, or the path was never written"
        )
    return target.read_bytes()


def listing(seq: int, version: int) -> list[dict]:
    base = _version_dir(seq, version)
    entries = (_entry(base, file) for file in _files(base))
    return sorted(entries, key=lambda entry: entry["path"])
