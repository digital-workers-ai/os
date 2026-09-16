---
name: dw-carousel
description: Write and render a carousel on the carousel look, one idea per slide, with a cover that states the promise and a closing that says what to do
makes: carousel
user-invocable: true
argument-hint: "[the idea, or the slot theme, with the ratio]"
---

# Skill: Carousel

Make one carousel from the ask on the `carousel` look. The ask is an idea,
a calendar slot's theme, or a call to draw from. The carousel is the files
this skill writes through `files.write`; nothing it says on the way is
kept.

## What it reads

- `looks.read("carousel")`: the cover, slide and closing slots, each
  slot's `max`, the slide count it allows, the ratios it renders, the
  sample `content.yaml` and the layouts
- `brand.read("voice")` and `brand.read("language")`: how the company
  sounds, the words it uses and the words it refuses
- `brand.read("pillars")` and `brand.read("audiences")`: the subject the
  carousel serves and who reads it
- `brand.read("objections")`: an objection a slide can answer
- `brand.read("proof")`: the only place a number comes from
- `transcript.read()` and `transcript.read(ref)` when the ask names a call
- `calendar.read(slot)` when the ask names a slot
- `assets.read(seq)` when the ask names an earlier carousel

## Steps

1. Read the look and the brand files, then the call or slot the ask
   names. Take the ratio the ask names, else `4:5`. On an edit, read the
   earlier `content.yaml` and keep every slide the ask did not name. On a
   resize, keep the content and change only the ratio.
2. Pick one idea and the pillar it serves. Plan the slides: the cover
   states the promise, each slide carries one point, the closing says
   what to do next. Stay inside the slide count the look allows.
3. Write `content.yaml` in the shape of the look's sample: `cover`,
   `slides` in order, `closing`, every slot inside its `max`.
4. Render with `carousel.render("carousel", content, ratio)` and write
   the renders in order as `slide-01.png`, `slide-02.png` and on through
   the closing, two digits each. A render that refuses a slot names it;
   shorten that slot and render again.
5. Write `claims.md`: one line per slide text that asserts something, as
   `<sentence> | proof | <heading in proof.md>` or
   `<sentence> | transcript | <ref>`. Then `build.md`: one short paragraph
   on what was made, how many slides, and what it cost in renders.
6. When something the carousel needs is missing, no proof for a number,
   a call that is not there, a ratio the look does not render, write
   `held.md` naming it and stop.

## Rules

- One idea per slide. A slide that needs a second sentence to be
  understood is two slides.
- The cover states the promise: what the reader has by the last slide.
  No "swipe", no arrows.
- The closing states what to do, one action, in the `cta` slot.
- Each slide's title stands on its own; a reader who lands on slide four
  knows what it says.
- Numbers come from `proof.md` only. A number with no proof line is not
  written.
- A quote is verbatim, in quotation marks, from the transcript or brand
  file its `claims.md` line cites.
- No hashtags, no emoji, no engagement bait, no "save this for later".
- Every asserting slide has a line in `claims.md`. A line with no source
  holds the run, so text with no source is cut before it is written.
- An edit changes what the ask names and nothing else. A resize renders
  every slide again at the new ratio with the same content.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.
