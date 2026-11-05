#!/usr/bin/env python3
"""The guard's words in the user's languages (Vietnamese, Japanese, English): how a yes, a no, a not-yet, a script
question, an idea question or a habit image is said, and which language a line is in. Every word list the guard reads
lives here, so a new language is one file's change. guard.py re-exports every name."""
from pathlib import Path
import json
import re
import unicodedata


IDEA_ASK = re.compile(r"\b(angle|interpretation\w*|ideas?|ý\s+tưởng|góc\s+nhìn|cách\s+hiểu)\b|アイデア|切り口", re.I)


IDEA_HEADER = re.compile(r"\b(idea|angle|story|ý\s+tưởng|góc\s+nhìn|câu\s+chuyện|cốt\s+truyện)\b", re.I)


NOT_IDEA = re.compile(r"jury|format|draft|final|text|font|music|sound|existing|already|"
                      r"giám khảo|bản nháp|phông chữ|âm nhạc|âm thanh|hiện có|đã có|thư mục này|cùng ý tưởng|tiếp tục", re.I)


HABIT_IMAGES = {   # images generated films reach for by habit: in a plan only when the user asked for them
    "a lighthouse or lanterns": r"lighthouse|lantern|hải\s+đăng|đèn\s+lồng|lồng\s+đèn",
    "neon": r"\bneon",
    "floating balloons": r"balloon|bóng\s+bay",
}


NOT_WANTED = re.compile(r"\b(no|not|without|never|don'?t|avoid|"
                        r"đừng|không\s+muốn|không\s+cần|không\s+có|không\s+dùng|bỏ|cấm|trừ)\b", re.I)


USERS_OWN = re.compile(r"\((?:the )?user(?:'s)?(?: own| brief)?\b[^)]*\)|\((?:của\s+)?người\s+dùng[^)]*\)", re.I)


EN_WORDS = {"the", "and", "you", "your", "which", "what", "should", "with", "for", "this", "that", "would", "is",
            "are", "of", "to", "a", "an", "do", "how", "make", "want", "film", "yes", "no", "please", "why", "or"}


VI_WORDS = {"và", "là", "của", "có", "không", "được", "cho", "một", "những", "này", "đi", "tôi", "mình", "bạn", "làm",
            "với", "thì", "nhé", "nhỉ", "muốn", "hãy", "gì", "sao", "đó", "rồi", "cũng", "nào", "vậy", "ơi", "ạ", "thế",
            "cái", "các", "nên", "đã", "sẽ", "đang", "phim", "xem", "giúp", "nhưng", "hay", "chưa", "ok"}


VI_LETTERS = re.compile(r"[ăđơưĂĐƠƯ\u1ea0-\u1ef9]")      # letters only Vietnamese writes (Ơ Ư Đ and the stacked vowels)


def vi_score(text):
    """Vietnamese function words plus lowercase words with a Vietnamese-only letter (a capitalised name like Đà Nẵng
    in an English line does not count)."""
    words = re.findall(r"[^\W\d_]+", unicodedata.normalize("NFC", text))
    fn = sum(w.lower() in VI_WORDS for w in words)
    content = sum(1 for w in words if w == w.lower() and VI_LETTERS.search(w))
    return fn, content


KANA = re.compile(r"[\u3040-\u30ff]")              # hiragana and katakana: only Japanese writes them


def language(text):
    """'vi', 'ja', 'en' or None: Japanese by its kana (kanji alone could be Chinese or a name), Vietnamese and English
    against each other by their small function words, so a name in the other language does not flip a line. A
    Vietnamese letter counts only in a lowercase word, never a Capitalised name; a short Vietnamese line (a function
    word and a word with a Vietnamese-only letter, no English) is enough."""
    if len(KANA.findall(text)) >= 3:
        return "ja"
    vi_fn, vi_content = vi_score(text)
    vi = vi_fn + vi_content
    en_fn = sum(w.lower() in EN_WORDS for w in re.findall(r"[A-Za-z']+", text))
    if vi_content >= 1 and vi >= 2 and vi >= en_fn:   # Vietnamese writes letters English never does
        return "vi"
    if en_fn >= 3 and en_fn > vi:
        return "en"
    return None


NOT_THE_USER = ("Stop hook feedback", "Another Claude session sent a message", "Caveat:", "[Request interrupted",
                "PreToolUse", "PostToolUse", "UserPromptSubmit hook", "[Image", "[Subagent",
                "This session is being continued", "Background (from the session")   # hooks and helpers speak as "user" in the log


