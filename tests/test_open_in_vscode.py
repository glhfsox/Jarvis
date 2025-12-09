import importlib
import os
from pathlib import Path


def test_open_in_vscode_missing(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    target = root / "foo.txt"
    target.write_text("test")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("PATH", "")  # ensure 'code' is not found

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    res = core.open_in_vscode("foo.txt")
    assert "not found" in res.lower()
