import os
import subprocess
from pathlib import Path
from typing import Optional, Dict

from config import load_settings
from .weather import get_weather as _get_weather


_settings = load_settings()
ROOT_DIR = Path(os.environ.get("JARVIS_ROOT", Path(__file__).resolve().parent.parent)).resolve()

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


def _resolve_path(path: str) -> Path:
    p = Path(path)
    if not p.is_absolute():
        p = ROOT_DIR / p
    p = p.resolve()
    if ROOT_DIR not in p.parents and p != ROOT_DIR:
        raise ValueError("Path is outside allowed root")
    return p


def open_url(url: str) -> str:
    return f"Opened {url} in the default browser"


def open_app(name: str) -> str:
    key = normalize_app_key(name)
    return f"Launched app: {key}"


def close_app(name: str) -> str:
    key = normalize_app_key(name)
    return f"Requested to close app: {key}"


def read_file(path: str, max_bytes: int = 8000) -> str:
    p = _resolve_path(path)
    data = p.read_bytes()
    truncated = data[:max_bytes]
    text = truncated.decode("utf-8", errors="replace")
    if len(data) > max_bytes:
        text += "\n... [truncated]"
    return text


def list_dir(path: Optional[str] = None, max_entries: int = 50) -> str:
    p = _resolve_path(path or ".")
    if not p.is_dir():
        return f"{p} is not a directory"
    entries = []
    for i, child in enumerate(sorted(p.iterdir())):
        if i >= max_entries:
            entries.append("... (truncated)")
            break
        tag = "DIR" if child.is_dir() else "FILE"
        entries.append(f"{tag} {child.name}")
    return "\n".join(entries)


def open_in_vscode(path: str) -> str:
    p = _resolve_path(path)
    try:
        subprocess.Popen(["code", str(p)])
        return f"Opened in VS Code: {p}"
    except FileNotFoundError:
        return "VS Code ('code') not found in PATH"


def get_weather(city: Optional[str] = None) -> str:
    return _get_weather(city)
