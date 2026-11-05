# Installs the rubydai-make-video-skill Claude Code skill on Windows. Double-click setup.bat to run it.
# Safe to run again: anything already in place is skipped, an existing clone is pulled.
# Keep this file ASCII-only: Windows PowerShell 5.1 misreads UTF-8 without a BOM.

# ---- Configuration --------------------------------------------------------
$Desktop = [Environment]::GetFolderPath('Desktop')
# One entry per skill: skill name, repo URL, folder that holds the clone
$Skills = @(
    @{ Name = 'rubydai-make-video-skill'; Url = 'https://github.com/rubydai-dev/rubydai-make-video-skill.git'; Parent = (Join-Path $Desktop 'Javascript Projects') }
)

# Lines that must be in ~/.claude/CLAUDE.md.
# A line is skipped if the file already mentions `skill name` in backticks.
$ClaudeMdLines = @(
    @{ Skill = 'rubydai-make-video-skill'; Line = '- When the user asks for a short film, a video, an animation, an ad or a music video made with code, always use the `rubydai-make-video-skill` skill.' }
)
# ---------------------------------------------------------------------------

$SkillsDir = Join-Path $env:USERPROFILE '.claude\skills'
$ClaudeMd = Join-Path $env:USERPROFILE '.claude\CLAUDE.md'
$Utf8 = New-Object System.Text.UTF8Encoding $false
$script:Errors = 0

function Ok($msg)   { Write-Host '  [ok] ' -ForegroundColor Green -NoNewline; Write-Host $msg }
function Warn($msg) { Write-Host '  [!]  ' -ForegroundColor Yellow -NoNewline; Write-Host $msg }
function Fail($msg) { Write-Host '  [x]  ' -ForegroundColor Red -NoNewline; Write-Host $msg; $script:Errors++ }

function Finish {
    Write-Host ''
    if ($script:Errors -eq 0) {
        Write-Host 'Done. Start a new Claude Code session and type / to see the skill.'
    } else {
        Write-Host "$($script:Errors) error(s); see the [x] lines above."
    }
    exit $script:Errors
}

function Same-Path($a, $b) {
    return ($a.TrimEnd('\') -ieq $b.TrimEnd('\'))
}

Write-Host '== Tools =='
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Warn 'git is missing. Installing it with winget...'
        winget install --id Git.Git -e --source winget --accept-package-agreements --accept-source-agreements
        Fail 'Once git is installed, close this window and double-click setup.bat again (a new window picks up git).'
    } else {
        Fail 'git is missing. Install it from https://git-scm.com/download/win, then double-click setup.bat again.'
    }
    Finish
}
Ok ((git --version) -replace '^git version ', 'git ')

if (Get-Command claude -ErrorAction SilentlyContinue) {
    Ok 'Claude Code is installed'
} else {
    Warn "The claude command wasn't found. The skill is installed anyway; remember to install Claude Code."
}

# What the kit needs to make a film. Missing ones are reported, not installed: the agent offers them too.
$need = 'winget install OpenJS.NodeJS Gyan.FFmpeg Google.Chrome Python.Python.3.12'
if (Get-Command node -ErrorAction SilentlyContinue) {
    $v = (node -v)
    if ([int](($v -replace '^v', '').Split('.')[0]) -ge 22) { Ok "Node.js $v" } else { Warn "Node.js $v is older than 22. Upgrade with: winget install OpenJS.NodeJS" }
} else { Warn "Node.js is missing (the kit and its guard need it). Install with: $need" }
if ((Get-Command py -ErrorAction SilentlyContinue) -or (Get-Command python -ErrorAction SilentlyContinue)) { Ok 'Python 3' } else { Warn "Python 3 is missing. Install with: $need" }
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Ok 'ffmpeg' } else { Warn "ffmpeg is missing. Install with: $need" }

Write-Host ''
Write-Host '== Skill =='
New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
foreach ($s in $Skills) {
    $repo = Join-Path $s.Parent $s.Name
    $link = Join-Path $SkillsDir $s.Name
    Write-Host $s.Name

    $skillMd = Join-Path $repo 'SKILL.md'
    if (Test-Path (Join-Path $repo '.git')) {
        git -C $repo pull --ff-only -q
        if ($LASTEXITCODE -eq 0) { Ok "Pulled: $repo" }
        else { Warn "Couldn't pull (uncommitted changes or a diverged branch?); the local copy is used as it is: $repo" }
    } elseif ((Test-Path $skillMd) -and (Select-String -Path $skillMd -Pattern ('^name: ' + $s.Name + '$') -Quiet)) {
        Warn "$repo is the skill but not a git clone: linked as it is (no pull)."
    } elseif (Test-Path $repo) {
        Fail "$repo exists but is neither a git clone nor this skill; skipped."
        continue
    } else {
        New-Item -ItemType Directory -Force -Path $s.Parent | Out-Null
        git clone -q $s.Url $repo
        if ($LASTEXITCODE -eq 0) { Ok "Cloned into $repo" }
        else { Fail "Couldn't clone $($s.Url)"; continue }
    }

    # A directory junction works without admin rights or Developer Mode, unlike a symlink.
    $item = Get-Item -LiteralPath $link -Force -ErrorAction SilentlyContinue
    if ($null -eq $item) {
        New-Item -ItemType Junction -Path $link -Target $repo | Out-Null
        Ok "Created junction: $link (edits in the repo apply at once)"
    } elseif ($item.LinkType) {
        $target = @($item.Target)[0]
        if (Same-Path $target $repo) { Ok "Link is correct: $link" }
        else { Fail "$link points to $target, not $repo. Delete that link and run again." }
    } else {
        Fail "$link exists and isn't a link; skipped (install only in one place)."
    }
}

Write-Host ''
Write-Host '== ~/.claude/CLAUDE.md =='
if (-not (Test-Path $ClaudeMd)) { [IO.File]::WriteAllText($ClaudeMd, '', $Utf8) }
foreach ($c in $ClaudeMdLines) {
    $text = [IO.File]::ReadAllText($ClaudeMd, $Utf8)
    if ($text.Contains('`' + $c.Skill + '`')) {
        Ok "Already mentions $($c.Skill)"
    } else {
        $prefix = if ($text.Length -gt 0 -and -not $text.EndsWith("`n")) { "`r`n" } else { '' }
        [IO.File]::AppendAllText($ClaudeMd, $prefix + $c.Line + "`r`n", $Utf8)
        Ok "Added: $($c.Line)"
    }
}

Finish
