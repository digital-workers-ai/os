---
name: dw-newsletter
description: Write one email to the company's list from its own proof and voice, with a subject line that does not read like marketing. Drafts the text, builds the HTML after approval, answers a free-text ask over MCP.
user-invocable: true
argument-hint: "[the subject, or the slot]"
---

# Skill: Newsletter

One email. `newsletter.md` is the text a person reads and edits;
`newsletter.html` is what a sending tool would take. This skill never sends
anything and never asks who is on the list.

An email is opened in an inbox that is already losing. The subject line and
the first sentence are the whole negotiation; everything after them is a
reward for a decision the reader has already made.

## What it reads

`proof.md` first, because a good email is usually one real number and what it
meant. `voice.md` is how the company sounds; `audiences.md` says which of the
company's readers this one is for, and an email addressed to all of them is
addressed to none. `language.md` keeps the words theirs.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`calendar.read`, `transcript.read` and `files.write`, and nothing else is
reachable — no shell, no network, no database. If the email needs something
that is not there, write `held.md` naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run: `newsletter.md` only, no HTML,
nothing paid for. `build.md` says what the build will do and what it costs.

**build** runs after a person approved. The text is whatever survived their
edits, and `newsletter.html` is written from it — one column, system fonts,
the same words, no image the text depends on.

**chat** is an ask over MCP with no proposal behind it. It behaves like build
and the result goes back to the caller and into the Library marked "from
chat". Nothing was approved, so every rule that would hold a draft holds here.

## Steps

1. Find the one thing worth an email. Usually a line in `proof.md`: a number
   that moved, a thing the company now does that it did not. An email with no
   such thing is not written, and `held.md` says so.
2. Write the first sentence. It carries the whole email: what happened, in
   plain words, with no throat-clearing, no "hope you're well", no promise of
   what the email is about to do.
3. Write the body — three or four short paragraphs. The number, what it
   means, and the one thing the reader can do about it.
4. Write the subject line last, from the first sentence. Under six words, all
   lowercase, and it names the thing rather than selling it.
5. Write `claims.md`. One line per asserting sentence: the sentence, then
   `proof`, `transcript` or `competitor_ad`, then the ref, separated by ` | `.
   An unsourced sentence is rewritten or cut.
6. Write `build.md`, then `newsletter.md` through `files.write`. In build and
   chat write `newsletter.html` beside it, with the subject line on the first
   line and nothing that needs a stylesheet to make sense.

## Rules

- The subject line is under six words, lowercase, and reads like a person
  wrote it to one other person. No colons splitting a claim from a promise,
  no "introducing", no "you won't believe", no urgency that is not real.
- The first sentence carries the load. If it could be cut without loss, it
  should have been.
- One link. The email points at one thing, and a reader who clicks nothing
  still got the point.
- Numbers come from `proof.md` and nowhere else.
- A quote appears verbatim in the transcript or brand file it cites.
- `newsletter.html` says exactly what `newsletter.md` says. Nothing appears in
  one that a person did not read in the other.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the sentence quoted,
  and stop.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- Subjects get cut, not written. Draft the honest sentence, then keep the
  three words of it that name the thing (#186, 2026-08-28).
- One link an email. A second link costs the first one most of its clicks
  (#191, 2026-09-01).
