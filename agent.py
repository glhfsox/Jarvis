import json
from json import JSONDecoder
from typing import List, Dict, Callable, Any

from openai.types.chat import ChatCompletionMessageParam

from llm_client import ask_llm
from tools.registry import get_tools_map, build_system_tools_description


TOOLS: Dict[str, Callable[..., str]] = get_tools_map()

_EXTRA_RULES = """
RULES FOR PATH REQUESTS:
- For any request to create a folder/file ("create/make folder/file", "создай папку/файл"), call make_dir or write_file.
- For any request to delete/remove a file/folder ("delete/remove", "удали/удалить"), call delete_path.
- For "move/перемести/переместить/rename/переименуй/переименовать/copy/скопируй/скопировать", use move_path/rename_path/copy_path.
- For "replace/замени/заменить", use replace_text. For "insert/вставь/вставить/добавь ... после/перед", use insert_text.
- Treat "current directory/current folder/project root/корень проекта/здесь" as the project root directory.
- Treat paths starting with "documents/", "документы/", "docs/" as under ~/Documents.
- If the user says "in it/в ней/в нём", apply it to the most recently mentioned directory in the SAME request.
- If the user says "delete the last/удали последний", delete the last file path mentioned in the SAME request.
- Preserve user-provided path text (including '~') when calling the tool; the backend will normalize it.
- If the tool succeeds, confirm using the normalized path returned by the tool.

MULTI-ACTION EXAMPLE (keep output JSON only):
User: "создай папку ii в текущей директории, в ней создай файл out.txt и put.txt и удали последний"
Assistant:
[
  {"tool":"make_dir","args":{"path":"ii"}},
  {"tool":"write_file","args":{"path":"ii/out.txt","content":""}},
  {"tool":"write_file","args":{"path":"ii/put.txt","content":""}},
  {"tool":"delete_path","args":{"path":"ii/put.txt"}}
]

If no tool is needed, answer the user normally as text.
"""

SYSTEM_TOOLS_DESCRIPTION = build_system_tools_description(extra_rules=_EXTRA_RULES)


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
    def _extract_tool_calls(raw: str) -> list[dict]:
        dec = JSONDecoder()
        s = raw.strip()

        try:
            data: Any = json.loads(s)
        except json.JSONDecodeError:
            data = None
        if isinstance(data, dict) and "tool" in data:
            return [data]
        if isinstance(data, list):
            tool_items = [x for x in data if isinstance(x, dict) and "tool" in x]
            if tool_items:
                return tool_items

        # robust path: find the first json object/array anywhere in the response 
        for i, ch in enumerate(raw):
            if ch not in "{[":
                continue
            try:
                obj, _end = dec.raw_decode(raw[i:])
            except Exception:
                continue
            if isinstance(obj, dict) and "tool" in obj:
                return [obj]
            if isinstance(obj, list):
                tool_items = [x for x in obj if isinstance(x, dict) and "tool" in x]
                if tool_items:
                    return tool_items
        return []

    history.append({"role": "user", "content": user_text})

    raw = ask_llm(history)

    tool_calls = _extract_tool_calls(raw)
    if tool_calls:
        results: list[str] = []
        for call in tool_calls:
            tool_name = call.get("tool")
            args = call.get("args", {}) or {}

            if tool_name not in TOOLS:
                results.append(f"Unknown tool: {tool_name}")
                continue

            try:
                results.append(TOOLS[tool_name](**args))
            except Exception as e:
                results.append(f"Tool '{tool_name}' failed: {type(e).__name__}: {e}")

        out = results[0] if len(results) == 1 else "\n".join(f"{i+1}) {r}" for i, r in enumerate(results))
        history.append({"role": "assistant", "content": out})
        return out

    reply = raw
    history.append({"role": "assistant", "content": reply})
    return reply
