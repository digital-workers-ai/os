---
name: dw-post
description: Write one LinkedIn post in the company's voice from its own proof, every claim carrying its source. Drafts text cheaply, builds the images after a person approves, answers a free-text ask over MCP.
user-invocable: true
argument-hint: "[the idea, the slot, or a transcript id]"
---

# Skill: Post

One LinkedIn post. `post.md` is the text; a build puts at most two images
beside it. One idea, said once, in the company's own words, for a reader who
has scrolled past forty posts today and stopped on none of them.

## What it reads

`voice.md` is how the company sounds. `pillars.md` is what it is allowed to
be about, so the idea comes from a pillar or the post has no reason to exist.
`audiences.md` names who is being addressed and `language.md` gives their own
words back to them. `proof.md` is the only place a number may come from;
there is no second place. When the input names a call, `transcript.read`
returns it and one sentence from it may be quoted.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`calendar.read`, `transcript.read`, `looks.read`, `image.render` and
`files.write`, and nothing else is reachable — no shell, no network, no
database. If the post needs something that is not there, write `held.md`
naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run: the text and nothing else. No render
is paid for. `build.md` says what the build would render, so a person
approving knows the price before paying it.

**build** runs after a person approved the proposal. The text is whatever
survived their edits, and the images render through `image.render` on an
image look, under `dw-image`'s rules: fields inside the look's limits, text as
HTML, background generated only here.

**chat** is an ask that arrived over MCP with no proposal behind it. It
behaves like build — real images, a real post — and the result goes back to
the caller and into the Library marked "from chat". Nothing was approved, so
every rule below that would hold a draft holds this too.

## Steps

1. Settle the one idea. From the argument, or from the slot's theme through
   `calendar.read`. Read `pillars.md` and say which pillar it sits under; a
   post under no pillar is not written.
2. Read `voice.md`, `audiences.md`, `language.md`. Read `proof.md` before
   writing, not after, so the post is built out of what can be proved rather
   than trimmed down to it.
3. Write the opening line first and alone. It is concrete: a thing that
   happened, a thing someone said, a thing that is true of the reader's
   Tuesday. Not a statistic, not a question, not a premise.
4. Write the body. Short paragraphs, the useful thing early, one idea
   carried to its end. At most one quote, lifted verbatim from the
   transcript or brand file it cites.
5. Write `claims.md`. Every sentence that asserts something gets one line:
   the sentence, then `proof`, `transcript` or `competitor_ad`, then the ref,
   separated by ` | `. A sentence with no line is an unsourced claim: rewrite
   it or cut it.
6. Write `build.md` — one short paragraph on what a build renders and what it
   costs — then `post.md` through `files.write`. In build and chat, render the
   images and write those too.

## Rules

- One idea. A post that could be split into two posts is two posts.
- The opening line is concrete and it is never a statistic. A number may
  appear later, and only if `proof.md` holds it.
- At most one quote, and it appears verbatim in the transcript or the brand
  file named beside it. A quote tightened, trimmed or smoothed is not a quote.
- No hashtags. No emoji. No engagement bait, no "thoughts?", no line that
  exists only to be commented on.
- Numbers come from `proof.md` and nowhere else. A number that is not there
  cannot be written, however sure you are of it.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft. Write `held.md` with the sentence
  quoted and stop; a held draft is worth more than a wrong one.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Never lead with a statistic. The number lands after the reader is already in
  the sentence, not before (#209, 2026-09-12).
- One quote a post, verbatim. Two quotes and the post is quoting rather than
  saying (#198, 2026-09-05).
