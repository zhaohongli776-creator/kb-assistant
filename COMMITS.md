# 提交计划：把 M1 骨架按模块拆成 11 次提交

一次性文档。跑完这 11 条就可以删掉，或者挪进 `docs/` 留作记录。

写在 2026-11-21，对应 M1（后端打通）收尾阶段。2026-11-22 远端仓库改名为 `kb-assistant`，并已推上第 1 条的五个文件。2026-11-25 做 D5 上传落盘时把原本的第 6 条拆成两条（`main.py` 单飞、`db.py`+`models.py`+`requirements.txt` 单飞），于是 10 条变 11 条。

## 为什么要拆

代码是一次写完的，历史却可以按模块切。区别在于 `git log` 给人看的是什么：10 条各自说明一件事，读起来是"按模块推进"；1 条 `init` 加 300 行，读起来是"别人一天写完丢给我的"。面试官翻仓库通常先翻提交历史。

拆开还有个实际好处：`git bisect` 能定位到具体模块，回滚只损失一层。

## 开工前

```powershell
cd D:\kb-assistant
git status --short
git reset
```

`git status` 会显示一堆 `A`，那是之前 `git add .` 的残留。`git reset` 不带参数只清暂存区，工作区的文件一个都不会动。别用 `--hard`。

执行完再跑一次 `git status --short`，应该全变成 `??`。

不过远端那个仓库已经有提交了（见文末「推到 GitHub」），所以这一步更该这么写：

```powershell
git fetch origin
git reset --mixed origin/main
```

`--mixed` 只动 HEAD 和暂存区，工作区一个字节都不碰。它同时干了上面 `git reset` 的活，还顺手把远端那条 `36498f0 chore` 接成本地历史的根，好处是后面 `git push` 直接快进，不用 `--force`，也不用解释为什么强推。

执行后 `git status --short` 应该是：`README.md` 显示 `M`（本地重写版与远端两行版不同），其余文件全 `??`。`README.md` 挂着 `M` 无所谓，第 9 条提交时才 `git add` 它。

remote 还没改名的话，把 `origin` 换成旧名字 `企业智能知识库助手`。

## 十一次提交

| # | 提交信息 | 包含文件 | 状态 |
|---|---|---|---|
| 1 | `chore: 初始化仓库骨架与依赖清单` | `.gitignore` `.gitattributes` `.env.example` `requirements.txt` | ✅ 远端 `36498f0`，不重写 |
| 2 | `build: pytest 路径配置与 conftest 引导` | `pyproject.toml` `conftest.py` | ✅ `44c9b56` |
| 3 | `feat(db): documents 表 DDL、connect_timeout 与 .env 自读取` | `db.py` | ✅ `4b3d9f0` |
| 4 | `feat(models): Pydantic 校验（扩展名白名单、50MB 上限）` | `models.py` | ✅ `731ca2d` |
| 5 | `feat(repo): 仓库层双实现，create 支持 stored_path，closing() 显式关连接` | `repo.py` | ✅ `808e9bb` |
| 6 | `feat(api): documents 增删查与上传端点，含 stored_path 列迁移` | `main.py` | ✅ `05504d9` |
| 7 | `feat(db): stored_path 列、DocumentOut 字段与 python-multipart 依赖` | `db.py` `models.py` `requirements.txt` | ✅ `a1de5d5` |
| 8 | `test: 30 条测试覆盖接口、上传落盘与真库约束` | `tests/` | ✅ `5929448` |
| 9 | `chore(scripts): pg.ps1 本地数据库启停` | `scripts/` | ⬜ 待提交 |
| 10 | `docs(readme): 跑法、接口表、M1 验证清单与 9 条踩坑记录` | `README.md` | ⬜ 待提交 |
| 11 | `docs: M1 提交计划与拆分依据` | `COMMITS.md` | ⬜ 待提交 |

第 6、7 条原本是一条「`feat(api): health 与 documents 增删查，依赖注入可换实现`」。D5 加 `POST /documents/upload` 之后 `main.py` 从 90 行长到 173 行，塞着「6 个接口」和「新增上传」两件事，`git log` 里那句信息会撒谎。拆开的判据是：删掉上传端点后第 6 条仍然能跑能测，而 `stored_path` 这一列只服务上传，单独走第 7 条。

## 直接跑

**第 1 条在远端，第 2 到 8 条已经落地（2026-11-23 与 11-25）。** 剩下三条：

