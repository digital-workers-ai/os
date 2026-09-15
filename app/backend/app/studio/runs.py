from dataclasses import dataclass

from app.skills import catalog, runner
from app.studio import errors


@dataclass(frozen=True)
class Started:
    skill_run: int
    ask: runner.Ask


def sha(skill):
    try:
        return catalog.load(skill).sha
    except catalog.SkillError as exc:
        raise errors.Refused(str(exc)) from exc


async def start(session, **fields):
    ask = runner.Ask(caller="studio", **fields)
    try:
        return Started(await runner.open_run(session, ask), ask)
    except catalog.SkillError as exc:
        raise errors.Refused(str(exc)) from exc
