NOTE : this readme was genereated by ai , so are some comments . im too lazy tho

# Jarvis – Local Voice Assistant

Jarvis is a small local voice assistant that runs in your terminal. It listens through your microphone, answers with synthetic speech, and can open apps, browse to URLs, and check the weather via a few simple tools.

## Features
- Voice input powered by OpenAI Whisper (`whisper-1`).
- Chat responses via OpenAI Chat Completions (default model `gpt-5.1`).
- Text‑to‑speech using `gpt-4o-mini-tts` streamed to `ffplay`.
- Tools for opening URLs, launching/closing local apps, and fetching weather from OpenWeather.
- Works both with spoken input and plain typed text.

## Requirements
- Python 3.9+.
- `ffmpeg` / `ffplay` installed and available in `PATH`.
- Python dependencies from `requirements.txt`.

## Installation

Create and activate a virtual environment (optional, but recommended):

```bash
python -m venv .venv
source .venv/bin/activate  # on Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Configuration

Jarvis is configured via environment variables (see `config.py`):

- `OPENAI_API_KEY` – required, used for chat, STT and TTS.
- `OPENWEATHER_API_KEY` – optional, enables real weather data.

You can also adjust default models, recording duration, default city and app command mappings in `config.py`.

## Running

From the project root:

```bash
python main.py
```

Then follow the on‑screen instructions:

- Press Enter on an empty line to record a short voice command.
- Or type a message and press Enter to send text.
- Say or type `exit`, `quit`, `стоп`, `выход`, etc. to close Jarvis.
App launching/closing is currently tuned for Linux (uses `pkill` and binary names like `telegram-desktop`, `firefox`, etc.). Adjust `app_commands` in `config.py` if your setup is different.

Fast Local C++ Action Engine
Jarvis now uses a separate C++ daemon (see `cpp/`) for instant system-level actions.  
It handles fast app launching, URL opening, media controls, system commands, and window actions — all executed locally and independently from Python.
