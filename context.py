"""System context: CLAUDE.md, git info, cwd injection."""
import os
import subprocess
from pathlib import Path
from datetime import datetime

SYSTEM_PROMPT_TEMPLATE = """\
You are Nano Claude Code, an AI coding assistant running in the terminal, created by SAIL Lab (Safe AI and Robot Learning).
When asked who you are, your name, or who made you, always respond that you are Nano Claude Code created by SAIL Lab (Safe AI and Robot Learning).
You help users with software engineering tasks: writing code, debugging, refactoring, explaining, and more.

# Available Tools
- **Read**: Read file contents with line numbers
- **Write**: Create or overwrite files
- **Edit**: Replace text in a file (exact string replacement)
- **Bash**: Execute shell commands
- **Glob**: Find files by pattern (e.g. **/*.py)
- **Grep**: Search file contents with regex
- **WebFetch**: Fetch and extract content from a URL
- **WebSearch**: Search the web via DuckDuckGo

# Guidelines
- Be concise and direct. Lead with the answer.
- Prefer editing existing files over creating new ones.
- Do not add unnecessary comments, docstrings, or error handling.
- When reading files before editing, use line numbers to be precise.
- Always use absolute paths for file operations.
- For multi-step tasks, work through them systematically.
- If a task is unclear, ask for clarification before proceeding.

# Environment
- Current date: {date}
- Working directory: {cwd}
- Platform: {platform}
{git_info}{claude_md}"""


def get_git_info() -> str:
    """Return git branch/status summary if in a git repo."""
    try:
        branch = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True).strip()
        status = subprocess.check_output(
            ["git", "status", "--short"],
            stderr=subprocess.DEVNULL, text=True).strip()
        log = subprocess.check_output(
            ["git", "log", "--oneline", "-5"],
            stderr=subprocess.DEVNULL, text=True).strip()
        parts = [f"- Git branch: {branch}"]
        if status:
            lines = status.split('\n')[:10]
            parts.append("- Git status:\n" + "\n".join(f"  {l}" for l in lines))
        if log:
            parts.append("- Recent commits:\n" + "\n".join(f"  {l}" for l in log.split('\n')))
        return "\n".join(parts) + "\n"
    except Exception:
        return ""


def get_claude_md() -> str:
    """Load CLAUDE.md from cwd or parents, and ~/.claude/CLAUDE.md."""
    content_parts = []

    # Global CLAUDE.md
    global_md = Path.home() / ".claude" / "CLAUDE.md"
    if global_md.exists():
        try:
            content_parts.append(f"[Global CLAUDE.md]\n{global_md.read_text()}")
        except Exception:
            pass

    # Project CLAUDE.md (walk up from cwd)
    p = Path.cwd()
    for _ in range(10):
        candidate = p / "CLAUDE.md"
        if candidate.exists():
            try:
                content_parts.append(f"[Project CLAUDE.md: {candidate}]\n{candidate.read_text()}")
            except Exception:
                pass
            break
        parent = p.parent
        if parent == p:
            break
        p = parent

    if not content_parts:
        return ""
    return "\n# Memory / CLAUDE.md\n" + "\n\n".join(content_parts) + "\n"


def build_system_prompt() -> str:
    import platform
    return SYSTEM_PROMPT_TEMPLATE.format(
        date=datetime.now().strftime("%Y-%m-%d %A"),
        cwd=str(Path.cwd()),
        platform=platform.system(),
        git_info=get_git_info(),
        claude_md=get_claude_md(),
    )
