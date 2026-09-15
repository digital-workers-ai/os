from pathlib import PurePosixPath

from app import media

TEXT_CAP = 256 * 1024

TEXT_TYPES = ("text/", "application/json", "application/yaml")

TEXT_SUFFIXES = (".md", ".markdown", ".yaml", ".yml", ".json", ".html", ".txt")


def refuses(path):
    return path.startswith("/") or ".." in PurePosixPath(path).parts


def is_text(path, media_type):
    return media_type.startswith(TEXT_TYPES) or path.lower().endswith(TEXT_SUFFIXES)


def read(where, path):
    return media.read(*where, path)


def text_of(where, path, media_type, size):
    if not is_text(path, media_type) or size > TEXT_CAP:
        return None
    try:
        return read(where, path).decode("utf-8", "replace")
    except media.MediaError:
        return None


def listed(where, path, media_type, size, url):
    return {
        "path": path,
        "media_type": media_type,
        "bytes": size,
        "text": text_of(where, path, media_type, size),
        "url": url,
    }
