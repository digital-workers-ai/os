---
name: dw-video
description: Make one vertical video ad from a look — a validated content.yaml and a storyboard on a draft, avatar scenes, transcription, composition and export on a build, with the render count stated before anything is paid for.
user-invocable: true
argument-hint: "[the idea, and the look]"
---

# Skill: Video

One vertical video ad. `content.yaml` is the whole script and every on-screen
field, scene by scene, in the vocabulary the look defines. A draft stops
there and assembles a storyboard from the look's existing frames. A build
turns it into `video.mp4`.

A build costs real renders — one per avatar scene, plus transcription,
composition and export. Say how many before starting. A person approving a
video is approving a bill.

## What it reads

`looks.read` returns the look: its scene vocabulary, the fields each scene
takes, the character limit measured for each field, and the frames a
storyboard is built from. `proof.md` is the only place a number in a scene or
a line of script may come from. `voice.md` is how the avatar talks, which is
how the company talks with the punctuation taken out.

The toolbelt is fixed. This skill uses `brand.read`, `brand.list`,
`looks.read`, `calendar.read`, `transcript.read`, `video.plan`, `video.render`
and `files.write`, and nothing else is reachable — no shell, no network, no
database.
`video.plan` checks a `content.yaml` against the look and answers with what
breaks; it renders nothing and costs nothing. `video.render` does the whole
pipeline behind one call. If the video needs something that is not there,
write `held.md` naming what is missing, and stop.

## Modes

**draft** is the marketer's daily run: `content.yaml`, validated through
`video.plan` until it comes back clean, and `storyboard.html` assembled from
the look's own frames with each scene's text dropped in. No avatar is
rendered, nothing is transcribed, nothing is paid for. `build.md` names the
render count and the stages.

**build** runs after a person approved. The `content.yaml` is the approved one
— if it differs from the draft, say so rather than quietly using the new one.
`video.render` renders the avatar scenes, transcribes them, composes and
exports, reporting each stage as it finishes.

**chat** is an ask over MCP with no proposal behind it. It behaves like build,
so it spends money nobody approved: state the render count in the answer
before calling `video.render`. The result goes back to the caller and into the
Library marked "from chat".

## Steps

1. Read the look through `looks.read`. The scene vocabulary is closed: the
   look's list is the whole list, and a type not on it does not exist.
2. Settle the one claim the ad makes, from `proof.md`, and the order of scenes
   that gets a viewer to it inside the first three seconds.
3. Write `content.yaml`: every scene, its type, its fields, the avatar script
   for the scenes that have one. Count characters against the look's limits as
   you write.
4. Run `video.plan`. Fix exactly what it names and run it again. Three failed
   passes on the same field means the scene is wrong, not the wording: write
   `held.md` and stop.
5. Write `claims.md`. One line per stated number or claim, on screen or in the
   script: the text, then `proof`, `transcript` or `competitor_ad`, then the
   ref, separated by ` | `.
6. Write `build.md`: the render count, the stages, and the estimate. On a
   draft, assemble `storyboard.html` and stop here.
7. On a build or a chat call, `video.render`, then write every file it
   produces through `files.write` — the mp4 and the composition beside it.

## Rules

- A draft never renders an avatar. The storyboard is the look's existing
  frames with text in them; that is the whole point of a draft.
- `video.plan` comes back clean before anything is rendered. A render started
  on an invalid `content.yaml` wastes the whole run, not one scene.
- Numbers come from `proof.md` and nowhere else, on screen and in the script.
- A quote appears verbatim in the transcript or brand file it cites.
- The render count is stated before the first render, every time, in every
  mode. A build that costs more than the draft promised says so and stops.
- Never invent a scene type, a field or a look. Looks change by pull request.
- Nothing is printed. The asset is the files written through `files.write`.
- A claim you cannot source holds the draft: `held.md`, the line quoted, and
  stop.

## Lessons

The taste agent appends here, one line each, when a correction has shown up
three times. Nothing else in this file changes without a person.

- The first scene is a sentence a person would actually say out loud, not a
  title card the viewer has to read (#195, 2026-09-03).
- Script to the look's measured seconds, not to the word count. A scene that
  overruns gets cut mid-word in the export (#207, 2026-09-10).
