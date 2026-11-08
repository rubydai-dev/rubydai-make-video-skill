# Stickman Explainer: Style Prompt

> A faceless-channel explainer drawn in one pen: stick figures with circle heads and simple, readable faces act out
> every idea on a clean paper ground, beside hand-drawn props, arrows and one accent colour. Every joint is code, so
> the figures walk, point, push and react on the narration's beat.
> References (grammar only, never copy): the stick-figure explainers of faceless YouTube channels (psychology,
> self-help, business and tech parables) and classic whiteboard comics. Ideas after stickman-video-director (MIT),
> rewritten for code: no prompt, image or asset of that project is used.

## 1. Essence, and what it is not

- **The figure tells the idea.** Each beat is one action that shows the sentence: a figure pushes a wobbling stack,
  points at a rising bar, hides behind a door, carries a too-heavy box. The narration says it, the figure *does* it.
- **One pen for everything:** figures, props, arrows and handwritten labels share one line weight and one wobble, so the
  world reads as one drawing.
- **Faces carry the feeling:** a circle, two dots, brows and a mouth. The 16 emotions of the rig (scared, proud,
  confused, tired…) are enough; exaggerate them, never add realistic features.
- **Constant small motion:** a figure is never frozen for more than about 2.5 s; idle breathing, blinks, a nod, a
  hand that taps, a prop that arrives on the spoken word.

Not Whiteboard (no drawing hand, no strokes being drawn by a marker on camera), not One-line (the line breaks between
objects), not Line Boil (no colour cel fills; ink on paper).

## 2. Materials & rendering

- **Ground:** off-white paper (`#f8f6f1`) with a faint square grid (5 % ink), or plain paper; the dark variant is a
  near-black ground with a cream ink.
- **Figures:** `CAST` entries with `rig: 'stick'` (`characters.md` §5): circle head filled with the ground colour,
  single-line torso and limbs, small ink hands and oval feet; options `tuft` (hair strokes), `hat` (a beanie),
  `scarf`, `glasses`, `line` (stroke width, default 0.022 of the height).
- **Props and sets:** drawn with `SKETCH` (`line`, `shape`, `rect`, `ellipse`, `hatch`): white-filled objects with an
  ink outline and occasional hatching for shadow; the accent colour fills only the one object that matters.
- **The boil (optional):** `boil: true` on the figure and `{ boil: true, t }` on `SKETCH` calls make the line tremble
  on twos (3 drawings); use it on the whole frame or not at all.

## 3. Colour logic

- Ink and paper, plus **one accent** (signal red `#e8463a` by default) for the thing the sentence is about: the rising
  bar, the alarm, the play button, the one box that falls. A second colour only when the story compares two sides.
- Never colour the figures' bodies; a figure is told apart by its silhouette (tuft, hat, scarf, height).

## 4. Type & subtitles

- A handwritten display face for labels on the board (`fonts.py search "handwritten"`, checked for the film's
  language), short: 1–4 words.
- Subtitles in one clean sans, **one line**, cut at natural phrase boundaries and real pauses, never a mechanical word
  count; on paper, dark text on a light label; never covering a figure's face or hands.

## 5. Motion quality

- Poses from `STICK_POSES` (idle, stand, walk, run, point, present, wave, cheer, think, facepalm, shrug, push, carry,
  sit, type, cower, dance, jump, nod, shake), blended with `next` / `k` and an ease (`EASE.inOut`) over 0.2–0.4 s;
  any joint can be set directly with `joints`.
- Anticipation and settle: a figure winds up (`k` overshoots slightly with `MOTION.back`) and holds the reaction
  0.5–1 s. Feet stay on the ground by themselves (the rig plants the lower foot).
- Props move on the spoken word: a note slides in, a box drops, an arrow draws itself (`line` with a growing point
  list); hand-drawn effect marks (wobble lines, sweat, `!` and `?` with `mark`) on the beat.

## 6. Camera grammar

- Mostly locked; a slow push-in on the reveal, a quick punch-in on a reaction, a truck to follow a walking figure.
- Scene changes by meaning: a cut, a slide of the whole paper (wipe), or a figure walking off one edge and on the next.

## 7. Sound palette

- Voice-led: the narration sets the timing; the picture fits the real speech, never the other way round (no slowing or
  padding the voice).
- Light, causal effects at voice-first levels: pencil scratch when a line draws, paper slide, a soft pop when a prop
  arrives, a wobble on the falling stack, a woodblock on a comic beat (`samples.py get woodblock`); a quiet bed.

## 8. Native moves (shot types)

| Shot | Use it for |
|---|---|
| Act-out | The sentence as one action: push, carry, hide, fall |
| Board reveal | A figure presents a chart or list that draws itself |
| Two figures | A contrast: what most people do / what works |
| Thought bubble | What the figure imagines: a small scene inside a cloud |
| Pile-up | Pressure growing: objects stack and wobble on the beat |
| Walk-through | A figure walks from one idea to the next across a wide paper |

## 9. Pitfalls of the medium

- A figure standing still while the voice talks: give every beat an action or a reaction.
- Too many colours turn the clean page into clip art; keep one accent.
- Faces too small to read on a phone: a face needs about 120 px of figure height.
- Text that repeats the narration word for word; labels add, the voice tells.

## 10. Engine

Quick `film.html`: `character()` with a `rig: 'stick'` cast member (the model sheet works the same:
`?modelsheet=<name>`), `SKETCH` for every prop and set, Canvas 2D only. The look family is `handmade-ink`; set
`PALETTE` to the paper and ink above and turn the family's grade off (`LOOK.grade = ''`) so the accent stays clean.

## 11. Variation space

- **Ground:** paper with grid, plain paper, warm cream, or dark (cream ink on near-black).
- **Accent:** red, blue, green or a brand colour; one per film.
- **Line:** clean (no boil) or boiling on twos; thin (0.018) or bold (0.028).
- **Density:** a new action every 2–4 s for shorts, every 4–6 s for long narrated videos.

## Optional: redraw with an AI image model, after the film works

Off by default. Offer it only **after the code draft is approved** (the idea, the beats, the timing and the motion are
locked), as one question with the honest trade-off:

- **What it changes:** the static sets and props get richer detail (shading, texture, objects) from an image model,
  using each scene's code frame as the reference image so the layout stays the same.
- **What stays code:** the figures, so they keep moving, stay identical across scenes and stay on the beat. Redrawing
  the figures too is possible, but then they become still images that only pan, zoom and slide.
- **Rules:** ask which model or API to use, and say the cost before any paid call; generate the sets as layers behind
  the code-drawn figures; every generated image gets a row in `LICENSES.csv` (engine, model, date, terms); the code
  version stays the master, so the film can always be rendered without the images.
