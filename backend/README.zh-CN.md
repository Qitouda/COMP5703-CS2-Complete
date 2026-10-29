# CS-2 后端

**v1.0 标准版**：应用版本 `1.0.0`，发布标签 `v1.0`。接口 schema 与评分 Rubric 继续使用各自的版本号。前端对接见[接口说明](docs/FRONTEND_API.zh-CN.md)。

日常开发入口：`main`，已含合并后的历史报告与 PDF 证据定位改动；见[三个仓库的版本与交接说明](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/main/docs/DEVELOPMENT_HANDOFF.zh-CN.md)及[当前项目文档](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/main/docs/project/README_%E9%A1%B9%E7%9B%AE%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md)。固定标签 `r2c-sync-2026-10-01` 保留原交接快照。现有 `/v1/assessments` 是旧五维评分；独立的 `/v1/credibility/assessments` 已接入实时模型，现场抽取主张、寻找论文内证据并生成判断，再核对原文位置、引文、数字和条件；启动与验收见[实时主张核查](docs/credibility/live-claims.md)。可信度计分现已接入数据组 `0.2-provisional-complete` 试验规则，明确标注试验分；显式请求 `0.1-draft` 仍不出分，见[计分接入与操作](docs/credibility/provisional-scoring.md)。

本地 BE-07 已接入任务持久化、检查点恢复、证据快照、三项独立核查和受限模型工具调用。
操作见[恢复与离线重放](docs/credibility/durable-evidence.md)和[外部证据工具](docs/credibility/external-tools.md)。
请求 `schema_version="credibility-0.5.0-draft"`（省略时的默认值）可获得覆盖、执行、外部模型核查和
`reference_verification_summary`，其中包含已提取引用的核实率及未核实原因。代码分支现保留原引 ref／子目录，
记录固定 SHA 的实现／依赖／数据说明，并在模型新确认仓库后补查实现与讨论，见[代码证据与可用性核查](docs/credibility/code-usability.md)。
历史检查器 `code-checks-2.3-implementation-shells`／Prompt `credibility-external-code-1.7` 已加入空壳排除、实际模块抽读和坏 payload 保留 partial；最新六篇有界技术执行完成（原 1.7 五篇＋LoRA 独立重试），原两批各 5/6 的失败历史保留；讨论覆盖及实际执行缺口见操作手册。
当前 0.5 已新增[自动外部代码发现](docs/credibility/code-discovery.md)：检查器 2.5／仓库语义 Prompt 1.12／发现器及发现 Prompt 1.5／供应商适配器 1.2。最新十篇 fresh 专项为6 completed、4 partial，十篇来源审计均通过。Object-Centric 已确认实现（代码分7），额外长页截断和候选上限仍保留partial；CoT片段引用校验通过（4分），一项候选Fetch服务404仍保留partial。LoRA两次16000 tokens输出截断、Limits共享读取上限也保持partial；DataMIL官方实现及后续讨论核查完成（7分）。自动回归与Ruff通过，完整测试历史及覆盖范围见操作手册。新增 `code_discovery` 单独记录候选、来源和状态；所有早期失败历史保留。
有界计划完成可同时保持 `scope_complete=false`，不表示已经运行论文代码。
引用核查已在 Crossref 之后接入有界 arXiv 与官方出版来源补查，见[自动多来源引用核查](docs/credibility/reference-auto.md)。
计分仍采用选定的试验规则，跨论文真实验收及人工复核与自动化测试分别记录。

| 显式可信度 API 版本 | 返回结构 |
|---|---|
| `credibility-0.1.0-draft` | 原结构，无覆盖／执行／外部核查／引用摘要 |
| `credibility-0.2.0-draft` | 增加覆盖／执行／外部核查，无引用摘要 |
| `credibility-0.3.0-draft` | 增加引用核实率及未核实原因摘要 |
| `credibility-0.4.0-draft` | 与 0.3 相同公开字段，澄清代码有界计划完成与关联后续查语义 |
| `credibility-0.5.0-draft`（默认） | 增加 `code_discovery`，分别记录外部发现候选、来源证明和有界执行状态 |

