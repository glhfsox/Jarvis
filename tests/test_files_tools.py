import importlib
import os
from pathlib import Path


def test_read_and_list(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    file_path = root / "hello.txt"
    file_path.write_text("hello world")
    subdir = root / "sub"
    subdir.mkdir()
    (subdir / "inner.txt").write_text("inner")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    content = core.read_file("hello.txt")
    assert "hello world" in content

    listing = core.list_dir(".")
    assert "FILE hello.txt" in listing
    assert "DIR sub" in listing
