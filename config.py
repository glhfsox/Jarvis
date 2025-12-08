import json
import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    openai_key: str
    chat_model: str = "gpt-5.1"
    stt_model: str = "whisper-1"
    stt_sample_rate: int = 16000
    recording_duration: float = 5.0
    openweather_api_key: str | None = None
    default_city: str = "Warsaw"
    app_commands: dict | None = None
    use_wake_word: bool = False
    default_browser: str = "firefox"
    default_terminal: str = "gnome-terminal"
    volume_step_percent: int = 5
    brightness_step_percent: int = 5


def _load_json_config() -> dict:
    path = os.environ.get("JARVIS_CONFIG", "jarvis.config.json")
    cfg_path = Path(path)
    if not cfg_path.exists():
        return {}
    try:
        return json.loads(cfg_path.read_text())
    except Exception:
        return {}


def _get_int(cfg: dict, key: str, default: int) -> int:
    try:
        return int(cfg.get(key, default))
    except Exception:
        return default


def load_settings() -> Settings:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    ow_key = os.environ.get("OPENWEATHER_API_KEY")
    cfg = _load_json_config()

    default_app_commands = {
        "steam": "steam",
        "telegram": "telegram-desktop",
        "firefox": "firefox",
        "browser": "firefox",
        "code": "code",
        "vscode": "code",
        "spotify": "spotify",
        "chrome": "google-chrome",
        "chromium": "chromium",
        "terminal": "gnome-terminal",
    }

    app_commands = cfg.get("app_commands") or default_app_commands

    return Settings(
        openai_key=api_key,
        openweather_api_key=ow_key,
        app_commands=app_commands,
        use_wake_word=cfg.get("use_wake_word", os.getenv("JARVIS_USE_WAKE_WORD", "0") == "1"),
        default_browser=cfg.get("default_browser", "firefox"),
        default_terminal=cfg.get("default_terminal", "gnome-terminal"),
        volume_step_percent=_get_int(cfg, "volume_step_percent", 5),
        brightness_step_percent=_get_int(cfg, "brightness_step_percent", 5),
    )
