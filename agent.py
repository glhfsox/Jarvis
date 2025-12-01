import json
from typing import List, Dict, Callable, Any

from openai.types.chat import ChatCompletionMessageParam

from llm_client import ask_llm
from tools.core import open_url, open_app, close_app, get_weather


TOOLS: Dict[str, Callable[..., str]] = {
    "open_url": open_url,
    "open_app": open_app,
    "close_app": close_app,
    "get_weather": get_weather,
}

SYSTEM_TOOLS_DESCRIPTION = """
You have access to the following tools. When you want to call a tool, you MUST respond
ONLY with a JSON object of the form {"tool": "...", "args": {...}}.

Tools:

1) open_url(url: str)
   - Opens the given URL in the system default browser.
   - IMPORTANT: Even if the user says "in Firefox" or "in Chrome",
     you MUST still call only `open_url` and let the OS choose the browser.
   - Example:
     {"tool": "open_url", "args": {"url": "https://spotify.com"}}

2) open_app(name: str)
   - Launches a local application by name, e.g. "steam", "telegram", "firefox", "chrome", "chromium", "spotify".
   - The assistant may receive names like "Telegram Desktop", "гугл хром", "спотифай";
     these will be mapped internally to the correct app.
   - Example:
     {"tool": "open_app", "args": {"name": "telegram"}}

3) close_app(name: str)
   - Tries to close a local application by name (Linux-only, uses 'pkill -f').
   - Uses the same name normalization as open_app.
   - Example:
     {"tool": "close_app", "args": {"name": "chrome"}}

4) get_weather(city: str | optional)
   - Returns a short weather summary for the given city.
   - If no city is provided, use the default city.
   - Example:
     {"tool": "get_weather", "args": {"city": "Warsaw"}}

If no tool is needed, answer the user normally as text.
"""


def make_system_message() -> ChatCompletionMessageParam:
    return {
        "role": "system",
        "content": (
            "You are a local voice assistant running on the user's machine. "
            "Use tools when they can help execute user commands or fetch data.\n\n"
            + SYSTEM_TOOLS_DESCRIPTION
        ),
    }


def handle_user_text(
    history: List[ChatCompletionMessageParam],
    user_text: str,
) -> str:
    history.append({"role": "user", "content": user_text})

    raw = ask_llm(history)

    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError:
        data = None

    if isinstance(data, dict) and "tool" in data:
        tool_name = data.get("tool")
        args = data.get("args", {}) or {}

        if tool_name not in TOOLS:
            reply = f"Unknown tool: {tool_name}"
            history.append({"role": "assistant", "content": reply})
            return reply

        result = TOOLS[tool_name](**args)

        followup = (
            f"User said: {user_text}\n"
            f"I called tool '{tool_name}' with arguments {args}.\n"
            f"Tool returned: {result}\n"
            "Now answer the user based on this."
        )
        history.append({"role": "assistant", "content": followup})

        final = ask_llm(history)
        history.append({"role": "assistant", "content": final})
        return final

    reply = raw
    history.append({"role": "assistant", "content": reply})
    return reply
