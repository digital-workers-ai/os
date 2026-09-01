import ast
import subprocess
import sys
import textwrap
import tomllib
from pathlib import Path

import pytest

from app import config

APP = Path(__file__).resolve().parent.parent / "app"
BACKEND = APP.parent
PYPROJECT = BACKEND / "pyproject.toml"
LLM = APP / "llm"

INFERENCE_PACKAGES = {"llm", "enrichment", "coaching", "conversation"}
COMPOSITION_ROOT = {"api", "main"}

LLM_PACKAGES = {
    "anthropic",
    "openai",
    "cohere",
    "google",
    "mistralai",
    "langchain",
    "litellm",
    "ollama",
    "transformers",
    "vertexai",
}
FORBIDDEN_ANYWHERE = LLM_PACKAGES - {"anthropic"}


def _first_party_modules() -> dict:
    out = {}
    for path in sorted(APP.rglob("*.py")):
        parts = path.relative_to(APP.parent).with_suffix("").parts
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join(parts)] = path
    return out


def _first_party_edges(path: Path) -> set:
    edges = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            edges |= {a.name for a in node.names if a.name.startswith("app")}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            module = node.module or ""
            if module == "app" or module.startswith("app."):
                edges.add(module)
                edges |= {f"{module}.{a.name}" for a in node.names}
    return edges


def _package_of(module: str) -> str:
    parts = module.split(".")
    return parts[1] if len(parts) > 1 else ""


def _reaches(start: str, target_package: str, modules: dict) -> list:
    seen, stack = set(), [(start, [start])]
    while stack:
        current, trail = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        edges = _first_party_edges(modules[current]) if current in modules else set()
        for edge in edges:
            if _package_of(edge) == target_package:
                return trail + [edge]
            for candidate in (edge, edge.rsplit(".", 1)[0]):
                if candidate in modules and candidate not in seen:
                    stack.append((candidate, trail + [candidate]))
    return []


def _imported_roots(path: Path) -> set:
    roots = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            roots |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots.add((node.module or "").split(".")[0])
    return roots


class TestDependencies:
    def test_only_the_one_model_client_is_installed(self):
        __import__("anthropic")
        for package in sorted(FORBIDDEN_ANYWHERE):
            if package in ("google", "transformers"):
                continue
            with pytest.raises(ImportError):
                __import__(package)

    def test_the_dependency_list_declares_exactly_one_model_client(self):
        declared = tomllib.loads(PYPROJECT.read_text())["project"]["dependencies"]
        names = {
            d.split(">")[0].split("=")[0].split("[")[0].strip().lower()
            for d in declared
        }
        assert "anthropic" in names
        assert not (names & FORBIDDEN_ANYWHERE), names & FORBIDDEN_ANYWHERE


class TestTheBoundaryIsWhereItSaysItIs:
    def test_exactly_one_module_imports_a_vendor_sdk(self):
        offenders = []
        for path in sorted(APP.rglob("*.py")):
            if LLM in path.parents:
                continue
            hit = _imported_roots(path) & LLM_PACKAGES
            if hit:
                offenders.append(f"{path.relative_to(APP)}: {sorted(hit)}")
        assert offenders == []

    def test_the_llm_module_exists_and_does_import_one(self):
        assert LLM.is_dir()
        found = {root for path in LLM.rglob("*.py") for root in _imported_roots(path)}
        assert "anthropic" in found

    def test_the_substrate_is_derived_by_subtraction_not_enumeration(self):
        packages = {
            p.name for p in APP.iterdir() if p.is_dir() and not p.name.startswith("__")
        }
        substrate = packages - INFERENCE_PACKAGES - COMPOSITION_ROOT
        assert {"engine", "sources"} <= substrate

    def test_no_substrate_module_reaches_the_llm_module(self):
        modules = _first_party_modules()
        offenders = []
        for module in sorted(modules):
            if _package_of(module) in INFERENCE_PACKAGES | COMPOSITION_ROOT:
                continue
            trail = _reaches(module, "llm", modules)
            if trail:
                offenders.append(" -> ".join(trail))
        assert offenders == []

    def test_no_substrate_module_names_a_client_in_a_dynamic_import(self):
        offenders = []
        for path in sorted(APP.rglob("*.py")):
            dotted = f"app.{path.relative_to(APP)}".replace("/", ".")
            if _package_of(dotted) in INFERENCE_PACKAGES | COMPOSITION_ROOT:
                continue
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.Call):
                    continue
                name = getattr(node.func, "attr", getattr(node.func, "id", ""))
                if name not in ("import_module", "__import__"):
                    continue
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        if arg.value.split(".")[
                            0
                        ] in LLM_PACKAGES or arg.value.startswith("app.llm"):
                            offenders.append(f"{path.name}:{node.lineno}")
        assert offenders == []

    def test_every_substrate_module_imports_with_the_client_unimportable(self):
        modules = sorted(
            m
            for m in _first_party_modules()
            if _package_of(m) not in INFERENCE_PACKAGES | COMPOSITION_ROOT
        )
        program = textwrap.dedent(f"""
            import sys
            BANNED = {sorted(LLM_PACKAGES)!r}

            class Blocker:
                def find_module(self, name, path=None):
                    return self.find_spec(name, path)
                def find_spec(self, name, path=None, target=None):
                    if name.split(".")[0] in BANNED:
                        raise ImportError(
                            "a substrate module reached " + name)
                    return None

            sys.meta_path.insert(0, Blocker())
            import importlib
            failed = []
            for module in {modules!r}:
                try:
                    importlib.import_module(module)
                except ImportError as exc:
                    if "a substrate module reached" in str(exc):
                        failed.append(module + ": " + str(exc))
            print("|".join(failed))
        """)
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            cwd=APP.parent,
            timeout=180,
        )
        assert result.returncode == 0, result.stderr[-2000:]
        assert result.stdout.strip() == "", result.stdout


def test_no_module_executes_code_from_data():
    forbidden = {"eval", "exec", "compile"}
    offenders = []
    for path in sorted(APP.rglob("*.py")):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in forbidden
            ):
                offenders.append(f"{path.name}:{node.lineno} {node.func.id}")
    assert offenders == []


class TestStartupRefusesAMisconfiguredDeploy:
    def test_a_clean_environment_boots_with_enrichment_off(self):
        assert config.validate_startup(env={}) is None

    def test_enrichment_on_without_a_credential_refuses_the_boot(self, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        with pytest.raises(config.StartupError, match="ENRICHMENT_ENABLED"):
            config.validate_startup(env={})

    @pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"])
    def test_either_credential_form_satisfies_it(self, name, monkeypatch):
        monkeypatch.setattr(config.settings, "ENRICHMENT_ENABLED", True)
        config.validate_startup(env={name: "sk-something"})

    def test_a_credential_with_enrichment_off_is_allowed_but_unused(self):
        config.validate_startup(env={"ANTHROPIC_API_KEY": "sk-something"})


def test_enrichment_ships_off_by_default():
    assert config.settings.ENRICHMENT_ENABLED is False
