from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

RESOLUTIONS = ("portrait", "landscape", "square", "four-five")


class Project(BaseModel):
    name: str
    resolution: Literal["portrait", "landscape", "square", "four-five"] = "portrait"


class BlockNudge(BaseModel):
    dx: float | None = None
    dy: float | None = None
    scale: float | None = Field(None, gt=0.2, le=4)
    size: int | None = Field(None, gt=8, le=400)
    line_height: float | None = Field(None, gt=0.5, le=3)


class SceneLayout(BaseModel):
    dx: float = 0
    dy: float = 0
    scale: float = Field(1, gt=0.2, le=4)
    size: int | None = Field(None, gt=8, le=400)
    line_height: float | None = Field(None, gt=0.5, le=3)
    blocks: dict[str, BlockNudge] | None = None


class SceneAnimation(BaseModel):
    cascade: bool = False
    delay: float = Field(0.15, ge=0, le=2)
    start: float = Field(0.0, ge=0, le=10)
    duration: float | None = Field(None, gt=0.05, le=3)


class BaseScene(BaseModel):
    type: str
    duration: float
    background: Literal["video", "solid"] = "video"
    script: str
    slot: int | None = None
    hold: float | None = None
    layout: SceneLayout | None = None
    anim: SceneAnimation | None = None


class BaseContentSpec(BaseModel):
    project: Project
    voice: str | None = None
    scenes: list[BaseScene]


def shows_avatar(scene) -> bool:
    return getattr(scene, "background", "video") == "video"


class SceneStatus(StrEnum):
    pending = "pending"
    rendering = "rendering"
    rendered = "rendered"
    transcribed = "transcribed"
    failed = "failed"


class SceneState(BaseModel):
    index: int
    status: SceneStatus = SceneStatus.pending
    video_id: str | None = None
    video_path: str | None = None
    actual_duration: float | None = None
    transcript: dict | None = None
    source: str | None = None
    error: str | None = None


class PipelineState(BaseModel):
    scenes: list[SceneState] = []

    def for_scene(self, index: int) -> SceneState:
        for scene in self.scenes:
            if scene.index == index:
                return scene
        state = SceneState(index=index)
        self.scenes.append(state)
        return state
