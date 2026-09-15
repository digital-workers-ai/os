import argparse
import json
import re
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.engine import checks, mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import registry
from tools.pull_source import CAPTURES

REAL_FIXTURES = checks.REAL_FIXTURES
EXPECTED = "expected.json"
CAPTURED_AT = datetime(2026, 8, 2, tzinfo=UTC)

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]*[a-zA-Z]")
PHONE = re.compile(
    r"(?<![\w-])(?:\+\d{1,3}[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?![\w-])"
    r"|(?<!\w)\+\d{8,15}(?!\w)"
)
SECRET = "api_key="


def strings(value, path: str):
    if isinstance(value, dict):
        for key, child in value.items():
            yield from strings(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from strings(child, f"{path}[{index}]")
    elif isinstance(value, str):
        yield path, value


def looks_personal(text: str) -> str | None:
    if EMAIL.search(text):
        return "an email address"
    if PHONE.search(text):
        return "a phone number"
    if SECRET in text:
        return "an api_key"
    return None


def offences(files: list[Path]) -> list[str]:
    found = []
    for file in files:
        for path, text in strings(json.loads(file.read_text()), file.name):
            kind = looks_personal(text)
            if kind:
                found.append(f"{path} looks like {kind}")
    return found


def replay(source: str, files: list[Path]) -> tuple[dict, SyncReport]:
    lines = mappings.load()
    line_index = mappings.by_object(lines)
    transform_map = transforms.load_map()
    onto = ontology.load()
    module = registry.discover().get(source)
    report = SyncReport()
    for line in lines:
        if line.source == source:
            report.declare_path(line.entity, line.key)
    extracted: dict = {}
    for file in files:
        for record in json.loads(file.read_text()):
            for entity in pipeline.project_payload(
                source=source,
                object_type=file.stem,
                source_id=record["source_id"],
                payload=record["payload"],
                raw_event_id=None,
                ingested_at=CAPTURED_AT,
                seq=1,
                onto=onto,
                line_index=line_index,
                transform_map=transform_map,
                report=report,
                connector_module=module,
            ):
                extracted.setdefault(file.stem, {}).setdefault(entity.entity_type, {})[
                    entity.source_id
                ] = {attr: fact.value for attr, fact in sorted(entity.facts.items())}
    return extracted, report


def promote(source: str, captures: Path, fixtures: Path) -> tuple[str, int]:
    captured = sorted((captures / source).glob("*.json"))
    if not captured:
        return f"refused: no capture files under {captures / source}", 1
    found = offences(captured)
    if found:
        return "\n".join(["refused:", *(f"  {line}" for line in found)]), 1
    target = fixtures / source
    target.mkdir(parents=True, exist_ok=True)
    copied = [shutil.copy(file, target / file.name) for file in captured]
    extracted, report = replay(source, copied)
    expected = {
        "clears": dict(sorted(report.clears.items())),
        "extracted": extracted,
        "skips": dict(sorted(report.skips.items())),
    }
    (target / EXPECTED).write_text(
        json.dumps(expected, indent=2, sort_keys=True) + "\n"
    )
    lines = [f"{source}: {target}"]
    for file in copied:
        counts = " ".join(
            f"{entity_type}={len(rows)}"
            for entity_type, rows in sorted(extracted.get(file.stem, {}).items())
        )
        records = len(json.loads(file.read_text()))
        lines.append(f"{file.stem}: records={records} {counts or 'extracted=0'}")
    lines.append(f"dead paths: {', '.join(report.dead_paths()) or 'none'}")
    for name in ("skips", "clears"):
        counted = sorted(expected[name].items())
        lines.append(f"{name}: {', '.join(f'{k}={v}' for k, v in counted) or 'none'}")
    lines.append(f"expected: {target / EXPECTED}")
    return "\n".join(lines), 0


def parse(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.promote_capture")
    parser.add_argument("source", choices=sorted(registry.discover()))
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    text, code = promote(args.source, CAPTURES, REAL_FIXTURES)
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
