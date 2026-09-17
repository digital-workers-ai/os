---
name: dw-newsletter
description: Write one issue of the newsletter as Markdown and as one-column HTML that say the same thing, with every number taken from proof
makes: newsletter
user-invocable: true
argument-hint: "[the theme, or what this issue should say]"
---

# Skill: Newsletter

Make one issue of the newsletter from the ask. The ask is a theme, a
calendar slot's theme, or what this issue should say. The issue is the
files this skill writes through `files.write`; nothing it says on the way
is kept.

## What it reads

- `brand.read("brand-brain")`: what the company is and does
- `brand.read("voice")` and `brand.read("language")`: how it sounds, the
  words it uses and the words it refuses
- `brand.read("pillars")` and `brand.read("audiences")`: the subject this
  issue serves and who opens it
- `brand.read("objections")`: what readers push back on, to answer one
- `brand.read("proof")`: the only place a number comes from
- `transcript.read()` and `transcript.read(ref)` when the ask names a call
- `calendar.read(slot)` when the ask names a slot
- `assets.read(seq)` when the ask names an earlier issue

## Steps

1. Read the brand files, then the call or slot the ask names. On an edit,
   read the earlier issue first and keep every section the ask did not
   name.
2. Pick the one thing this issue says, the pillar it serves and the
   audience it is written for. Pick one objection from `objections.md`
   the issue answers on the way.
3. Write `newsletter.md`. Line one is the subject line, under six words.
   Then a blank line, then the email: a first paragraph that says the
   useful thing, sections a reader can skim by their headings, the
   objection answered where it comes up, and one ask at the end.
4. Write `newsletter.html`: one column, at most 600 pixels wide, inline
   styles only, the same words as `newsletter.md` in the same order as
   headings and paragraphs. No image the text depends on; a reader whose
   mail client shows no images loses nothing.
5. Write `claims.md`: one line per sentence that asserts something, as
   `<sentence> | proof | <heading in proof.md>` or
   `<sentence> | transcript | <ref>`. Then `build.md`: one short paragraph
   on what was made, which files, and what it cost in reads.
6. When something the issue needs is missing, no proof for the number, a
   call that is not there, write `held.md` naming it and stop.

## Rules

- The subject line says what the issue says, in under six words. No
  "you won't believe", no "quick question", no reader's name.
- The Markdown and the HTML are one email: same words, same order. A
  reader of either gets the whole issue.
- The useful thing comes first. The company's own news, if any, comes
  after it.
- One ask per issue, at the end, in one sentence.
- Numbers come from `proof.md` only. A number with no proof line is not
  written.
- A quote is verbatim, in quotation marks, from the transcript or brand
  file its `claims.md` line cites.
- No hashtags, no emoji, no engagement bait: no ask whose only purpose is
  a reply, a forward or a click.
- Every asserting sentence has a line in `claims.md`. A line with no
  source holds the run, so a sentence with no source is cut before it is
  written.
- An edit changes what the ask names and nothing else.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.
