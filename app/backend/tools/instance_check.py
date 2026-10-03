import argparse
import json
import re
import sys
from pathlib import Path

from app.caches import DEFINITIONS_DIR
from app.coaching import briefer
from app.engine import checks, mappings, spy
from app.enrichment import vocabulary
from tests import ground_truth
from tools import seed_demo
from tools.pull_source import MOCK_FIXTURES

WORLD_DATA = Path(ground_truth.ADVERSARIAL_ROOT) / "seeds" / "world" / "data.yaml"
SCANNED = [
    ("definitions", DEFINITIONS_DIR),
    ("app/backend/fixtures", MOCK_FIXTURES.parent),
    ("mock/world/data.yaml", WORLD_DATA),
    ("README.md", DEFINITIONS_DIR.resolve().parent / "README.md"),
]


def load_world() -> tuple[object, list[str]]:
    try:
        world = ground_truth.world()
    except Exception as e:
        return None, [f"seeds.world failed to load: {type(e).__name__}: {e}"]
    if world is None:
        root = ground_truth.ADVERSARIAL_ROOT
        return None, [f"seeds.world is not importable from {root}"]
    return world, []


def check_world() -> list[str]:
    world, problems = load_world()
    if problems:
        return problems
    present = (
        ("company", world.COMPANIES),
        ("person", world.PEOPLE),
        ("spy brand", world.SPY_BRAND.get("name")),
        ("competitor", world.SPY_COMPETITORS),
    )
    problems = [f"no {label}" for label, found in present if not found]
    named = spy.load()
    sections = (
        ("brand", world.SPY_BRAND),
        ("competitors", world.SPY_COMPETITORS),
        ("queries", world.SPY_QUERIES),
    )
    problems += [
        f"spy.{section} differs between the world and definitions/spy.yaml"
        for section, found in sections
        if found != named[section]
    ]
    return problems


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


def labels(reading: str) -> dict[str, tuple]:
    return {field.name: field.labels for field in vocabulary.load()[reading].fields}


def call_problems(calls: list[dict], world) -> list[str]:
    asked = labels("sales_call")
    problems = []
    for call in calls:
        key = call["key"]
        found = sum(key in sales_call.topic for sales_call in world.SALES_CALLS)
        if found != 1:
            problems.append(f"call {key!r} is in {found} sales call topics, not one")
        answers = [("interest", call["interest"]), ("timing", call["timing"])]
        answers += [("pain_points", label) for label in call["pain_points"]]
        problems += [
            f"call {key!r}: {attr} {label!r} is not a sales_call label"
            for attr, label in answers
            if label not in asked[attr]
        ]
    return problems


def ticket_problems(tickets: list[dict], world) -> list[str]:
    complaints = labels("support_ticket")["complaint"]
    problems = []
    for ticket in tickets:
        prefix, complaint = ticket["subject"], ticket["complaint"]
        if not any(t.subject.startswith(prefix) for t in world.TICKETS):
            problems.append(f"ticket {prefix!r} starts no ticket subject in the world")
        if complaint not in complaints:
            problems.append(
                f"ticket {prefix!r}: complaint {complaint!r} "
                "is not a support_ticket label"
            )
    return problems


def briefing_problems(seed: dict) -> list[str]:
    keys = {call["key"] for call in seed["calls"]}
    problems = []
    for role, texts in seed["briefings"].items():
        if role not in briefer.roles():
            problems.append(f"briefing {role!r} has no reader in definitions/briefs/")
        named = {
            name
            for text in (*texts["history"], texts["latest"])
            for name in seed_demo.PLACEHOLDER.findall(text)
        }
        problems += [
            f"briefing {role!r} names {{{name}}}, which is no call key"
            for name in sorted(named - keys)
        ]
    problems += [
        f"finding {finding['rule']!r} names call {finding['call']!r}, "
        "which is no call key"
        for finding in seed["read"]["findings"]
        if finding["call"] not in keys
    ]
    return problems


def lookalike_problems(lookalikes: list[dict]) -> list[str]:
    sources = {line.source for line in mappings.load()}
    return [
        f"look-alike {pair['pair']!r} comes from {record['source']!r}, "
        "which mappings.yaml does not name"
        for pair in lookalikes
        for record in pair["records"]
        if record["source"] not in sources
    ]


def check_seed() -> list[str]:
    world, problems = load_world()
    if problems:
        return problems
    try:
        seed = seed_demo.read_seed()
        return [
            *call_problems(seed["calls"], world),
            *ticket_problems(seed["tickets"], world),
            *briefing_problems(seed),
            *lookalike_problems(seed["lookalikes"]),
        ]
    except Exception as e:
        return [f"{seed_demo.SEED.name} failed to load: {type(e).__name__}: {e}"]


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
    ("seed", check_seed),
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
