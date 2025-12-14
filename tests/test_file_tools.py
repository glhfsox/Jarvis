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

    # empty file creation (content omitted)
    res_empty = core.write_file("empty.txt")
    assert "Wrote to" in res_empty
    assert (root / "empty.txt").read_text() == ""

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


def test_move_copy_rename(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs = tmp_path / "Docs"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    core.write_file("a.txt", "hi", append=False)
    res_move = core.move_path("a.txt", "b.txt")
    assert "Moved:" in res_move
    assert not (root / "a.txt").exists()
    assert (root / "b.txt").read_text() == "hi"

    res_move_docs = core.move_path("b.txt", "documents/b.txt")
    assert "Moved:" in res_move_docs
    assert not (root / "b.txt").exists()
    assert (docs / "b.txt").read_text() == "hi"

    res_rename = core.rename_path("documents/b.txt", "c.txt")
    assert "Moved:" in res_rename
    assert not (docs / "b.txt").exists()
    assert (docs / "c.txt").read_text() == "hi"

    core.make_dir("dir1")
    core.write_file("dir1/x.txt", "x", append=False)
    res_copy_dir = core.copy_path("dir1", "dir2")
    assert "Copied directory" in res_copy_dir
    assert (root / "dir1" / "x.txt").read_text() == "x"
    assert (root / "dir2" / "x.txt").read_text() == "x"


def test_replace_and_insert_text(monkeypatch, tmp_path):
    root = tmp_path / "proj"
    docs = tmp_path / "Docs"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(docs))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    core.write_file("edit.txt", "line1\nline2\n", append=False)

    res_insert = core.insert_text("edit.txt", text="INSERT\n", after="line1\n")
    assert "Inserted text" in res_insert
    assert (root / "edit.txt").read_text() == "line1\nINSERT\nline2\n"

    res_replace = core.replace_text("edit.txt", old="line2", new="LINE2", count=1)
    assert "Replaced 1 occurrence" in res_replace
    assert (root / "edit.txt").read_text() == "line1\nINSERT\nLINE2\n"


def test_refuses_recursive_copy_or_move(monkeypatch, tmp_path):
    root = tmp_path / "proj"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(tmp_path / "Docs"))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    core.make_dir("dir")
    res_move = core.move_path("dir", "dir/sub")
    assert "into itself" in res_move.lower()

    core.make_dir("dir2")
    res_copy = core.copy_path("dir2", "dir2/sub")
    assert "into itself" in res_copy.lower()


def test_rename_rejects_path_new_name(monkeypatch, tmp_path):
    root = tmp_path / "proj"

    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("JARVIS_ROOT", str(root))
    monkeypatch.setenv("JARVIS_DOCUMENTS", str(tmp_path / "Docs"))

    core = importlib.import_module("tools.core")
    importlib.reload(core)

    core.write_file("a.txt", "x", append=False)
    res = core.rename_path("a.txt", "sub/a.txt")
    assert "invalid new_name" in res.lower()

