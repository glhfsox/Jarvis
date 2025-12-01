import os
from dataclasses import dataclass


@dataclass
class Settings:
    openai_key: str
    chat_model: str = "gpt-5.1"
    stt_model: str = "whisper-1"
    stt_sample_rate: int = 16000
    recording_duration: float = 5.0
    openweather_api_key: str | None = None
    default_city: str = "Warsaw"
    app_commands: dict | None = None


def load_settings() -> Settings:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set")

    ow_key = os.getenv("OPENWEATHER_API_KEY")

    app_commands = {
        "steam": "steam",
        "telegram": "telegram-desktop",
        "firefox": "firefox",
        "browser": "firefox",
        "code": "code",
        "vscode": "code",
        "spotify": "spotify",
    }

    return Settings(
        openai_key=api_key,
        openweather_api_key=ow_key,
        app_commands=app_commands,
    )
