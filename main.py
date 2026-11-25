"""知识库助手 · M1 后端骨架。

跑起来：
    pip install -r requirements.txt
    python db.py                 # 建表（需要 DATABASE_URL）
    uvicorn main:app --reload
    # 打开 http://127.0.0.1:8000/docs

接口：
    GET    /health              健康检查（含数据库连通性）
    POST   /documents           登记一份文档元数据（201；重名 409；参数错 422）
    POST   /documents/upload    上传文件本体（multipart；落盘 + 登记；超 50MB 413）
    GET    /documents           列出文档（默认 50 条）
    GET    /documents/{id}      取一份（404）
    DELETE /documents/{id}      删除（404；连带删磁盘文件）
"""
from __future__ import annotations

import os
from contextlib import closing
from pathlib import Path, PurePosixPath
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status

from models import DocumentIn, DocumentOut, HealthOut
from repo import DocRepo, DuplicateFilename, InMemoryRepo, PgRepo

app = FastAPI(title="KB Assistant · M1", version="0.1.0")

# 上传约束：与 models.DocumentIn 的校验保持一致，这里是拿文件时再挡一次。
ALLOWED_EXT = (".pdf", ".docx", ".txt", ".md")
MAX_BYTES = 50 * 1024 * 1024
CHUNK = 1 << 20  # 1MB 一片，50MB 也不进内存


def upload_dir() -> Path:
    """落盘目录。KB_UPLOAD_DIR 可覆盖（测试用 tmp_path），默认 ./uploads。"""
    d = Path(os.environ.get("KB_UPLOAD_DIR", "uploads"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def _safe_filename(raw: str | None) -> str:
    """客户端给的 filename 是任意字符串：`../../etc/passwd`、`a\\b.txt` 都见过。

    只取最后一段，再按白名单卡扩展名，别让请求决定磁盘路径。
    """
    if not raw:
        raise HTTPException(422, "缺少文件名")
    name = PurePosixPath(raw.replace("\\", "/")).name.strip()
    if not name or name in {".", ".."} or len(name) > 255:
        raise HTTPException(422, f"文件名非法: {raw!r}")
    if PurePosixPath(name).suffix.lower() not in ALLOWED_EXT:
        raise HTTPException(422, f"扩展名只支持 {'/'.join(ALLOWED_EXT)}")
    return name


def _remove_stored(stored: str | None) -> None:
    """按库里记的文件名删盘上文件。再挡一次路径穿越：只认最后一段。"""
    if not stored:
        return
    name = PurePosixPath(stored.replace("\\", "/")).name
    if name and name not in {".", ".."}:
        (upload_dir() / name).unlink(missing_ok=True)

_repo_singleton: DocRepo | None = None
if os.environ.get("KB_REPO", "pg") == "memory":  # 无数据库时可用 KB_REPO=memory 起服务
    _repo_singleton = InMemoryRepo()


def get_repo() -> DocRepo:
    """依赖注入点：测试里用 app.dependency_overrides[get_repo] 换成内存实现。"""
    global _repo_singleton
    if _repo_singleton is None:
        _repo_singleton = PgRepo()
    return _repo_singleton


@app.get("/health", response_model=HealthOut)
def health() -> HealthOut:
    db_state = "ok"
    try:
        from db import connect  # noqa: PLC0415

        # closing()：psycopg 的 with conn 不关连接，健康检查最容易被高频调用，必须显式关。
        with closing(connect()) as conn:
            with conn.cursor() as cur:
                cur.execute("select 1")
                cur.fetchone()
    except Exception as exc:  # 数据库没起来也不该让健康检查 500
        db_state = f"down: {type(exc).__name__}"
    return HealthOut(status="ok", db=db_state)


@app.post("/documents", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentIn, repo: DocRepo = Depends(get_repo)) -> DocumentOut:
    try:
        row = repo.create(payload.filename, payload.size_bytes)
    except DuplicateFilename as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, f"文件名已存在: {exc}") from exc
    return DocumentOut(**row)


@app.post("/documents/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...), repo: DocRepo = Depends(get_repo)
) -> DocumentOut:
    """收文件本体：先落盘临时名，再写库，最后改名成 `{uuid}_{原名}`。

    顺序是刻意的——库里一旦有记录，盘上文件必然已在；反过来（先写库后落盘）
    会出现指向空文件的记录，那是脏数据。
    """
    root = upload_dir()
    name = _safe_filename(file.filename)

    token = uuid4().hex
    tmp = root / f".{token}.part"
    final_name = f"{token}_{name}"     # uuid 前缀：绕开 Windows 大小写不敏感的同名冲突
    final = root / final_name

    size = 0
    try:
        with tmp.open("wb") as fh:
            while chunk := await file.read(CHUNK):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise HTTPException(413, "文件超过 50MB 上限")
                fh.write(chunk)
    except BaseException:
        tmp.unlink(missing_ok=True)     # 超限/中断都不留半截文件
        raise
    finally:
        await file.close()

    if size == 0:
        tmp.unlink(missing_ok=True)
        raise HTTPException(422, "空文件")

    tmp.replace(final)                  # 同盘改名，原子
    try:
        row = repo.create(name, size, final_name)
    except DuplicateFilename as exc:
        final.unlink(missing_ok=True)   # 库拒绝 → 磁盘也回收，别留孤儿
        raise HTTPException(status.HTTP_409_CONFLICT, f"文件名已存在: {exc}") from exc
    except BaseException:
        final.unlink(missing_ok=True)
        raise
    return DocumentOut(**row)


@app.get("/documents", response_model=list[DocumentOut])
def list_documents(limit: int = 50, repo: DocRepo = Depends(get_repo)) -> list[DocumentOut]:
    if not 1 <= limit <= 200:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "limit 必须在 1..200")
    return [DocumentOut(**r) for r in repo.list(limit)]


@app.get("/documents/{doc_id}", response_model=DocumentOut)
def get_document(doc_id: int, repo: DocRepo = Depends(get_repo)) -> DocumentOut:
    row = repo.get(doc_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"文档不存在: {doc_id}")
    return DocumentOut(**row)


@app.delete("/documents/{doc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(doc_id: int, repo: DocRepo = Depends(get_repo)) -> None:
    row = repo.get(doc_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"文档不存在: {doc_id}")
    repo.delete(doc_id)
    _remove_stored(row.get("stored_path"))
