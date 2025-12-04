import os
import threading
from pathlib import Path
from typing import Callable, List, Optional

import pvporcupine as pv
from dotenv import load_dotenv
from pvporcupine import Porcupine
from pvrecorder import PvRecorder

from .speechtotext import transcribe_once

load_dotenv()


def _first_existing(pattern: str) -> Optional[str]:
    base = Path(pv.__file__).resolve().parent
    for path in base.glob(pattern):
        if path.is_file():
            return str(path)
    return None


PICOVOICE_ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY")

_ENV_LIB = os.environ.get("PICOVOICE_LIBRARY_PATH")
_AUTO_LIB = _first_existing("lib/**/libpv_porcupine.*")
PICOVOICE_LIBRARY_PATH = _ENV_LIB if _ENV_LIB else _AUTO_LIB

_ENV_MODEL = os.environ.get("PICOVOICE_MODEL_PATH")
_AUTO_MODEL = _first_existing("lib/common/porcupine_params.pv")
PICOVOICE_MODEL_PATH = _ENV_MODEL if _ENV_MODEL else _AUTO_MODEL
PICOVOICE_KEYWORD_PATH = os.environ.get(
    "PICOVOICE_KEYWORD_PATH",
    os.path.join("audio", "wakewords", "Jarvis_en_linux_v3_0_0.ppn"),
)


def _create_porcupine(
    keyword_paths: List[str],
    sensitivities: Optional[List[float]] = None,
) -> Porcupine:
    if not PICOVOICE_ACCESS_KEY:
        raise RuntimeError("PICOVOICE_ACCESS_KEY is not set")

    if sensitivities is None:
        sensitivities = [0.6] * len(keyword_paths)

    lib_path = PICOVOICE_LIBRARY_PATH
    if lib_path and not Path(lib_path).exists() and _AUTO_LIB:
        print(f"[WAKE] Provided library path {lib_path!r} missing, using {_AUTO_LIB!r}")
        lib_path = _AUTO_LIB
    if not lib_path or not Path(lib_path).exists():
        raise RuntimeError(
            f"PICOVOICE_LIBRARY_PATH not found at {lib_path!r}. "
            "Set it in .env or export it to point at libpv_porcupine.so."
        )

    model_path = PICOVOICE_MODEL_PATH
    if model_path and not Path(model_path).exists() and _AUTO_MODEL:
        print(f"[WAKE] Provided model path {model_path!r} missing, using {_AUTO_MODEL!r}")
        model_path = _AUTO_MODEL
    if not model_path or not Path(model_path).exists():
        raise RuntimeError(
            f"PICOVOICE_MODEL_PATH not found at {model_path!r}. "
            "Set it in .env or export it to point at porcupine_params.pv."
        )

    return pv.create(
        access_key=PICOVOICE_ACCESS_KEY,
        library_path=lib_path,
        model_path=model_path,
        keyword_paths=keyword_paths,
        sensitivities=sensitivities,
    )


def listen_command_after_wake(
    keyword_paths: Optional[List[str]] = None,
    sensitivities: Optional[List[float]] = None,
) -> Optional[str]:
    """
    Blocking helper: waits for the wake word once, then records a short command.
    """
    keyword_paths = keyword_paths or [PICOVOICE_KEYWORD_PATH]
    try:
        porcupine = _create_porcupine(keyword_paths, sensitivities)
    except Exception as exc:
        print(f"[WAKE] Could not initialise Porcupine: {exc}")
        return None

    recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
    print("[WAKE] Listening for wake word...")

    try:
        recorder.start()
        while True:
            pcm = recorder.read()
            result = porcupine.process(pcm)
            if result >= 0:
                print("[WAKE] Wake word detected.")
                break
    except Exception as exc:
        print(f"[WAKE] Wake word error: {exc}")
        return None
    finally:
        try:
            recorder.stop()
        except Exception:
            pass
        recorder.delete()
        porcupine.delete()

    print("[WAKE] Listening for command...")
    cmd = transcribe_once()
    if not cmd:
        print("[WAKE] Empty command after wake word.")
        return None
    return cmd


class WakeWordEngine:
    """
    Runs a background Porcupine loop and triggers a callback with the transcribed
    command once the wake word is heard. Stops/starts around STT so the mic
    is not held by both Porcupine and sounddevice at the same time.
    """

    def __init__(
        self,
        keyword_paths: Optional[List[str]] = None,
        sensitivities: Optional[List[float]] = None,
        on_command: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.keyword_paths = keyword_paths or [PICOVOICE_KEYWORD_PATH]
        self.sensitivities = sensitivities
        self.on_command = on_command

        self.enabled = bool(PICOVOICE_ACCESS_KEY)
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> bool:
        if not PICOVOICE_ACCESS_KEY:
            print("[WAKE] PICOVOICE_ACCESS_KEY is not set; wake word disabled.")
            self.enabled = False
            return False

        if self._thread and self._thread.is_alive():
            return True

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self.enabled = True
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
        self.enabled = False

    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            cmd = self._listen_once()
            if not cmd:
                continue

            if self._stop_event.is_set():
                break

            if self.on_command:
                try:
                    self.on_command(cmd)
                except Exception as exc:
                    print(f"[WAKE] on_command callback failed: {exc}")
                    break

    def _listen_once(self) -> Optional[str]:
        try:
            porcupine = _create_porcupine(self.keyword_paths, self.sensitivities)
        except Exception as exc:
            print(f"[WAKE] Could not initialise Porcupine: {exc}")
            self._stop_event.set()
            return None

        recorder = PvRecorder(device_index=-1, frame_length=porcupine.frame_length)
        print("[WAKE] Listening for wake word...")

        try:
            recorder.start()
            while not self._stop_event.is_set():
                pcm = recorder.read()
                result = porcupine.process(pcm)
                if result >= 0:
                    print("[WAKE] Wake word detected.")
                    break
        except Exception as exc:
            print(f"[WAKE] Wake word error: {exc}")
            return None
        finally:
            try:
                recorder.stop()
            except Exception:
                pass
            recorder.delete()
            porcupine.delete()

        if self._stop_event.is_set():
            return None

        print("[WAKE] Listening for command...")
        cmd = transcribe_once()
        if not cmd:
            print("[WAKE] Empty command after wake word.")
            return None
        return cmd
