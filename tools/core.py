import subprocess
import webbrowser
from typing import Optional, Dict

from config import load_settings
from .weather import get_weather as _get_weather


_settings = load_settings()

APP_COMMANDS: Dict[str, str] = _settings.app_commands or {
    "firefox": "firefox",
    "browser": "firefox",
    "chrome": "google-chrome",
    "chromium": "chromium",
    "telegram": "telegram-desktop",
    "spotify": "spotify",
}


APP_SYNONYMS: Dict[str, str] = {
    "firefox": "firefox",
    "mozilla firefox": "firefox",
    "браузер": "firefox",
    "браузер файрфокс": "firefox",
    "браузер firefox": "firefox",

    "chrome": "chrome",
    "google chrome": "chrome",
    "гугл хром": "chrome",
    "хром": "chrome",

    
    "chromium": "chromium",
    "гугл хромиум": "chromium",
    "хромиум": "chromium",
    
    "telegram": "telegram",
    "telegram desktop": "telegram",
    "телеграм": "telegram-desktop",
    "телеграм десктоп": "telegram",
    "телега" : "telegram",
    "телегу" : "telegram" ,

    "spotify": "spotify",
    "спотифай": "spotify",
    "спотик" : "spotify",
}


def normalize_app_key(name: str) -> str:
    base = name.lower().strip()
    for ch in [".", ",", "!", "?", ":"]:
        base = base.replace(ch, "")
    base = base.strip()

    
    if base in APP_SYNONYMS:
        return APP_SYNONYMS[base]

    if base.endswith(" browser"):
        base = base.replace(" browser", "").strip()
    if base.endswith(" браузер"):
        base = base.replace(" браузер", "").strip()

    if base in APP_SYNONYMS:
        return APP_SYNONYMS[base]

    return base


def open_url(url: str) -> str:
    """
    Always open URL in the system default browser.
    We intentionally ignore which browser the user mentions.
    """
    try:
        webbrowser.open(url)
        return f"Opened {url} in the default browser"
    except Exception as e:
        return f"Failed to open URL: {e}"


def open_app(name: str) -> str:
    key = normalize_app_key(name)
    cmd = APP_COMMANDS.get(key)
    if not cmd:
        return f"Unknown app: {name}"
    try:
        subprocess.Popen(
            cmd.split(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return f"Launched app: {key}"
    except Exception as e:
        return f"Failed to launch app '{name}': {e}"


def close_app(name: str) -> str:
    """
    Tries to close an app by killing its process based on the binary name.
    Linux-only (uses pkill -f).
    """
    key = normalize_app_key(name)
    cmd = APP_COMMANDS.get(key)
    if not cmd:
        return f"Unknown app: {name}"

    pattern = cmd.split()[0]
    try:
        subprocess.run(
            ["pkill", "-f", pattern],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return f"Requested to close app: {key}"
    except Exception as e:
        return f"Failed to close app '{name}': {e}"


def get_weather(city: Optional[str] = None) -> str:
    return _get_weather(city)
