# `aios` — frames

Ported from the `/ai-os` hero in `~/projects/dw/landings`
(`src/pages/ai-os.tsx`, `src/components/aios/FunnelVortex.tsx`). The source is
a wide two-column block; these are the same parts stacked for 9:16.

All frames 1080×1920 on `#F5F4ED`, 88px side margins.

## hook

The opening statement. The hero's own beat.

```
┌──────────────────────────────┐
│                              │
│                              │
│                              │
│  AI OPERATING SYSTEM         │  eyebrow, orange, 30px, tracked
│                              │
│  Every signal in.            │  116px Inter 400, two lines,
│  Intelligence out.           │  each rising out of its own mask
│                              │
│                              │
│                              │
└──────────────────────────────┘
```

## statement

The argument — the part no drawing makes on its own.

```
┌──────────────────────────────┐
│                              │
│  None of it adds up          │  78px
│  on its own.                 │
│                              │
│  Every customer action       │  38px, muted, 860px measure
│  leaves a trace somewhere —  │
│  a comment, a reply, an      │
│  invoice, a call.            │
│                              │
└──────────────────────────────┘
```

## intake

The stream. Twelve sources fall at a constant 131 px/s, each trailing seven
ghosts of itself, and each is taken by the slab rather than fading out — the
slab is opaque and sits above the lane in the stacking order. No stem: nothing
comes out on this frame.

```
┌──────────────────────────────┐
│      EVERY SIGNAL, ONE PLACE │  caption, orange, centred
│  ▁▁  ▁▁▁▁   ▁▁    ▁▁▁        │  ← lane top: masked, chips fade in
│  ▢comment  ▢share   ▢email   │
│      ▢like    ▢booking       │  full-bleed: outer lanes run wider
│   ▢call   ▢ad click  ▢review │  than the slab and are clipped
│      ▢message  ▢follow       │
│ ┌──────────────────────────┐ │
│ │   AI OPERATING SYSTEM    │ │  opaque, above the lane
│ └──────────────────────────┘ │
│                              │
└──────────────────────────────┘
```

## briefing

What comes out. Three cards visible; the column ticks down one row every 2.6s,
so a new card arrives at the top and the oldest is clipped at the bottom.

```
┌──────────────────────────────┐
│   WHAT CHANGED, WHAT NEEDS   │  caption
│ ┌──────────────────────────┐ │
│ │   AI OPERATING SYSTEM    │ │
│ └────────────┬─────────────┘ │  stem: the system feeds these
│ ┌──────────────────────────┐ │
│ │ ▲ 50%  up in traffic     │ │  green — only a rise is green
│ ├──────────────────────────┤ │
│ │ !  Follow up with Sandra │ │  orange
│ ├──────────────────────────┤ │
│ │ ▼ 8%   drop in reply rate│ │  orange
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

## cta

```
┌──────────────────────────────┐
│                              │
│  See the whole picture.      │  78px
│                              │
│  ⬤ Book a walkthrough        │  solid ink pill
│  ◯ See the architecture      │  tan hairline pill
│                              │
└──────────────────────────────┘
```

## pitch

The hero's left column, entire: eyebrow, a two-line headline, the evidence and
one button. `variant` picks the treatment; all ten carry the same copy and the
same animation and differ only in CSS, so none can fall behind the others.

```
 1  left rail      the baseline: flush left, orange dots
 2  centred        everything centred, markers dropped
 3  card           the copy on a white card, like a briefing card
 4  numbered       01 / 02 / 03 in the accent
 5  badge          the eyebrow set in the slab's own material
 6  ruled          hairline rules between items, no markers
 7  turn first     the closing line promoted above the list
 8  boxed list     the list inside a hairline box
 9  chips          items as the pills from the falling stream
10  card stack     items as separate white cards, like the output
```

`dark` is orthogonal to all ten: it redefines the palette tokens on the frame,
so every variant inherits the dark ground without naming a colour of its own.

## funnel

The whole graphic on one frame — stream, system, briefings. `intake` and
`briefing` each draw half of it, and half of it does not make the argument.

```
 1  baseline       caption, rounded slab, three briefings
 2  no caption     the reference frame exactly — the graphic alone
 3  band           slab full-bleed: a layer passed through, not landed in
 4  panel          the whole graphic on a card, as an instrument
 5  tall stream    more fall, two briefings — weighted to what arrives
 6  two up         short lane, two briefings, set larger to be read
 7  pill           slab fully rounded, in the chips' own language
 8  squared        every radius off; instrumentation, not marketing
 9  accent slab    the system in orange — the swallow made obvious
10  narrow         slab and cards pulled in; the frame visibly funnels
```

What a variant may change is how much of the fall is on screen, how the slab is
cut and how many briefings are visible. What it may not change is the fall rate
or the card pitch: the ticker translates by exactly one row, and moving either
would be a different drawing rather than a different treatment of one.

## mailstack

The funnel's top half with a pile of briefings building under it. Two to four
cards: one is not a pile, five is a filing cabinet. The one graphic scene that
does not open assembled, because arriving one at a time is the claim.

## feed

The output side alone: six to ten findings, masked top and bottom so the list
visibly continues. Its loop period is the fall cycle, so a feed scene and a
funnel scene cut against each other without either jumping at the wrap.
