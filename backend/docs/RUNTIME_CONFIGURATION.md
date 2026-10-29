# 当前运行配置

同步日期：2026-10-30。`.env.example` 保存当前本地运行的非密钥配置，复制后填写自己的凭据：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
```

从合并仓库根目录运行上面的 `cd backend`；已位于 backend 时跳过。已有 `.env` 保留原文件，按下表核对配置后重启服务。模板不会携带本机 API Key、GitHub Token、联系邮箱或已有数据库。

| 设置 | 当前模板值 |
|---|---|
| `LLM_PROVIDER` / `PARSER_PROVIDER` | `openai` / `generic` |
| GPT | `gpt-6.1-sol`，`OPENAI_REASONING_EFFORT=medium` |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1`，与当前磁盘 `.env` 一致 |
| Claude | `claude-sonnet-5`，`CLAUDE_ENABLED=true`，`ANTHROPIC_CHAT_TRANSPORT=sse` |
| Gemini | `gemini-3.1-flash-lite`，`GEMINI_ENABLED=true`，`GEMINI_CHAT_TRANSPORT=sse` |
| Gemini 推理 | `GEMINI_REASONING_EFFORT=minimal`，`GEMINI_THINKING_HEADROOM=0` |
| Claude / Gemini 兼容端点 | `https://www.yunzhuhub.com/v1` |
| `LLM_TIMEOUT_SECONDS` / `LLM_MAX_RETRIES` | `300` / `2` |
| `CREDIBILITY_WORKERS` | `1` |
| Crossref 单次请求 / 分支期限 | `15` 秒 / `600` 秒 |
| 多来源引用补查期限 | `600` 秒 |
| `ARXIV_TIMEOUT_SECONDS` | `45` 秒 |
| 中转请求容量 / 超时冷却 | `1` / `150` 秒，通过配套启动脚本启用 |

Claude/Gemini 仍需各自有效的 API Key。代码检索共用 OpenAI 搜索通道，需要 `OPENAI_API_KEY`。更换模型或供应商端点后需重新核对样本结果。

旧本地启动脚本曾断言三个模型端点均为中转地址；当前磁盘 `.env` 的 OpenAI 端点已经是官方地址。可移植启动脚本读取 `.env` 和进程环境的实际值，不再强制该旧断言。进程环境优先于 `.env`；如使用已授权中转，应在本地配置对应 `OPENAI_BASE_URL` 及凭据。

## 启动与 timeout

普通启动使用现有 Makefile：

```bash
make run
```

它强制 GPT／generic。复现当前本机中转容量管理时，使用迁入仓库的启动脚本：

```bash
.venv/bin/python scripts/serve_local.py --check
.venv/bin/python scripts/serve_local.py
```

`--check` 只验证并显示非密钥配置，不启动服务、不发网络请求。脚本从任意目录均可运行，先切换到 backend，再加载 `.env`；`--env-file`、`--host`、`--port` 可显式覆盖。

该启动方式保留原运行脚本的网络检查和中转容量门控。容量固定为 1，同一中转上的模型请求跨线程、跨进程串行；流式响应完整读取或关闭后才释放容量。遇到 timeout、已发送后的取消、未读完的流以及原脚本定义的 429/524 等状态时，下一次请求等待冷却。`RELAY_COOLDOWN_SECONDS=150` 可配置冷却秒数；共享 `RELAY_CAPACITY_STATE_DIR=./data/.relay-capacity` 保持多进程一致。当前匹配的主机为 `www.yunzhuhub.com` / `yunzhuhub.com`，模型路径为 `/v1/responses`、`/v1/chat/completions`、`/v1/messages`；官方 OpenAI 地址和其他主机不受此门控限制。实现沿用 Unix `fcntl` 文件锁，适用于 macOS/Linux。

`LLM_TIMEOUT_SECONDS=300` 配置 HTTPX 单次连接／写入／读取等待；SSE 的读取限制是两次读取之间的空闲时间。它不是整篇论文或整个 SSE 流的 300 秒总时限。Gemini 能力配置还保留至少 300 秒的下限。容量排队、冷却、重试和多次模型调用会增加总耗时。前端单次 HTTP 请求超时仍为 30 秒；创建核查任务后轮询状态，核查可以运行更久。

## 存储与旧数据

模板统一使用 backend 内的可移植路径：

| 用途 | 路径 |
|---|---|
| SQLite | `./data/cs2.db` |
| 上传 PDF | `./data/uploads` |
| arXiv 缓存 | `./data/arxiv` |
| 不可变来源证据 | `./data/credibility-artifacts`，默认跟随上传目录父目录 |
| Crossref 共享状态 | `./data/crossref/state.sqlite3` |
| SSE 使用记录 | `./data/sse-usage.jsonl` |
| 中转容量锁与冷却状态 | `./data/.relay-capacity` |

原本机的这些文件位于工作区 `outputs/provider-live-runtime-20261025/`，由原 `.env` 引用；此次同步保留原文件和原配置。新仓库首次启动创建独立存储，不会带入历史报告。需要继续使用旧报告时，停服后把数据库、上传文件及不可变来源证据作为同一套存储保留，并一致更新路径。`CREDIBILITY_ARTIFACT_DIR` 是进程环境选项；配套启动脚本会把 `.env` 的值加载到进程环境，普通 `make run` 应显式导出该变量或沿用上传目录旁的默认位置。

`Settings` 无 `.env` 时的离线默认值、独立 benchmark CLI 的默认值和数据组评分模型均保持其原用途；当前运行配置以复制后的 `.env` 为准。旧 `.env` 中的 `DEEPSEEK_*`、`RUBRIC_CONFIG_PATH` 和 `RUBRIC_GUIDE_PATH` 已不被当前 Settings 使用，不写入新模板。