```powershell
cd D:\kb-assistant

git add scripts/
git commit -m "chore(scripts): pg.ps1 本地数据库启停"

git add README.md .gitignore
git commit -m "docs(readme): 跑法、接口表、M1 验证清单与 9 条踩坑记录"

git add COMMITS.md
git commit -m "docs: M1 提交计划与拆分依据"
```

`.gitignore` 跟 README 一起提交，因为 D5 补了 `*.pem` `*.key` `*.pfx` 和 `*.mp4` 三条规则——演示录屏放在仓库外面 `D:\kb-assistant-demos\`，但规则得先立起来，免得哪天手滑拖进仓库。

起点是 `36498f0`（远端那条 `chore`）。当初把本地历史接到它上面用的是：

```powershell
git fetch origin
git reset --mixed origin/main       # 只动 HEAD 和暂存区，工作区一个字节不碰
```

这一步已经做过了，别再跑一遍——现在 HEAD 已经在 `5929448`，再 `reset --mixed origin/main` 会把 7 条提交从历史里摘掉（工作区文件还在，但提交信息白写了）。

## 中途怎么验

每提交一次跑一遍 `python -m pytest -q`。

第 2 到 5 次会看到 `no tests ran in 0.01s`，这是对的，测试文件还没入库。第 8 次之后必须始终是 `30 passed`；真库那 4 条依赖 PostgreSQL 在跑，库没起来会 skip 成 `26 passed, 4 skipped`——**看到 skip 先去起库**，别当通过：

```powershell
powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 status
powershell -ExecutionPolicy RemoteSigned -File .\scripts\pg.ps1 start
```

某次变红就停下，说明那个提交本身不完整，别继续往下堆。

## 全部跑完

```powershell
cd D:\kb-assistant
git log --oneline                   # 11 行（远端 chore + 本地 10 条）
git status --short                  # 应该是空的
python -m pytest -q                 # 30 passed
git push -u origin main
git tag -a v0.1.0 -m "M1 后端打通"
git push origin v0.1.0
```

## 三条纪律

`.env` 永远不入库。真实密钥只写在这个文件里，`.env.example` 放占位值。万一误提交，改密码比改历史便宜。

`raw/` 那套规矩不适用于这个仓库，但同样的道理有：别把 `uploads/`、`*.db`、`__pycache__` 塞进来。`.gitignore` 已经挡住，`git add .` 之前扫一眼 `git status` 更稳妥。

提交信息说"做了什么"，不说"改了哪些文件"。文件列表 `git show` 自己有。

## 之后怎么提交

这 10 条是重构，不是真实时间线。从 D5 上传落盘开始才是自然节奏。

### 节奏：一周 3 到 5 次，空窗不超过 3 天

提交的界线不是天数，是"一件事做完了"。但这界线太软，容易退化成"攒到周末再说"，所以配一条硬约束：

| 规矩 | 数值 | 为什么 |
|---|---|---|
| 每周提交 | 3 到 5 次 | 一个交付物拆成 3 个能跑的小步 |
| 单日至多 | 3 次 | 再往上说明拆太碎，或者把重构和功能混在一处 |
| 最长空窗 | 3 天 | 连着三天零提交，说明你在看文档不在写代码 |
| 收工前 | 必提 1 次 | 不管写没写完 |

最后一条最重要。一次编码坐下来，关电脑前至少提交一次：写完就提交成品，没写完就提交 `wip:` 开头的中途状态，第二天接着在上面改。不提交就关机，等于把明天前 20 分钟花在回忆昨天改到哪了。

### D5 一天长什么样

上传端点一天拆四次（2026-11-25 实际就是这么走的）：

1. `feat(repo): 仓库层双实现，create 支持 stored_path，closing() 显式关连接` —— `repo.py`，先把落盘后的元数据接口撑开
2. `feat(api): documents 增删查与上传端点，含 stored_path 列迁移` —— `main.py`，`.part` → 校验 → uuid 改名 → 写库
3. `feat(db): stored_path 列、DocumentOut 字段与 python-multipart 依赖` —— 建表 DDL 的幂等迁移与响应模型
4. `test: 30 条测试覆盖接口、上传落盘与真库约束` —— 测试从 19 条长到 30 条，含 409 不留垃圾文件、413 超限、路径穿越拍平

每条都能跑、能回滚、能单独拿出来讲。写成一条的话，出问题就得整体回退。

```powershell
git add repo.py
git commit -m "feat(repo): 仓库层双实现，create 支持 stored_path，closing() 显式关连接"

