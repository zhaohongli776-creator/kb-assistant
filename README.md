# kb-assistant

**是什么**：企业知识库问答系统的后端。M1 阶段只做一件事——用 API 管文档：文件传上来、落盘、元数据入库、能查能删，测试全绿。
**现在到哪**：M1 完成。6 个接口 / 唯一约束 409 / 参数与大小校验 422 / 超限 413 / 30 条测试全绿 / 上传落盘端到端验证过。解析与切片（M2）还没做。

演示录屏（24 秒，从选文件到列表回显）：`D:\kb-assistant-demos\2026-11-24-M1-upload-demo.mp4`

## 怎么跑

```powershell
# 0) 起数据库（本机装的是解压版 PostgreSQL 18.6，没有注册 Windows 服务）
powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 start
powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 status   # 确认 127.0.0.1:5432 在监听

# 1) 装依赖 + 配连接串
pip install -r requirements.txt
Copy-Item .env.example .env        # .env 已被 .gitignore 排除，不会进仓库
# 编辑 .env 里的 DATABASE_URL

# 2) 建表 + 起服务
python db.py                       # 幂等：表已存在时什么也不做，缺列会补
python -m uvicorn main:app --reload --port 8000
# 打开 http://127.0.0.1:8000/docs

# 3) 测试
python -m pytest -q                # 30 passed（库没起来会 skip 4 条 → 26 passed）
```

`db.py` 会自己读同目录 `.env`（标准库实现，没引 python-dotenv）；环境变量优先于 `.env`。

> 本机没有 `pwsh`（PowerShell 7 没装），只有 `powershell.exe`（5.1）。所有命令按 5.1 写。想用 `.\scripts\pg.ps1 start` 这种简写，得先 `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` 一次。

