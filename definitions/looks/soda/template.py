import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, StringConstraints, computed_field

from app.render.scenes import BaseContentSpec, BaseScene


class Theme(BaseModel):
    font_display: str = "Big Shoulders Display"
    font_body: str = "Inter"
    color_positive: str = "#10b981"
    color_negative: str = "#dc2626"
    color_bg: str = "#111"
    color_text: str = "#fff"


class TitleContent(BaseModel):
    line1: str = Field(..., max_length=20)
    line2: str = Field(..., max_length=14)
    line3: str | None = Field(None, max_length=24)
    position: Literal["top", "center", "bottom"] = "bottom"


class StatBlockContent(BaseModel):
    header: str = Field(..., max_length=20)
    stat: str = Field(..., max_length=4)
    stat_label: str = Field(..., max_length=20)
    stat_sub: str = Field(..., max_length=18)
    bullets: list[Annotated[str, StringConstraints(max_length=28)]]


class ProsConsColumn(BaseModel):
    header: str = Field(..., max_length=18)
    items: list[Annotated[str, StringConstraints(max_length=26)]]


class ProsConsContent(BaseModel):
    title: str = Field(..., max_length=18)
    positive: ProsConsColumn
    negative: ProsConsColumn


class CaptionContent(BaseModel):
    line1: str = Field(..., max_length=16)
    line2: str | None = Field(None, max_length=10)

    @computed_field
    @property
    def text(self) -> str:
        return f"{self.line1}\n{self.line2}" if self.line2 else self.line1
    position: Literal["top", "center", "bottom", "bottom-right"] = "bottom"
    animate: Literal["word-by-word", "line-by-line", "fade"] = "fade"
    tilt: bool = False


class DataTableRow(BaseModel):
    label: str = Field(..., max_length=16)
    values: list[Annotated[str, StringConstraints(max_length=8)]]
    small: bool = False


class DataTableContent(BaseModel):
    title: str = Field(..., max_length=18)
    columns: list[Annotated[str, StringConstraints(max_length=12)]]
    rows: list[DataTableRow]


class HeroContent(BaseModel):
    text: str = Field(..., max_length=24)
    icon: str = Field("✓", max_length=2)
    banner_text: str | None = Field(None, max_length=24)
    banner_icon: str | None = Field(None, max_length=2)


class CTAContent(BaseModel):
    headline: str = Field(..., max_length=40)
    banner_text: str | None = Field(None, max_length=22)


class TitleScene(BaseScene):
    type: Literal["title"]
    content: TitleContent


class StatBlockScene(BaseScene):
    type: Literal["stat-block"]
    variant: Literal["positive", "negative"]
    content: StatBlockContent


class ProsConsScene(BaseScene):
    type: Literal["pros-cons"]
    background: Literal["video", "solid"] = "solid"
    content: ProsConsContent


class CaptionScene(BaseScene):
    type: Literal["caption"]
    content: CaptionContent


class DataTableScene(BaseScene):
    type: Literal["data-table"]
    background: Literal["video", "solid"] = "solid"
    content: DataTableContent


class HeroScene(BaseScene):
    type: Literal["hero"]
    content: HeroContent


class CTAScene(BaseScene):
    type: Literal["cta"]
    content: CTAContent


Scene = Annotated[
    Union[
        TitleScene,
        StatBlockScene,
        ProsConsScene,
        CaptionScene,
        DataTableScene,
        HeroScene,
        CTAScene,
    ],
    Field(discriminator="type"),
]


class ContentSpec(BaseContentSpec):
    theme: Theme = Theme()
    scenes: list[Scene]


HEYGEN_ID = "1d13879ecba7459eac21fa2da3673b86"


SLOTS = [
    {"id": "evNkGQex", "pose": "walking on the path, regular soda can at her hip"},
    {"id": "xBtRtXfj", "pose": "holding the regular soda can up to camera"},
    {"id": "B2kLStS3", "pose": "holding the ZERO+ can, hand on hip"},
    {"id": "K9TRN5DT", "pose": "standing on the path, regular soda can lowered"},
    {"id": "D90xZ6cc", "pose": "drinking ZERO+ through a straw"},
    {"id": "8xuUVyD4", "pose": "seated on a bench, talking to camera"},
    {"id": "VZHRU1il", "pose": "holding ZERO+ up, thumbs up"},
    {"id": "tilCVNb5", "pose": "selfie, arm extended, ZERO+ in hand"},
]


VOICE_ID = "25a40947b46942c1a8e5bd329074bba2"


VOICE_CONFIRMED = False

PLANNER_PROMPT = """You are a UGC video content planner. Given a product or topic, generate a content plan that defines a short-form vertical video (TikTok/Reels style).

Available scene types:
- title: Big display text, 2-3 lines. Use for hooks/intros.
- stat-block: Card with one big stat + bullet points. variant: positive or negative.
- pros-cons: Two-column comparison grid. Use for side-by-side comparisons.
- caption: Simple text overlay on video. animate: word-by-word, line-by-line, or fade. position: top, center, bottom, or bottom-right.
- data-table: Grid comparing numbers between two options.
- hero: Big statement text + icon badge. Use for climax/conclusion.
- cta: Call to action headline, revealed word by word. Use for closing.

Rules:
- Total duration should be 20-30 seconds
- Match script length to duration (~2.5 words per second)
- Use exactly 8 scenes, one per avatar shot (see AVATAR SHOTS below)
- background: "video" shows the avatar, "solid" shows a dark screen (use for data-heavy scenes)
- Start with a hook (title), end with a CTA
- Keep text short and punchy - these are phone screens

CHARACTER LIMITS (hard - overlay text renders at up to 280px on a 1080px-wide
phone screen, and anything longer is silently cut off at the frame edge). These
are maximums, not targets: aim well under them. Newlines count as characters.

  title         line1 <=20   line2 <=14   line3 <=24
  stat-block    header <=20  stat <=4     stat_label <=20  stat_sub <=18
                bullets <=28 each (2-4 bullets)
  pros-cons     title <=18 (use a newline)  column header <=18
                items <=26 each (3-4 items)
  caption       line1 <=16 (small line)   line2 <=10 (big line, optional)
  data-table    title <=18 (use a newline)  column <=12  row label <=16
                cell value <=8
  hero          text <=24 (use a newline)   banner_text <=24
  cta           headline <=40   banner_text <=22

The "stat" and cell-value fields are for short numbers like "39g", "0", "140" -
not sentences. Prefer 2-3 short words over one long phrase everywhere.

AVATAR SHOTS - each scene is filmed as one of these, set by the scene's "slot"
field (1-8). Every slot must be used exactly once, so assign each scene the shot
that fits what it says. Note which can she is holding: putting a line praising
ZERO+ over a shot of the regular can reads as a mistake.

  1  walking on the path, regular soda can at her hip
  2  holding the regular soda can up to camera
  3  holding the ZERO+ can, hand on hip
  4  standing on the path, regular soda can lowered
  5  drinking ZERO+ through a straw
  6  seated on a bench, talking to camera
  7  holding ZERO+ up, thumbs up
  8  selfie, arm extended, ZERO+ in hand

Scenes still play in array order; "slot" only picks which shot each one uses."""


def zero_text(val: str) -> str:
    m = re.match(r"^(\d+)(.*)$", str(val))
    return "0" + m.group(2) if m else val


FILTERS = {"zero_text": zero_text}


WORD_SYNC = {"caption": "text", "cta": "headline"}
