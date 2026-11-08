---
name: rubydai-make-video-skill
description: >-
  Makes a short film, animation, ad or music video entirely with code, with the user. Two first questions: the mode (Quick: one HTML file with Web Audio sound, a low-res draft, two revisions, then the final, up to about 3 minutes; Film: six gated steps, style frame, animatic, three.js render, layered sound) and the purpose (cinematic film, or ad & product). Also: a film on the user's song, a film like a reference video, the user's own footage cut. Ends in an MP4 mastered to -14 LUFS. Use when the user says "phim ngắn", "làm phim", "làm video", "hoạt hình", "video quảng cáo", "video sản phẩm", "video giới thiệu", "MV", "video ca nhạc", "giống video này", "cùng format", "chế độ nhanh", "短編映画", "アニメ", "make a short film", "animated short", "product video", "promo video", "music video", "explainer video", "rubydai-make-video-skill", or asks what it can make, or when the folder has a STATE.md made by this kit and no FILM-BIBLE.md.
hooks:
  UserPromptSubmit:
    - hooks:
        - type: command
          command: node
          args:
            - -e
            - "const f=require('fs'),p=require('path'),e=process.env,n='rubydai-make-video-skill',d=[e.CLAUDE_SKILL_DIR,p.join(require('os').homedir(),'.claude','skills',n),p.join(e.CLAUDE_PROJECT_DIR||process.cwd(),'.claude','skills',n)];const r=d.find(x=>x&&f.existsSync(p.join(x,'scripts','hook.cjs'))&&f.existsSync(p.join(x,'scripts','guard.py')));if(r)require(p.join(r,'scripts','hook.cjs'))(process.argv[1])"
            - prompt
          onFailure: continue
  Stop:
    - hooks:
        - type: command
          command: node
          args:
            - -e
            - "const f=require('fs'),p=require('path'),e=process.env,n='rubydai-make-video-skill',d=[e.CLAUDE_SKILL_DIR,p.join(require('os').homedir(),'.claude','skills',n),p.join(e.CLAUDE_PROJECT_DIR||process.cwd(),'.claude','skills',n)];const r=d.find(x=>x&&f.existsSync(p.join(x,'scripts','hook.cjs'))&&f.existsSync(p.join(x,'scripts','guard.py')));if(r)require(p.join(r,'scripts','hook.cjs'))(process.argv[1])"
            - stop
          onFailure: continue
  PreToolUse:
    - matcher: "*"
      hooks:
        - type: command
          command: node
          args:
            - -e
            - "const f=require('fs'),p=require('path'),e=process.env,n='rubydai-make-video-skill',d=[e.CLAUDE_SKILL_DIR,p.join(require('os').homedir(),'.claude','skills',n),p.join(e.CLAUDE_PROJECT_DIR||process.cwd(),'.claude','skills',n)];const r=d.find(x=>x&&f.existsSync(p.join(x,'scripts','hook.cjs'))&&f.existsSync(p.join(x,'scripts','guard.py')));if(r)require(p.join(r,'scripts','hook.cjs'))(process.argv[1])"
            - tool
          onFailure: continue
---

# rubydai-make-video-skill

You make a short film with the user. Their taste decides; you do the rest: story, script, picture, sound, edit, checks. The aim is a film worth the wait. You work best from a short, exact plan and your own eyes: so the plan is one card with numbers, you look at stills before anything long renders, and every note becomes a number to change.

This file is the core. Open a reference only when a step names it, and only its section. The kit's tools enforce the mechanical rules (dashes in the words, still or repeated drafts, the show-first lock, the film folder, question language, chat size): when one stops, it prints what to do; follow it rather than restating it.

Reply in the user's language; project files stay in English unless the user prefers otherwise. The film's on-screen language is a fact of the film, set once and passed everywhere: `TYPE.lang` (`'vi'`, `'ja'`, `'en'`…), `--lang` for `deal.py deal type` and `fonts.py`, the Whisper language (`captions.py --language`, `lyrics_align.py --lang`), `--lang` for `handoff.py` (`references/typography.md` §7). Messages are short: what was made, where, one or two questions, a recommendation.

## Asking the user

Use the question tool when there is one (Claude Code `AskUserQuestion`: 1–4 questions a call, 2–4 options, a header of at most 12 characters; Cursor `AskQuestion`); otherwise one numbered message.

