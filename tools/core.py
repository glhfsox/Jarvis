import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict

from config import load_settings
from .weather import get_weather as _get_weather
import logging

logger = logging.getLogger("jarvis.core")

def _env_path(name: str, default: Path) -> Path:
    val = os.environ.get(name)
    base = Path(val) if val is not None else default
    return base.expanduser().resolve()

_settings = load_settings()
ROOT_DIR = _env_path("JARVIS_ROOT", Path(__file__).resolve().parent.parent)
DOCS_DIR = _env_path("JARVIS_DOCUMENTS", Path.home() / "Documents")

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
    def normalize_user_path(raw: str):
        s = raw.strip()
        lower = s.lower()

        current_aliases = (
            "current directory", "current dir", "current folder",
            "текущая директория", "текущая папка",
            "project root", "project directory", "project folder",
            "root of project", "root folder", "корень проекта",
            "this directory", "this folder", "here", ".", "здесь"
        )
        if lower in current_aliases or lower == "":
            return ".", ROOT_DIR

        for prefix in ("jarvis/", "джарвис/", "jarvis\\", "джарвис\\"):
            if lower.startswith(prefix):
                return s[len(prefix):], ROOT_DIR
        if lower in ("jarvis", "джарвис"):
            return ".", ROOT_DIR

        for prefix in ("documents/", "документы/", "documents\\", "документы\\", "docs/"):
            if lower.startswith(prefix):
                return s[len(prefix):], DOCS_DIR
        if lower in ("documents", "документы", "docs"):
            return ".", DOCS_DIR

        return s or ".", ROOT_DIR

    norm, base_root = normalize_user_path(path)
    p = Path(norm).expanduser()
    base_root = base_root.expanduser()
    if not p.is_absolute():
        p = base_root / p
    p = p.expanduser().resolve()

    def under(root: Path) -> bool:
        return p == root or root in p.parents

    allowed_roots = [ROOT_DIR]
    if DOCS_DIR:
        allowed_roots.append(DOCS_DIR)

    if not any(under(r) for r in allowed_roots):
        raise ValueError("Path is outside allowed roots")
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


def summarize_file(path: str, max_bytes: int = 16000, head_lines: int = 20) -> str:
    if max_bytes is None or max_bytes <= 0:
        max_bytes = getattr(_settings, "summarize_max_bytes", 16000)
        if max_bytes <= 0:
            logger.warning("summarize_max_bytes <= 0; therefore was set to 16k. change the parameter in config.")
            max_bytes = 16000
    if head_lines is None or head_lines <= 0:
        head_lines = getattr(_settings, "summarize_head_lines", 20)
        if head_lines <= 0:
            logger.warning("summarize_head_lines <= 0; therefore was set to 20. change the parameter in config.")
            head_lines = 20
    p = _resolve_path(path)
    if p.is_dir():
        return f"{p} is a directory; try list_dir instead"
    data = p.read_bytes()
    truncated = data[:max_bytes]
    text = truncated.decode("utf-8", errors="replace")
    lines = text.splitlines()
    head = "\n".join(lines[:head_lines])
    meta = f"Path: {p}\nSize: {len(data)} bytes"
    if len(data) > max_bytes:
        head += "\n... [truncated]"
    return f"{meta}\n\n{head}"


def _search_text(target: Path, query: str, max_matches: int) -> str:
    matches = []

    def search_file(f: Path):
        try:
            if f.stat().st_size > 200_000:
                return
        except OSError:
            return
        try:
            with f.open("r", encoding="utf-8", errors="ignore") as fh:
                for idx, line in enumerate(fh, start=1):
                    if query in line:
                        matches.append(f"{f}:{idx}:{line.rstrip()}")
                        if len(matches) >= max_matches:
                            return True
        except (OSError, UnicodeError):
            return
        return False

    if target.is_file():
        search_file(target)
    else:
        for f in target.rglob("*"):
            if len(matches) >= max_matches:
                break
            if f.is_file():
                if search_file(f):
                    break

    if not matches:
        return "No matches"
    if len(matches) > max_matches:
        matches = matches[:max_matches] + ["... (truncated)"]
    return "\n".join(matches)


def search_text(query: str, path: Optional[str] = None, max_matches: int = 20) -> str:
    target = _resolve_path(path or ".")
    if not query.strip():
        return "Empty query"
    cmd = ["rg", "-n", "--with-filename", "--max-count", "1", "--max-filesize", "200K", query, str(target)]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return _search_text(target, query, max_matches)
    if proc.returncode not in (0, 1):
        return f"rg error: {proc.stderr.strip()}"
    lines = proc.stdout.strip().splitlines()
    if not lines:
        return _search_text(target, query, max_matches)
    if len(lines) > max_matches:
        lines = lines[:max_matches] + ["... (truncated)"]
    return "\n".join(lines)

def make_dir(path: str) -> str:
    p = _resolve_path(path)
    try:
        p.mkdir(parents=True, exist_ok=True)
        msg = f"Directory ensured: {p}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to create directory {p}: {e}"


def write_file(path: str, content: str = "", append: bool = False) -> str:
    p = _resolve_path(path)
    try:
        if content is None:
            content = ""
        p.parent.mkdir(parents=True, exist_ok=True)
        mode = "a" if append else "w"
        with p.open(mode, encoding="utf-8") as f:
            f.write(content)
        action = "Appended to" if append else "Wrote to"
        msg = f"{action} {p}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to write {p}: {e}"