HANDOFF_OPENING = {"Tiếp tục từ STATE.md": "vi", "STATE.mdから続けて": "ja", "Continue from STATE.md": "en"}   # the lines handoff.py LINES sends


def user_language(transcript):
    """The language of the user's own latest message that shows one: their typed words, never a pasted brief, an image
    placeholder or a helper's hand-back."""
    try:
        lines = Path(transcript).read_text(encoding="utf-8", errors="replace").splitlines()[-400:]
    except OSError:
        return None
    for line in reversed(lines):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        if r.get("type") != "user" or r.get("isSidechain"):
            continue
        c = (r.get("message") or {}).get("content")
        if isinstance(c, list):
            if any(isinstance(x, dict) and x.get("type") == "tool_result" for x in c):
                continue
            c = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text")
        if not isinstance(c, str):
            continue
        args = re.search(r"<command-args>(.*?)</command-args>", c, re.S)       # a slash command: its words are the user's
        if args:
            c = args.group(1)
        c = re.sub(r"<pasted_content[^>]*>.*?</pasted_content[^>]*>", " ", c, flags=re.S)
        c = re.sub(r"\[Image[^\]]*\]", " ", c)
        handed = next((lang for line, lang in HANDOFF_OPENING.items() if line in c), None)
        if handed:                           # a handoff prompt: the rest of it is the kit's English, its opening line is theirs
            return handed
        if c.strip() and not c.lstrip().startswith("<") and not c.lstrip().startswith(NOT_THE_USER) \
                and "Base directory for this skill" not in c:
            found = language(c[:2000])
            if found:
                return found
    return None


JURY = re.compile(r"jury|giám\s+khảo", re.I)


SCRIPT_ASK = re.compile(r"kịch\s+bản|lời\s+thoại|hồi\b|script|chốt|\block\b|narration", re.I)


NOT_THE_SCRIPT = re.compile(r"colou?r script|kịch\s+bản\s+màu|subtitles?|phụ\s+đề|(?:sang\s+|tới\s+)?bước\s+kịch\s+bản|"
                            r"(?:to|on to|into)\s+the\s+script(?:\s+(?:and\s+text\s+)?step)?", re.I)


NOT_SCRIPT_ASK = re.compile(r"bản\s+nháp|draft|dựng|\bcut\b|người\s+dẫn|lời\s+dẫn|narrator|voice|xử\s+lý\s+giọng", re.I)


BEATS = re.compile(r"^(beat sheet|beats|các nhịp|nhịp phim)", re.I)


INSTRUCTION = re.compile(r"^\**(word budget|estimate seconds|total words|wordless|không lời|none)\b", re.I)


SCRIPT_PARTS = re.compile(r"^(lines|on.screen text|narration|dialogue|lời thoại|lời dẫn|chữ trên màn hình)", re.I)


SCOPED = re.compile(r"(?:done when|finished when|stop when|stop after|xong khi|dừng khi|dừng sau|làm xong thì dừng)\W*:?",
                    re.I | re.M)


APPROVAL = re.compile(r"★|はい|進めて|お願いします|それでいい|\b(ok|yes|approve\w*|go on|continue|"
                      r"được|đồng\s+ý|duyệt|tiếp\s+tục|làm\s+đi|ừ|ừm|oke|okela)\b", re.I)


NOT_GO = re.compile(r"\b(notes?|swap|change\w*|revi[sz]\w*|fix|i'll|i will|let me|tôi\s+sẽ|mình\s+sẽ|để\s+tôi|"
                    r"góp\s+ý|ghi\s+chú|sửa|đổi|thay|chỉnh|khác)\b", re.I)


BARE_NO = {"no", "wait", "later", "stop", "notyet", "notnow", "いいえ", "まだ", "待って", "không", "khoan", "chờ", "đợi",
           "chờđã", "đợiđã", "khoanđã", "chưa", "dừng", "dừnglại", "thôi", "chưađâu", "đểsau"}


# In a picked line: its words. Never a bare "không" or "chưa": they sit inside ordinary Vietnamese lines ("Biển không im").
NOT_YET = re.compile(r"まだ|待って|いいえ|後で|\b(no|not|stop|wait|later|khoan|chờ\s+đã|đợi\s+đã|dừng\s+lại|để\s+sau)\b", re.I)


DENIED = re.compile(r"進めないで|承認しない|やめて|\b((?:don'?t|do\s+not)\s+(?:continue|go\s+on|approve|proceed)|not\s+(?:ok|approved)|"
                    r"không\s+(?:duyệt|đồng\s+ý|tiếp\s+tục|được|ok)|chưa\s+(?:duyệt|được|ok)|đừng\s+tiếp\s+tục)\b", re.I)