传输版本独立于 `rubric_version`，五版同固定 checks 的 `0.2-provisional-complete` 数值规则不变。

FastAPI + Pydantic 后端。日常运行使用 GPT 和通用解析器，接收
arXiv 链接或 PDF 后返回符合《统一字段合同 v0.4》的完整报告；离线界面开发可显式选择 fixture。

`.env.example` 已同步 2026-10-30 本地运行的非密钥配置：模型请求等待 300 秒、可信度
worker 为 1、Claude/Gemini 使用 SSE，Gemini 为 `gemini-3.1-flash-lite`／`minimal`，
thinking headroom 为 0。模板的密钥留空，数据库、上传、缓存和审计文件改为 `backend/`
内的相对路径。端点、并发门控启动方式和旧数据迁移见[运行配置](docs/RUNTIME_CONFIGURATION.md)。

## 已实现基础能力（旧五维接口）

系统现在支持任意格式合法的 arXiv ID、abs/PDF 链接和用户上传 PDF。通用流程会下载或读取
真实 PDF，提取元数据、章节、正文块、图表和链接，将结构化快照写入数据库，然后执行英文
机器学习论文判断门。只有能够确认为英文机器学习研究论文的文档才进入五维评分；其他内容
返回 `failed + UNABLE_TO_ASSESS + report:null`，不会生成数字分数。

评分规则从版本化 Rubric 加载，当前版本为 `0.1-draft`，分析 Prompt 为 `analysis-v0.4`。
数据组的 30 篇论文只用于回归，不是运行时白名单。详细设计见
[`R2_ARXIV_STRUCTURED_INGESTION.zh-CN.md`](docs/R2_ARXIV_STRUCTURED_INGESTION.zh-CN.md) 和
[`R2_ELIGIBILITY_AND_RUBRIC.zh-CN.md`](docs/R2_ELIGIBILITY_AND_RUBRIC.zh-CN.md)。

上传默认位于 data/uploads，文件权限 0600；不通过 HTTP 提供原文件。完整任务与报告快照保存在本地 SQLite 的 `assessment_snapshots` 表，重启后仍可按 ID 打开已完成报告；重启时未完成的任务会标记为失败，需重新提交。此版本用于本机单实例联调，无身份认证、无自动文件清理，不要直接作为公网服务发布。

## 旧五维端到端测试（推荐）

以下步骤会调用真实 GPT API 并产生费用。先进入后端仓库，准备环境：

```bash
cd backend
[ -d .venv ] || python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
```

如果 `.venv` 已存在，可以跳过创建步骤。在 `.env` 中配置 `OPENAI_API_KEY`，
使用`LLM_PROVIDER=openai`；模型密钥只放本地配置，不复制到隔离测试副本。
当前 GPT 型号为 `gpt-6.1-sol`，推理强度为 `medium`。通过已授权中转接入时，
填写对应的 `OPENAI_BASE_URL`（包含 `/v1`）和该中转自己的 Key。

不要把 Key 放进前端、命令历史或 Git。`.env` 已存在时不要再次复制模板，以免覆盖现有 Key。

### 1. 启动通用后端

```bash
make run-generic
```

这个命令强制使用 `LLM_PROVIDER=openai` 和 `PARSER_PROVIDER=generic`。另开终端检查：

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/v1/models
```

健康检查应包含：

```json
{
  "status": "ok",
  "rubric_version": "0.1-draft",
  "rubric_sha256": "...",
  "llm_provider": "openai",
  "parser_provider": "generic"
}
```

模型接口中的 `model_gpt_v1` 应为 `is_available: true` 且 `is_default: true`。
若不可用，检查 `OPENAI_API_KEY` 是否已读取，并在修改 `.env` 后重启后端。
Claude/Gemini 配置 Key 后列出，完成真实样本验收再启用；三者的代码检索共用
配置的 OpenAI 搜索通道。比较模型时，应固定或记录这一共享组件。

### 2. 启动前端

在另一个终端运行：

```bash
cd frontend
CS2_NPM_CACHE="$(mktemp -d /tmp/cs2-npm-cache.XXXXXX)"
npm ci --cache "$CS2_NPM_CACHE"
VITE_API_MODE=http npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 `http://127.0.0.1:5173/`。开发服务器会把 `/v1` 请求转发到本机 8000 端口，HTTP
失败时不会回退到 Mock。

