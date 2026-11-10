# Stickman Explainer: Style Prompt

> A coloured story-cartoon for faceless Shorts, Reels and TikTok channels: stick-limbed figures with big round cream
> heads, simple faces and clothed bean bodies (a shirt and tie, a uniform, a hoodie) act out every beat inside fully
> coloured, softly shaded sets, with heavy white captions outlined in black. Every joint is code, so the figures walk,
> point, flick, cower and react on the beat, and they look the same in every scene.
> References (grammar only, never copy a channel's characters, sets or episodes): the coloured stick-figure story
> channels of vertical video (a suspect in a pink tiled cell between two officers; "what would you do" and "how it
> works" shorts) and newspaper strip cartoons. Ideas after stickman-video-director (MIT), rewritten for code: no
> prompt, image or asset of that project is used.

## 1. Essence, and what it is not

- **The figure tells the beat.** Each beat is one action that shows the line: a figure flicks a burr away, hides
  behind a door, carries a box too heavy for him, gets cornered by two officers. The caption says it, the figure *does* it.
- **Bodies, not lines alone.** The head is big (about a third of the figure across), the torso is a clothed bean that
  says who this is (a white shirt and a rust tie, a navy uniform with a belt and a badge, a green hoodie), and only the
  arms and legs are single black sticks with small dark hands and shoes. A figure is told apart by its clothes,
  hair or cap at a glance.
- **A real, coloured place in every shot:** a tiled cell with a ceiling lamp and a barred window, a meadow under a
  morning sky, a dry plain with mesas, an office with a water cooler. The set is drawn flat with soft gradients and
  no outlines, so the black-outlined cast pops off it.
- **Faces carry the feeling:** dots, brows and a mouth on the cream circle; the 16 emotions of the rig (scared, proud,
  confused, tired…) exaggerated, plus a `?` or `!` over the head; never realistic features.
- **Constant small motion:** a figure is never frozen for more than about 2.5 s: idle breathing, blinks, a nod, a
  prop that arrives on the beat, grass that bends where a foot passes.

Not Whiteboard (no drawing hand), not ink on paper alone (the old one-pen look is a variant now, §11), not Line Boil
(no boiling cel outlines on the sets), not 3D (everything is flat 2D in planes).

## 2. Materials & rendering

- **Figures:** `CAST` entries with `rig: 'toon'` (`characters.md` §5), drawn by the same `character()` call and model
  sheet as every rig. Options: `skin` (cream to peach; `#fde6d4` by default), `hair` + `hairStyle` (`side`,
  `short`, `bun`, `bald`, or `cap` with its `cap` colour for officers, drivers, chefs), `top` (the shirt or jacket),
  `collar`, `tie` + `tieStripe`, `belt` + `buckle`, `pants` (the band of trousers under the belt), `badge` (a star on
  the chest and the cap), `glasses`, `build` (torso width), `headSize`, `line` (limb width, 0.015 of the height).
  Outlines are near-black (`#1e1a17`), about 1.1 % of the figure's height on the head and torso.
- **Props that belong to the story** (the burr, the stolen cake, the phone) carry the same black outline as the cast,
  with a shaded side and a small highlight. `toonPoints()` gives the shin, hands, head and chest, so a prop rides on a
  figure exactly (a seed on the shin, a key in the hand).
- **Sets:** flat vector colour, no outlines, soft linear gradients (a sky, a wall darkening toward a corner), darker
  flat shapes for depth (a tiled wall's grout, a shadow under a bench), contact shadows under every figure (the rig
  draws its own) and every object. Interiors in one-point perspective (back wall, side walls, floor), exteriors in
  planes (sky, far hills or skyline, middle band, the ground the cast stands on, big blurred foreground blades or
  objects for depth).
- **Depth:** three to four planes at different `z` through `plane()`; the near plane can go soft with `cam.aperture`
  (0.5–1.5) in close shots.

## 3. Colour logic

- A full, bright palette per place, decided by its story: a candy-pink cell, a cool teal morning, a warm dry
  afternoon. The light arc of the film is said by the set's colours (cool to warm when the story travels far).
- **One story accent:** the object the film is about gets the one saturated colour nothing else uses (signal red
  `#e8463a` for a burr, a ticket, an alarm). Clothes stay in their own family (white, navy, rust, olive).
- Avoid a blue-to-violet ground over most of the film (it reads generated and `make.py` flags it); a sky leans teal or
  warm.

## 4. Type & captions

- **Captions are the look:** heavy white letters with a thick dark outline (`outlineCaption()`: weight 900, outline
  0.24 of the size, popping in word by word with a small overshoot), one line, 1–6 words, in the frame where they
  cover nothing that acts: by default the lower middle (about 68 % of the height) as the channels place them; above
  the heads (about 20 %) when the action happens low in the frame (feet, a prop on the floor). Never over a face or a
  hand doing the beat.
- A heavy geometric or rounded sans with the film's marks: Vietnamese `Be Vietnam Pro` 900 (made for its diacritics),
  otherwise a dealt display face checked with `fonts.py`; never a script face for captions.
- Signs inside the set (a door's "EXIT", a sticky note) are part of the set, short, in its own colour.

## 5. Motion quality

- Poses from `STICK_POSES` (idle, stand, walk, run, point, present, wave, cheer, think, facepalm, shrug, push, carry,
  sit, type, cower, dance, jump, nod, shake), blended with `next` / `k` over 0.15–0.4 s; any joint set directly with
  `joints` for a gag pose (a knee lifted to inspect a shin, an arm wound back for a flick) and eased between named
  joint sets.
- The walk: one rig cycle per beat (`p = t * 0.92 / beat`), so footfalls land on the eighths; the world moves at the
  stride's speed so feet do not skate.
- Anticipation, action, settle: wind up 0.1 s, the action in 2–4 frames, a spring settle (`MOTION.spring`, 0.5–0.7)
  and a held reaction of 0.5–1 s. Props that pop in use `MOTION.back` (s 2.0–2.2) on the beat.
- Secondary motion everywhere: grass bends away from a passing foot, a hooked prop turns a beat late, effect marks
  (three short dashes) burst on an impact or a pop.

## 6. Camera grammar

- A truck with a walking figure, a punch-in to an extreme close-up of the detail (a shin, a hand, an eye) with the
  background soft and streaming, a high wide map or plan view for distance, a slow push-in on the payoff.
- Scene changes by meaning: a cut on the bar, a match cut on the detail, a paper slide (wipe with the incoming page's
  edge shadowed) when the place changes far.

## 7. Sound palette

- Music-led for a wordless short (a real open-licence recording: whistling, ukulele, pizzicato; the cuts on its bars),
  voice-led when there is a narrator (the picture fits the real speech).
- Cartoon foley, recorded first: footsteps on the right ground (one per footfall, from the rig's strike times), pops
  for things that appear, a finger snap, a soft dirt thud, a spring boing, a creak; one low whoosh at most for a paper
  slide. Effects sit no more than about 6 dB under the music at their own moment.

## 8. Native moves (shot types)

| Shot | Use it for |
|---|---|
| Act-out | The beat as one action: flick, hide, carry, fall |
| Cornered | One figure between two others (officers, bosses): a reaction shot that sells the stakes |
| Detail punch-in | An extreme close-up of what matters (a shin with a burr, a hand on a key), background soft |
| Map or plan | A picture map from above with a dotted path drawing itself: distance and time in two seconds |
| Two figures | A contrast: what most people do / what works |
| Walk-through | A figure walks from one idea to the next across a wide set, the camera trucking with him |

## 9. Pitfalls of the medium

- A figure standing still while the caption talks: every beat an action or a reaction.
- Sets with black outlines like the cast: the figures stop popping; keep outlines for the cast and the story's props.
- Faces too small on a phone: in 9:16 a head needs about 200 px across (the figure about 40 % of the frame height).
- A note, mark or caption drawn over the face: notes leave the lips sideways, captions move above or below.
- Every colour saturated: keep the one accent for the story's object.
- The reference channel's exact characters or sets copied: build this story's own cast and places.

## 10. Engine

Quick `film.html`: `CAST` entries with `rig: 'toon'`, `character()` (model sheet: `?modelsheet=<name>`),
`toonPoints()` for props that ride on a figure, `outlineCaption()` for the captions, Canvas 2D only, flat planes with
`plane()` (and `cam.aperture` for a soft near plane). The look family is `glossy-commercial` with its grade and bloom
off (`LOOK.grade = ''`, `LOOK.bloom = 0`, no texture, no grain, no vignette) so the flat colours stay exact; the film
sets its own `PALETTE`. Sets are the film's own scene functions (gradients, filled shapes, seeded instances with
`lazy()`), never a stock background.

## 11. Variation space

- **Cast:** office (white shirt, rust tie), officers (navy uniform, cap with a badge, belt), street (hoodie, cap),
  kitchen (apron, bun); one silhouette per role.
- **Sets:** a candy-coloured interior (a pink tiled cell, a mint office), an outdoor day (meadow, city street), a
  warm dry place, night interiors lit by one lamp (a darker set, the cast's cream faces still lit).
- **Accent:** red, yellow or green; one per film.
- **Captions:** lower middle (default) or above the heads; white on black outline, or yellow for one emphasised word.
- **Ink-on-paper variant** (only when asked): `rig: 'stick'` figures drawn in one pen with `SKETCH` on grid paper
  with one accent colour, the `handmade-ink` family with its grade off (the kit's earlier Stickman look).
- **Density:** a new action every 1.5–3 s for shorts, every 4–6 s for long narrated videos.

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
