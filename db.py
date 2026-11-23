"""数据层：PostgreSQL 连接与建表（M1 的 D1 步）。"""
from __future__ import annotations

import os
from pathlib import Path

_ENV_FILE = Path(__file__).with_name(".env")


def _load_dotenv() -> None:
    """把同目录 .env 里的 KEY=VALUE 灌进环境变量（已存在的变量不覆盖）。

    只用标准库，不引 python-dotenv：`.env` 只是本地开发的便利，不是依赖。
    """
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key, value = key.strip(), value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


_load_dotenv()

DSN = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/kb")

DDL = """
create table if not exists documents (
    id           bigserial primary key,
    filename     text        not null,
    size_bytes   bigint      not null check (size_bytes >= 0),
    status       text        not null default 'pending',
    uploaded_at  timestamptz not null default now(),
    constraint documents_filename_uniq unique (filename)
);
create index if not exists documents_uploaded_at_idx on documents (uploaded_at desc);
"""


def connect(*, connect_timeout: int = 3):
    """返回一个 psycopg 连接；import 放在函数里，纯算法测试不需要装驱动。

    默认带 connect_timeout，避免数据库不可达时健康检查挂死。
    """
    import psycopg  # noqa: PLC0415

    kwargs = {} if "connect_timeout" in DSN else {"connect_timeout": connect_timeout}
    return psycopg.connect(DSN, **kwargs)


def init_schema(conn=None) -> None:
    own = conn is None
    conn = conn or connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL)
        conn.commit()
    finally:
        if own:
            conn.close()


if __name__ == "__main__":
    init_schema()
    print(f"schema 就绪：{DSN}")
