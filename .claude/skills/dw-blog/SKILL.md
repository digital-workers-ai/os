---
name: dw-blog
description: Write one article that says the useful thing first, built from the company's pillars, proof and objections, and from what competitors actually published when the theme is competitive.
user-invocable: true
argument-hint: "[the theme, the slot, or a swipe item id]"
---

# Skill: Blog

One article: `post.md`, front matter on top, the body below. Written for
someone who arrived from a search with a question and will leave the moment
the page starts warming up.

## What it reads

`pillars.md` says what the company has standing to write about. `proof.md` is
the only place a number may come from. `objections.md` is what the reader
already thinks is wrong with this, and an article that does not answer at
least one of them is a brochure. `language.md` keeps the reader's own words in
the headings, where a search will find them.

When the theme is competitive, `swipe.search` returns what competitors have
published — pages, posts and ads with their labels and the quote each label
came from — and `swipe.read` opens one of them in full. Their copy is
material to answer, never to borrow.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`calendar.read`, `swipe.search`, `swipe.read`, `transcript.read` and
`files.write`, and nothing else is reachable — no shell, no network, no
database. If the article needs something that is not there, write `held.md`
naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run and writes the whole article. Text costs
almost nothing, so a blog draft is the real thing rather than an outline; a
person edits prose, not a promise of prose.

**build** runs after approval and is close to a formality here: the text is
whatever survived the edits and the front matter is filled in. A build that
finds the text unchanged says so rather than quietly rewriting it.

**chat** is an ask over MCP with no proposal behind it. It behaves like build
and the result goes back to the caller and into the Library marked "from
chat". Nothing was approved, so every rule that would hold a draft holds here.

## Steps

1. Settle the question the article answers, in the reader's words. Check it
   against `pillars.md`; a question the company has no standing on is not
   answered here.
2. If the theme is competitive, read the competitor material through
   `swipe.search` before writing. Note what they claim and what they leave
   out. Never name them in the article.
3. Answer the question in the first hundred words. The reader who stops there
   should have got what they came for.
4. Build the sections around what a reader would ask next, one per section,
   each headed with the words they would use. Every section should still make
   sense pulled out on its own.
5. Answer at least one objection from `objections.md` in the reader's framing,
   not as a straw man you built to knock down.
6. Write `claims.md`. One line per asserting sentence: the sentence, then
   `proof`, `transcript` or `competitor_ad`, then the ref, separated by ` | `.
7. Write `build.md`, then `post.md` through `files.write`, front matter
   carrying title, description, date and the pillar it sits under.

## Rules

- The useful thing goes first. No setup, no history of the industry, no
  paragraph explaining what the article will explain.
- Sections stand alone. A section that only makes sense after the one above
  it belongs merged into it.
- No conclusion that restates the article. Stop at the last useful sentence.
- Numbers come from `proof.md` and nowhere else.
- A quote appears verbatim in the transcript, brand file or competitor entity
  it cites, and a competitor's line is answered, never repurposed.
- No competitor is named. Answer what they claim, never say who claimed it.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the sentence quoted,
  and stop.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Cut the first two paragraphs after drafting. The article almost always
  starts at the third (#174, 2026-08-19).
- Headings get the reader's words from `language.md`, not the company's
  internal name for the thing (#182, 2026-08-25).