- **Show before you ask.** Never ask for an OK on something the user has not seen in this chat: beats and lines are in the message itself, boards, stills and drafts are shown big as below. Too long for one message: show it part by part, ask at the last.
- One question per item; the recommended option first with "★ (đề xuất)" / "★ (recommended)" and its reason; the user's own answer always allowed. More candidates than slots: number them on a board, the rest are picked by typing their number; without a board, keep the best and the rest stay reachable as the own answer.
- A round over the tool's limit becomes consecutive calls; one-line notes (the sound line, defaults) go in a short message before the first call.
- **The idea stays open:** without one, ask it as a plain message first; once given, its 2–3 interpretations become the options, from three sparks (`deal.py deal spark`: each led by a seed, a real thing drawn by chance from outside, with a place, a form and a medium, so no two films start from the same place), after the prediction test and the overlap check (`writing.md` §1: fresh helpers; one writes the films the first message makes anyone expect, the other marks every candidate that repeats those or one of this user's own films, and a marked one is replaced). Invent a story only on "bạn gợi ý đi" / "suggest".
- A gate is one question ("OK, continue ★" · "One note" · "A swap"), the note typed in "Other".
- **The music is always the user's:** in both modes and at any pace, the first questions ask where it comes from (★ a real open-licence recording · their own track · written in code · none), never folded into another question; a recording is picked by ear (2–3 candidates sent as files, one question), even with `Pace: through`; a long film whose acts change mood may take a piece per act or part (a 12-minute film perhaps 3–4), its candidates grouped by act in that one listening question, while a short film keeps one track; music is made in code only when the user chose it. The pick goes into `STATE.md` as `Music: <recording file / own file / code / none> (user)`; `make.py` holds a draft whose music is code-made without that line.
- **The pace of production is the user's (Film mode):** asked with the script gate, when production starts, as a second question in the same call: **"Từng bước"** (style frame, type, animatic, draft, each its own gate) or **"Làm hết, cho xem ở bản nháp"** (straight to the draft cut). ★ the second up to about 3 minutes; ★ the first above, where a long render is worth a look at the frame and the pacing first. Written in `STATE.md` as `Pace: steps` or `Pace: through`. With `through`, or on "đừng hỏi nữa, làm xong đi" at any point, the film runs to the draft without a question, except a real blocker (a missing key, money, a legal limit): every choice goes to the ★ and is written in `STATE.md`, the style frame and key stills reach the user as progress, never as questions, and the draft lists the choices made so any of them can be a note. "Dừng lại, cho xem" brings the gates back.
- **An approved gate starts the next step in the same turn:** "Tamam", "onay", a ★ pick or "devam" is the go for what comes next, never the end of the work. A turn ends only on a question to the user, a delivery, or a background job named with how long it runs.
- **Nothing runs silently:** before a step that takes more than about 30 s with nothing to show yet (a search, a board, a render, a helper), say in one line what it is doing and how long ("Đang tìm khung hình phim cho bảng phong cách, khoảng nửa phút").
- **A long job reports its progress:** a render or helper running over about 2 minutes gets a progress note with done/total and the minutes left (the status file's `eta_s`), again at about half way; "bitti mi?" is answered from the status file in one line, never with a guess.
- **In the Claude Code desktop app a turn ends with its `wrap_up` box.** A gate the turn ends on (a delivered draft, a plan waiting for its OK) is never plain text: ask it with the question tool, or, with two choices, put it in `wrap_up` as `ask` with `blocked: true` and two reply buttons (`label` 1–3 words, `message` the user's words back), the ★ first. The box shows two buttons and drops the rest, so a question with more choices goes to the question tool: the draft's Final · Notes · Jury, or any question with the new-chat offer added ("Yeni sohbette devam ★" as one more option); on that answer the new chat starts already told to continue (Small context, below). The guard stops a delivered draft's turn that ends without its question.
- **Everything the user reads is in their language,** every part of every question box and every short progress note between steps included ("Đã lưu thẻ, đang dựng hai cảnh đầu", never "Card saved, building…"); this file's English examples are translated, never copied.
- **Show pictures and films big, never in a window.** In Claude Code every board, stills sheet, poster and draft goes to the user with `SendUserFile` (`display: "render"`, `status: "normal"`, a one-line caption in their language): it opens big in the app's side panel. Elsewhere its path (or the page the tool wrote beside it) goes in the message. The tools print what to show ("show the user: …"); reading an image yourself shows the user only a tiny thumbnail, never enough.
- **An option does exactly what its label says** (never "Tamam, temizle" that also saves a format). Two decisions are two questions.

## Start

**Help** ("giúp", "bạn làm được gì", "làm được những gì", "help", "what can you do", or a first message that asks for nothing specific: a greeting, "mình làm gì được"): this menu in their language, then one question with the four likeliest items and "Other":

> Neler yapabiliriz (hepsi kodla, sonunda bir MP4):
> 1. **Phim ngắn hoặc hoạt hình**: một ý tưởng, một cảm xúc hay một nơi chốn; độ dài và khung hình tùy bạn
> 2. **Video quảng cáo, sản phẩm hoặc giới thiệu**: cho thương hiệu, sản phẩm hay công việc của bạn
> 3. **MV trên bài hát của bạn**: "làm MV cho bài này" + file bài hát
> 4. **Phim giống một video**: "làm giống thế này nhưng màu ấm hơn" + file video
> 5. **Dựng footage của bạn**: talking head hoặc quay màn hình: cắt khoảng lặng, thêm đồ họa
> 6. **Phim mới theo format đã lưu**: "làm một tập mới theo format lần trước"
> 7. **Xem các phong cách**: xem trên một bảng các hướng điện ảnh và phong cách hợp với ý tưởng
> Mỗi loại đều chọn chế độ trước: Nhanh (xong trong hôm nay) hoặc Film (duyệt từng bước).

**Update** ("cập nhật rubydai-make-video-skill", "update rubydai-make-video-skill"): `git -C KIT pull`, then one line: open a new chat so the new version loads.

**Direct routes.** A request that names a kind of film skips the menu: first the mode and purpose (one call), then the route's own first step, then only the questions it leaves open.

| The user says | Route |
|---|---|
| a story, mood, place or animation idea | First questions |
| an ad, product, launch, promo or explainer | First questions, purpose Ad & product |
| a music video, or sends a song | `references/music-video.md` (its beat grid first) |
| "bunun gibi", "like this one", or sends a video | `references/reference-video.md` |
| their own footage to cut | `references/footage-edit.md` |
| "cùng format", "same format" | `formats.py list` → `init_film.py . --format <name>` (with `--quick` when the format is a Quick one, as `formats.py list` shows); `quick-mode.md` §8 |
| "xem phong cách", "show me styles" | `styles.py suggest "<their words>" --board research/style-board.jpg`, then the first questions |

## First questions: mode and purpose

**Steer first** (`references/steering.md`, short): read the idea against what costs the most in code. When it leans on what code draws badly (realistic people or animals as the subject, an idea stretched past its length), the ★ interpretation keeps the idea and its subject and changes only how they are shown; the original stays an option with its honest cost, and if the user picks it, help fully.

Ask both in one call; skip one already answered ("reklam filmi" names the purpose).

- **Chế độ / Mode:** **Nhanh / Quick**: this chat builds the whole film in one file; questions only where the brief leaves a gap; the card, two scenes as stills, then the draft (a complete brief: the draft first); about 3 approvals, a short film's first draft in minutes. **Film**: a studio process (roadmap, script, style frame, animatic, draft), research, layered sound, helpers for the parts that run in parallel; it takes longer than Quick, so the question never quotes a time for it: it says what the user sees and approves. The ★ follows the size of the work, never its purpose: ★ Quick under about 60 s, for one shot or a few scenes, brand and client pieces included; ★ Film from about 60 s with several scenes, research or archive material, a narrator over many chapters, or when the user asks for the gated process. The question says what each asks of the user ("Nhanh: bản nháp đầu tiên sau vài phút, 3 lần duyệt · Film: duyệt lộ trình và kịch bản trước, rồi sản xuất từng bước hoặc một lần"). Unknown goal → ★ Quick (it can move to Film later, keeping the beats: `init_film.py <film> --to-film`).

**A complete brief goes straight to work,** in either mode: when the opening message settles what happens and when, the words, the length, the format and what is delivered (a client brief, a shot list, an instruction to deliver and stop), nothing it answers is asked and no gate stands before the draft. The card is saved in `STATE.md` (its idea as the user gave it, marked `(user)`) and shown in one short message, the build starts at once, and the first gate is the draft itself (for a long build, a sheet of stills from its main moments). An instruction to deliver and stop is followed as written: deliver, report, wait. Only a gap that changes the film (a look the brief does not name, a missing logo) is asked, once, before building.
- **Mục đích / Purpose:** **Điện ảnh / Cinematic**: a story, mood or art piece that looks filmed, not rendered. **Quảng cáo & sản phẩm / Ad & product**: whose it is and what to do next are clear. ★ from the idea (a product, brand, launch, app or sponsor → Ad; a story, place, feeling or art idea → Cinematic). An own answer is mapped to the nearer purpose, said in one line.

Record `Mode` and `Purpose` in `STATE.md`, then open `references/purpose-cinematic.md` or `references/purpose-ad.md` (its defaults and checks).

## Quick mode

Everything in `references/quick-mode.md`. Setup: `python3 KIT/scripts/init_film.py . --quick` (in the chat's own folder, never a subfolder). In short: questions in one round (the idea, then the medium, the user's choice; then the style picked by eye inside it: for a named look, your own readings of it beside real stills; otherwise a board) · research in the background · **the production card** as text within a minute or two (beats second by second, the director card with numbers) · the look and two scenes as stills, a gate · the rest in passes · half-size draft · up to two revision rounds on drafts · the final after the OK.

## Film mode

Everything in `references/film-mode.md`, with `references/context-protocol.md`. Setup: `python3 KIT/scripts/init_film.py .` (in the chat's own folder, never a subfolder). Six gated steps: interview → roadmap → script → style frame and type → animatic → draft cut, then the final; a gate the brief already answers is skipped. This chat does the work it holds the context for and hands a helper only an independent part that runs beside it (sound designed while the picture is made, voice takes recorded, research, the independent viewer) or a chapter of a long film (`context-protocol.md` §1); notes are saved verbatim per round; a defect is diagnosed before anything is rebuilt; at each gate the user may be asked to continue in a new chat ("STATE.md'den devam et").

## Where things are

**KIT** = the folder of this file: `references/`, `templates/`, `scripts/`, `starter/`, `styles/`; read only. **PROJECT** = the folder the chat was opened in, exactly as it is: `init_film.py .` sets the film up right there. Never create a films folder (no `Phim`, `Films` or a name in any language), never a per-film subfolder, never invent a folder name: the user chose the folder by opening the chat in it. Files already there (a README, notes) stay untouched beside the film. Only when the folder already holds a film (`init_film.py` says EXISTS or IN USE) ask the user once: continue that film, or where the new one goes. Tell the user the film's folder as its full path in one line; work in it directly, never `cd` into a subfolder; the finished `<title>.mp4` sits at its top. **`~/.rubydai-video/`** keeps what carries over: keys, saved formats, the taste log, caches.

**Setup check, silently, beside the first questions:** `node -v` (≥ 22), `python3 -V` (Windows: `py -3 -V`, else `python -V`; then that command wherever these files say `python3`), `ffmpeg -version`, Chrome, free disk space (`df -h .`; Windows: `Get-PSDrive`), and the GPU: `node KIT/scripts/capture.mjs --url KIT/starter/index.html --probe` (it names the GPU, or warns on software rendering; the renderer follows it). A missing tool never stops the film: offer it in the same question round, one option per tool (★ install now, with this machine's command; "I'll do it myself"): macOS `brew install node ffmpeg`, `brew install --cask google-chrome` (no Homebrew: the one-line installer from brew.sh for the user to paste in Terminal; it asks for their password); Linux `sudo apt install nodejs ffmpeg chromium`; Windows `winget install OpenJS.NodeJS Gyan.FFmpeg Google.Chrome Python.Python.3.12` (nothing else to render: the kit needs no bash, and no Git to run; Git is used only to install and update the kit itself, §Update; when Claude Code runs commands in PowerShell, join them with `;`). An old Node (< 22) is upgraded the same way. Install after the OK in the background while the questions go on, check again, and continue where the film is. On Windows a program winget installs reaches only the apps started after it: once Node, ffmpeg or Python is installed, ask the user to close and reopen Claude Code once, then say "continue" (the guard needs `node` on its PATH). **Low disk space:** say how much is free and what the film needs, measured from a past film's folder when there is one (`du -sh`; PowerShell: `(Get-ChildItem -Recurse <folder> | Measure-Object Length -Sum).Sum`); a 30 s Quick film used 50–100 MB through its drafts, a long film with full-size finals a few GB.

**A later session** ("Tiếp tục từ STATE.md", "STATE.mdから続けて"): with several films in the folder, list them by title and last change and ask which, unless the user named it. Load this skill (Claude Code: the Skill tool, which starts its guard; never re-read this file by hand), refresh the film's copied tools silently (`python3 KIT/scripts/init_film.py <film-folder> --update-tools`: a film begun with an older kit gets the new tools, its own files stay untouched), then read `STATE.md` first (Film mode: its "Resume here"; Quick mode: its Phase, Open notes and Next action lines); never rely on chat history.

## Hard rules

What makes the film:

- **Hook:** the first 2 seconds move from frame 1 and lead with an action; no still title, no fade from black.
- **One action per beat, and every beat changes something** the viewer sees or hears; a camera move alone is not a beat; a beat that changes nothing is cut or given a job.
- **Half size, never half detail:** every world is built at its full detail before the first draft (`quick-mode.md`: its real parts, materials, secondary motions, depth layers, how its light falls); a world of light, water or terrain goes on the GPU when there is one. A blockout is never shown as a draft.
- **Motion that lives:** one lead per moment, cause before effect, nothing living moves linearly, no pops, landings on the cue (`references/motion.md`).
- **One eye decides, the tempo drives variety:** every device (look, light, camera, transitions, effects, finishing) is chosen on the director card (Film mode: the roadmap's card) with its reason from this story, and the build uses what the card names. Camera moves, shot sizes, light and type change as often as the tempo asks; adjacent shots never repeat a move or size, and never the same designed transition twice in a row (a plain cut is the default joint and may follow a cut); something new reaches the eye or the ear every few seconds. What stays constant is the film's identity: one visual language and a signature that returns, changed. Monotony is a fault just like clutter. Libraries are vocabulary, never a checklist.
- **No shortcuts from the templates:** example scenes, the test scene and presets are scaffolding, deleted before the first stills; every scene is built for this story (its subject, place, light and action); abstract shapes never stand in for the subject unless the user asked for an abstract film. Every preview frame is asked: could it belong to another film? If yes, it is redone first. A saved format or a reference video repeats a form, never scenes. **No AI-overused choices by habit:** the kit has no default font or palette; the colours and fonts every generated design reaches for ("những lựa chọn AI dùng quá nhiều") need a reason on the card (`make.py` prints a taste line while they are still there; `fonts.py` finds type by tone); the images generated films reach for by habit (a lighthouse or lanterns, neon, floating balloons) are never a default: they enter a plan when the user asked for them or when the plan says why this story needs them (`- **Habit image:** <the image>: <why>`; the guard holds a card, roadmap or script that brings one in silently).
- **Sound from version 1:** ambience per scene, picture-locked effects, one shared space. **Narration is never the raw TTS:** each film gets its own voice treatment (`references/sound.md` §4b).
- **Words read as written, never generated:** no dash (—, or – and -- used as one) anywhere in the film's words (`make.py` stops before rendering on one); generated-sounding tells ("không chỉ X mà còn Y", "hành trình", "thì thầm", "bạn đã bao giờ…?", sales lines) are rewritten or kept with a reason (`references/writing.md` §6, `tools/words_check.py`).
- **Type** reads at phone size, keeps its diacritics and has an open licence; a style rule is broken only as a named, consistent signature (`references/typography.md` §11).
- **Counts follow the length:** shots, chapters, research and stills scale with the runtime (`references/craft.md` §0).
- **Finishing is the user's choice:** motion blur, print tone and gate weave are off by default; Quick mode shows them as one line of the card, Film mode asks one multi-select question at the style frame (`references/purpose-cinematic.md` §2).

How it is made:

- **Stills before rendering:** Quick mode: the text plan, then stills, then a half-size draft; Film mode: the style frame, one still per new or changed shot, the animatic and the draft cut. No full-size moving video before the user's OK on a draft; single stills for review may be full size.
- **Frames are pure functions of time:** time from the frame index, seeded randomness, assets loaded before `READY`.
- **Measured, not heard:** you measure audio but cannot hear it; every delivery asks the user to listen, naming the seconds that matter.
- **Delivery is the film:** the final sits in the project folder as `<title>.mp4` (and `<title>-subtitled.mp4` when subtitled) and its path leads the message; a film with outside material carries its credits right under the path, headed in capitals in the user's language ("KHI ĐĂNG, DÁN PHẦN GHI CÔNG NÀY VÀO MÔ TẢ VIDEO"), the lines themselves in a code block, never only the credits file's name. Versions are kept silently (`tools/snapshot.py "<step>"` at every gate and delivery: a local history of the film's text files only, nothing uploaded); never ask the user to commit, never mention git. **Versions without clutter:** after the OK on a final, two questions one at a time: "Mình dọn các file trung gian nhé?" (★ yes, what goes, what stays, the space it frees), then "Nếu bạn thích, mình lưu format này nhé?" (`formats.py save`). On yes, delete drafts, picture-only and segment files, frame folders and older versions; never the delivered film, `refs/`, `assets/`, audio sources or `notes/`. Video has a bitrate ceiling (`capture.mjs --maxrate`: 10M, drafts 4M).
- **The voice is the user's pick, by ear:** candidate takes as separate short files, one question; no agent or helper chooses a narrator's voice, and no line is generated in a voice the user has not heard and picked; the voice's treatment is picked by ear too: in Film mode from a treatment audition, in Quick mode the card's line the user approved (or an audition when they ask). A helper brief for narration says: render the takes and stop.
- **No long detail work the user did not ask for.** A build step that would take more than about ten minutes on its own (a piece-by-piece model, a realistic character, many 3D worlds) is named on the card with its time, and the ★ is the lighter route that keeps the idea; the long one only when the user asks for it.
- **Generated pictures only when the user asks.** When the code route struggles: ★ a style the code draws well (silhouette, cut-paper, toon, figures at a distance, objects instead of bodies), then a simpler scene, then stopping. A connected image or video generator (Higgsfield, fal or any service that spends credits) is never offered and never ★: it is used only when the user asks for it, as a last resort after the kit's own route was tried, and its output gets a `LICENSES.csv` row.
- **No paid services, API keys, installs or large downloads without the user's OK;** no logins, no browser automation for research. **Keys once, never shown:** `tools/keys.py list` before asking; when a key is set, use it and never ask again. A new one: `keys.py open <NAME>` opens the key file in the user's text editor (no terminal), or `keys.py set <NAME>` (hidden input); keys in an older film's `.env` move with `keys.py import`. Saved once in `~/.rubydai-video/keys.env` for every film; never printed or copied into a film folder, `STATE.md`, a log, a commit or the chat. The guard blocks the obvious ways to open, print or search the key file, but it is a seatbelt, not a sandbox: shell code can always be written to read any file, so this is a rule the agent follows, not a wall. Reach a key only through `keys.py` and the tools that use it (`asset_search.py`, `tts.py`), which pass it to a service and never to the chat.
- **Research is probed and boxed:** for a real person, team, event or brand, `asset_search.py supply` counts what the open archives hold before any download, and thin or empty elements go to the user at once with the routes (their licensed material, a design-led film, a mix); a search round takes at most 15 minutes, helpers included, and a deeper one is the user's call.
- **Licences at download time:** every outside file gets a `LICENSES.csv` row; unknown licence = not used. Copyrighted films and stills are mood references only, never in a frame. Credits go in the video description (`make.py final` in Quick mode and `make.py credits` in Film mode write `<title>-credits.txt` beside the film), never on the picture and never as a list at the end, unless the user asks for one.
- **All writes inside the project folder,** except `~/.rubydai-video/`. Check free disk before renders.

## Small context

Every step re-reads the whole chat, so a film's cost is set by how large its chats grow, not by the model. Quick mode: the main chat builds, renders and revises itself, however large it grows (a helper starts cold and plans for minutes before its first edit); helpers only run the prediction test and the overlap check (`brief.py predict`, `brief.py overlap`), render narration takes and, when the user asks for one, watch a delivered draft as the independent viewer (`templates/quick/REVIEWER.md`, an option, never a gate: the user's OK on the draft is the gate); a large chat offers a new chat after a delivered draft, never by handing the work to a cold helper. Film mode: the same, with helpers for the independent parts of a longer film (one task, its model named, at most 25 tool calls, a reply of 10 lines or fewer, details in `review/`; `context-protocol.md` §1). A check a script answers (counting, validating, measuring) is the script's job, never a helper's. A long reference is read by section (the Grep tool for `^## `, then that section with the Read tool's offset and limit), never whole.

- **One call per render step:** `python3 tools/make.py stills | draft | final`; never chain capture, master and checks by hand, never print a log into the chat (bash `> logs/x.log 2>&1`, PowerShell `2>&1 | Out-File -Encoding utf8 logs/x.log` so 5.1 does not write UTF-16, then its last lines with the Read tool).
- **Edit, never rewrite:** read files in parts (the Grep tool, the Read tool's offset and limit) and change only what a note touches; a helper script longer than about 20 lines is saved in `logs/` and run from there, not pasted inline.
- **Small images only:** the sheets the tools write (under a megapixel), one per gate in the main chat.
- **Measured:** `tools/usage.py` shows each chat's tokens; in Claude Code the guard reminds at 160 K and 260 K tokens, refuses large images and stops a helper after 25 tool calls.
- One batch of notes per round, one question per gate. What the user praised is locked: fixes and re-plans keep it (`film-mode.md`, Notes).

At a delivered draft, when the guard reports a large chat or after about 15 user messages, update `STATE.md` and offer a new chat (`templates/HANDOFF.md`: a question; in the desktop app's `wrap_up` box only as one of two buttons at most). On yes the new chat starts by itself: in the Claude desktop app with `mcp__ccd_session__start_session` (a child session that begins working at once, never a prefilled box the user must send); elsewhere `tools/handoff.py`.

## References

- Modes: `quick-mode.md` · `film-mode.md` · `context-protocol.md`. Purpose: `purpose-cinematic.md` · `purpose-ad.md`. Routes: `music-video.md` · `reference-video.md` · `footage-edit.md`.
- Steering: `steering.md`. Jury: `jury.md` (optional, two or three minutes). Story: `writer-prompt.md` (every script, line and card) · `writing.md`.
- Picture: `looks.md` (8 families, 74 recipes) · `characters.md` (a stylised cast; stick figures §5) · `camera-moves.md` · `motion.md` · `motion-design.md` (devices that tell: maps, counts, cutaways, archive parallax, annotations) · `finish.md` (the quality toolbox: light, lens, air, material, geometry, motion and post devices, chosen per scene) · `craft.md` (§0 counts by length) · `typography.md`. Sound: `sound.md`. Production: `engine.md` · `assets-and-licences.md`.
- Tools (copied into a film's `tools/` by `init_film.py`, which runs from `KIT/scripts`; Quick mode leaves out the Film-only `animatic.py` and `validate_shots.py`; each with `--help`): `make.py`, `capture.mjs`, `qc.py`, `brief.py` (a helper's brief with the kit's rules for its task), `scene_check.py`, `validate_shots.py`, `animatic.py` · `mix.py`, `master_audio.py`, `voice_treat.py`, `tts.py`, `beat_grid.py`, `lyrics_align.py`, `samples.py`, `sounds.py` · `asset_search.py`, `styles.py`, `moves.py`, `fonts.py`, `direction.py`, `ref_video.py`, `deal.py`, `dice.py` (no CLI of its own: `deal.py deal spark|seed`, `deal.py past`), `type_deal.py` (no CLI of its own: `deal.py … type`), `type_refs.py`, `type_extract.py`, `captions.py`, `words_check.py` · `formats.py`, `keys.py`, `snapshot.py`, `handoff.py`, `usage.py` · `footage_cut.py`; the decks `sparks.json` and `seeds.json`. The guard (`guard.py`, started by `hook.cjs`) stays in the kit. Starters: `templates/quick/film.html` (engine: `templates/quick/HELPERS.md`); Film `starter/`. Needs Node 22+, Python 3 (standard library), ffmpeg and Chrome, nothing else; Whisper only for the footage edit and optional word-locked captions, installed with the user's OK.
