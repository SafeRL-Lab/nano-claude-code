#!/usr/bin/env python3
"""
Nano Claude Code — Minimal Python implementation of Claude Code.

Usage:
  python nano_claude.py [options] [prompt]

Options:
  -p, --print          Non-interactive: run prompt and exit (also --print-output)
  -m, --model MODEL    Override model
  --accept-all         Never ask permission (dangerous)
  --verbose            Show thinking + token counts
  --version            Print version and exit

Slash commands in REPL:
  /help       Show this help
  /clear      Clear conversation
  /model [m]  Show or set model
  /config     Show config / set key=value
  /save [f]   Save session to file
  /load [f]   Load session from file
  /history    Print conversation history
  /context    Show context window usage
  /cost       Show API cost this session
  /verbose    Toggle verbose mode
  /thinking   Toggle extended thinking
  /permissions [mode]  Set permission mode
  /cwd [path] Show or change working directory
  /exit /quit Exit
"""
from __future__ import annotations

import os
import sys
import json
import readline
import atexit
import argparse
import textwrap
from pathlib import Path
from datetime import datetime
from typing import Optional

# ── Optional rich for markdown rendering ──────────────────────────────────
try:
    from rich.console import Console
    from rich.markdown import Markdown
    from rich.syntax import Syntax
    from rich.panel import Panel
    from rich import print as rprint
    _RICH = True
    console = Console()
except ImportError:
    _RICH = False
    console = None

VERSION = "1.0.0"

# ── ANSI helpers (used even with rich for non-markdown output) ─────────────
C = {
    "cyan":    "\033[36m",
    "green":   "\033[32m",
    "yellow":  "\033[33m",
    "red":     "\033[31m",
    "blue":    "\033[34m",
    "magenta": "\033[35m",
    "bold":    "\033[1m",
    "dim":     "\033[2m",
    "reset":   "\033[0m",
}

def clr(text: str, *keys: str) -> str:
    return "".join(C[k] for k in keys) + str(text) + C["reset"]

def info(msg: str):   print(clr(msg, "cyan"))
def ok(msg: str):     print(clr(msg, "green"))
def warn(msg: str):   print(clr(f"Warning: {msg}", "yellow"))
def err(msg: str):    print(clr(f"Error: {msg}", "red"), file=sys.stderr)


# ── Conversation rendering ─────────────────────────────────────────────────

_accumulated_text: list[str] = []   # buffer text during streaming

def stream_text(chunk: str):
    """Called for each streamed text chunk."""
    print(chunk, end="", flush=True)
    _accumulated_text.append(chunk)

def stream_thinking(chunk: str, verbose: bool):
    if verbose:
        print(clr(chunk, "dim"), end="", flush=True)

def flush_response():
    """After streaming, optionally re-render as markdown."""
    full = "".join(_accumulated_text)
    _accumulated_text.clear()
    if _RICH and full.strip():
        # Re-print with markdown rendering
        print("\r", end="")      # go to line start to overwrite last newline
        # only re-render if there's actual markdown (contains # * ` _ etc.)
        if any(c in full for c in ("#", "*", "`", "_", "[")):
            print()   # newline after streaming
            console.print(Markdown(full))
            return
    print()  # ensure newline after stream

def print_tool_start(name: str, inputs: dict, verbose: bool):
    """Show tool invocation."""
    desc = _tool_desc(name, inputs)
    print(clr(f"\n  ⚙  {desc}", "dim", "cyan"), flush=True)
    if verbose:
        print(clr(f"     inputs: {json.dumps(inputs, ensure_ascii=False)[:200]}", "dim"))