> **测试的唯一入口是 `python -m pytest`。** 别用 `python tests/test_repo.py` 直接跑测试文件——那完全不经过 pytest，`sys.path[0]` 变成 `tests\`，`from repo import ...` 必然 `ModuleNotFoundError`。仓库根的 `conftest.py` + `pyproject.toml` 的 `pythonpath = ["."]` 保证从任何工作目录（仓库根 / `tests\` / `C:\`）跑都全绿。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 探活，顺带 ping 一次库 |
| POST | `/documents` | 只登记元数据（不上传文件本体） |
| POST | `/documents/upload` | 上传文件：落盘 + 登记，201 |
| GET | `/documents` | 列表，默认 50 条，按时间倒序；`?limit=` 限 1..200，越界 400 |
| GET | `/documents/{id}` | 取一份，没有则 404 |
| DELETE | `/documents/{id}` | 删除，连带删磁盘文件，204 |

状态码：重名 `409`、扩展名/空文件/`limit` 越界 `400`、参数校验 `422`、超 50MB `413`。

## 验证清单（M1 收工判据）

- [x] `/health` 返回 `{"status":"ok","db":"ok"}`
- [x] `/docs` 上能走通增删查（POST 201 → GET 200 → 重名 409 → DELETE 204）
- [x] 上传 `POST /documents/upload` → 磁盘有文件、库里有行、`stored_path` 三处一致
- [x] `pytest -q` → 30 passed
- [x] 重启 uvicorn 后之前登记的文档还在（真落库）；重启 PostgreSQL 后也在
- [x] 连打 150 次 `/health` 后 `pg_stat_activity` 里只有 1 条连接（无连接泄漏）
- [x] 上传失败（重名 409 / 超限 413 / 扩展名 422）不会在磁盘留垃圾文件
- [ ] 换台电脑按本 README 能跑起来

## 结构

```
db.py            PostgreSQL 连接 + 建表 DDL（含 stored_path 幂等迁移）+ .env 读取
repo.py          仓库层：PgRepo（生产）/ InMemoryRepo（测试），closing() 显式关连接
models.py        Pydantic 校验（422 就长在这里）
main.py          6 个接口 + 上传落盘 + 依赖注入（app.dependency_overrides 换实现）
scripts/pg.ps1   本地 PostgreSQL 启停（start/stop/restart/status）
conftest.py      pytest 引导：把仓库根塞进 sys.path
pyproject.toml   pytest 配置（pythonpath / testpaths）
tests/           test_api 11（内存）· test_upload 11（落盘/回滚）· test_repo 4（假连接）· test_pg_repo 4（真库，不可达自动 skip）
```

上传落盘的顺序是：写 `.{uuid}.part` → 边流边算大小（超限立刻 413）→ 校验扩展名 → `replace()` 成 `{uuid}_{原名}` → 才调 `repo.create()`。所以**任何一条库里的行都意味着磁盘上的文件真的存在**；反过来先写库再落盘，中途崩了就是一条指向空气的行。

## 踩过的坑（都写进了测试或注释，别再踩一遍）

1. **psycopg 的 `with conn:` 只提交事务，不关闭连接。** 用它当连接管理会每请求漏一条连接，100 次后打满 `max_connections`，服务整体挂死。必须 `contextlib.closing()` 显式关。
2. **`return` 不能写在 `with conn:` 块里。** 提前返回会跳过 `conn.commit()`，psycopg 在关闭时回滚整条事务——`create()` 明明返回了 id，库里却查不到。正确顺序是：取结果 → commit → 关闭；异常路径 rollback。
3. **`pg_ctl -l` 的日志不能放 `data\` 目录。** postmaster 自己也在 data 里写日志，撞上会报 `could not open file: sharing violation` 并空转 30 秒。日志放 `%TEMP%`。
4. **写给 `powershell.exe`（5.1）执行的 `.ps1` 必须存成 UTF-8 with BOM。** 没有 BOM 时它按 GBK 读，中文注释会被撕成乱码并报语法错（`Unexpected token 'data'`）。
5. **`Start-Process -Wait` 会连子孙进程一起等。** postmaster 不会退出，于是命令永远挂住。要启动数据库用 `-PassThru` 不等待，或交给计划任务。
6. **解压版 PostgreSQL 不注册 Windows 服务。** 重启电脑后 5432 没人监听，`/health` 报 `db: down`。本机已用计划任务 `PostgreSQL18-kb`（登录时触发）+ 启动文件夹 `postgres-kb.cmd` 兜底。
7. **别用 `python tests/xxx.py` 跑测试。** pytest 的 prepend 模式只把测试文件所在目录放进 `sys.path`，仓库根不在里面 → `ModuleNotFoundError: No module named 'repo'`。入口固定为 `python -m pytest`；根目录的 `conftest.py` 与 `pyproject.toml` 的 `pythonpath = ["."]` 负责路径，两者互补（老版本 pytest 不认 `pythonpath`，靠 conftest 兜底）。
8. **磁盘文件名加 uuid 前缀不是画蛇添足。** NTFS 大小写不敏感，`A.txt` 和 `a.txt` 落盘会互相覆盖；PostgreSQL 的 `UNIQUE` 是区分大小写的。同一批文件同时伺候两种语义必然对不上，所以磁盘名是 `{uuid}_{原名}`，撞名交给 uuid 解决，原始文件名只活在库里。`stored_path` 存裸文件名而不是完整路径，是为了让存储根目录以后能搬家。
9. **`/docs` 里那个 `Execute` 在卡片最底部，`Cancel` 在最顶部。** 录制和演示时按错两次都死在这儿——展开接口卡片后眼睛往上看容易点到 `Cancel`/`Reset`，真正的蓝色提交条在最下面。

## 数据库密码

本机 `postgres` 用户的密码已重置为 `postgres`（`pg_hba.conf` 临时改 trust → `ALTER USER` → 立刻还原成 `scram-sha-256`，原文件备份在 `data\pg_hba.conf.bak-20261121`）。生产环境请改成强密码并只放在 `.env` 里。

## 已知限制

- 只做「存」，不做「懂」：不解析、不切片、不向量化（M2 开始）
- 没有鉴权、没有分页游标、没有软删除
- 上传不看文件内容，只信扩展名；改过扩展名的 PE/文档会照收
- 连接是"每请求一开一关"，没有连接池；QPS 上来后换 `psycopg_pool`
- 单机单目录，没有对象存储，也没有并发上传的清理任务（进程被杀会留下 `.part`）