git add main.py
git commit -m "feat(api): documents 增删查与上传端点，含 stored_path 列迁移"

git add db.py models.py requirements.txt
git commit -m "feat(db): stored_path 列、DocumentOut 字段与 python-multipart 依赖"

git add tests/
git commit -m "test: 30 条测试覆盖接口、上传落盘与真库约束"
```

### 什么不算一次提交

- 测试是红的还提交（收工时的 `wip:` 除外，但下一条提交必须修绿）
- 一次改了 8 个文件，写不出一句准确的话
- `update`、`fix`、`改一下`、`.` 这类信息
- 单纯为了让 GitHub 绿格子有颜色

最后一条要提防：绿格子会让人提交垃圾。读者是面试官，他点开看提交信息，不看方块密度。

### 顺便当日报

一天多次提交的好处是 `git log` 自动成了工作记录，周复盘不用凭记忆：

```powershell
git log --since="1 week ago" --pretty="%ad %s" --date=format:"%m-%d %a"
```

W1 到 W16 按这节奏跑完，总提交量在 50 到 80 条之间。这个数对作品集够用，而且每条都能讲。

### 攒着不交的代价

三天的改动攒到一处，结果一定是：`git add .`、写一句"完成上传功能"、把三个不相关的改动塞进一条。哪天要回退，退掉的比想退的多。

之前那 7 周零产出，问题不在提交频率，在于没有可提交的东西。有东西可提交却攒着不交，是同一个毛病的轻症版本。

## 推到 GitHub

本地 10 条都绿了再推，别边推边改。

远程仓库已经建好了，先说清它现在长什么样：

- remote 名是 `origin`，地址 `https://github.com/zhaohongli776-creator/kb-assistant.git`
- `origin/main` 上有两次提交：`a38360a Initial commit` 和 `36498f0 chore`，后者就是提交计划的第 1 条
- 本地已经在 `36498f0` 之上接了 7 条，所以现在是干净的快进关系，`push` 不需要 `--force`

### 一，仓库名已经改好了

2026-11-22 从 `-`（建仓时填的中文被 GitHub 清空）改成了 `kb-assistant`，remote 也从中文名改成了 `origin`。这一步不用再做。

如果哪天又要改，网页 Settings → Repository name，然后本地：

```powershell
git remote set-url origin https://github.com/zhaohongli776-creator/kb-assistant.git
git fetch origin
```

### 二，远端那条提交当根留着

远端那五个文件（`.gitignore` `.gitattributes` `.env.example` `requirements.txt` README 的早期版）就是第 1 条，本地已经同步过来，留着它不损失任何东西，还能免掉一次 `--force`。做法就是「开工前」那节写的 `git reset --mixed origin/main`。

如果你压根不想留，`git push --force origin main` 也安全：仓库刚建，没有别人的工作被覆盖。但保留更省事，历史里多一条 `chore` 是常态，不是污点。

### 三，推

```powershell
git push -u origin main
```

10 条新提交快进到远端。

### 关于分支

这次不要开分支。

分支解决的是"两条线同时往前跑"，你这里只有一条线：一个人、一个分支、没有 PR 评审、没有并行实验。10 条提交全落 `main`，`git log` 读起来就是一条直线，这是最干净的形状。开了分支反而多出 `合并` 提交和"哪个分支是最新的"这类没意义的问题。

分支也装不了"部分文件"。任何分支都是整棵树的快照，`main` 和 `m1` 都包含全部文件。想让某些文件不进仓库只有一条路：写进 `.gitignore`。

分支更不提供保密性。如果"提交到分支"是想把 `.env` 或数据库密码藏起来，行不通——push 出去就上了 GitHub 的服务器，private 也只是访问控制，不是加密隔离。

以后真正该开分支的有三种，出现再说：

- 试一个不确定的方案（换异步 psycopg、装 pgvector 改检索），开 `trial/async-pg`，成了合回来，不成删掉，`main` 全程能跑
- 给交付物打标记，用 tag 不用分支：M1 收尾时 `git tag -a v0.1.0 -m "M1 后端打通"`，比开个 `release` 分支省事
- M4 要上线而新功能正在写，那时才需要让 `main` 随时可发布

仓库先 private，等 M4 上线、有公网链接再转 public。