def print_tool_end(name: str, result: str, verbose: bool):
    lines = result.count("\n") + 1
    size = len(result)
    summary = f"→ {lines} lines ({size} chars)"
    if not result.startswith("Error") and not result.startswith("Denied"):
        print(clr(f"  ✓ {summary}", "dim", "green"), flush=True)
    else:
        print(clr(f"  ✗ {result[:120]}", "dim", "red"), flush=True)
    if verbose and not result.startswith("Denied"):
        preview = result[:500] + ("…" if len(result) > 500 else "")
        print(clr(f"     {preview.replace(chr(10), chr(10)+'     ')}", "dim"))

def _tool_desc(name: str, inputs: dict) -> str:
    if name == "Read":   return f"Read({inputs.get('file_path','')})"
    if name == "Write":  return f"Write({inputs.get('file_path','')})"
    if name == "Edit":   return f"Edit({inputs.get('file_path','')})"
    if name == "Bash":   return f"Bash({inputs.get('command','')[:80]})"
    if name == "Glob":   return f"Glob({inputs.get('pattern','')})"
    if name == "Grep":   return f"Grep({inputs.get('pattern','')})"
    if name == "WebFetch":  return f"WebFetch({inputs.get('url','')[:60]})"
    if name == "WebSearch": return f"WebSearch({inputs.get('query','')})"
    return f"{name}({list(inputs.values())[:1]})"


# ── Permission prompt ──────────────────────────────────────────────────────

def ask_permission_interactive(desc: str, config: dict) -> bool:
    try:
        print()
        ans = input(clr(f"  Allow: {desc}  [y/N/a(ccept-all)] ", "yellow")).strip().lower()
        if ans == "a":
            config["permission_mode"] = "accept-all"
            ok("  Permission mode set to accept-all for this session.")
            return True
        return ans in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        return False


# ── Slash commands ─────────────────────────────────────────────────────────

def cmd_help(_args: str, _state, _config) -> bool:
    print(__doc__)
    return True

def cmd_clear(_args: str, state, _config) -> bool:
    state.messages.clear()
    state.turn_count = 0
    ok("Conversation cleared.")
    return True

def cmd_model(args: str, _state, config) -> bool:
    from providers import PROVIDERS, detect_provider
    if not args:
        model = config["model"]
        pname = detect_provider(model)
        info(f"Current model:    {model}  (provider: {pname})")
        info("\nAvailable models by provider:")
        for pn, pdata in PROVIDERS.items():
            ms = pdata.get("models", [])
            if ms:
                info(f"  {pn:12s}  " + ", ".join(ms[:4]) + ("..." if len(ms) > 4 else ""))
        info("\nFormat: 'provider/model' or just model name (auto-detected)")
        info("  e.g. /model gpt-4o")
        info("  e.g. /model ollama/qwen2.5-coder")
        info("  e.g. /model kimi:moonshot-v1-32k")
    else:
        # Accept both "ollama/model" and "ollama:model" syntax
        m = args.strip().replace(":", "/", 1)
        config["model"] = m
        pname = detect_provider(m)
        ok(f"Model set to {m}  (provider: {pname})")
        from config import save_config
        save_config(config)
    return True

def cmd_config(args: str, _state, config) -> bool:
    from config import save_config
    if not args:
        display = {k: v for k, v in config.items() if k != "api_key"}
        print(json.dumps(display, indent=2))
    elif "=" in args:
        key, _, val = args.partition("=")
        key, val = key.strip(), val.strip()
        # Type coercion
        if val.lower() in ("true", "false"):
            val = val.lower() == "true"
        elif val.isdigit():
            val = int(val)
        config[key] = val
        save_config(config)
        ok(f"Set {key} = {val}")
    else:
        k = args.strip()
        v = config.get(k, "(not set)")
        info(f"{k} = {v}")
    return True

