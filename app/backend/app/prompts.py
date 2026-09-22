import re
from pathlib import Path

from app.caches import DEFINITIONS_DIR, load_mapping, register

DEFAULT_PROMPTS = DEFINITIONS_DIR / "prompts.yaml"
RESERVED = ("version", "fence")
PLACEHOLDERS = ("{fence_open}", "{fence_close}")
_TAG = re.compile(r"^[a-z][a-z0-9_]*$")


class PromptError(ValueError):
    pass


_cache: dict | None = None


@register
def _reset() -> None:
    global _cache
    _cache = None


def _check(name, section, target) -> None:
    if not isinstance(section, dict):
        raise PromptError(f"{target.name}: {name} must map keys to prompt text")
    texts = {key: value for key, value in section.items() if key not in RESERVED}
    if not texts:
        raise PromptError(f"{target.name}: {name} holds no prompt text")
    if "version" in section and not isinstance(section["version"], str):
        raise PromptError(f"{target.name}: {name}.version must be a string")
    tag = section.get("fence")
    fenced = "fence" in section
    if fenced and not (isinstance(tag, str) and _TAG.match(tag)):
        raise PromptError(f"{target.name}: {name}.fence must be a tag like estate_data")
    for key, value in texts.items():
        if not isinstance(value, str) or not value.strip():
            raise PromptError(f"{target.name}: {name}.{key} must be non-empty text")
        if not fenced and any(marker in value for marker in PLACEHOLDERS):
            raise PromptError(
                f"{target.name}: {name}.{key} names a fence "
                "the section does not declare"
            )


def load(path=None) -> dict:
    global _cache
    if path is None and _cache is not None:
        return _cache
    target = Path(path or DEFAULT_PROMPTS)
    doc = load_mapping(target, PromptError)
    for name, section in doc.items():
        _check(name, section, target)
    if path is None:
        _cache = doc
    return doc


def _section(name) -> dict:
    doc = load()
    if name not in doc:
        raise PromptError(f"{DEFAULT_PROMPTS.name}: no section {name!r}")
    return doc[name]


def fence(section) -> tuple[str, str]:
    tag = _section(section).get("fence")
    if tag is None:
        raise PromptError(f"{DEFAULT_PROMPTS.name}: {section} declares no fence")
    return f"<{tag}>", f"</{tag}>"


def version(section) -> str:
    found = _section(section).get("version")
    if found is None:
        raise PromptError(f"{DEFAULT_PROMPTS.name}: {section} declares no version")
    return found


def text(section, key) -> str:
    found = _section(section)
    if key in RESERVED or key not in found:
        raise PromptError(f"{DEFAULT_PROMPTS.name}: {section} has no prompt {key!r}")
    body = found[key]
    if "fence" in found:
        for marker, tag in zip(PLACEHOLDERS, fence(section), strict=True):
            body = body.replace(marker, tag)
    return body
