import importlib
from pathlib import Path


def test_agent_runs_multiple_tools(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs = tmp_path / "Docs"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs))

    core = importlib.import_module("tools.core")
    importlib.reload(core)
    agent = importlib.import_module("agent")
    importlib.reload(agent)

    monkeypatch.setattr(
        agent,
        "ask_llm",
        lambda _history: (
            '[{"tool":"make_dir","args":{"path":"a"}},'
            '{"tool":"write_file","args":{"path":"a/x.txt","content":"hi","append":false}},'
            '{"tool":"delete_path","args":{"path":"a/x.txt"}}]'
        ),
    )

    history = [agent.make_system_message()]
    out = agent.handle_user_text(history, "create folder a, write file, then delete it")

    assert "Directory ensured" in out
    assert "Wrote to" in out
    assert "Deleted file" in out
    assert (root / "a").is_dir()
    assert not (root / "a" / "x.txt").exists()


def test_agent_extracts_embedded_json_array(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs = tmp_path / "Docs"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs))

    core = importlib.import_module("tools.core")
    importlib.reload(core)
    agent = importlib.import_module("agent")
    importlib.reload(agent)

    monkeypatch.setattr(
        agent,
        "ask_llm",
        lambda _history: (
            "Sure:\n"
            '[{"tool":"write_file","args":{"path":"documents/note.txt","content":"doc","append":false}},'
            '{"tool":"delete_path","args":{"path":"documents/note.txt"}}]'
            "\nDone."
        ),
    )

    history = [agent.make_system_message()]
    out = agent.handle_user_text(history, "write then delete a doc note")

    assert "Wrote to" in out
    assert "Deleted file" in out
    assert not (Path(str(docs)) / "note.txt").exists()

