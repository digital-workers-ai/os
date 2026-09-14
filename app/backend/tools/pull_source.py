import argparse
import asyncio
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from app import clock
from app.caches import BACKEND_DIR
from app.engine import checks, mappings, ontology, pipeline, transforms
from app.engine.report import SyncReport
from app.sources import registry
from app.sources.client import collect_stats, redact_url
from app.sources.creds import credentials_for

MOCK_FIXTURES = checks.REAL_FIXTURES.parent / "mock"
CAPTURES = BACKEND_DIR / "captures"
NO_RECORDS_DEAD = "no records, dead paths not evaluated"
NO_RECORDS_COMPARE = "no records, shape not compared"


@dataclass
class Pulled:
    base_url: str = ""
    records: dict = field(default_factory=dict)
    requests: Counter = field(default_factory=Counter)
    unattributed: int = 0
    notes: dict | None = None
    error: str | None = None


async def pull(source: str) -> Pulled:
    module = registry.get(source)
    pulled = Pulled()
    stats = collect_stats()
    counted = 0

    async def store(session, *, object_type, source_id, raw_payload, **_):
        nonlocal counted
        pulled.requests[object_type] += stats.pages_read - counted
        counted = stats.pages_read
        pulled.records.setdefault(object_type, []).append((source_id, raw_payload))

    try:
        pulled.base_url = redact_url(credentials_for(source).base_url)
        with stats:
            pulled.notes = await module.pull(None, store)
    except Exception as e:
        pulled.error = f"{type(e).__name__}: {e}"
    pulled.unattributed = stats.pages_read - counted
    return pulled


def assess(source: str, module, records: dict) -> dict:
    lines = mappings.load()
    line_index = mappings.by_object(lines)
    transform_map = transforms.load_map()
    onto = ontology.load()
    mapped = sorted({line.object_type for line in lines if line.source == source})
    assessed: dict = {}
    for name in dict.fromkeys([*records, *mapped]):
        report = SyncReport()
        for line in line_index.get((source, name), []):
            report.declare_path(line.entity, line.key)
        accepted = 0
        for source_id, payload in records.get(name, []):
            entities = pipeline.project_payload(
                source=source,
                object_type=name,
                source_id=source_id,
                payload=payload,
                raw_event_id=None,
                ingested_at=clock.now(),
                seq=1,
                onto=onto,
                line_index=line_index,
                transform_map=transform_map,
                report=report,
                connector_module=module,
            )
            accepted += bool(entities)
        assessed[name] = (accepted, report)
    return assessed


def json_type(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int | float):
        return "number"
    if isinstance(value, str):
        return "string"
    return "list" if isinstance(value, list) else "object"


def key_types(payloads: list, prefix: str = "") -> dict:
    types: dict = {}
    for payload in payloads:
        for key, value in payload.items():
            path = f"{prefix}{key}"
            types.setdefault(path, set()).add(json_type(value))
            listed = isinstance(value, list)
            children = [
                c for c in (value if listed else [value]) if isinstance(c, dict)
            ]
            nested = key_types(children, f"{path}[]." if listed else f"{path}.")
            for child, kinds in nested.items():
                types.setdefault(child, set()).update(kinds)
    return types


def diff(real: dict, mock: dict) -> tuple[str, bool]:
    only_real = sorted(set(real) - set(mock))
    only_mock = sorted(set(mock) - set(real))
    mismatched = sorted(p for p in set(real) & set(mock) if real[p] != mock[p])
    mismatches = [
        f"{p} real={'|'.join(sorted(real[p]))} mock={'|'.join(sorted(mock[p]))}"
        for p in mismatched
    ]
    text = (
        f"only in real: {', '.join(only_real) or 'none'}; "
        f"only in mock: {', '.join(only_mock) or 'none'}; "
        f"type mismatches: {', '.join(mismatches) or 'none'}"
    )
    return text, bool(only_real or only_mock or mismatched)


def mock_diff(source: str, name: str, payloads: list) -> tuple[str, bool]:
    path = MOCK_FIXTURES / source / f"{name}.json"
    if not path.exists():
        return f"no mock fixture at {path}", True
    mock = key_types([row["payload"] for row in json.loads(path.read_text())])
    return diff(key_types(payloads), mock)


def write_capture(directory: Path, source: str, records: dict, names) -> Path:
    target = directory / source
    target.mkdir(parents=True, exist_ok=True)
    for name in names:
        rows = [
            {"payload": payload, "source_id": source_id}
            for source_id, payload in records.get(name, [])
        ]
        text = json.dumps(rows, indent=2, sort_keys=True)
        (target / f"{name}.json").write_text(text + "\n")
    return target


async def report(
    source: str, *, compare: bool = False, capture: Path | None = None
) -> tuple[str, int]:
    pulled = await pull(source)
    assessed = assess(source, registry.get(source), pulled.records)
    lines = [f"{source}: {pulled.base_url}"]
    failed = pulled.error is not None
    for name, (accepted, found) in assessed.items():
        payloads = [payload for _id, payload in pulled.records.get(name, [])]
        lines.append(
            f"{name}: requests={pulled.requests[name]} "
            f"records={len(payloads)} accepted={accepted}"
        )
        dead = found.dead_paths() if payloads else []
        failed = failed or bool(dead)
        listed = (", ".join(dead) or "none") if payloads else NO_RECORDS_DEAD
        lines.append(f"  dead paths: {listed}")
        skips = sorted({**found.skips, **found.records_skipped}.items())
        lines.append(f"  skips: {', '.join(f'{k}={v}' for k, v in skips) or 'none'}")
        if compare:
            text, differs = (
                mock_diff(source, name, payloads)
                if payloads
                else (NO_RECORDS_COMPARE, False)
            )
            failed = failed or differs
            lines.append(f"  compare: {text}")
    if pulled.notes:
        notes = sorted(pulled.notes.items())
        lines.append(f"notes: {' '.join(f'{k}={v}' for k, v in notes)}")
    if pulled.unattributed:
        lines.append(f"unattributed requests: {pulled.unattributed}")
    if pulled.error:
        lines.append(f"error: {pulled.error}")
    if capture is not None:
        lines.append(
            f"captured: {write_capture(capture, source, pulled.records, assessed)}"
        )
    return "\n".join(lines), int(failed)


def parse(argv) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m tools.pull_source")
    parser.add_argument("source", choices=sorted(registry.discover()))
    parser.add_argument("--compare", action="store_true")
    parser.add_argument("--capture", nargs="?", const=CAPTURES, type=Path)
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse(argv)
    text, code = asyncio.run(
        report(args.source, compare=args.compare, capture=args.capture)
    )
    print(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
