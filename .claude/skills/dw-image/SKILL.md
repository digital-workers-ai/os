---
name: dw-image
description: Render promotional images from an image look — the text as HTML inside the look's measured limits, the background generated only on a build, one file per variant.
user-invocable: true
argument-hint: "[the proof point, and the look]"
---

# Skill: Image

Promotional images on one proof point. Each variant is one file: `v1.png`,
`v2.png`, `v3.png`. The look decides everything about how they are set — the
grid, the type, the ratio, the character budget of each field. This skill
decides only what the words are.

Text is never generated pixels. It is HTML the look renders, so it is sharp
at any size, spelled correctly, and identical to what the proposal showed.
Only the background is ever generated, and only on a build.

## What it reads

`looks.read` returns the look: its fields, the character limit measured for
each one, and the ratios it sets. `proof.md` is the only place a number on
an image may come from; `transcript.read` is where a quoted line comes from.
`voice.md` keeps the four or five words in the company's register, and
`audiences.md` says who is squinting at this in a feed.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`looks.read`, `calendar.read`, `transcript.read`, `image.render` and
`files.write`, and nothing else is reachable — no shell, no network, no
database. If an image needs something that is not there, write `held.md`
naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run. Two or three variants on one proof
point, rendered small by `image.render` on a flat background — no generated
pixels, nothing paid for. The variants differ in what they say, not in how
they are decorated, so a person is choosing a line and not a texture.

**build** runs after a person ticked the variants worth keeping. Only those
render, at full size, and `image.render` generates the background here. The
text is the text they approved, unchanged.

**chat** is an ask over MCP with no proposal behind it. It behaves like build:
full size, generated background, back to the caller and into the Library
marked "from chat". Nothing was approved, so every rule that would hold a
draft holds here.

## Steps

1. Read the look through `looks.read` before writing a word. Its fields and
   their limits are the shape of the sentence you are allowed to write.
2. Settle the one proof point from `proof.md`. One number, or one claim. An
   image carrying two ideas carries neither.
3. Write each variant's fields, counting characters as you go. A field over
   its limit is rewritten now; the render refuses it later either way, and a
   refused render is a wasted call.
4. Write `claims.md`. One line per field that asserts something: the text,
   then `proof`, `transcript` or `competitor_ad`, then the ref, separated by
   ` | `. A number on an image with no line in `claims.md` is not rendered.
5. Call `image.render` per variant — the look, the field values, the size, and
   on a build the background prompt. If it refuses, read what it named, fix
   that field, and call it again; never work around a refusal by shortening
   the look's expectations.
6. Write `build.md` — how many renders a build costs — then each rendered
   file through `files.write`.

## Rules

- The text is HTML rendered by the look. Never ask for words as pixels, never
  ask the background to contain a word, a number or a logo.
- The background is generated on a build and on a chat call, never on a
  draft. A draft's background is flat.
- Every field is inside the look's measured limit. The render refuses anything
  else, and that refusal is the look being right, not the look being fussy.
- Numbers come from `proof.md` and nowhere else.
- A quote set into a field appears verbatim in the transcript or brand file it
  cites. A testimonial trimmed to fit the look's limit is not a testimonial;
  pick a shorter one.
- One proof point per image. Variants say it differently; they do not say
  different things.
- Never invent a look, a field or a slot name. If the look lacks a field the
  image needs, write `held.md` and stop: looks change by pull request.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the field quoted, and
  stop. Nothing renders.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Write to two thirds of the limit. A field at exactly its maximum sets badly
  on a phone even when the render accepts it (#177, 2026-08-21).
- Variants are three sentences about one number, not one sentence in three
  colourways (#203, 2026-09-08).
