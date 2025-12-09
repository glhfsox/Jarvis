import json
import importlib
import os
from pathlib import Path


def test_load_settings_custom_config(monkeypatch, tmp_path):
    cfg_path = tmp_path / "jarvis.config.json"
    cfg_data = {
        "default_browser": "google-chrome",
        "default_terminal": "alacritty",
        "volume_step_percent": 7,
        "brightness_step_percent": 11,
        "app_commands": {"browser": "google-chrome", "code": "code-insiders"},
        "use_wake_word": True,
    }
    cfg_path.write_text(json.dumps(cfg_data))

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_CONFIG", str(cfg_path))

    config = importlib.import_module("config")
    importlib.reload(config)
    settings = config.load_settings()

    assert settings.default_browser == "google-chrome"
    assert settings.default_terminal == "alacritty"
    assert settings.volume_step_percent == 7
    assert settings.brightness_step_percent == 11
    assert settings.use_wake_word is True
    assert settings.app_commands["browser"] == "google-chrome"
    assert settings.app_commands["code"] == "code-insiders"


def test_load_settings_defaults(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    # point to a non-existent config to avoid picking up user/repo file
    monkeypatch.setenv("JARVIS_CONFIG", str(tmp_path / "nope.json"))

    config = importlib.import_module("config")
    importlib.reload(config)
    settings = config.load_settings()

    assert settings.default_browser == "firefox"
    assert settings.default_terminal == "gnome-terminal"
    assert settings.volume_step_percent == 5
    assert settings.brightness_step_percent == 5
    assert settings.app_commands["browser"] == "firefox"
    assert settings.app_commands["telegram"] == "telegram-desktop"
