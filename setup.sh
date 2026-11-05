#!/bin/bash
# Installs the rubydai-make-video-skill Claude Code skill on macOS or Linux. On a Mac, double-click setup.command instead.
# On Windows, double-click setup.bat.
# Safe to run again: anything already in place is skipped, an existing clone is pulled.

# ---- Configuration --------------------------------------------------------
# One line per skill: skill name | repo URL | folder that holds the clone
SKILLS=(
  "rubydai-make-video-skill|https://github.com/rubydai-dev/rubydai-make-video-skill.git|$HOME/Desktop/Javascript Projects"
)

# Lines that must be in ~/.claude/CLAUDE.md: skill name | line.
# A line is skipped if the file already mentions `skill name` in backticks.
CLAUDE_MD_LINES=(
  "rubydai-make-video-skill|- When the user asks for a short film, a video, an animation, an ad or a music video made with code, always use the \`rubydai-make-video-skill\` skill."
)
# ---------------------------------------------------------------------------

SKILLS_DIR="$HOME/.claude/skills"
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
ERRORS=0

ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$1"; }
fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; ERRORS=$((ERRORS + 1)); }

finish() {
  echo
  if [ "$ERRORS" -eq 0 ]; then
    echo "Done. Start a new Claude Code session and type / to see the skill."
  else
    echo "$ERRORS error(s); see the ✗ lines above."
  fi
  exit "$ERRORS"
}

install_hint() {   # the command that installs $1 on this machine
  if [ "$(uname)" = "Darwin" ]; then
    if command -v brew >/dev/null 2>&1; then echo "brew install $1"
    else echo "Homebrew from https://brew.sh, then: brew install $1"; fi
  elif command -v apt-get >/dev/null 2>&1; then echo "sudo apt-get install $1"
  elif command -v dnf >/dev/null 2>&1; then echo "sudo dnf install $1"
  elif command -v pacman >/dev/null 2>&1; then echo "sudo pacman -S $1"
  else echo "your package manager ($1)"; fi
}

echo "== Tools =="
if [ "$(uname)" = "Darwin" ] && ! xcode-select -p >/dev/null 2>&1; then
  # On macOS, /usr/bin/git exists even before the Command Line Tools are installed, so check those instead.
  warn "Command Line Tools (git) are missing. Opening the installer..."
  xcode-select --install 2>/dev/null
  fail "Once the Command Line Tools are installed, run this again."
  finish
fi
if ! command -v git >/dev/null 2>&1; then
  fail "git is missing. Install it with: $(install_hint git), then run this again."
  finish
fi
ok "git $(git --version | awk '{print $3}')"

if command -v claude >/dev/null 2>&1; then
  ok "Claude Code is installed"
else
  warn "The claude command wasn't found. The skill is installed anyway; remember to install Claude Code."
fi

# What the kit needs to make a film. Missing ones are reported, not installed: the agent offers them too.
if command -v node >/dev/null 2>&1; then
  major=$(node -v | sed 's/^v//; s/\..*//')
  if [ "$major" -ge 22 ] 2>/dev/null; then ok "Node.js $(node -v)"
  else warn "Node.js $(node -v) is older than 22. Upgrade with: $(install_hint node)"; fi
else
  warn "Node.js is missing (the kit and its guard need it). Install with: $(install_hint node)"
fi
if command -v python3 >/dev/null 2>&1; then ok "$(python3 -V)"
else warn "Python 3 is missing. Install with: $(install_hint python3)"; fi
if command -v ffmpeg >/dev/null 2>&1; then ok "ffmpeg $(ffmpeg -version 2>/dev/null | head -1 | awk '{print $3}')"
else warn "ffmpeg is missing. Install with: $(install_hint ffmpeg)"; fi
if [ -d "/Applications/Google Chrome.app" ] || command -v google-chrome >/dev/null 2>&1 || command -v chromium >/dev/null 2>&1; then
  ok "Chrome / Chromium"
else
  warn "Chrome or Chromium was not found (renders need one). macOS: brew install --cask google-chrome"
fi

echo
echo "== Skill =="
mkdir -p "$SKILLS_DIR"
for entry in "${SKILLS[@]}"; do
  IFS='|' read -r name url parent <<< "$entry"
  repo="$parent/$name"
  link="$SKILLS_DIR/$name"
  echo "$name"

  if [ -d "$repo/.git" ]; then
    if git -C "$repo" pull --ff-only -q; then
      ok "Pulled: $repo"
    else
      warn "Couldn't pull (uncommitted changes or a diverged branch?); the local copy is used as it is: $repo"
    fi
  elif [ -f "$repo/SKILL.md" ] && grep -q "^name: $name\$" "$repo/SKILL.md"; then
    warn "$repo is the skill but not a git clone: linked as it is (no pull)."
  elif [ -e "$repo" ]; then
    fail "$repo exists but is neither a git clone nor this skill; skipped."
    continue
  else
    mkdir -p "$parent"
    if git clone -q "$url" "$repo"; then
      ok "Cloned into $repo"
    else
      fail "Couldn't clone $url"
      continue
    fi
  fi

  if [ -L "$link" ]; then
    if [ "$(readlink "$link")" = "$repo" ]; then
      ok "Symlink is correct: $link"
    else
      fail "$link points to $(readlink "$link"), not $repo. Delete that symlink and run again."
    fi
  elif [ -e "$link" ]; then
    fail "$link exists and isn't a symlink; skipped (install only in one place)."
  else
    ln -s "$repo" "$link" && ok "Created symlink: $link (edits in the repo apply at once)"
  fi
done

echo
echo "== ~/.claude/CLAUDE.md =="
mkdir -p "$(dirname "$CLAUDE_MD")"
touch "$CLAUDE_MD"
for entry in "${CLAUDE_MD_LINES[@]}"; do
  skill="${entry%%|*}"
  line="${entry#*|}"
  if grep -qF -- "\`$skill\`" "$CLAUDE_MD"; then
    ok "Already mentions $skill"
  else
    # Add a newline first if the file doesn't end with one
    [ -s "$CLAUDE_MD" ] && [ "$(tail -c1 "$CLAUDE_MD")" != "" ] && echo >> "$CLAUDE_MD"
    echo "$line" >> "$CLAUDE_MD"
    ok "Added: $line"
  fi
done

finish
