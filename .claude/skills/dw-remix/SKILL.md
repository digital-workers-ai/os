---
name: dw-remix
description: Rebuild one swipe item as ours — keep the structure the caller asked to keep, replace every piece of substance with the company's own proof and voice, and record the ancestor it came from.
user-invocable: true
argument-hint: "<swipe item id> [keep: hook, structure, offer]"
---

# Skill: Remix

One competitor item, rebuilt as ours. The caller says what to keep — hook
type, structure, offer, any combination — and everything else is replaced.

What is kept is a shape: that this ad opens on a contrast, that it runs
problem, proof, offer, that it leads with a price. What is replaced is
everything the shape was holding: their claim, their number, their customer,
their words. A remix that keeps a sentence is not a remix.

The ancestor is recorded. Every asset this skill makes names the swipe item it
came from, so a person can always see what we were looking at.

## What it reads

`swipe.read` returns the item as it arrived: the creative, the copy fields,
first and last seen, how long it has run, and its labels — angle, hook,
format, offer, proof — each carrying the quote it was read from. Those labels
are the shape; the quotes are what gets thrown away.

`proof.md` is the only place our numbers come from. `voice.md` and
`language.md` make it sound like us rather than like a translation.
`pillars.md` decides whether we have anything to say in this shape at all.
`looks.read` gives the look its fields and limits.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`swipe.read`, `swipe.search`, `looks.read`, `calendar.read`,
`transcript.read`, `image.render`, `video.plan`, `video.render` and
`files.write`, and nothing else is reachable — no shell, no network, no
database. If the remix needs something that is not there, write `held.md`
naming what is missing, and stop.

## Modes

**draft** is what Studio's Remix button runs: the copy, the cheap preview, and
`remix.md`. An image drafts small on a flat background under `dw-image`'s
rules; a video drafts as a validated `content.yaml` and a storyboard from the
look's frames, under `dw-video`'s rules. No render is paid for.

**build** runs after a person approved: the real render on the same look, the
copy they edited.

**chat** is an ask over MCP naming a swipe item, with no proposal behind it.
It behaves like build and lands in the Library marked "from chat". Nothing was
approved, so every rule that would hold a draft holds here.

## Steps

1. Read the item through `swipe.read`. Write down its labels and the quote
   behind each: this is what it does, and this is what it says.
2. Take the caller's keep list. Anything not on it is replaced, including
   things that seem harmless to keep.
3. Check `pillars.md`. If we have nothing true to put in this shape, write
   `held.md` and stop; a shape filled with nothing is worse than an empty slot.
4. Rebuild, element by element, against the kept shape. Our proof where their
   proof was, our offer where theirs was unless offer was kept, our reader's
   words throughout.
5. Write `remix.md`. First line `ancestor: <swipe item id>`. Then two short
   lists: what was kept, and what was replaced with what. Plain enough that a
   person disagreeing knows exactly where to disagree.
6. Write `claims.md`. One line per asserting sentence: the text, then `proof`,
   `transcript` or `competitor_ad`, then the ref, separated by ` | `. The
   ancestor goes in as evidence, never as a claim.
7. Build the asset on the look, write `build.md`, then every file through
   `files.write`.

## Rules

- Never carry a sentence, a phrase or a number across. Their "$499 a month" is
  their number; ours is in `proof.md` or it does not appear.
- Never name the competitor in the output. The ancestor lives in `remix.md`
  and in the asset's lineage, not in the ad.
- Keep only what was asked for. Keeping more because it worked for them is how
  a remix becomes a copy.
- Numbers come from `proof.md` and nowhere else.
- A quote appears verbatim in the transcript or brand file it cites. A quote
  from the swipe item is evidence, never copy.
- `remix.md` is written every time, including when nothing was kept. It is how
  a person audits this skill.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the line quoted, and
  stop.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Keeping the offer usually keeps their pricing model too. Say so in
  `remix.md` when the caller ticks it (#188, 2026-08-30).
- Their hook works because of who they sell to. Check `audiences.md` before
  keeping a hook type, not after (#199, 2026-09-05).
