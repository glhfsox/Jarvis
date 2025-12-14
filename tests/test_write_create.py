import importlib
import os
from pathlib import Path


def test_write_and_make_dir(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(tmp_path / "Docs"))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    res_dir = core.make_dir("foo/bar")
    assert "Directory ensured" in res_dir
    assert (root / "foo" / "bar").is_dir()

    res_write = core.write_file("foo/bar/file.txt", "hello", append=False)
    assert "Wrote to" in res_write
    assert (root / "foo" / "bar" / "file.txt").read_text() == "hello"

    res_append = core.write_file("foo/bar/file.txt", " world", append=True)
    assert "Appended to" in res_append
    assert (root / "foo" / "bar" / "file.txt").read_text() == "hello world"

    # documents alias
    res_docs_dir = core.make_dir("documents/sub")
    assert "Directory ensured" in res_docs_dir
    docs_root = Path(os.environ["JARVIS_DOCUMENTS"])
    assert (docs_root / "sub").is_dir()

    res_docs_file = core.write_file("documents/note.txt", "doc", append=False)
    assert "Wrote to" in res_docs_file
    assert (docs_root / "note.txt").read_text() == "doc"


def test_tilde_paths(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", "~/jarvis_root")
    monkeypatch.setenv("JARVIS_DOCUMENTS", "~/Documents")

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    res_root = core.make_dir("nested/root")
    assert "Directory ensured" in res_root
    assert (home / "jarvis_root" / "nested" / "root").is_dir()

    res_docs_alias = core.make_dir("documents/sub")
    assert "Directory ensured" in res_docs_alias
    assert (home / "Documents" / "sub").is_dir()

    res_docs_tilde = core.write_file("~/Documents/note.txt", "hi", append=False)
    assert "Wrote to" in res_docs_tilde
    assert (home / "Documents" / "note.txt").read_text() == "hi"


def test_delete_path_file_and_dir(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs_root = tmp_path / "Docs"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs_root))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    core.write_file("tmp.txt", "x", append=False)
    assert (root / "tmp.txt").exists()

    res_del_file = core.delete_path("tmp.txt")
    assert "Deleted file" in res_del_file
    assert not (root / "tmp.txt").exists()

    core.make_dir("dir1")
    core.write_file("dir1/a.txt", "y", append=False)
    assert (root / "dir1" / "a.txt").exists()

    res_del_dir = core.delete_path("dir1")
    assert "Deleted directory" in res_del_dir
    assert not (root / "dir1").exists()

    core.write_file("documents/note.txt", "doc", append=False)
    assert (docs_root / "note.txt").exists()

    res_del_docs_file = core.delete_path("documents/note.txt")
    assert "Deleted file" in res_del_docs_file
    assert not (docs_root / "note.txt").exists()


def test_delete_path_refuses_roots(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs_root = tmp_path / "Docs"
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs_root))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    res_root = core.delete_path(".")
    assert "Refusing to delete root directory" in res_root

    res_docs = core.delete_path("documents")
    assert "Refusing to delete root directory" in res_docs
