import tempfile
import wave
from typing import Optional

import sounddevice as sd
from openai import OpenAI

from config import load_settings

_settings = load_settings()
client = OpenAI(api_key=_settings.openai_key)

HOTWORDS = ["джарвис", "jarvis", "эй джарвис", "hey jarvis" , "алло" , "nigga"]


def record_chunk(duration_sec: float = 3.0, sample_rate: int = 16000) -> str:
    frames = int(duration_sec * sample_rate)
    audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())

    return path


def listen_for_command() -> Optional[str]:
    """
    Records a short chunk of audio, transcribes it and,
    if a hotword is present, returns the text AFTER the hotword.
    Otherwise returns None.
    """
    path = record_chunk(duration_sec=3.0, sample_rate=_settings.stt_sample_rate)

    try:
        with open(path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=_settings.stt_model,  # whisper-1
                file=f,
            )
    except Exception:
        return None

    text = (result.text or "").strip()
    if not text:
        return None

    lower = text.lower()

    for hot in HOTWORDS:
        idx = lower.find(hot)
        if idx != -1:
            cmd = text[idx + len(hot):].strip(" ,.!?;:")
            return cmd or ""

    return None
