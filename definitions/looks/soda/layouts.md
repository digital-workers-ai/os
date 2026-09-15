# Scene ASCII layouts — soda

Where each scene type's overlay text sits on the phone, taken from the absolute
positions in `base.html.j2`. Shown at the script-approval gate, before anything
is rendered. If the CSS moves, update these.

One frame per scene, stacked vertically — never side by side. 48 columns wide,
~15 rows tall. Label each `Scene N — <type>`, plus any modifiers in parens
(`position`, `tilt`, `animate`, `variant`). Substitute the scene's real text;
truncate with `…` only when a line genuinely will not fit.

`[ avatar ]` marks where the shot shows through (`background: video`); leave the
frame empty for `background: solid`.

## title

Three lines at the bottom; line2 is the huge one. `position: top` / `center`
moves the whole block up.

```
Scene 1 — title
┌──────────────────────────────────────────────┐
│                                              │
│                                              │
│                  [ avatar ]                  │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│   POST-WORKOUT                               │
│                                              │
│   CRASH?                                     │
│   Fix it in 20 minutes                       │
│                                              │
└──────────────────────────────────────────────┘
```

## stat-block

Card in the upper right, avatar to its left. Bullets take `✕` when
`variant: negative`, `✓` when positive.

```
Scene 2 — stat-block (negative)
┌──────────────────────────────────────────────┐
│                    ┌───────────────────────┐ │
│                    │  REGULAR SODA         │ │
│                    │                       │ │
│                    │      39g              │ │
│      [ avatar ]    │  SUGAR PER CAN        │ │
│                    │  then the crash       │ │
│                    │                       │ │
│                    │  ✕ Spikes then drops  │ │
│                    │  ✕ Zero electrolytes  │ │
│                    │  ✕ Slows muscle recov │ │
│                    └───────────────────────┘ │
│                                              │
│                                              │
│                                              │
│                                              │
└──────────────────────────────────────────────┘
```

## caption

Small line1 above huge line2, placed per `position` (top / center / bottom /
bottom-right).

```
Scene 3 — caption (center, tilt, word-by-word)
┌──────────────────────────────────────────────┐
│                                              │
│                                              │
│                  [ avatar ]                  │
│                                              │
│                                              │
│        Sugar isn't                           │
│                                              │
│        RECOVERY                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
└──────────────────────────────────────────────┘
```

## data-table

Solid. Title top left, then the grid: row labels down the left, one column per
entry in `columns`.

```
Scene 4 — data-table (solid)
┌──────────────────────────────────────────────┐
│                                              │
│   PER SERVING                                │
│                                              │
│   ─────────────────────────────────────────  │
│                        Soda        ZERO+     │
│   ─────────────────────────────────────────  │
│   Sugar                 39g          0g      │
│   Calories              140          15      │
│   Electrolytes          0mg        480mg     │
│   B-Vitamins             No         Yes      │
│   ─────────────────────────────────────────  │
│                                              │
│                                              │
│                                              │
│                                              │
└──────────────────────────────────────────────┘
```

## pros-cons

Solid. Title top left, two cards side by side below — positive with `✓`,
negative with `✕`.

```
Scene 5 — pros-cons (solid)
┌──────────────────────────────────────────────┐
│                                              │
│   RECOVERY                                   │
│   CHECK                                      │
│                                              │
│   ┌────────────────────┐ ┌─────────────────┐ │
│   │ ZERO+              │ │ Regular soda    │ │
│   │                    │ │                 │ │
│   │ ✓ Electrolytes+B6  │ │ ✕ 39g of sugar  │ │
│   │ ✓ Hydrates in min  │ │ ✕ Dehydrates    │ │
│   │ ✓ No sugar crash   │ │ ✕ Crash by 30   │ │
│   └────────────────────┘ └─────────────────┘ │
│                                              │
│                                              │
│                                              │
│                                              │
└──────────────────────────────────────────────┘
```

## hero

Icon top left, text block lower left, banner bottom right.

```
Scene 7 — hero
┌──────────────────────────────────────────────┐
│   ⚡                                          │
│                                              │
│                  [ avatar ]                  │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│   RECOVER                                    │
│                                              │
│   FASTER                                     │
│                                              │
│                    ✓ 0 sugar · 480mg salts   │
│                                              │
└──────────────────────────────────────────────┘
```

## cta

Headline lower left, banner bottom right.

```
Scene 8 — cta
┌──────────────────────────────────────────────┐
│                                              │
│                                              │
│                  [ avatar ]                  │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│                                              │
│   Grab ZERO+ and                             │
│   finish strong.                             │
│                                              │
│                            Link in bio       │
│                                              │
└──────────────────────────────────────────────┘
```
