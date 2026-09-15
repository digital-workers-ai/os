from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, StringConstraints

from app.render.scenes import BaseContentSpec, BaseScene


class Theme(BaseModel):

    font_display: str = "Inter"
    font_body: str = "Inter"
    color_ink: str = "#1A1A1A"
    color_bg: str = "#F5F4ED"
    color_accent: str = "#FD4E00"
    color_muted: str = "#666666"
    color_cream: str = "#E0DCC1"
    color_tan: str = "#ADAB9E"
    color_card: str = "#FFFFFF"
    color_positive: str = "#12A150"


class HookContent(BaseModel):

    eyebrow: str = Field(..., max_length=34)
    headline: str = Field(..., max_length=40)


class StatementContent(BaseModel):

    eyebrow: str | None = Field(None, max_length=34)
    headline: str = Field(..., max_length=54)
    body: str = Field(..., max_length=170)


class IntakeContent(BaseModel):

    label: str = Field("AI Operating System", max_length=30)
    caption: str = Field(..., max_length=60)


class BriefLine(BaseModel):

    kind: Literal["up", "down", "alert"] = "alert"

    stat: str | None = Field(None, max_length=6)
    text: str = Field(..., max_length=40)


class BriefingContent(BaseModel):

    label: str = Field("AI Operating System", max_length=30)
    caption: str = Field(..., max_length=60)
    briefs: list[BriefLine] = Field(..., min_length=3, max_length=6)


class PitchContent(BaseModel):

    eyebrow: str = Field(..., max_length=34)

    headline: str = Field(..., max_length=40)

    bullets: list[Annotated[str, StringConstraints(max_length=60)]] | None = Field(
        None, min_length=2, max_length=4
    )

    body: str = Field(..., max_length=150)

    primary: str = Field(..., max_length=30)


class MailCard(BaseModel):

    date: str = Field(..., max_length=14)
    subject: str = Field(..., max_length=60)
    lines: list[Annotated[str, StringConstraints(max_length=46)]] = Field(
        ..., min_length=2, max_length=3
    )


class MailStackContent(BaseModel):

    label: str = Field("AI Operating System", max_length=30)
    caption: str | None = Field(None, max_length=60)

    sender: str = Field("AI Operating System", max_length=28)
    cards: list[MailCard] = Field(..., min_length=2, max_length=4)


class FeedItem(BaseModel):

    severity: Literal["high", "medium"] = "medium"

    text: str = Field(..., max_length=52)

    meta: str | None = Field(None, max_length=28)


class FeedContent(BaseModel):

    caption: str | None = Field(None, max_length=60)

    title: str = Field(..., max_length=30)

    findings: list[FeedItem] = Field(..., min_length=6, max_length=10)


class FunnelContent(BaseModel):

    label: str = Field("AI Operating System", max_length=30)

    caption: str | None = Field(None, max_length=60)
    briefs: list[BriefLine] = Field(..., min_length=3, max_length=6)

    closer: str | None = Field(None, max_length=60)


class CtaContent(BaseModel):

    headline: str = Field(..., max_length=54)
    primary: str = Field(..., max_length=22)
    secondary: str | None = Field(None, max_length=22)


class AiosScene(BaseScene):

    background: Literal["solid"] = "solid"
    script: str = ""


class HookScene(AiosScene):
    type: Literal["hook"]
    content: HookContent


class StatementScene(AiosScene):
    type: Literal["statement"]
    content: StatementContent


class IntakeScene(AiosScene):
    type: Literal["intake"]
    content: IntakeContent


class BriefingScene(AiosScene):
    type: Literal["briefing"]
    content: BriefingContent


class PitchScene(AiosScene):

    type: Literal["pitch"]
    variant: int = Field(1, ge=1, le=10)
    dark: bool = False
    content: PitchContent


class MailStackScene(AiosScene):

    type: Literal["mailstack"]
    variant: int = Field(1, ge=1, le=10)
    dark: bool = False
    content: MailStackContent


class FeedScene(AiosScene):

    type: Literal["feed"]
    dark: bool = False
    content: FeedContent


class FunnelScene(AiosScene):

    type: Literal["funnel"]
    variant: int = Field(1, ge=1, le=10)
    dark: bool = False
    content: FunnelContent


class CtaScene(AiosScene):
    type: Literal["cta"]
    content: CtaContent


Scene = Annotated[
    Union[
        HookScene,
        StatementScene,
        IntakeScene,
        BriefingScene,
        FunnelScene,
        FeedScene,
        MailStackScene,
        PitchScene,
        CtaScene,
    ],
    Field(discriminator="type"),
]


class ContentSpec(BaseContentSpec):

    theme: Theme = Theme()
    scenes: list[Scene]


HEYGEN_ID = ""


MIN_INTAKE = 9.0
MIN_BRIEFING = 8.0
MIN_FUNNEL = 9.0

PLANNER_PROMPT = """You are writing copy for a short, silent, vertical product
video about an AI Operating System — a system that pulls every customer signal
a business produces into one place and hands back a briefing each morning.

There is no voiceover and no presenter. Every word you write appears on screen,
so write display copy, not narration: short, declarative, and able to be read
in the time the scene is on screen. Never write a sentence that only makes
sense when spoken.

The scene types, in the order they usually run:

- hook       an eyebrow and a two-line headline. Use "\\n" to force the break;
             the two lines should be two statements that pivot on each other,
             the way "Every signal in. / Intelligence out." does.
- statement  a smaller headline over one paragraph. This is where an argument
             goes — the thing no drawing can make on its own.
- pitch      the eyebrow, a two-line headline asking what the reader has
             already missed, the evidence, and one button. When the evidence is
             several short facts, write them as `bullets` and let `body` be the
             line that turns them; only write it as one paragraph when it is
             genuinely one thought. Loss, not features — "a reply nobody
             answered" beats "unified data".
             Pair it with `funnel` for a two-scene cut.
- funnel     the whole graphic: signals falling in, the system, and the
             briefings coming out. Prefer this to the two below — it is the
             argument in one picture. You write an optional caption and four to
             six briefing lines.
- intake     the falling-signal graphic alone. You write only its caption, and the
             graphic is already saying "signals are arriving from everywhere",
             so the caption should say something the picture cannot.
- briefing   the graphic's other half: cards that tick past under the system.
             You write four to six of them. Each is one line a real operator
             would want at 8am — a movement with a number, or something that
             needs a person. Mix `up`, `down` and `alert`; do not make them all
             good news, and do not invent implausibly round figures.
- cta        a closing line and one or two button labels.

Keep every field inside its limit. Prefer concrete nouns over abstractions:
"a reply, an invoice, a call" beats "customer touchpoints".
"""
