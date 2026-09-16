---
name: dw-post
description: Write one LinkedIn post on one idea and render its image on a look, with every number taken from proof
makes: post
user-invocable: true
argument-hint: "[the idea, the slot theme, or a call to quote]"
---

# Skill: Post

Make one LinkedIn post from the ask and one image to carry it. The ask is
an idea, a calendar slot's theme, or a call to quote from. The post is the
files this skill writes through `files.write`; nothing it says on the way
is kept.

## What it reads

- `brand.read("voice")` and `brand.read("language")`: how the company
  sounds, the words it uses and the words it refuses
- `brand.read("pillars")` and `brand.read("audiences")`: which subject the
  post serves and who reads it
- `brand.read("proof")`: the only place a number comes from
- `transcript.read()` to find a call the ask names, then
  `transcript.read(ref)` for its words
- `calendar.read(slot)` when the ask names a slot: its theme, look and ratio
- `looks.read(name)`: the look's slots and their limits, before rendering
- `assets.read(seq)` when the ask names an earlier post

## Steps

1. Read the brand files, then the call or slot the ask names. On an edit or
   a resize, read the earlier post first and keep every line and choice the
   ask did not name.
2. Pick one idea from the ask and the one pillar it serves. When the ask
   offers several ideas, take the first and leave the rest.
3. Write `post.md`: a first line that states something concrete, a body a
   reader can use without clicking anything, and at most one quote, copied
   word for word from the transcript or brand file it comes from. Under
   1,300 characters.
4. Take the look and ratio the ask names, else `stat-card` at `1:1`. Fill
   the look's slots from the post, inside each slot's `max`, with the
   number the post leans on.
5. Paint with `image.paint(prompt, ratio)`: the prompt describes a scene
   and asks for no words, letters, numerals, signs or logos. Render the
   card over it with `image.render(look, fields, ratio, picture)` and write
   the render as `image.png`.
6. Write `claims.md`: one line per sentence that asserts something, as
   `<sentence> | proof | <heading in proof.md>` or
   `<sentence> | transcript | <ref>`. Then `build.md`: one short paragraph
   on what was made, which files, and what it cost in reads, paints and
   renders.
7. When something the post needs is missing, no proof for the number, a
   call that is not there, a look that does not exist, write `held.md`
   naming it and stop.

## Rules

- One idea per post. A second idea is a second post.
- The first line states a thing. It never asks a question, never promises
  a thread, never opens with "unpopular opinion".
- Numbers come from `proof.md` only. A number with no proof line is not
  written, and is not rounded into a vaguer one either.
- A quote is verbatim, in quotation marks, from the transcript or brand
  file its `claims.md` line cites. No paraphrase in quotation marks.
- No hashtags, no emoji, no engagement bait: no "agree?", no "repost if",
  no "comment X and I'll send it".
- The picture prompt describes a scene, never text. The card carries the
  words.
- Every asserting sentence has a line in `claims.md`. A line with no
  source holds the run, so a sentence with no source is cut before it is
  written.
- An edit changes what the ask names and nothing else. A resize keeps the
  words and paints a fresh picture at the new ratio.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.