### 3. 按顺序验收四条路径

| 场景 | 操作 | 预期结果 |
|---|---|---|
| Manifest 外 arXiv | 输入 `1706.03762` 或其 abs/PDF 链接 | 自动识别实际版本，完成五维报告 |
| 用户 PDF | 上传一份带文本层的英文 ML 论文 PDF | 与 arXiv 使用相同解析、门控和评分流程 |
| 无法评估 | 上传一份明显非 ML 或非研究论文 PDF | 显示“无法得出评估结果”，不显示分数 |
| 无效 PDF | 上传损坏、空白或加密 PDF | 上传或解析阶段明确失败，不生成报告 |

任务成功时应依次经过获取、解析、分析、证据关联和报告就绪。无法评估时，最终快照应满足：

```json
{
  "status": "failed",
  "report": null,
  "error": {
    "code": "UNABLE_TO_ASSESS",
    "retryable": false
  }
}
```

### 4. 确认结构化数据已入库

后端使用默认 SQLite 配置时，完成一次 arXiv 或 PDF 解析后运行：

```bash
sqlite3 data/cs2.db '
SELECT p.id, p.arxiv_id, p.title, d.parser, d.parse_quality
FROM papers p JOIN parsed_docs d ON d.paper_id = p.id
ORDER BY d.id DESC LIMIT 5;'
```

通用解析记录的 `parser` 应为 `generic-pypdf-v2`。原始 PDF 路径属于私有信息，不会通过
Assessment API 返回。任务进行时使用内存轮询，同时将状态和完整报告快照写入本地数据库。
重启后可从 `GET /v1/assessments/{id}` 打开已保存报告；旧版本未保存的报告无法补回。

## 第一轮 benchmark 回归模式

需要复现固定样本 `paper_001 / 2307.08122v3` 时，可运行：

```bash
make run-real
```

该命令使用 `PARSER_PROVIDER=benchmark`，只接受 `2307.08122v3`，用于回归对照，不是
第二轮通用运行方式。

## Fixture 开发模式

以下命令用于无费用接口开发和自动测试，不会分析真实论文：

```bash
pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
LLM_PROVIDER=fixture PARSER_PROVIDER=stub python3 -m uvicorn app.main:app --reload --port 8000
```

上面的进程环境变量显式选择 fixture/stub；`make run` 会强制使用 GPT／generic，
需要真实模型 Key。浏览器打开 `http://localhost:8000/docs`。Fixture 使用本地 SQLite，
不需要 Docker 或 API Key。
虚拟环境与验证步骤见 [`docs/LOCAL_SETUP.md`](docs/LOCAL_SETUP.md)。

## 可用命令

```bash
make run         # 启动开发服务（SQLite + 内置后台任务）
make run-real    # 强制 GPT + paper_001 Benchmark 真实测试
make run-generic # 强制 GPT + 通用 arXiv/PDF 解析、门控和评分
make test        # 运行自动化测试
make lint        # 运行代码检查
make smoke       # 端到端跑一遍并检查契约硬规则
make docker-up   # 启动完整栈（Postgres / Redis / Celery / GROBID）
```

