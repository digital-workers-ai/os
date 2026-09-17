---
name: dw-blog
description: Write one blog post with front matter that gives the useful thing first, heads its sections in the reader's words and answers an objection
makes: blog
user-invocable: true
argument-hint: "[the question the piece answers, or the slot theme]"
---

# Skill: Blog

Make one blog post from the ask. The ask is a question readers have, a
calendar slot's theme, or a call whose answer deserves a page. The post is
the files this skill writes through `files.write`; nothing it says on the
way is kept.

## What it reads

- `brand.read("brand-brain")`: what the company is and does
- `brand.read("voice")` and `brand.read("language")`: how it sounds, the
  words it uses and the words it refuses
- `brand.read("pillars")` and `brand.read("audiences")`: the pillar the
  post files under and who is reading
- `brand.read("objections")`: the objections a post answers
- `brand.read("proof")`: the only place a number comes from
- `transcript.read()` and `transcript.read(ref)` when the ask names a call
- `calendar.read(slot)` when the ask names a slot
- `assets.read(seq)` when the ask names an earlier post

## Steps

1. Read the brand files, then the call or slot the ask names. On an edit,
   read the earlier post first and keep every section the ask did not
   name.
2. Pick the one question the post answers, the pillar it files under, and
   at least one objection from `objections.md` it answers.
3. Write `post.md`. Front matter: `title`, `description` in one sentence,
   `date` as YYYY-MM-DD from the slot or the ask, `pillar` as named in
   `pillars.md`. Then the body: the answer in the first paragraph,
   sections under headings in the reader's words, the objection answered
   in its own section, and an ending that says what to do next.
4. Write `claims.md`: one line per sentence that asserts something, as
   `<sentence> | proof | <heading in proof.md>` or
   `<sentence> | transcript | <ref>`. Then `build.md`: one short paragraph
   on what was made and what it cost in reads.
5. When something the post needs is missing, no proof for the number, a
   call that is not there, no date to put in the front matter, write
   `held.md` naming it and stop.

## Rules

- The useful thing sits in the first paragraph. No "in this post we
  will", no history of the problem before the answer.
- Headings are what a reader would say or search for, never the
  company's own terms or a product name on its own.
- At least one objection is answered, named the way a reader says it,
  then met with what `proof.md` or the transcript shows.
- Numbers come from `proof.md` only. A number with no proof line is not
  written.
- A quote is verbatim, in quotation marks, from the transcript or brand
  file its `claims.md` line cites.
- No link the brand files do not carry. The skill cannot open a page, so
  it never invents one.
- No hashtags, no emoji, no engagement bait, no closing question written
  to draw comments.
- Every asserting sentence has a line in `claims.md`. A line with no
  source holds the run, so a sentence with no source is cut before it is
  written.
- An edit changes what the ask names and nothing else.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.
