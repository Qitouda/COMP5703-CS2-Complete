# 本地跑一遍后端

macOS，仓库在 `~/Documents/capstone/cs2-backend`。默认配置**不需要** Docker、
Postgres、Redis 或任何 API key —— SQLite + FastAPI 内置后台任务 + fixture 模型。

## 情况 A：仓库里已经有 .venv（当前就是）

`.venv` 已经建好了（Python 3.13.2，项目以 editable 模式装好，pytest / ruff / uvicorn
都在）。只差一个 `.env`：

```bash
cd ~/Documents/capstone/cs2-backend
source .venv/bin/activate
cp .env.example .env          # 只需做一次
make run
```

打开 http://localhost:8000/docs

## 情况 B：从零建

`.venv` 弄坏了或换机器时：

```bash
cd ~/Documents/capstone/cs2-backend
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
make run
```

`.venv` 和 `.env` 都在 `.gitignore` 里，不会进版本库。

## 确认它真的活着

`make run` 那个终端别关，另开一个：

```bash
cd ~/Documents/capstone/cs2-backend
source .venv/bin/activate
make smoke
```

期望输出：

```
→ http://localhost:8000/health
  schema 0.4 / rubric 0.1-draft / llm fixture
→ POST /v1/assessments
  assessment_id = asmt_xxxxxxxxxxxx
→ 轮询 /v1/assessments/asmt_xxxxxxxxxxxx
  status=completed stage=report_ready progress=100%
  overall=7.2 (good) provisional=False
  dimensions=5 checklist=6 evidence=5
✓ 端到端通过
```

它会建一个 arXiv 任务、轮询到出报告，并断言契约里定死的硬规则（completed 必须对应
report_ready + 100%、dimensions 恒 5、checklist 恒 6、没有悬空证据引用）。
换了端口就 `make smoke PORT=8001`。

出现的那几条 warning 是**正常的**：fixture 报告里的页码和 checklist 与 stub 解析器造的
假文本对不上，校验层如实降级——这恰好证明校验在工作。接上真实解析后就没有了。

浏览器里手动点也行：http://localhost:8000/docs

## 其他命令

```bash
make test          # 75 个测试
make lint          # ruff
make smoke         # 端到端跑一遍并检查契约硬规则
make port          # 看谁占着 8000
make stop          # 停掉本项目残留的 uvicorn
make run PORT=8001 # 换端口起
make docker-up     # 完整栈：Postgres / Redis / Celery / GROBID
```

## 拿数据组的真实论文跑校验

数据组仓库克隆在 `~/Documents/capstone/数据/cs2-paper-benchmark`，
`tests/test_parsing_benchmark.py` 里那条对着 paper_001 的用例会自动跑（找不到目录就跳过）。
手动试：

```bash
source .venv/bin/activate
python3 -c "
from app.parsing.benchmark import load_parsed_document
doc = load_parsed_document('../数据/cs2-paper-benchmark/data/parsed/paper_001/v3')
idx = doc.build_index()
print(len(doc.blocks), 'chunks,', len(doc.elements), 'elements, pages', min(idx.pages), '-', max(idx.pages))
"
```

## 可能会踩的三个坑

**1. `.git` 里的 lock 文件。** 网络同步盘挂载的文件夹禁止删除文件，git 清理不掉自己的
`.git/*.lock`，我把它们挪到了 `_to_delete/`（已在 .gitignore，约 456KB）。
你在自己的终端里没这个限制，可以直接删：

```bash
rm -rf ~/Documents/capstone/cs2-backend/_to_delete
```

**2. `Address already in use`（端口 8000 被占）。**
`uvicorn --reload` 会起父子两个进程，Ctrl-C 没收干净时子进程会继续占着端口。

```bash
make port          # 先看是什么占着
make stop          # 是本项目残留的就停掉，然后 make run
make run PORT=8001 # 是别的程序占的就换端口
```

换端口后前端的 `VITE_API_BASE_URL` 之类也要跟着改。

**3. 忘了 activate。** `make run` 走的是 `python3 -m uvicorn`，没激活 venv 的话会用系统
Python，报 `No module named uvicorn`。命令行提示符前面有 `(.venv)` 才算激活了。
