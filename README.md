# kb-assistant

企业知识库问答系统的后端。当前版本做「存」这一层：上传文档，文件落盘、元数据写进 PostgreSQL，随后能列、能查、能删。

解析、切片、向量化检索都还没做——传上来的文档目前只是被存着，不会被读懂。

## 前置

- Python 3.10+
- PostgreSQL 12+，连接串通过 `DATABASE_URL` 提供

## 快速开始

```bash
pip install -r requirements.txt

# 把 .env.example 复制成 .env，再把里面的 CHANGE_ME 换成你的数据库口令
python db.py                                    # 建表，幂等，可反复执行
python -m uvicorn main:app --reload --port 8000
```

打开 <http://127.0.0.1:8000/docs>，Swagger 里可以直接选文件试上传，不用写客户端。

跑测试：

```bash
python -m pytest -q                             # 30 passed
```

数据库连不上时，依赖真库的 4 条会自动 skip 成 `26 passed, 4 skipped`——看到 skip 先去把数据库起起来。

> Windows 上如果 PostgreSQL 是解压版、没注册成 Windows 服务，可以用 `scripts/pg.ps1 start|stop|status` 代管。已经在正常监听 5432 的环境（Windows 服务 / systemd / Docker / 云托管）跳过这一步。

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/health` | 探活，顺带 ping 一次数据库 |
| POST | `/documents` | 只登记元数据，不上传文件本体 |
| POST | `/documents/upload` | 上传文件：落盘 + 登记 |
| GET | `/documents` | 列表，默认 50 条，按上传时间倒序 |
| GET | `/documents/{id}` | 取单个文档 |
| DELETE | `/documents/{id}` | 删除，连带删掉磁盘文件 |

约束：扩展名限 `.pdf` `.docx` `.txt` `.md`，单文件 ≤ 50MB，文件名全库唯一。列表的 `?limit=` 取值 1..200。

状态码：重名 `409`、参数不合法 `422`、超 50MB `413`、`limit` 越界 `400`、文档不存在 `404`。

## 配置

只有一个环境变量。

| 名称 | 说明 |
|---|---|
| `DATABASE_URL` | PostgreSQL 连接串，必填，例如 `postgresql://user:pass@host:5432/kb` |

`db.py` 自己读同目录的 `.env`（标准库实现，不需要 python-dotenv），格式是 `KEY=VALUE`；已经存在的环境变量优先于 `.env`。

仓库里不存任何凭据。`.env.example` 里的 `CHANGE_ME` 是占位符，照抄跑不通；真实口令只写在本地 `.env` 里，那个文件被 `.gitignore` 排除。忘了配就直接连库，会拿到一句明确的报错，而不是默默用某个默认口令连上去。

## 项目结构

```
db.py            数据库连接、建表 DDL、.env 读取
repo.py          仓库层接口 + 两个实现：PgRepo（生产）/ InMemoryRepo（测试）
models.py        Pydantic 请求与响应模型，422 就长在这里
main.py          全部 HTTP 路由与上传落盘逻辑
scripts/pg.ps1   Windows 解压版 PostgreSQL 启停
tests/           接口、上传落盘、仓库层、真库约束
```

## 已知限制

- 不解析文档内容，只信扩展名；改过扩展名的可执行文件会照收
- 没有鉴权、没有分页游标、没有软删除
- 每请求开一条连接、用完就关，没有连接池
- 单机单目录存储，没有对象存储；进程被强杀会留下 `.part` 临时文件

## 开发笔记

踩坑记录、设计取舍、调试备忘在 [NOTES.md](NOTES.md)。
