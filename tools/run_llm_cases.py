import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

# ensure project root is on sys.path 
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from openai import OpenAI

from config import load_settings


def build_prompt(transcript: str) -> str:
    #mirror the C++ buildPrompt logic so comparisons stay consistent
    prompt = []
    prompt.append("You are a command parser for a LOCAL voice assistant.")
    prompt.append("I will give you a transcript of the last few seconds of the user's speech (in English or Russian).")
    prompt.append("")
    prompt.append("Your task:")
    prompt.append("1) Extract ALL executable commands that appear in the text.")
    prompt.append("2) Return ONLY JSON. Never add explanations, comments, or extra text.")
    prompt.append("")
    prompt.append("VALID JSON OUTPUT FORMS:")
    prompt.append("- If there are NO commands -> return: null")
    prompt.append("- If there is ONE command -> return a single object OR an array with one object")
    prompt.append("- If there are MULTIPLE commands -> return a JSON array of objects")
    prompt.append("")
    prompt.append("Each command object must have the structure:")
    prompt.append(r'{"name": "<command_name>", "args": {...}, "raw_text": "<original_text_fragment>"}')
    prompt.append("")
    prompt.append("ALLOWED COMMANDS:")
    prompt.append("  - open_url(url: string)")
    prompt.append("  - open_app(name: string)")
    prompt.append("  - close_app(name: string)")
    prompt.append("  - open_terminal(command: optional string)")
    prompt.append("  - media_play_pause()")
    prompt.append("  - media_next()")
    prompt.append("  - media_prev()")
    prompt.append("  - media_volume_up()")
    prompt.append("  - media_volume_down()")
    prompt.append("  - media_seek_forward()")
    prompt.append("  - media_seek_backward()")
    prompt.append("  - media_volume_mute()")
    prompt.append("  - media_volume_unmute()")
    prompt.append("  - system_volume_up()")
    prompt.append("  - system_volume_down()")
    prompt.append("  - system_volume_mute()")
    prompt.append("  - system_volume_unmute()")
    prompt.append("  - system_brightness_up()")
    prompt.append("  - system_brightness_down()")
    prompt.append("  - wifi_on()")
    prompt.append("  - wifi_off()")
    prompt.append("  - bluetooth_on()")
    prompt.append("  - bluetooth_off()")
    prompt.append("  - system_lock()")
    prompt.append("  - system_shutdown()")
    prompt.append("  - system_reboot()")
    prompt.append("  - window_focus(name?: string, id?: string)  # prefer id if provided")
    prompt.append("  - window_close(name?: string, id?: string)  # prefer id if provided")
    prompt.append("  - window_inspect(name?: string)             # list windows, optionally highlight best match")
    prompt.append("")
    prompt.append("  - window_focus_last()")
    prompt.append("  - window_close_last()")
    prompt.append("")
    prompt.append("Rules:")
    prompt.append("- ALWAYS return valid JSON only (null, object, or array).")
    prompt.append("- If the user asks for several actions in one phrase ('open youtube and vs code'), split them into multiple command objects in an array.")
    prompt.append("- Do NOT invent URLs; use only those explicitly mentioned.")
    prompt.append("- Convert phrases like 'youtube dot com' -> 'youtube.com'.")
    prompt.append("- Preserve the original user phrase in raw_text.")
    prompt.append("- If the user says 'open Firefox' then later 'close it', you MUST use window_close_last(), not close_app.")
    prompt.append("- Same for terminals and apps: 'close it' / 'закрой его' -> window_close_last().")
    prompt.append("")
    prompt.append('Here is the transcript:')
    prompt.append(f'"""{transcript}"""')
    return "\n".join(prompt)


def run_cases(cases: List[Dict[str, Any]], model: str | None = None) -> Dict[str, Any]:
    settings = load_settings()
    client = OpenAI(api_key=settings.openai_key)
    use_model = model or settings.chat_model

    results: Dict[str, Any] = {}
    for case in cases:
        cid = case.get("id")
        transcript = case.get("transcript", "")
        if not cid:
            continue
        try:
            prompt = build_prompt(transcript)
            resp = client.chat.completions.create(
                model=use_model,
                messages=[
                    {"role": "system", "content": "You parse voice commands and return ONLY JSON."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=256,
                temperature=0.0,
            )
            content = resp.choices[0].message.content or ""
            parsed: Any
            try:
                parsed = json.loads(content)
            except Exception:
                parsed = content
            results[cid] = parsed
        except Exception as e:
            results[cid] = {"error": str(e)}
    return results


def main():
    parser = argparse.ArgumentParser(description="Run LLM parser over cases and dump results for A/B compare.")
    parser.add_argument("--cases", required=True, help="JSON file with cases: [{id, transcript, expected?}, ...]")
    parser.add_argument("--output", required=True, help="Path to write run results JSON (id -> raw content)")
    parser.add_argument("--model", help="Override model (defaults to chat_model from config)")
    args = parser.parse_args()

    cases = json.loads(Path(args.cases).read_text())
    results = run_cases(cases, model=args.model)
    Path(args.output).write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"Wrote {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
