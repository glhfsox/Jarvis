import json
from json import JSONDecoder
from typing import List, Dict, Callable, Any

from openai.types.chat import ChatCompletionMessageParam

from llm_client import ask_llm
from tools.core import (
    open_url,
    open_app,
    close_app,
    get_weather,
    read_file,
    list_dir,
    open_in_vscode,
    summarize_file,
    search_text,
    write_file,
    make_dir,
)


TOOLS: Dict[str, Callable[..., str]] = {
    "open_url": open_url,
    "open_app": open_app,
    "close_app": close_app,
    "get_weather": get_weather,
    "read_file": read_file,
    "list_dir": list_dir,
    "open_in_vscode": open_in_vscode,
    "summarize_file": summarize_file,
    "search_text": search_text,
    "write_file": write_file,
    "make_dir": make_dir,
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
   - Launches a local application by name, e.g. "steam", "telegram", "firefox", "chrome", "chromium", "spotify",
     editors like "code" / "vscode", or a terminal such as "terminal" / "gnome-terminal".
   - The assistant may receive names like "Telegram Desktop", "гугл хром", "спотифай", "visual studio code", "терминал";
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

5) read_file(path: str, max_bytes?: int)
   - Reads a text file from the project root (or a subpath) and returns its contents (truncated if too long).
   - Paths are resolved relative to the project root; access outside root is blocked.
   - Example:
     {"tool": "read_file", "args": {"path": "README.md"}}

6) list_dir(path?: str, max_entries?: int)
   - Lists files/directories at the given path (default: project root).
   - Paths are resolved relative to the project root.
   - Example:
     {"tool": "list_dir", "args": {"path": "cpp"}}

7) open_in_vscode(path: str)
   - Opens the given file or folder in VS Code (uses the 'code' CLI).
   - Paths are resolved relative to the project root.
   - Example:
     {"tool": "open_in_vscode", "args": {"path": "cpp/actions.cpp"}}

8) summarize_file(path: str, max_bytes?: int, head_lines?: int)
   - Returns a short summary: path, size, and the first N lines (truncated).
   - Example:
     {"tool": "summarize_file", "args": {"path": "README.md", "head_lines": 30}}

9) search_text(query: str, path?: str, max_matches?: int)
   - Grep-like search (using ripgrep) under the project root.
   - Example:
     {"tool": "search_text", "args": {"query": "window_close_last", "path": "cpp"}}

10) write_file(path: str, content: str, append?: bool)
    - Writes text to a file (creates parent directories if needed). Paths are rooted to the project root.
    - Absolute paths or ones starting with ~ are allowed if they resolve inside the project root or Documents (~/Documents).
    - Aliases: "current directory"/"project root" -> ~/githubproj/Jarvis; "documents/..." -> ~/Documents.
    - Example:
      {"tool": "write_file", "args": {"path": "notes/todo.txt", "content": "hello", "append": true}}

11) make_dir(path: str)
    - Creates a directory (parents ok) under the project root.
    - Absolute/~ paths allowed if inside project root or Documents (~/Documents). Same aliases as above.
    - Example:
      {"tool": "make_dir", "args": {"path": "logs/run1"}}

RULES FOR PATH REQUESTS:
- For any request to create a folder/file ("create/make folder/file", "создай папку/файл"), call make_dir or write_file.
- Treat "current directory/current folder/project root/корень проекта/здесь" as the project root directory.
- Treat paths starting with "documents/", "документы/", "docs/" as under ~/Documents.
- Preserve user-provided path text (including '~') when calling the tool; the backend will normalize it.
- If the tool succeeds, confirm using the normalized path returned by the tool.

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
    def _extract_tool_call(raw: str) -> dict | None:
        dec = JSONDecoder()
        s = raw.strip()

        try:
            data: Any = json.loads(s)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "tool" in data:
            return data
        if isinstance(data, list) and data and isinstance(data[0], dict) and "tool" in data[0]:
            return data[0]

        # robust path: find the first json object/array anywhere in the response 
        for i, ch in enumerate(raw):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(raw[i:])
            except Exception:
                continue
            if isinstance(obj, dict) and "tool" in obj:
                return obj
            if isinstance(obj, list) and obj and isinstance(obj[0], dict) and "tool" in obj[0]:
                return obj[0]
        return None

    history.append({"role": "user", "content": user_text})

    raw = ask_llm(history)

    tool_call = _extract_tool_call(raw)
    if tool_call is not None:
        tool_name = tool_call.get("tool")
        args = tool_call.get("args", {}) or {}

        if tool_name not in TOOLS:
            reply = f"Unknown tool: {tool_name}"
            history.append({"role": "assistant", "content": reply})
            return reply

        result = TOOLS[tool_name](**args)

        # Return the tool result directly to avoid the model outputting mixed JSON+text
        # and to ensure deterministic confirmation for filesystem operations.
        history.append({"role": "assistant", "content": result})
        return result

    reply = raw
    history.append({"role": "assistant", "content": reply})
    return reply
