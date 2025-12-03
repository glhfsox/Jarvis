from typing import Optional
from .speechtotext import transcribe_once

WAKE_WORDS = {"jarvis", "джарвис"}


def _contains_wake_word(text: str) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return any(w in lowered for w in WAKE_WORDS)


def wait_for_wake_word(max_attempts: int = 5) -> bool:
    
    for attempt in range(1, max_attempts + 1):
        print(f"Attempt {attempt}/{max_attempts}: waiting for wake word...")
        text = transcribe_once()  

        if not text:
            print("No speech recognized.")
            continue

        if _contains_wake_word(text):
            print(f"Wake word detected in: {text!r}")
            return True

        print(f"No wake word in: {text!r}")

    print("Wake word not detected, giving up.")
    return False


def listen_command_after_wake() -> Optional[str]:
    if not wait_for_wake_word():
        return None

    print(" Wake word detected, listening for command...")
    cmd = transcribe_once()
    if not cmd:
        print("Empty command after wake word.")
        return None
    return cmd
