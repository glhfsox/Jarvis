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
    "code": "code",
    "vscode": "code",
    "terminal": "gnome-terminal",
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

    "terminal": "terminal",
    "gnome terminal": "terminal",
    "gnome-terminal": "terminal",
    "терминал": "terminal",

    "code": "code",
    "vs code": "code",
    "vscode": "code",
    "visual studio code": "code",
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
    return f"Opened {url} in the default browser"


def open_app(name: str) -> str:
    key = normalize_app_key(name)
    return f"Launched app: {key}"


def close_app(name: str) -> str:
    key = normalize_app_key(name)
    return f"Requested to close app: {key}"


def get_weather(city: Optional[str] = None) -> str:
    return _get_weather(city)
