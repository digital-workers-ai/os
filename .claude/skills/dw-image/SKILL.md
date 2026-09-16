---
name: dw-image
description: Paint a wordless picture and render the brand's words over it on a named look and ratio, from a content file it also writes
makes: image
user-invocable: true
argument-hint: "[what the card says, with the look and the ratio]"
---

# Skill: Image

Make one image on one look from the ask. The ask names the look, the
ratio and what the card says: a number, a quote or a list. The image is
the files this skill writes through `files.write`; nothing it says on the
way is kept.

## What it reads

- `looks.read(name)`: the look's slots, each slot's `max`, the ratios it
  renders, the sample `content.yaml` and the layouts
- `brand.read("voice")` and `brand.read("language")`: how the company
  sounds, the words it uses and the words it refuses
- `brand.read("proof")`: the only place a number comes from
- `transcript.read()` and `transcript.read(ref)` when a quote comes from
  a call
- `assets.read(seq)` when the ask names an earlier image

## Steps

1. Read the look the ask names. Take the ratio the ask names, else the
   first ratio the look lists.
2. On an edit, read the earlier image's `content.yaml` and keep every
   slot and the prompt the ask did not name. On a resize, keep every slot
   and the prompt and change only the ratio.
3. Write the slot text: HTML, one entry per slot the look declares, each
   inside its `max`. The number comes from `proof.md`; a quote is verbatim
   from the transcript or brand file it cites; a list has one point per
   item.
4. Paint with `image.paint(prompt, ratio)`: the prompt describes a scene
   and asks for no words, letters, numerals, signs or logos. On a resize
   the picture is painted fresh at the new ratio from the kept prompt,
   never reused.
5. Render with `image.render(look, fields, ratio, picture)` and write the
   render as `image.png`. A render that refuses a slot names it; shorten
   that slot and render again.
6. Write `content.yaml`: the slots and their text in the shape of the
   look's sample, plus `look`, `ratio` and `prompt`.
7. Write `claims.md`: one line per slot text that asserts something, as
   `<sentence> | proof | <heading in proof.md>` or
   `<sentence> | transcript | <ref>`. Then `build.md`: one short paragraph
   on what was made and what it cost in paints and renders.
8. When something the image needs is missing, a look that does not
   exist, a ratio it does not render, no proof for the number, write
   `held.md` naming it and stop.

## Rules

- The picture carries no words. The words are the slots; the card puts
  them over the picture.
- Slot text is HTML inside the slot's `max`: the words and the inline
  tags the look's sample uses, nothing else.
- Numbers come from `proof.md` only. A number with no proof line is not
  written.
- A quote is verbatim, in quotation marks, from the transcript or brand
  file its `claims.md` line cites.
- No hashtags, no emoji, no engagement bait.
- Every asserting slot has a line in `claims.md`. A line with no source
  holds the run, so text with no source is cut before it is written.
- An edit changes what the ask names and nothing else. A resize is a
  fresh picture at the new ratio, never a stretched one.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.
