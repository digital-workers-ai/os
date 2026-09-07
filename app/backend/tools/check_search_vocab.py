import ast
import re
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
PYTHON_VOCAB = BACKEND / "app" / "search_vocab.py"
TS_VOCAB = BACKEND.parent / "frontend" / "src" / "search" / "vocab.ts"
ENUMS = {"Mode": "MODES", "Kind": "KIND", "Param": "PARAM"}
SCALARS = (
    "MARK_OPEN",
    "MARK_CLOSE",
    "EVIDENCE_SEP",
    "LABEL_SEP",
    "ANCHOR_SEP",
    "BRIEFING_REF_SEP",
    "MIN_QUERY_CHARS",
    "DEFAULT_LIMIT",
    "MAX_LIMIT",
)
TS_EXPORT = re.compile(
    r"export const (\w+) = (\[[^\]]*\]|\{[^}]*\}|'[^']*'|\"[^\"]*\"|-?\d+(?:\.\d+)?)"
)
TS_STRING = re.compile(r"'([^']*)'|\"([^\"]*)\"")
TS_OBJECT_VALUE = re.compile(r":\s*(?:'([^']*)'|\"([^\"]*)\")")


def python_values(source: str) -> dict:
    values: dict = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.ClassDef):
            values[node.name] = {
                stmt.value.value for stmt in node.body if isinstance(stmt, ast.Assign)
            }
        elif isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            values[node.targets[0].id] = node.value.value
    return values


def ts_values(source: str) -> dict:
    values: dict = {}
    for name, literal in TS_EXPORT.findall(source):
        if literal[0] == "{":
            values[name] = {a or b for a, b in TS_OBJECT_VALUE.findall(literal)}
        elif literal[0] == "[":
            values[name] = {a or b for a, b in TS_STRING.findall(literal)}
        elif literal[0] in "'\"":
            values[name] = literal[1:-1]
        else:
            values[name] = float(literal) if "." in literal else int(literal)
    return values


def shown(value) -> str:
    return repr(sorted(value) if isinstance(value, set) else value)


def drift(python: dict, ts: dict) -> list[str]:
    problems = []
    for py_name, ts_name in [*ENUMS.items(), *zip(SCALARS, SCALARS, strict=True)]:
        if py_name not in python:
            problems.append(f"{py_name}: missing from {PYTHON_VOCAB}")
        elif ts_name not in ts:
            problems.append(f"{ts_name}: missing from {TS_VOCAB}")
        elif python[py_name] != ts[ts_name]:
            problems.append(
                f"{py_name} drifted: python {shown(python[py_name])} "
                f"vs ts {ts_name} {shown(ts[ts_name])}"
            )
    return problems


def main() -> int:
    for path in (PYTHON_VOCAB, TS_VOCAB):
        if not path.exists():
            print(f"{path} does not exist", file=sys.stderr)
            return 1
    problems = drift(
        python_values(PYTHON_VOCAB.read_text()), ts_values(TS_VOCAB.read_text())
    )
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1
    print("search vocabulary: backend and frontend agree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
