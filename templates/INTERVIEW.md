# Interview

<!--
For the agent:
- This is the Film mode interview. The mode question (Quick / Film, SKILL.md "First questions"; the steps: references/film-mode.md) comes before it;
  Quick mode uses its own questions in one round (references/quick-mode.md §1): idea · medium · length and format ·
  style and mood · "Ses / Sound" · "Müzik / Music" (its own question): a) narrator + music · b) music + sound effects only, no words · c) on-screen
  text + music · d) own; ★ by purpose (promo / explainer → a; mood / art piece → b); never pick the voice-over
  silently. With a narrator, the same round adds voice type (warm documentary, energetic, intimate first person,
  elderly storyteller, playful, deadpan) and language (★ the user's language), as a follow-up tool call or as
  sub-options in the text message; word budget 30 s ≤ 40, 60 s ≤ 80; default engine Gemini TTS with a style
  prompt (ElevenLabs optional; the user's key and OK). The one-line sound identity follows that answer.
  The fifth question is "Referanslar / References": ★ search open sources, one board · only my own (refs/) · skip.
  Answers go into templates/quick/STATE.md (Sound (Q4), Music, Voice, Sound identity), not into this file.
- Question tool first (SKILL.md "Asking the user"): when the environment has an interactive multiple-choice tool
  (Claude Code: AskUserQuestion, 1-4 questions per call, 2-4 options each, an "Other" row always added;
  Cursor: AskQuestion), USE IT: one question per item, 2-4 options with the ★ one first and "★ (recommended)"
  in its label, the user's own answer always allowed; ask in the order of `references/film-mode.md` (Step 1): call 1 = Q1 and Q2 (two questions: length and format, and the medium); then the direction board is built for the picked interpretation and sent; call 2 = Q3 (about the board) and Q4; call 3 = Q5 and Q6;
  Q1 stays an open question (plain message or the "Other" field) when no idea has been given yet. The defaults
  block goes in a short text message before the first call.
- Without such a tool: the same order in messages (Q1 and Q2, then the board with Q3 and Q4, then Q5 and Q6), numbered, in the user's language (English and Vietnamese versions below).
- Q1 asks for the user's own idea first, as free text. If their first message already contains an idea, show
  2-3 interpretations of THAT idea in Q1 (one marked ★). Only if they say "no idea / suggest" ("fikrim yok /
  sen öner") offer 3 ideas. Never replace their idea with an unrelated one.
- Every other question: 3-5 concrete options, one marked ★ (recommended for this idea, with a few words why),
  and always "your own answer". A free answer is never forced into an option. If the idea is not known yet, mark
  the ★ that suits most ideas and refine the options in the follow-up.
- Q6 is in words only: Quality / Balanced / Economy. Never show money amounts.
- The purpose (Cinematic / Ad & product) is asked with the mode, before this interview; its file
  (references/purpose-cinematic.md or purpose-ad.md) sets the ★ of Q3 and Q5 and its own follow-up inputs.
- If the purpose is Ad & product (or Q1 shows a product, brand, ad or sponsor film), ask for the facts the specificity test needs (name and meaning,
  place, numbers, one constraint, materials, rituals, printed objects, sounds; references/writing.md §12) in one
  follow-up line; the full test is mandatory for these films. A story piece gets the light world test only.
- After the questions, show the defaults block once. "ok" / "tamam" accepts all of it; any line can be changed.
- Check the machine yourself (node, python3, ffmpeg, Chrome, free disk, capture.mjs --probe); never ask.
- The context and revision protocol (references/context-protocol.md) applies from this message on; the defaults
  block names it in one line.
- When answers arrive: write them into the Answers table below (Source: user / accepted ★ / default), set the
  STATE.md fields, then write the roadmap. If Q1 came back as a bare idea, the roadmap message opens with the 2-3
  interpretations to pick from.
-->

## Message (English)

> Let's make your film. Six quick questions; pick an option, combine them, or answer in your own words.
>
> **1. Your idea.** What is the film about, in a sentence or two? (If you have none, say "suggest" and I'll offer three.)
> *[If an idea is already known: 2-3 interpretations of it, one ★, plus "your own".]*
>
> **2. Length and format** (★ the length this idea needs, and why). a) 15 s vertical 9:16 (Reels/Shorts/TikTok) · b) 30 s vertical 9:16 · c) 60 s vertical or 16:9 · d) 1–3 min 16:9 (YouTube) · e) 3–8 min, built in acts · f) square 1:1 · g) your own
> - Medium, what the film is made of (asked as its own question): a) ★ *[the medium that suits the idea, and why]* · b) 3D realistic (real light and materials, like live action; the longest to build, above all with several worlds) · c) 2D animation (cel, rubber hose, anime) · d) hand-made (paint, ink, cut paper, clay or a maquette) · e) motion design · f) your own
>
> **3. Style** (with the direction board image, `review/directions.jpg`, three directions authored for this film): A) *[name: one line of the look and why it serves the story]* · B) *[…]* · C) *[…]*: ★ *[the one that fits, with a reason]* · see a proof frame of each first (this film's own subject in each direction) · from my references (drop images into `refs/`) · your own
>
> **4. Tone and references.** Three mood words, plus anything you love (images in `refs/`, links or film titles with timestamps in `refs/links.txt`). a) ★ *[three words that fit the idea]* · b) *[another set]* · c) *[a contrasting set]* · d) your own: Should I search open sources for references too? ★ yes, one board with the roadmap · only mine · skip
>
> **5. Voice and sound.**
> - Voice (★ from the purpose file, with a reason): a) none (picture and sound tell it) · b) narrator (warm, deadpan, playful, intimate first person, storyteller…) · c) dialogue · d) your own
> - Music, always its own question: a) ★ a real open-licence recording (2–3 candidates played to you, you pick by ear; a long film may take one per act) · b) my own song or track (send the file, and the lyric timings if it has words) · c) written in code for this film (code scores share a small set of voices and sound alike from film to film) · d) no music, sound design only
> - Sound identity, one line each: a) ★ *[concept 1]* · b) *[concept 2]* · c) *[concept 3]* · d) your own
>
> **6. Profile.** a) Quality (best result, takes longer) · b) ★ Balanced · c) Economy (fast and light) · d) your own
>
> **Defaults** (reply "ok", or change any line):
> - Engine: GPU pipeline in the browser (three.js), rendered frame by frame; code only, no paid models
> - Hook: the subject acts from frame 1 and the camera moves with it (a camera move alone is not a hook); checked by measurement
> - Subtitles: none unless you ask (at most 2 languages, stacked, in a safe area)
> - On-screen text: allowed where the format wants it (6 words per card at most)
> - Faces: allowed when the story needs them; for close-ups I suggest stylised faces or silhouettes
> - Deliverable: one master in your format + a poster frame; notes in one batch per round
> - Working method: this chat stays short; I do the work I hold the context for, and a fresh helper takes the parts that run beside it (sound, narration takes, research, the independent viewer); at each checkpoint I may suggest a new chat with one line: "Continue from STATE.md"