def cmd_save(args: str, state, _config) -> bool:
    from config import SESSIONS_DIR
    fname = args.strip() or f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    path = Path(fname) if "/" in fname else SESSIONS_DIR / fname
    data = {
        "messages": [
            m if not isinstance(m.get("content"), list) else
            {**m, "content": [
                b if isinstance(b, dict) else b.model_dump()
                for b in m["content"]
            ]}
            for m in state.messages
        ],
        "turn_count": state.turn_count,
        "total_input_tokens": state.total_input_tokens,
        "total_output_tokens": state.total_output_tokens,
    }
    path.write_text(json.dumps(data, indent=2, default=str))
    ok(f"Session saved to {path}")
    return True

def cmd_load(args: str, state, _config) -> bool:
    from config import SESSIONS_DIR
    if not args.strip():
        # List available sessions
        sessions = sorted(SESSIONS_DIR.glob("*.json"))
        if not sessions:
            info("No saved sessions found.")
        else:
            info("Saved sessions:")
            for s in sessions:
                info(f"  {s.name}")
        return True
    fname = args.strip()
    path = Path(fname) if "/" in fname else SESSIONS_DIR / fname
    if not path.exists():
        err(f"File not found: {path}")
        return True
    data = json.loads(path.read_text())
    state.messages = data.get("messages", [])
    state.turn_count = data.get("turn_count", 0)
    state.total_input_tokens = data.get("total_input_tokens", 0)
    state.total_output_tokens = data.get("total_output_tokens", 0)
    ok(f"Session loaded from {path} ({len(state.messages)} messages)")
    return True

def cmd_history(_args: str, state, _config) -> bool:
    if not state.messages:
        info("(empty conversation)")
        return True
    for i, m in enumerate(state.messages):
        role = clr(m["role"].upper(), "bold",
                   "cyan" if m["role"] == "user" else "green")
        content = m["content"]
        if isinstance(content, str):
            print(f"[{i}] {role}: {content[:200]}")
        elif isinstance(content, list):
            for block in content:
                if isinstance(block, dict):
                    btype = block.get("type", "")
                else:
                    btype = getattr(block, "type", "")
                if btype == "text":
                    text = block.get("text", "") if isinstance(block, dict) else block.text
                    print(f"[{i}] {role}: {text[:200]}")
                elif btype == "tool_use":
                    name = block.get("name", "") if isinstance(block, dict) else block.name
                    print(f"[{i}] {role}: [tool_use: {name}]")
                elif btype == "tool_result":
                    cval = block.get("content", "") if isinstance(block, dict) else block.content
                    print(f"[{i}] {role}: [tool_result: {str(cval)[:100]}]")
    return True

def cmd_context(_args: str, state, config) -> bool:
    import anthropic
    # Rough token estimate: 4 chars ≈ 1 token
    msg_chars = sum(
        len(str(m.get("content", ""))) for m in state.messages
    )
    est_tokens = msg_chars // 4
    info(f"Messages:         {len(state.messages)}")
    info(f"Estimated tokens: ~{est_tokens:,}")
    info(f"Model:            {config['model']}")
    info(f"Max tokens:       {config['max_tokens']:,}")
    return True

def cmd_cost(_args: str, state, config) -> bool:
    from config import calc_cost
    cost = calc_cost(config["model"],
                     state.total_input_tokens,
                     state.total_output_tokens)
    info(f"Input tokens:  {state.total_input_tokens:,}")
    info(f"Output tokens: {state.total_output_tokens:,}")
    info(f"Est. cost:     ${cost:.4f} USD")
    return True

def cmd_verbose(_args: str, _state, config) -> bool:
    config["verbose"] = not config.get("verbose", False)
    state_str = "ON" if config["verbose"] else "OFF"
    ok(f"Verbose mode: {state_str}")
    return True

def cmd_thinking(_args: str, _state, config) -> bool:
    config["thinking"] = not config.get("thinking", False)
    state_str = "ON" if config["thinking"] else "OFF"
    ok(f"Extended thinking: {state_str}")
    return True

