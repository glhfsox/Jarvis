import importlib
from pathlib import Path


def test_summarize_and_search(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    file_path = root / "hello.txt"
    file_path.write_text("line1\nline2\nline3\nline4\nline5\n")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    summary = core.summarize_file("hello.txt", head_lines=2)
    assert "Size:" in summary
    assert "line1" in summary and "line2" in summary

    res = core.search_text("line3", path="hello.txt", max_matches=5)
    assert "hello.txt" in res
