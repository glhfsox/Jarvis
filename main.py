from typing import List
from openai.types.chat import ChatCompletionMessageParam
from config import load_settings
from agent import handle_user_text, make_system_message
from audio.speechtotext import transcribe_once
from audio.texttospeech import speak, stop_speaking
from audio.wakeword import listen_command_after_wake
from cpp_assistant import CppAssistant

EXIT_KEYWORDS = {
    "exit", "quit", "end", "stop", "bye",
    "выход", "конец", "стоп", "хватит", "до свидания",
}


def is_exit_phrase(text: str) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(word in lower for word in EXIT_KEYWORDS) or lower.strip() == "q"


def main() -> None:
    settings = load_settings()

    history: List[ChatCompletionMessageParam] = [make_system_message()]

    cpp = CppAssistant(binary_path="./assistant")
    cpp.start()

    print("=== Local Assistant – press ENTER to speak, type text or 'exit' to quit ===")
    print("Instructions:")
    print("  - Press ENTER on an empty line to speak (microphone).")
    print("  - Type a message and press ENTER to send text directly.")
    print("  - Say or type: exit / quit / стоп / выход (etc.) to quit.")
    print()

    try:
        while True:
            user_input = input(">>> ")

            if is_exit_phrase(user_input):
                stop_speaking()
                speak("Goodbye.", streaming=True)
                break

            if user_input.strip() == "":
                stop_speaking()
                if settings.use_wake_word:
                    user_text = listen_command_after_wake()
                else : 
                    user_text = transcribe_once()
                if not user_text:
                    print("[MAIN] No transcription. Try again.")
                    continue
                print(f"[VOICE] {user_text}")
            else:
                stop_speaking()
                user_text = user_input.strip()
                print(f"[TEXT] {user_text}")

            if is_exit_phrase(user_text):
                stop_speaking()
                speak("Goodbye.", streaming=True)
                break

            cpp.send_chunk(user_text)

            reply = handle_user_text(history, user_text)
            print(f"AI: {reply}")
            speak(reply, streaming=True)

    finally:
        cpp.stop()


if __name__ == "__main__":
    main()
