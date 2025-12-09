import importlib
import json


def test_normalize_app_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_CONFIG", str(tmp_path / "missing.json"))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    assert core.normalize_app_key("гугл хром!") == "chrome"
    assert core.normalize_app_key("Telegram Desktop") == "telegram"
    assert core.normalize_app_key("visual studio code") == "code"
    assert core.normalize_app_key("браузер firefox") == "firefox"
    assert core.normalize_app_key("vscode,") == "code"