def delete_path(path: str, recursive: bool = True) -> str:
    p = _resolve_path(path)
    try:
        if p == ROOT_DIR or (DOCS_DIR and p == DOCS_DIR):
            return f"Refusing to delete root directory: {p}"

        if not p.exists():
            return f"Path not found: {p}"

        if p.is_dir():
            if recursive:
                shutil.rmtree(p)
            else:
                p.rmdir()
            msg = f"Deleted directory: {p}"
            print(f"Jarvis: {msg}")
            return msg

        p.unlink()
        msg = f"Deleted file: {p}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to delete {p}: {e}"


def move_path(src: str, dest: str, overwrite: bool = False) -> str:
    src_p = _resolve_path(src)
    dest_p = _resolve_path(dest)
    try:
        if not src_p.exists():
            return f"Path not found: {src_p}"

        if dest_p.is_dir():
            dest_final = dest_p / src_p.name
        else:
            dest_final = dest_p

        if src_p == dest_final:
            return f"Source and destination are the same: {src_p}"

        if src_p.is_dir() and src_p in dest_final.parents:
            return f"Refusing to move a directory into itself: {src_p} -> {dest_final}"

        dest_final.parent.mkdir(parents=True, exist_ok=True)

        if dest_final.exists():
            if not overwrite:
                return f"Destination exists: {dest_final}"
            if dest_final == ROOT_DIR or (DOCS_DIR and dest_final == DOCS_DIR):
                return f"Refusing to delete root directory: {dest_final}"
            if dest_final.is_dir():
                shutil.rmtree(dest_final)
            else:
                dest_final.unlink()

        shutil.move(str(src_p), str(dest_final))
        msg = f"Moved: {src_p} -> {dest_final}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to move {src_p} -> {dest_p}: {e}"


def copy_path(src: str, dest: str, overwrite: bool = False) -> str:
    src_p = _resolve_path(src)
    dest_p = _resolve_path(dest)
    try:
        if not src_p.exists():
            return f"Path not found: {src_p}"

        if dest_p.is_dir():
            dest_final = dest_p / src_p.name
        else:
            dest_final = dest_p

        if src_p == dest_final:
            return f"Source and destination are the same: {src_p}"

        if src_p.is_dir() and src_p in dest_final.parents:
            return f"Refusing to copy a directory into itself: {src_p} -> {dest_final}"

        if dest_final.exists():
            if not overwrite:
                return f"Destination exists: {dest_final}"
            if dest_final == ROOT_DIR or (DOCS_DIR and dest_final == DOCS_DIR):
                return f"Refusing to delete root directory: {dest_final}"
            if dest_final.is_dir():
                shutil.rmtree(dest_final)
            else:
                dest_final.unlink()

        if src_p.is_dir():
            shutil.copytree(src_p, dest_final)
            msg = f"Copied directory: {src_p} -> {dest_final}"
        else:
            dest_final.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_p, dest_final)
            msg = f"Copied file: {src_p} -> {dest_final}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to copy {src_p} -> {dest_p}: {e}"


def rename_path(path: str, new_name: str, overwrite: bool = False) -> str:
    p = _resolve_path(path)
    try:
        if not p.exists():
            return f"Path not found: {p}"

        name = (new_name or "").strip()
        if not name:
            return "Invalid new_name"
        if "/" in name or "\\" in name:
            return "Invalid new_name (must be a name, not a path)"
        if name in (".", ".."):
            return "Invalid new_name"

        dest_final = p.parent / name
        return move_path(str(p), str(dest_final), overwrite=overwrite)
    except Exception as e:
        return f"Failed to rename {p}: {e}"


def replace_text(path: str, old: str, new: str, count: int = 1) -> str:
    p = _resolve_path(path)
    try:
        if not p.exists():
            return f"Path not found: {p}"
        if p.is_dir():
            return f"{p} is a directory"
        if not old:
            return "Old text is empty"

        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Failed to read {p}: not valid text"

        occurrences = text.count(old)
        if occurrences == 0:
            return f"Text not found in {p}"

        if count is None:
            count = 1
        if count <= 0:
            count = -1

        replaced = occurrences if count == -1 else min(count, occurrences)
        new_text = text.replace(old, new, count)
        p.write_text(new_text, encoding="utf-8")

        msg = f"Replaced {replaced} occurrence(s) in {p}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to edit {p}: {e}"


def insert_text(path: str, text: str, after: str | None = None, before: str | None = None) -> str:
    p = _resolve_path(path)
    try:
        if not p.exists():
            return f"Path not found: {p}"
        if p.is_dir():
            return f"{p} is a directory"
        if after and before:
            return "Provide only one of 'after' or 'before'"

        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Failed to read {p}: not valid UTF-8 text"

        insert_at = None
        if after is not None:
            idx = content.find(after)
            if idx == -1:
                return f"Anchor not found in {p}"
            insert_at = idx + len(after)
        elif before is not None:
            idx = content.find(before)
            if idx == -1:
                return f"Anchor not found in {p}"
            insert_at = idx
        else:
            insert_at = len(content)

        updated = content[:insert_at] + (text or "") + content[insert_at:]
        p.write_text(updated, encoding="utf-8")

        msg = f"Inserted text into {p}"
        print(f"Jarvis: {msg}")
        return msg
    except Exception as e:
        return f"Failed to edit {p}: {e}"


def get_weather(city: Optional[str] = None) -> str:
    return _get_weather(city)
