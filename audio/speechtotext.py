import tempfile
import wave
from typing import Optional

import sounddevice as sd
import numpy as np
from openai import OpenAI

from config import load_settings

_settings = load_settings()
_client = OpenAI(api_key=_settings.openai_key)


def _record_audio_to_wav_file(path: str, duration_sec: float, sample_rate: int) -> None:
    print(f"[STT] Listening for {duration_sec:.1f} seconds...")

    frames = int(duration_sec * sample_rate)
    audio = sd.rec(frames, samplerate=sample_rate, channels=1, dtype="int16")
    sd.wait()

    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(audio.tobytes())


def transcribe_once() -> Optional[str]:
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name

        _record_audio_to_wav_file(
            path=wav_path,
            duration_sec=_settings.recording_duration,
            sample_rate=_settings.stt_sample_rate,
        )

        print("[STT] Sending audio for transcription...")

        with open(wav_path, "rb") as audio_file:
            result = _client.audio.transcriptions.create(
                model="whisper-1", 
                file=audio_file,
                response_format="json",
            )

    except Exception as e:
        print(f"Speech-to-text error: {e}")
        return None

    text = getattr(result, "text", None)
    if not text:
        print("[STT] Empty transcription result.")
        return None

    print(f"[STT] You said: {text!r}")
    return text.strip()
