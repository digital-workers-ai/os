---
name: dw-counter-ad
description: Make an ad that answers an angle a competitor has been running long enough for it to be working, using the company's own proof and its readers' objections, without ever naming the competitor.
user-invocable: true
argument-hint: "[the angle, or a swipe item id]"
---

# Skill: Counter ad

An ad that answers an angle. `copy.md` is the text — primary, headline, call
to action — and beside it an image or a video on the look the slot asked for.

The angle is the thing being answered, never the ad. A competitor running one
creative for ninety days has found something true about the reader, and that
truth is worth answering. Their wording is not worth borrowing, their name is
not worth spending our impression on, and their claims are not ours to repeat.

## What it reads

`swipe.search` returns the swipe file — competitor ads with their labels and
the quote each label came from, first seen, last seen, and how long each has
run. Days running is the evidence: one new ad is noise, five ads on one angle
that have all run a month is a position. `swipe.read` opens one item in full.

`objections.md` is what our reader already believes, which is usually the
thing the competitor's angle is pressing on. `proof.md` is the only place a
number may come from. `voice.md` and `language.md` keep the answer ours.
`looks.read` gives the look its fields and limits.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`swipe.search`, `swipe.read`, `looks.read`, `calendar.read`,
`transcript.read`, `image.render`, `video.plan`, `video.render` and
`files.write`, and nothing else is reachable — no shell, no network, no
database. If the ad needs something that is not there, write `held.md`
naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run: `copy.md`, and the asset as a cheap
preview. An image ad drafts as the look rendered small on a flat background,
under `dw-image`'s rules. A video ad drafts as a validated `content.yaml` and
a storyboard from the look's frames, under `dw-video`'s rules. No render is
paid for; `build.md` says what one would cost.

**build** runs after a person approved: the real render on the same look, the
copy they edited, nothing re-decided.

**chat** is an ask over MCP with no proposal behind it. It behaves like build
and lands in the Library marked "from chat". Nothing was approved, so every
rule that would hold a draft holds here.

## Steps

1. Name the angle. Read the swipe file sorted by days running, and say in one
   sentence what the competitor's ads are claiming about the reader's life.
   Cite the items: three ads on one angle, not one.
2. Find the objection it presses on in `objections.md`. That objection, in the
   reader's words, is what the ad is really about.
3. Answer it with our proof. Read `proof.md` and pick the one number or fact
   that makes the objection dissolve. If there is none, write `held.md` and
   stop: an answer with no proof behind it is an argument, and arguments lose.
4. Write `copy.md` — primary text, headline, call to action — in our voice,
   about our reader, never mentioning anyone else.
5. Write `claims.md`. One line per asserting sentence: the text, then `proof`,
   `transcript` or `competitor_ad`, then the ref, separated by ` | `. The
   competitor items that established the angle go in as evidence, not as
   claims: we are not asserting what they said is true.
6. Build the asset on the look — `dw-image`'s rules for an image,
   `dw-video`'s for a video — write `build.md`, then every file through
   `files.write`.

## Rules

- Never name the competitor. Not in copy, not on screen, not in a filename,
  not as "a certain tool". The reader should not be able to tell who we read.
- Answer the angle, not the ad. Nothing in the output should only make sense
  to someone who saw theirs.
- Never repeat a competitor's claim, even to deny it. Denying it is repeating
  it, and their number is not in `proof.md`.
- Days running is the evidence. An angle backed by one ad seen last week is
  not yet an angle; say so and propose nothing.
- Numbers come from `proof.md` and nowhere else.
- A quote appears verbatim in the transcript or brand file it cites, and a
  competitor's quote is evidence in `claims.md`, never copy in the ad.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the line quoted, and
  stop.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Answer the objection, not the competitor. An ad that reads as a reply has
  already conceded who set the terms (#201, 2026-09-06).
- Longevity is the only signal worth acting on. New ads are tests, and
  answering a test answers nothing (#212, 2026-09-13).