## Message (Tiếng Việt)

> Mình cùng làm phim nhé. Sáu câu hỏi ngắn; chọn một phương án, kết hợp, hoặc trả lời bằng lời của bạn.
>
> **1. Ý tưởng.** Phim kể về điều gì, trong một hai câu? (Chưa có ý tưởng thì gõ "bạn gợi ý đi", mình mang tới ba ý tưởng.)
> *[Nếu đã có ý tưởng: 2-3 cách hiểu ý tưởng đó, một cái ★, cộng "câu trả lời của bạn".]*
>
> **2. Độ dài và khung hình** (★ độ dài ý tưởng này cần, kèm lý do). a) 15 giây dọc 9:16 (Reels/Shorts/TikTok) · b) 30 giây dọc 9:16 · c) 60 giây dọc hoặc 16:9 · d) 1–3 phút 16:9 (YouTube) · e) 3–8 phút, dựng theo hồi · f) vuông 1:1 · g) câu trả lời của bạn
> - Chất liệu, phim được làm từ gì (một câu hỏi riêng): a) ★ *[chất liệu hợp ý tưởng, vì sao]* · b) 3D tả thực (ánh sáng và vật liệu thật, như quay thật; dựng lâu nhất, càng lâu nếu có nhiều thế giới) · c) hoạt hình 2D (cel, rubber hose, anime) · d) làm tay (sơn, mực, giấy cắt, đất sét hoặc mô hình) · e) motion graphics · f) câu trả lời của bạn
>
> **3. Phong cách** (kèm bảng định hướng `review/directions.jpg`, ba hướng dựng riêng cho phim này): A) *[tên: giao diện và vì sao nó phục vụ câu chuyện, một dòng]* · B) *[…]* · C) *[…]*: ★ *[hướng hợp nhất, kèm lý do]* · cho xem trước một khung thử của mỗi hướng (chính chủ đề của phim, theo hướng đó) · từ tham chiếu của tôi (thả ảnh vào thư mục `refs/`) · câu trả lời của bạn
>
> **4. Tông và tham chiếu.** Ba từ cảm xúc và những ví dụ bạn thích (ảnh trong `refs/`, link hoặc tên phim + phút trong `refs/links.txt`). a) ★ *[ba từ hợp ý tưởng]* · b) *[một bộ khác]* · c) *[một bộ ngược lại]* · d) câu trả lời của bạn: Mình tìm thêm tham chiếu từ nguồn mở nhé? ★ có, một bảng cùng với lộ trình · chỉ của tôi · bỏ qua
>
> **5. Âm thanh.**
> - Người dẫn (★ theo file mục đích, kèm lý do): a) không (để hình và tiếng kể) · b) lời dẫn (ấm, hài khô, tinh nghịch, ngôi thứ nhất, kể chuyện cổ tích…) · c) thoại · d) câu trả lời của bạn
> - Nhạc, luôn là một câu hỏi riêng: a) ★ một bản thu thật có giấy phép mở (nghe thử 2–3 bản, bạn chọn bằng tai; phim dài có thể mỗi hồi một bản) · b) bài hát hoặc bản nhạc của tôi (gửi file, có lời thì gửi mốc thời gian từng câu) · c) viết bằng code cho phim này (nhạc code dùng ít âm sắc và nghe giống nhau giữa các phim) · d) không nhạc, chỉ thiết kế âm thanh
> - Bản sắc âm thanh, mỗi phương án một dòng: a) ★ *[ý tưởng 1]* · b) *[ý tưởng 2]* · c) *[ý tưởng 3]* · d) câu trả lời của bạn
>
> **6. Hồ sơ.** a) Chất lượng (kết quả tốt nhất, lâu hơn) · b) ★ Cân bằng · c) Tiết kiệm (nhanh và nhẹ) · d) câu trả lời của bạn
>
> **Mặc định** (gõ "ok" hoặc sửa dòng bạn muốn):
> - Engine: GPU trong trình duyệt (three.js), render từng khung; chỉ code, không model trả phí
> - Hook: chủ thể làm gì đó ngay từ khung đầu, máy quay đi theo nó (chỉ chuyển động máy quay thì chưa phải hook); có đo để kiểm tra
> - Phụ đề: không có nếu bạn không cần (tối đa 2 ngôn ngữ, xếp chồng, trong vùng an toàn)
> - Chữ trên màn hình: tự do ở chỗ khung hình cần (tối đa 6 từ mỗi thẻ)
> - Khuôn mặt: tự do nếu câu chuyện cần; cận cảnh thì mình đề xuất mặt cách điệu hoặc bóng đen
> - Giao: một bản master theo khung hình của bạn + một khung poster; góp ý gửi một lần mỗi vòng
> - Cách làm: chat này giữ ngắn; việc mình đang nắm ngữ cảnh thì mình làm, phần chạy song song được (âm thanh, thử lời dẫn, nghiên cứu, người xem độc lập) giao cho helper mới nhận brief; ở mỗi checkpoint mình có thể gợi ý chat mới bằng một dòng: "Tiếp tục từ STATE.md"

## Answers

| # | Topic | Answer | Source (user / accepted ★ / default) |
|---|---|---|---|
| 1 | Idea (and the chosen interpretation) | | |
| 2 | Length · format · fps · medium | | |
| 3 | Style (the direction picked on the board) | | |
| 4 | Tone words · references | | |
| 5 | Voice · music · sound identity | | |
| 6 | Profile | | |
| — | Defaults (accepted / changed lines) | | |

## User references

| File, link or film + timestamps | What they like in it | Used for (look / sound / story) |
|---|---|---|

## Machine check (by the agent)

| Item | Result |
|---|---|
| Node ≥ 22 | |
| Python 3 | |
| ffmpeg / ffprobe | |
| Chrome / Chromium | |
| GPU in headless Chrome (`capture.mjs --probe`) | |
| Free disk (`df -h .`; Windows: `Get-PSDrive`) | |
