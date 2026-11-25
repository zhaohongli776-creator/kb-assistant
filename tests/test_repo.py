"""仓库层单测：连接必须被关闭。

背景：psycopg 3 的 `with conn:` 只提交/回滚事务，**不关闭连接**。
早先 PgRepo._run 与 /health 都用 `with connect() as conn:`，每次请求漏一条连接，
打满 max_connections（默认 100）后服务全挂。这两个测试就是钉死这个行为的。
"""
from __future__ import annotations

import psycopg

from repo import DuplicateFilename, PgRepo

ROW = (7, "policy.pdf", 1024, "pending", None)


class FakeCursor:
    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchone(self):
        return self._row

    def fetchall(self):
        return [self._row] if self._row else []


class FakeConn:
    def __init__(self, row=ROW):
        self.row = row
        self.closed = False
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return FakeCursor(self.row)

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


def test_run_closes_connection_after_create():
    conn = FakeConn()
    repo = PgRepo(conn_factory=lambda: conn)

    row = repo.create("policy.pdf", 1024)

    assert row["id"] == 7
    assert conn.committed is True
    assert conn.closed is True, "连接没关：with conn 不会替你关，必须用 closing()"


def test_run_closes_connection_on_error_path():
    class ExplodingConn(FakeConn):
        def cursor(self):
            self.closed_by_error = True
            raise psycopg.errors.UniqueViolation("duplicate key")

    conn = ExplodingConn()
    repo = PgRepo(conn_factory=lambda: conn)

    try:
        repo.create("policy.pdf", 1024)
    except DuplicateFilename:
        pass
    else:  # pragma: no cover
        raise AssertionError("唯一约束冲突必须翻译成 DuplicateFilename → 409")

    assert conn.closed is True, "异常路径同样要关连接"
    assert conn.rolled_back is True, "异常路径必须回滚，别把坏事务留在连接上"


def test_get_returns_none_when_missing():
    repo = PgRepo(conn_factory=lambda: FakeConn(row=None))
    assert repo.get(404) is None


def test_delete_returns_bool():
    assert PgRepo(conn_factory=lambda: FakeConn(row=(1,))).delete(1) is True
    assert PgRepo(conn_factory=lambda: FakeConn(row=None)).delete(1) is False
