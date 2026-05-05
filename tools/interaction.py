"""
tools_interaction.py — Interactive input tools: AskUserQuestion, SleepTimer,
and bridge-routing helpers (Telegram / WeChat / Slack).
"""
from __future__ import annotations

import threading
from typing import Optional

# ── Bridge turn-detection (thread-local) ──────────────────────────────────

_tg_thread_local    = threading.local()
_wx_thread_local    = threading.local()
_slack_thread_local = threading.local()


def _is_in_tg_turn(config: dict) -> bool:
    import runtime
    return (getattr(_tg_thread_local, "active", False)
            or bool(runtime.get_ctx(config).in_telegram_turn))


def _is_in_wx_turn(config: dict) -> bool:
    import runtime
    return (getattr(_wx_thread_local, "active", False)
            or bool(runtime.get_ctx(config).in_wechat_turn))


def _is_in_slack_turn(config: dict) -> bool:
    import runtime
    return (getattr(_slack_thread_local, "active", False)
            or bool(runtime.get_ctx(config).in_slack_turn))


def _is_in_web_turn(config: dict) -> bool:
    import runtime
    return bool(getattr(runtime.get_ctx(config), 'in_web_turn', False))


# ── AskUserQuestion ───────────────────────────────────────────────────────

_INPUT_WAIT_TIMEOUT = 300  # seconds before a remote input request times out


def _ask_user_question(
    question: str,
    options: list[dict] | None = None,
    allow_freetext: bool = True,
    config: dict | None = None,
) -> str:
    """Render a question to the user and synchronously return their answer.

    Runs in the agent thread that invoked the tool: prints the question,
    then delegates to ``ask_input_interactive`` so terminal/Telegram/WeChat/
    Slack/Web bridges all read input through their normal path.
    """
    config = config or {}
    options = options or []

    print()
    print("\033[1;35m❓ Question from assistant:\033[0m")
    print(f"   {question}")

    if options:
        print()
        for i, opt in enumerate(options, 1):
            label = opt.get("label", "")
            desc  = opt.get("description", "")
            line  = f"  [{i}] {label}"
            if desc:
                line += f" — {desc}"
            print(line)
        if allow_freetext:
            print("  [0] Type a custom answer")
        print()

        while True:
            raw = ask_input_interactive(
                "Your choice (number or text): ", config
            ).strip()
            if not raw:
                return ""
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(options):
                    return options[idx - 1].get("label", "")
                if idx == 0 and allow_freetext:
                    return ask_input_interactive("Your answer: ", config).strip()
                print(f"Invalid option: {idx}")
                continue
            if allow_freetext:
                return raw
            print("Please choose a number from the list.")

    print()
    return ask_input_interactive("Your answer: ", config).strip()


# ── ask_input_interactive (bridge routing) ────────────────────────────────

