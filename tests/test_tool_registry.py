import importlib


def test_registry_discovers_tools(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(tmp_path / "proj"))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(tmp_path / "Docs"))

    registry = importlib.import_module("tools.registry")

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    specs = registry.get_tool_specs()
    for name in [
        "make_dir",
        "write_file",
        "delete_path",
        "move_path",
        "copy_path",
        "rename_path",
        "replace_text",
        "insert_text",
    ]:
        assert name in specs

    prompt = registry.build_system_tools_description(extra_rules="EXTRA")
    assert "Tools:" in prompt
    assert "make_dir" in prompt
