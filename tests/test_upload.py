"""M1 的 D5：上传端点的落盘、拒绝与清理。

用内存仓库 + tmp_path，不碰数据库：

    python -m pytest tests/test_upload.py -q
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main
from repo import InMemoryRepo

PDF = b"%PDF-1.4 hello"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    """把落盘目录指到 tmp_path，并把仓库换成内存实现。"""
    root = tmp_path / "uploads"
    monkeypatch.setenv("KB_UPLOAD_DIR", str(root))
    repo = InMemoryRepo()
    main.app.dependency_overrides[main.get_repo] = lambda: repo
    with TestClient(main.app) as c:
        c.repo = repo
        c.upload_root = root
        yield c
    main.app.dependency_overrides.clear()


def files_in(root):
    return sorted(p.name for p in root.glob("*"))


def test_upload_saves_bytes_and_row(env):
    r = env.post("/documents/upload", files={"file": ("policy.pdf", PDF, "application/pdf")})
    assert r.status_code == 201
    body = r.json()
    assert body["filename"] == "policy.pdf"
    assert body["size_bytes"] == len(PDF)
    assert body["stored_path"].endswith("_policy.pdf")
    saved = env.upload_root / body["stored_path"]
    assert saved.read_bytes() == PDF
    # 临时 .part 必须清干净
    assert not [n for n in files_in(env.upload_root) if n.endswith(".part")]
    # 库里确实记了这条
    assert env.repo.get(body["id"])["stored_path"] == body["stored_path"]


def test_uploaded_doc_is_visible_to_list_and_get(env):
    doc_id = env.post(
        "/documents/upload", files={"file": ("faq.md", b"# hi", "text/markdown")}
    ).json()["id"]
    assert [d["filename"] for d in env.get("/documents").json()] == ["faq.md"]
    assert env.get(f"/documents/{doc_id}").json()["stored_path"].endswith("_faq.md")


def test_duplicate_returns_409_and_leaves_no_orphan(env):
    assert env.post("/documents/upload", files={"file": ("a.txt", b"1", "text/plain")}).status_code == 201
    r = env.post("/documents/upload", files={"file": ("a.txt", b"2", "text/plain")})
    assert r.status_code == 409
    # 只剩第一次那一个文件，第二次的落盘已回收
    assert len(files_in(env.upload_root)) == 1


@pytest.mark.parametrize("name", ["evil.exe", "noext", "shell.php"])
def test_extension_whitelist(env, name):
    r = env.post("/documents/upload", files={"file": (name, b"x", "application/octet-stream")})
    assert r.status_code == 422
    assert files_in(env.upload_root) == []


def test_empty_file_rejected(env):
    r = env.post("/documents/upload", files={"file": ("empty.txt", b"", "text/plain")})
    assert r.status_code == 422
    assert files_in(env.upload_root) == []


def test_oversize_returns_413_and_cleans_up(env, monkeypatch):
    monkeypatch.setattr(main, "MAX_BYTES", 8)
    r = env.post("/documents/upload", files={"file": ("big.txt", b"x" * 64, "text/plain")})
    assert r.status_code == 413
    assert files_in(env.upload_root) == []


def test_path_traversal_filename_is_flattened(env):
    r = env.post(
        "/documents/upload",
        files={"file": ("../../etc/evil.txt", b"pwn", "text/plain")},
    )
    assert r.status_code == 201
    stored = r.json()["stored_path"]
    assert ".." not in stored and "/" not in stored and "\\" not in stored
    assert stored.endswith("_evil.txt")
    # 没在 uploads 之外写出任何东西
    assert not (env.upload_root.parent / "etc").exists()


def test_delete_removes_file_from_disk(env):
    body = env.post(
        "/documents/upload", files={"file": ("gone.pdf", PDF, "application/pdf")}
    ).json()
    path = env.upload_root / body["stored_path"]
    assert path.exists()

    assert env.delete(f"/documents/{body['id']}").status_code == 204
    assert not path.exists()
    assert env.get(f"/documents/{body['id']}").status_code == 404


def test_delete_metadata_only_row_is_safe(env):
    """走 POST /documents 登记的行没有 stored_path，删除不该炸。"""
    doc_id = env.post("/documents", json={"filename": "meta.pdf", "size_bytes": 10}).json()["id"]
    assert env.delete(f"/documents/{doc_id}").status_code == 204