def ask_input_interactive(prompt: str, config: dict,
                          menu_text: str = None,
                          options: list[tuple[str, str]] | None = None) -> str:
    """Route input prompt to Telegram / WeChat / Slack bridge or terminal.

    `options` (optional) is a list of ``(button_label, return_value)`` pairs.
    When set and the active bridge supports it (Telegram today), the prompt
    is rendered as an inline_keyboard with one button per option; the user's
    click delivers the matching return_value back through the normal input
    event.  Bridges without inline-button support (WeChat, Slack, terminal)
    ignore `options` — callers should put a hint like ``[y/N/a]`` in the
    prompt text so those clients still know what to type.
    """
    import re as _re
    import threading as _threading
    import runtime as _runtime

    _session_ctx = _runtime.get_session_ctx(config.get("_session_id", "default"))

    # ── Slack ──────────────────────────────────────────────────────────────
    if _is_in_slack_turn(config) and _session_ctx.slack_send is not None:
        clean_prompt = _re.sub(r'\x1b\[[0-9;]*m', '', prompt).strip()
        payload = ""
        if menu_text:
            payload += _re.sub(r'\x1b\[[0-9;]*m', '', menu_text).strip() + "\n\n"
        payload += f"❓ Input Required\n{clean_prompt}"
        slack_channel = (_runtime.get_ctx(config).slack_current_channel
                         or config.get("slack_channel", ""))
        _session_ctx.slack_send(slack_channel, payload)
        evt = _threading.Event()
        _session_ctx.slack_input_event = evt
        if not evt.wait(timeout=_INPUT_WAIT_TIMEOUT):
            _session_ctx.slack_input_event = None
            return "(timeout: no input received)"
        text = _session_ctx.slack_input_value.strip()
        _session_ctx.slack_input_event = None
        _session_ctx.slack_input_value = ""
        return text

    # ── WeChat ─────────────────────────────────────────────────────────────
    if _is_in_wx_turn(config) and _session_ctx.wx_send is not None:
        clean_prompt = _re.sub(r'\x1b\[[0-9;]*m', '', prompt).strip()
        payload = ""
        if menu_text:
            payload += _re.sub(r'\x1b\[[0-9;]*m', '', menu_text).strip() + "\n\n"
        payload += f"❓ 需要输入\n{clean_prompt}"
        _session_ctx.wx_send(_runtime.get_ctx(config).wx_current_user_id or "", payload)
        evt = _threading.Event()
        _session_ctx.wx_input_event = evt
        if not evt.wait(timeout=_INPUT_WAIT_TIMEOUT):
            _session_ctx.wx_input_event = None
            return "(timeout: no input received)"
        text = _session_ctx.wx_input_value.strip()
        _session_ctx.wx_input_event = None
        _session_ctx.wx_input_value = ""
        return text

    # ── Web (chat API) ────────────────────────────────────────────────────
    if getattr(_session_ctx, 'in_web_turn', False):
        # Permission event is already pushed to WS by ChatSession._run_agent.
        # Just block here until the browser responds via /api/approve.
        evt = _threading.Event()
        _session_ctx.web_input_event = evt
        if not evt.wait(timeout=_INPUT_WAIT_TIMEOUT):
            _session_ctx.web_input_event = None
            return "(timeout: no input received)"
        text = _session_ctx.web_input_value.strip()
        _session_ctx.web_input_event = None
        _session_ctx.web_input_value = ""
        return text

    # ── Telegram ───────────────────────────────────────────────────────────
    if _is_in_tg_turn(config) and _session_ctx.tg_send is not None:
        token   = config.get("telegram_token")
        chat_id = config.get("telegram_chat_id")
        clean_prompt = _re.sub(r'\x1b\[[0-9;]*m', '', prompt).strip()
        payload = ""
        if menu_text:
            payload += _re.sub(r'\x1b\[[0-9;]*m', '', menu_text).strip() + "\n\n"
        payload += f"❓ *Input Required*\n{clean_prompt}"

        if options:
            # Inline-keyboard path: render real Telegram buttons. callback_data
            # carries a short prompt id so a click on a stale prompt cannot
            # deliver to the current waiting agent.
            import uuid as _uuid
            from bridges.telegram import _tg_send_keyboard
            prompt_id = _uuid.uuid4().hex[:8]
            keyboard = [
                [{"text": str(label),
                  "callback_data": f"cc:{prompt_id}:{value}"[:64]}]
                for (label, value) in options
            ]
            evt = _threading.Event()
            # Set the wiring BEFORE sending so a fast click cannot race in
            # before tg_input_event / tg_callback_prompt_id are visible.
            _session_ctx.tg_input_event = evt
            _session_ctx.tg_callback_prompt_id = prompt_id
            msg_id = _tg_send_keyboard(token, chat_id, payload, keyboard)
            _session_ctx.tg_callback_message_id = msg_id or 0
        else:
            _session_ctx.tg_send(token, chat_id, payload)
            evt = _threading.Event()
            _session_ctx.tg_input_event = evt

        if not evt.wait(timeout=_INPUT_WAIT_TIMEOUT):
            _session_ctx.tg_input_event = None
            _session_ctx.tg_callback_prompt_id = ""
            _session_ctx.tg_callback_message_id = 0
            return "(timeout: no input received)"
        text = _session_ctx.tg_input_value.strip()
        _session_ctx.tg_input_event = None
        _session_ctx.tg_input_value = ""
        _session_ctx.tg_callback_prompt_id = ""
        _session_ctx.tg_callback_message_id = 0
        return text

    # ── Terminal ────────────────────────────────────────────────────────────
    try:
        rl_prompt = _re.sub(r'(\x1b\[[0-9;]*m)', r'\001\1\002', prompt)
        return input(rl_prompt)
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


# ── SleepTimer ────────────────────────────────────────────────────────────

def _sleeptimer(seconds: int, config: dict) -> str:
    import runtime
    session_ctx = runtime.get_session_ctx(config.get("_session_id", "default"))
    cb = session_ctx.run_query
    if not cb:
        return "Error: No active REPL session (run_query not set for this session)"

    def worker():
        import time
        time.sleep(seconds)
        cb(
            "(System Automated Event): The timer has finished. "
            "Please wake up, perform any pending monitoring checks "
            "and report to the user now."
        )

    threading.Thread(target=worker, daemon=True).start()
    return (
        f"Timer successfully scheduled for {seconds} seconds. "
        "You can output your final thoughts and end your turn. "
        "You will be automatically awakened."
    )