def cmd_permissions(args: str, _state, config) -> bool:
    from config import save_config
    modes = ["auto", "accept-all", "manual"]
    if not args.strip():
        info(f"Permission mode: {config.get('permission_mode','auto')}")
        info(f"Available modes: {', '.join(modes)}")
    else:
        m = args.strip()
        if m not in modes:
            err(f"Unknown mode: {m}. Choose: {', '.join(modes)}")
        else:
            config["permission_mode"] = m
            save_config(config)
            ok(f"Permission mode set to: {m}")
    return True

def cmd_cwd(args: str, _state, _config) -> bool:
    if not args.strip():
        info(f"Working directory: {os.getcwd()}")
    else:
        p = args.strip()
        try:
            os.chdir(p)
            ok(f"Changed directory to: {os.getcwd()}")
        except Exception as e:
            err(str(e))
    return True

def cmd_exit(_args: str, _state, _config) -> bool:
    ok("Goodbye!")
    sys.exit(0)

COMMANDS = {
    "help":        cmd_help,
    "clear":       cmd_clear,
    "model":       cmd_model,
    "config":      cmd_config,
    "save":        cmd_save,
    "load":        cmd_load,
    "history":     cmd_history,
    "context":     cmd_context,
    "cost":        cmd_cost,
    "verbose":     cmd_verbose,
    "thinking":    cmd_thinking,
    "permissions": cmd_permissions,
    "cwd":         cmd_cwd,
    "exit":        cmd_exit,
    "quit":        cmd_exit,
}


def handle_slash(line: str, state, config) -> bool:
    """Handle /command [args]. Returns True if handled."""
    if not line.startswith("/"):
        return False
    parts = line[1:].split(None, 1)
    if not parts:
        return False
    cmd = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""
    handler = COMMANDS.get(cmd)
    if handler:
        handler(args, state, config)
        return True
    err(f"Unknown command: /{cmd}  (type /help for commands)")
    return True


# ── Input history setup ────────────────────────────────────────────────────

def setup_readline(history_file: Path):
    try:
        readline.read_history_file(str(history_file))
    except FileNotFoundError:
        pass
    readline.set_history_length(1000)
    atexit.register(readline.write_history_file, str(history_file))

    # Tab-complete slash commands
    commands = [f"/{c}" for c in COMMANDS]
    def completer(text: str, state: int):
        matches = [c for c in commands if c.startswith(text)]
        return matches[state] if state < len(matches) else None
    readline.set_completer(completer)
    readline.parse_and_bind("tab: complete")


# ── Main REPL ──────────────────────────────────────────────────────────────

