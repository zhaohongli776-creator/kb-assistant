"""仓库层：同一套接口两种实现——PostgreSQL（生产）与内存（测试）。

这样接口测试不需要数据库也能跑绿（M1 的 D4），而生产路径仍然是真库。
"""
from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
from typing import Protocol


class DuplicateFilename(Exception):
    """文件名唯一性冲突 → 映射成 HTTP 409。"""


class DocRepo(Protocol):
    def create(self, filename: str, size_bytes: int, stored_path: str | None = None) -> dict: ...
    def list(self, limit: int = 50) -> list[dict]: ...
    def get(self, doc_id: int) -> dict | None: ...
    def delete(self, doc_id: int) -> bool: ...


class InMemoryRepo:
    """测试用：行为与 PgRepo 对齐（含唯一约束与时间戳）。"""

    def __init__(self) -> None:
        self._rows: dict[int, dict] = {}
        self._next_id = 1
        self._names: set[str] = set()

    def create(self, filename: str, size_bytes: int, stored_path: str | None = None) -> dict:
        if filename in self._names:
            raise DuplicateFilename(filename)
        row = {
            "id": self._next_id,
            "filename": filename,
            "size_bytes": size_bytes,
            "status": "pending",
            "uploaded_at": datetime.now(timezone.utc),
            "stored_path": stored_path,
        }
        self._next_id += 1
        self._names.add(filename)
        self._rows[row["id"]] = row
        return row

    def list(self, limit: int = 50) -> list[dict]:
        return sorted(self._rows.values(), key=lambda r: r["id"], reverse=True)[:limit]

    def get(self, doc_id: int) -> dict | None:
        return self._rows.get(doc_id)

    def delete(self, doc_id: int) -> bool:
        row = self._rows.pop(doc_id, None)
        if row is None:
            return False
        self._names.discard(row["filename"])
        return True


class PgRepo:
    """生产用：documents 表读写。"""

    def __init__(self, conn_factory=None) -> None:
        from db import connect  # noqa: PLC0415

        self._connect = conn_factory or connect

    def _run(self, sql: str, params: tuple = (), fetch: str | None = None):
        # 三个坑一起钉死：
        # 1) psycopg 的 `with conn:` 只提交事务、不关连接 → 用 closing() 显式关；
        # 2) `return` 不能写在 with 块里，否则跳过 commit，事务被回滚（2026-11-21 实测踩到）；
        # 3) 异常路径也要回滚，别把失败的连接留在事务里。
        with closing(self._connect()) as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    if fetch == "one":
                        result = cur.fetchone()
                    elif fetch == "all":
                        result = cur.fetchall()
                    else:
                        result = None
                conn.commit()
            except BaseException:
                conn.rollback()
                raise
        return result

    @staticmethod
    def _row(r) -> dict:
        return {
            "id": r[0],
            "filename": r[1],
            "size_bytes": r[2],
            "status": r[3],
            "uploaded_at": r[4],
            # 容错：老驱动/测试桩可能只回 5 列，缺列按 None 处理
            "stored_path": r[5] if len(r) > 5 else None,
        }

    _COLS = "id, filename, size_bytes, status, uploaded_at, stored_path"

    def create(self, filename: str, size_bytes: int, stored_path: str | None = None) -> dict:
        import psycopg  # noqa: PLC0415

        try:
            r = self._run(
                "insert into documents (filename, size_bytes, stored_path) "
                f"values (%s, %s, %s) returning {self._COLS}",
                (filename, size_bytes, stored_path),
                fetch="one",
            )
        except psycopg.errors.UniqueViolation as exc:  # 唯一约束 → 409
            raise DuplicateFilename(filename) from exc
        return self._row(r)

    def list(self, limit: int = 50) -> list[dict]:
        rows = self._run(
            f"select {self._COLS} from documents order by id desc limit %s",
            (limit,),
            fetch="all",
        )
        return [self._row(r) for r in rows or []]

    def get(self, doc_id: int) -> dict | None:
        r = self._run(
            f"select {self._COLS} from documents where id = %s",
            (doc_id,),
            fetch="one",
        )
        return self._row(r) if r else None

    def delete(self, doc_id: int) -> bool:
        r = self._run("delete from documents where id = %s returning id", (doc_id,), fetch="one")
        return r is not None
