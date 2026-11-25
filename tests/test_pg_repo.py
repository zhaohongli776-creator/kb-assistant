"""真库集成测试：数据库可达才执行，否则整文件跳过。

    pwsh scripts/pg.ps1 start
    pytest -q

意义和内存测试不同：这里验证的是 DDL 约束（唯一的 filename、size >= 0 的 check）
和 timestamptz 到底对不对得上——这些只有真 PostgreSQL 能回答。
"""
from __future__ import annotations

import uuid
from contextlib import closing

import pytest

import db
from repo import DuplicateFilename, PgRepo


def _pg_reachable() -> bool:
    try:
        with closing(db.connect(connect_timeout=2)) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(), reason="PostgreSQL 不可达（先跑 pwsh scripts/pg.ps1 start）"
)


@pytest.fixture()
def repo():
    db.init_schema()
    return PgRepo()


@pytest.fixture()
def name(repo):
    """每次用唯一文件名，测试之间互不干扰；结束清理。"""
    fn = f"test-{uuid.uuid4().hex[:8]}.pdf"
    yield fn
    for row in repo.list(200):
        if row["filename"] == fn:
            repo.delete(row["id"])


def test_create_then_get_roundtrip(repo, name):
    created = repo.create(name, 2048)
    assert created["id"] > 0
    assert created["status"] == "pending"
    assert created["uploaded_at"] is not None  # 库里是 timestamptz，回来应带时区

    fetched = repo.get(created["id"])
    assert fetched["filename"] == name


def test_duplicate_filename_raises(repo, name):
    repo.create(name, 10)
    with pytest.raises(DuplicateFilename):
        repo.create(name, 20)


def test_list_is_desc_by_id(repo, name):
    first = repo.create(name, 10)
    rows = repo.list(200)
    ids = [r["id"] for r in rows]
    assert ids == sorted(ids, reverse=True)
    assert first["id"] in ids


def test_delete_removes_row(repo, name):
    created = repo.create(name, 10)
    assert repo.delete(created["id"]) is True
    assert repo.get(created["id"]) is None
    assert repo.delete(created["id"]) is False