def repl(config: dict, initial_prompt: str = None):
    from config import HISTORY_FILE
    from context import build_system_prompt
    from agent import AgentState, run, TextChunk, ThinkingChunk, ToolStart, ToolEnd, TurnDone, PermissionRequest

    setup_readline(HISTORY_FILE)
    state = AgentState()
    verbose = config.get("verbose", False)

    # Banner
    if not initial_prompt:
        from providers import detect_provider
        model    = config["model"]
        pname    = detect_provider(model)
        model_clr = clr(model, "cyan", "bold")
        prov_clr  = clr(f"({pname})", "dim")
        pmode     = clr(config.get("permission_mode", "auto"), "yellow")
        print(clr("╭─ Nano Claude Code ──────────────────────────────╮", "dim"))
        print(clr("│  Model: ", "dim") + model_clr + " " + prov_clr)
        print(clr("│  Permissions: ", "dim") + pmode)
        print(clr("│  /model to switch provider · /help for commands │", "dim"))
        print(clr("╰──────────────────────────────────────────────────╯", "dim"))
        print()

    def run_query(user_input: str):
        nonlocal verbose
        verbose = config.get("verbose", False)

        # Rebuild system prompt each turn (picks up cwd changes, etc.)
        system_prompt = build_system_prompt()

        print(clr("\n╭─ Claude ", "dim") + clr("●", "green") + clr(" ─────────────────────────", "dim"))
        print(clr("│ ", "dim"), end="", flush=True)

        thinking_started = False

        for event in run(user_input, state, config, system_prompt):
            if isinstance(event, TextChunk):
                stream_text(event.text)

            elif isinstance(event, ThinkingChunk):
                if verbose:
                    if not thinking_started:
                        print(clr("\n  [thinking]", "dim"))
                        thinking_started = True
                    stream_thinking(event.text, verbose)

            elif isinstance(event, ToolStart):
                flush_response()
                print_tool_start(event.name, event.inputs, verbose)

            elif isinstance(event, PermissionRequest):
                event.granted = ask_permission_interactive(event.description, config)

            elif isinstance(event, ToolEnd):
                print_tool_end(event.name, event.result, verbose)
                # Print prefix for next text
                print(clr("│ ", "dim"), end="", flush=True)

            elif isinstance(event, TurnDone):
                if verbose:
                    print(clr(
                        f"\n  [tokens: +{event.input_tokens} in / "
                        f"+{event.output_tokens} out]", "dim"
                    ))

        flush_response()
        print(clr("╰──────────────────────────────────────────────", "dim"))
        print()

    # ── Main loop ──
    if initial_prompt:
        try:
            run_query(initial_prompt)
        except KeyboardInterrupt:
            print()
        return

    while True:
        try:
            cwd_short = Path.cwd().name
            prompt = clr(f"\n[{cwd_short}] ", "dim") + clr("❯ ", "cyan", "bold")
            user_input = input(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            ok("Goodbye!")
            sys.exit(0)

        if not user_input:
            continue
        if handle_slash(user_input, state, config):
            continue

        try:
            run_query(user_input)
        except KeyboardInterrupt:
            print(clr("\n  (interrupted)", "yellow"))
            # Keep conversation history up to the interruption


# ── Entry point ────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="nano_claude",
        description="Nano Claude Code — minimal Python Claude Code implementation",
        add_help=False,
    )
    parser.add_argument("prompt", nargs="*", help="Initial prompt (non-interactive)")
    parser.add_argument("-p", "--print", "--print-output",
                        dest="print_mode", action="store_true",
                        help="Non-interactive mode: run prompt and exit")
    parser.add_argument("-m", "--model", help="Override model")
    parser.add_argument("--accept-all", action="store_true",
                        help="Never ask permission (accept all operations)")
    parser.add_argument("--verbose", action="store_true",
                        help="Show thinking + token counts")
    parser.add_argument("--thinking", action="store_true",
                        help="Enable extended thinking")
    parser.add_argument("--version", action="store_true", help="Print version")
    parser.add_argument("-h", "--help", action="store_true", help="Show help")

    args = parser.parse_args()

    if args.version:
        print(f"nano claude code v{VERSION}")
        sys.exit(0)

    if args.help:
        print(__doc__)
        sys.exit(0)

    from config import load_config, save_config, has_api_key
    from providers import detect_provider, PROVIDERS

    config = load_config()

    # Apply CLI overrides first (so key check uses the right provider)
    if args.model:
        config["model"] = args.model.replace(":", "/", 1)
    if args.accept_all:
        config["permission_mode"] = "accept-all"
    if args.verbose:
        config["verbose"] = True
    if args.thinking:
        config["thinking"] = True

    # Check API key for active provider (warn only, don't block local providers)
    if not has_api_key(config):
        pname = detect_provider(config["model"])
        prov  = PROVIDERS.get(pname, {})
        env   = prov.get("api_key_env", "")
        if env:   # local providers like ollama have no env key requirement
            warn(f"No API key found for provider '{pname}'. "
                 f"Set {env} or run: /config {pname}_api_key=YOUR_KEY")

    initial = " ".join(args.prompt) if args.prompt else None
    if args.print_mode and not initial:
        err("--print requires a prompt argument")
        sys.exit(1)

    repl(config, initial_prompt=initial)


if __name__ == "__main__":
    main()
