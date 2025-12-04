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
    "exit", "quit", "end", "stop", "bye",
    "выход", "конец", "стоп", "хватит", "до свидания",
}


def is_exit_phrase(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(word in lower for word in EXIT_KEYWORDS) or lower.strip() == "q"


def _process_user_text(
    history: List[ChatCompletionMessageParam],
    cpp: CppAssistant,
    user_text: str,
) -> bool:
    """
    Returns True if the app should exit.
    """
    if is_exit_phrase(user_text):
        stop_speaking()
        speak("Goodbye.", streaming=True)
        return True

    cpp.send_chunk(user_text)

    reply = handle_user_text(history, user_text)
    print(f"AI: {reply}")
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
        print("  - Wake word enabled: say 'Jarvis' (Porcupine) and speak.")
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
            else:
                stop_speaking()
                user_text = user_input.strip()
                print(f"[TEXT] {user_text}")

            if _process_user_text(history, cpp, user_text):
                break

    finally:
        stop_event.set()
        if wake:
            wake.stop()
        cpp.stop()


if __name__ == "__main__":
    main()