## 接口

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/health` | 健康检查，返回当前 schema / rubric 版本与运行模式 |
| GET | `/v1/venues` | Venue 选项 |
| GET | `/v1/models` | 模型选项 |
| POST | `/v1/uploads` | PDF 上传，返回 `upload_id` |
| POST | `/v1/assessments` | 创建任务，立刻返回 `assessment_id`（202） |
| GET | `/v1/assessments` | 搜索、排序和分页读取本地历史记录 |
| GET | `/v1/assessments/{id}` | 轮询状态与结果 |
| POST | `/internal/validate-report` | 内部工具：校验一份模型输出 |

评分是长任务，创建接口立刻返回，前端轮询状态，不要期待同步拿到报告。

## 运行模式

四组开关都在 `.env` 里，代码不需要改：

- `LLM_PROVIDER`：`fixture`（返回固定示例报告）、`openai`、`anthropic`或`google`；它决定默认模型，不限制已配置 Key 的其他模型选项
- `PARSER_PROVIDER`：`stub`、`benchmark`（仅加载 `paper_001`）、`generic`（通用）或 `grobid`
- `TASK_RUNNER`：`inline`（FastAPI 后台任务）或 `celery`
- `CREDIBILITY_PARSE_SOURCE`：`live`（默认，可信度核查用后端解析器解析输入论文，与五维一致）或 `benchmark`（优先读数据组 `data/data/parsed`，仅用于回归与历史验收重放）

仅测试数据组 `paper_001 / 2307.08122v3` 时，可设置：

```env
PARSER_PROVIDER=benchmark
BENCHMARK_PARSED_DIR=../data/data/parsed/paper_001/v3
BENCHMARK_SOURCE_RECORD=../data/data/source_snapshots/paper_001/source_record.json
BENCHMARK_ARXIV_ID=2307.08122v3
```

该模式拒绝其他 arXiv ID 和所有 PDF 输入，避免将固定样本错误地当成任意用户论文。

## 主要代码位置

- `app/schemas/`：字段合同 v0.4 对应的 Pydantic 类型与校验。
- `app/validation/`：证据校验、维度降级、可复现 checklist 交叉核对、总分计算。
- `app/llm/`：模型客户端接口、重试与 repair pass。
- `app/parsing/`：通用 arXiv 获取、PDF 结构化、位置 anchor 和 benchmark loader。
- `app/eligibility/`：评分前的英文机器学习论文判断门。
- `app/rubrics/`：版本化 Rubric、评分指南和严格加载器。
- `app/pipeline/orchestrator.py`：从输入到报告的端到端流程。
- `app/storage/`、`app/tracking/`：数据表与模型调用追踪。
- `docs/OPEN_QUESTIONS.md`：契约尚未规定、需要跨组确认的事项。

数据组 `cs2-paper-benchmark` 的解析产物用
`load_parsed_document(".../data/parsed/paper_001/v3").build_index()` 读进来，
直接喂给 `validate_report_payload(source_index=...)`，不必等 GROBID 通道。字段形状对齐
`paper_structuring_spec.md` v0.1，他们改了形状 `tests/test_parsing_benchmark.py` 会先红。

## 真实模型实现

GPT 客户端位于 `app/llm/openai.py`，Claude/Gemini 兼容客户端位于
`app/llm/compatible.py`，分析 Prompt 位于 `app/llm/prompts.py`。
模型输出统一经过 `app/validation/` 校验，分数由相同规则重算。
默认关闭历史供应商；现行入口不依赖其凭据或服务。

50 篇锁定全文评测使用 `scripts/run_full_benchmark.py --provider openai`，
默认读取 `.env` 中的 GPT 型号与推理设置。加 `--papers paper_001 paper_002 --execute`
先跑两篇，再在同一目录省略 `--papers` 完成全量。不能回放其他目录的模型输出。
运行器记录所有尝试的用量、失败、重试及价格来源；中转价格保留平台单位，
不把价格页显示的货币符号直接当成人民币。详细命令见英文 README。

## 约定

Overall Score、rating 和 `is_provisional` 一律由后端按契约 §10.5 计算，模型返回的
数值全部丢弃。`dimensions` 恒为 5 个、`reproducibility_checklist` 恒为 6 项，缺的用
`uncertain` / `unable_to_verify` 填。

证据的位置必须能回查：正文引用 chunk_id、表图引用解析出的编号，核对不上就降置信度，
页码不在解析范围内则置空，解析器自评的 `location_confidence` 是上限。不编造页码和引文。

改动字段前先更新《统一字段合同》并升版本，再改 `app/schemas/`。

## 相关仓库

- 前端：`Qitouda/COMP5703-CS2-Frontend`
- 数据组基准库：`eden-eden-new/cs2-paper-benchmark`
- 后端（本仓库）：`kanekogaido/cs2-capstone--backend`

## 数据安全

不得提交 `.env`、API key、论文 PDF 或任何用户上传内容，协作规范见
[`CONTRIBUTING.md`](CONTRIBUTING.md)。

英文正式版见 [`README.md`](README.md)。
