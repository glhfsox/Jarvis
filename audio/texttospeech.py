import hashlib
import subprocess
import threading
from pathlib import Path
from typing import Optional

from openai import OpenAI
from config import load_settings


_settings = load_settings()
client = OpenAI(api_key=_settings.openai_key)

CACHE_DIR = Path(__file__).resolve().parent / "tts_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_current_proc_lock = threading.Lock()
_current_proc: Optional[subprocess.Popen] = None


def _text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def stop_speaking() -> None:
    global _current_proc
    with _current_proc_lock:
        if _current_proc is not None:
            try:
                _current_proc.terminate()
            except Exception:
                pass
            _current_proc = None


def _tts_worker(text: str, streaming: bool) -> None:
    global _current_proc

    key = _text_hash(text)
    cache_path = CACHE_DIR / f"{key}.mp3"

    # if cached file exists and we are not in streaming mode,
    # just play it
    if cache_path.exists() and not streaming:
        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", str(cache_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with _current_proc_lock:
            _current_proc = proc
        proc.wait()
        with _current_proc_lock:
            if _current_proc is proc:
                _current_proc = None
        return

    if streaming:
        # request streaming response and stream bytes
        # both into ffplay and into cache file 
        resp = client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        )

        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", "-"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with _current_proc_lock:
            _current_proc = proc

        assert proc.stdin is not None

        try:
            with resp as r, open(cache_path, "wb") as f:
                for chunk in r.iter_bytes():
                    if not chunk:
                        continue
                    f.write(chunk)
                    try:
                        proc.stdin.write(chunk)
                    except BrokenPipeError:
                        break
        finally:
            try:
                if proc.stdin:
                    proc.stdin.close()
            except Exception:
                pass
            proc.wait()
            with _current_proc_lock:
                if _current_proc is proc:
                    _current_proc = None
    else:
        #non-streaming
        speech = client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="alloy",
            input=text,
        )
        audio_bytes = speech.read()
        with open(cache_path, "wb") as f:
            f.write(audio_bytes)

        proc = subprocess.Popen(
            ["ffplay", "-nodisp", "-autoexit", str(cache_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with _current_proc_lock:
            _current_proc = proc
        proc.wait()
        with _current_proc_lock:
            if _current_proc is proc:
                _current_proc = None


def looks_like_code(text: str) -> bool:
    if "```" in text:
        return True
    lines = text.splitlines()
    if len(lines) >= 5:
        code_markers = (";", "{", "}", "#include", "def ", "class ", "using ", "public:",
                         "private:", "import" , "from" , "using" ,"div")
        scored = sum(1 for ln in lines if any(tok in ln for tok in code_markers))
        if scored >= 2:
            return True
    return False


def speak(text: str, streaming: bool = True) -> None:
    if not text.strip():
        return

    if looks_like_code(text):
        # avoid reading code aloud just print it to the console
        print(text)
        return

    # stop any current speech first, so we can interrupt
    stop_speaking()

    thread = threading.Thread(
        target=_tts_worker,
        args=(text, streaming),
        daemon=True,
    )
    thread.start()
