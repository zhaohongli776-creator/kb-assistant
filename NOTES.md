# 开发笔记

给维护者看的。使用者只需要读 [README.md](README.md)。

## 上传落盘为什么是这个顺序

```
写 .{uuid}.part  →  边流边算大小（超限立刻 413）  →  校验扩展名
                 →  replace() 成 {uuid}_{原名}   →  才调 repo.create()
```

先落盘、后写库，保证**任何一条库里的行都对应一个真实存在的文件**。反过来先写库再落盘，中途崩掉就会留下一条指向空气的行，之后 `GET /documents` 能列出它，`DELETE` 又删不掉磁盘上不存在的东西。

失败路径统一收尾：重名 409 时把刚写的文件删掉再抛，超限 413 时删掉 `.part`，所以失败不留垃圾文件。

## 磁盘文件名为什么要加 uuid 前缀

NTFS 大小写不敏感，`A.txt` 和 `a.txt` 落盘会互相覆盖；而 PostgreSQL 的 `UNIQUE` 是区分大小写的，同一个库能同时存 `A.txt` 和 `a.txt` 两行。一套文件同时伺候两种语义，必然对不上。

所以磁盘名固定是 `{uuid}_{原始文件名}`，撞名交给 uuid 解决，原始文件名只活在库里。`stored_path` 存的是裸文件名而不是完整路径，这样存储根目录以后能搬家，数据不用改。

## 测试

唯一入口是 `python -m pytest`。别用 `python tests/test_repo.py` 直接跑测试文件——那完全不经过 pytest，`sys.path[0]` 变成 `tests\`，`from repo import ...` 必然 `ModuleNotFoundError`。

仓库根的 `conftest.py` 与 `pyproject.toml` 里的 `pythonpath = ["."]` 负责把仓库根塞进 `sys.path`，两者互补（老版本 pytest 不认 `pythonpath`，靠 conftest 兜底）。从任何工作目录跑都该全绿。

```
30 passed                      数据库在跑
26 passed, 4 skipped           数据库不可达，真库那 4 条自动 skip
```

看到 skip 不是通过，先把数据库起起来。

## Windows 环境的两个坑

本机没装 PowerShell 7，只有 `powershell.exe`（5.1）。所有命令按 5.1 写。

想用 `.\scripts\pg.ps1 start` 这种简写，得先开一次执行策略：

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

已经开着的终端会缓存旧策略，改完要重开。不然会报 `PSSecurityException` / `在此系统上禁止运行脚本`。

## 踩过的坑

1. **psycopg 的 `with conn:` 只提交事务，不关闭连接。** 用它当连接管理会每请求漏一条连接，100 次后打满 `max_connections`，服务整体挂死。必须 `contextlib.closing()` 显式关。

2. **`return` 不能写在 `with conn:` 块里。** 提前返回会跳过 `conn.commit()`，psycopg 在关闭时回滚整条事务——`create()` 明明返回了 id，库里却查不到。正确顺序是：取结果 → commit → 关闭；异常路径 rollback。

3. **`pg_ctl -l` 的日志不能放 `data\` 目录。** postmaster 自己也在 data 里写日志，撞上会报 `could not open file: sharing violation` 并空转 30 秒。日志放 `%TEMP%`。

4. **写给 `powershell.exe`（5.1）执行的 `.ps1` 必须存成 UTF-8 with BOM。** 没有 BOM 时它按 GBK 读，中文注释会被撕成乱码并报语法错（`Unexpected token 'data'`）。注意用编辑器改完这个文件要确认 BOM 还在。

5. **`Start-Process -Wait` 会连子孙进程一起等。** postmaster 不会退出，于是命令永远挂住。要启动数据库用 `-PassThru` 不等待，或交给计划任务。

6. **解压版 PostgreSQL 不注册 Windows 服务。** 重启电脑后 5432 没人监听，`/health` 报 `db: down`。本机用计划任务（登录时触发）+ 启动文件夹里的一个 `.cmd` 兜底；具体名字因人而异，不写进仓库。

7. **连接串会进终端和截图，打印前先打码。** `db.mask()` 把密码换成 `***`，`python db.py` 输出的 `schema 就绪：postgresql://postgres:***@localhost:5432/kb` 才是该出现在录屏和日志里的形状。原样 `print(DSN)` 等于把口令贴到墙上。

8. **默认连接串里不要放真实口令。** `db.DSN` 的兜底值是带 `CHANGE_ME` 的占位符，`connect()` 撞上它会直接抛 `RuntimeError` 指路 `.env`。这样忘了配置是显式失败，而不是悄悄用某个默认口令连上去——后者意味着口令迟早会跟着代码进仓库。

9. **`/docs` 里那个 `Execute` 在卡片最底部，`Cancel` 在最顶部。** 演示和录屏时两次都死在这儿——展开接口卡片后眼睛往上看容易点到 `Cancel`/`Reset`，真正的蓝色提交条在最下面。

## M1 收工验证记录

一次性验收，留着备查：

- [x] `/health` 返回 `{"status":"ok","db":"ok"}`
- [x] `/docs` 上走通增删查（POST 201 → GET 200 → 重名 409 → DELETE 204）
- [x] 上传 `POST /documents/upload` → 磁盘有文件、库里有行、`stored_path` 三处一致
- [x] `pytest -q` → 30 passed
- [x] 重启 uvicorn 后文档还在；重启 PostgreSQL 后也在
- [x] 连打 150 次 `/health` 后 `pg_stat_activity` 里只有 1 条连接（无连接泄漏）
- [x] 上传失败（409 / 413 / 422）不在磁盘留垃圾文件
- [ ] 换台电脑按 README 能跑起来
