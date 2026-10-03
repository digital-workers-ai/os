import argparse
import json
import re
import sys
from pathlib import Path

from app.caches import BACKEND_DIR, DEFINITIONS_DIR
from app.engine import checks, mappings
from tests import ground_truth
from tools import seed_demo
from tools.pull_source import MOCK_FIXTURES

WORLD_DATA = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "world" / "data.yaml"
SCANNED = [
    ("definitions", DEFINITIONS_DIR),
    ("app/backend/fixtures", MOCK_FIXTURES.parent),
    ("mock/world/data.yaml", WORLD_DATA),
    ("README.md", BACKEND_DIR.parents[1] / "README.md"),
]


def check_world() -> list[str]:
    try:
        world = ground_truth.world()
    except Exception as e:
        return [f"seeds.world failed to load: {type(e).__name__}: {e}"]
    if world is None:
        return [f"seeds.world is not importable from {ground_truth.ADVERSARIAL_ROOT}"]
    present = (
        ("company", world.COMPANIES),
        ("person", world.PEOPLE),
        ("spy brand", world.SPY_BRAND.get("name")),
        ("competitor", world.SPY_COMPETITORS),
    )
    return [f"no {label}" for label, found in present if not found]


def check_fixtures() -> list[str]:
    problems = []
    for source in sorted({line.source for line in mappings.load()}):
        directory = MOCK_FIXTURES / source
        expected = directory / "expected.json"
        if not expected.is_file():
            problems.append(f"{source}: no expected.json")
            continue
        for object_type in sorted(json.loads(expected.read_text())["extracted"]):
            if not (directory / f"{object_type}.json").is_file():
                problems.append(
                    f"{source}: {object_type}.json is listed in expected.json "
                    "but missing"
                )
    return problems


def check_studio() -> list[str]:
    problems = []
    for entry in seed_demo.read_library()["assets"]:
        for version in entry["versions"]:
            folder = seed_demo.version_folder(entry, version["version"])
            for file in version["files"]:
                path = folder / file["path"]
                shown = path.relative_to(seed_demo.STUDIO_FIXTURES)
                if not path.is_file():
                    problems.append(f"{shown} is listed but missing")
                elif path.stat().st_size != file["bytes"]:
                    problems.append(
                        f"{shown} is {path.stat().st_size} bytes, "
                        f"the manifest says {file['bytes']}"
                    )
    return problems


def pattern(term: str) -> re.Pattern:
    escaped = re.escape(term)
    if "." in term or "@" in term:
        return re.compile(escaped, re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", re.IGNORECASE)


def files_under(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    if root.is_dir():
        return sorted(path for path in root.rglob("*") if path.is_file())
    return []


def check_names(names: Path) -> list[str]:
    terms = [line.strip() for line in names.read_text().splitlines() if line.strip()]
    patterns = [(term, pattern(term)) for term in terms]
    found: dict[str, list[str]] = {term: [] for term in terms}
    for label, root in SCANNED:
        for path in files_under(root):
            text = path.read_bytes().decode("utf-8", "ignore")
            shown = label if path == root else f"{label}/{path.relative_to(root)}"
            for term, compiled in patterns:
                if compiled.search(text):
                    found[term].append(shown)
    return [f"{term!r} in {', '.join(paths)}" for term, paths in found.items() if paths]


CHECKS = (
    ("definitions", checks.run),
    ("world", check_world),
    ("fixtures", check_fixtures),
    ("studio", check_studio),
)


def report(names: Path | None) -> tuple[str, int]:
    results = [(label, check()) for label, check in CHECKS]
    if names is not None:
        results.append(("names", check_names(names)))
    lines = [f"{label}: {'; '.join(problems) or 'ok'}" for label, problems in results]
    if names is None:
        lines.append("names: skipped (no --names file)")
    return "\n".join(lines), int(any(problems for _label, problems in results))


def parse(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.instance_check")
    parser.add_argument("--names", type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    text, code = report(parse(argv).names)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
