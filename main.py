import threading
from queue import Empty, Queue
from typing import List, Tuple

from openai.types.chat import ChatCompletionMessageParam
from config import load_settings
from agent import handle_user_text, make_system_message
from audio.texttospeech import speak, stop_speaking
from audio.speechtotext import transcribe_once
from cpp_assistant import CppAssistant
from audio.wakeword import WakeWordEngine
from dotenv import load_dotenv

load_dotenv()
EXIT_KEYWORDS = {
    "exit", "quit", "end", "stop", "bye", "пока" ,
    "выход", "конец", "стоп", "хватит", "до свидания",
}


def is_exit_phrase(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(word in lower for word in EXIT_KEYWORDS) or lower.strip() == "q"


def _local_ack(text: str) -> str | None:
    t = text.lower()

    if "unmute" in t or "turn on sound" in t:
        return "Unmuted system audio."
    if "mute" in t and any(k in t for k in ["sound", "audio", "volume"]):
        return "Muted system audio."

    if any(k in t for k in ["volume up", "turn up", "louder"]):
        return "Volume increased."
    if any(k in t for k in ["volume down", "turn down", "quieter", "softer"]):
        return "Volume decreased."

    if any(k in t for k in ["brightness up", "brighter"]):
        return "Brightness increased."
    if any(k in t for k in ["brightness down", "dim", "dimmer"]):
        return "Brightness decreased."

    if "wifi off" in t or "turn off wifi" in t:
        return "Wi-Fi turned off."
    if "wifi on" in t or "turn on wifi" in t:
        return "Wi-Fi turned on."

    if "bluetooth off" in t or "turn off bluetooth" in t:
        return "Bluetooth turned off."
    if "bluetooth on" in t or "turn on bluetooth" in t:
        return "Bluetooth turned on."

    return None


def _process_user_text(
    history: List[ChatCompletionMessageParam],
    cpp: CppAssistant,
    user_text: str,
    speak_back: bool = True,
) -> bool:
    if is_exit_phrase(user_text):
        stop_speaking()
        if speak_back:
            speak("Goodbye.", streaming=True)
        return True

    cpp.send_chunk(user_text)

    ack = _local_ack(user_text)
    if ack:
        print(f"AI: {ack}")
        if speak_back:
            speak(ack, streaming=True)
        return False

    reply = handle_user_text(history, user_text)
    print(f"AI: {reply}")
    if speak_back:
        speak(reply, streaming=True)
    return False


def main() -> None:
    settings = load_settings()

    history: List[ChatCompletionMessageParam] = [make_system_message()]

    cpp = CppAssistant(binary_path="./assistant")
    cpp.start()

    print("=== Local Assistant ===")
    print("Instructions:")
    print("  - Type a message and press ENTER to send text directly.")
    print("  - Press ENTER on an empty line to record a quick voice command.")
    if settings.use_wake_word:
        print("  - Wake word enabled: say 'Jarvis' and speak.")
    print("  - Say or type: exit / quit / стоп / выход (etc.) to quit.")
    print()

    events: "Queue[Tuple[str, str | None]]" = Queue()
    stop_event = threading.Event()

    wake = None
    if settings.use_wake_word:
        wake = WakeWordEngine(
            on_command=lambda cmd: events.put(("wake", cmd)),
        )
        wake.start()

    def _stdin_reader() -> None:
        try:
            while not stop_event.is_set():
                line = input(">>> ")
                events.put(("text", line))
        except EOFError:
            pass
        finally:
            events.put(("shutdown", None))

    threading.Thread(target=_stdin_reader, daemon=True).start()

    try:
        while True:
            try:
                source, payload = events.get(timeout=0.2)
            except Empty:
                continue

            if source == "shutdown":
                break

            if source == "wake":
                user_text = (payload or "").strip()
                if not user_text:
                    print("[WAKE] Empty command after wake word.")
                    continue
                print(f"[WAKE] {user_text}")
                if _process_user_text(history, cpp, user_text):
                    break
                continue

            user_input = payload or ""
            if is_exit_phrase(user_input):
                stop_speaking()
                speak("Goodbye.", streaming=True)
                break

            if user_input.strip() == "":
                stop_speaking()
                user_text = transcribe_once()
                if not user_text:
                    print("[MAIN] No transcription. Try again.")
                    continue
                print(f"[VOICE] {user_text}")
                speak_back = True
            else:
                stop_speaking()
                user_text = user_input.strip()
                print(f"[TEXT] {user_text}")
                speak_back = False

            if _process_user_text(history, cpp, user_text, speak_back):
                break

    finally:
        stop_event.set()
        if wake:
            wake.stop()
        cpp.stop()


if __name__ == "__main__":
    main()
