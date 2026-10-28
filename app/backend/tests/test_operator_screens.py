import yaml

from app.caches import BACKEND_DIR
from app.skills import catalog

OPERATOR = BACKEND_DIR.parent.parent / "agents" / "operator.yaml"
SKILL = catalog.SKILLS_DIR / "dw-operator" / "SKILL.md"
SCREENS = "app/custom/src/apps/"
BUILDING_BLOCK = "building block"


def _brief():
    return yaml.safe_load(OPERATOR.read_text())["brief"]


def test_the_agents_folder_is_mounted_so_these_checks_cannot_silently_skip():
    assert OPERATOR.is_file(), (
        f"{OPERATOR} is absent inside the stack — add '../agents:/agents:ro' to "
        "the backend volumes in app/docker-compose.yml and restart the backend"
    )


def test_the_brief_reads_the_screens_the_apps_bring():
    assert SCREENS in _brief()


def test_the_brief_proposes_a_building_block():
    assert BUILDING_BLOCK in _brief()


def test_the_skill_reads_the_screens_the_apps_bring():
    assert SCREENS in SKILL.read_text()


def test_the_skill_proposes_a_building_block():
    assert BUILDING_BLOCK in SKILL.read_text()
