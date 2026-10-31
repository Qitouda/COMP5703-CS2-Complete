# PaperTrace · COMP5703 CS-2

PaperTrace 的完整开发仓库，合并当前前端、后端和数据项目。三部分使用同一级目录，后端的 benchmark 路径和前端帮助助手可以直接找到相邻组件。

## 客户交付与 Docker 启动

客户运行入口为仓库根目录的 `docker-compose.yml`。完整操作说明见 [Client handover and operations](docs/HANDOVER.md)，应用使用说明见 [User guide](frontend/assistant/guide.md)。

需要运行中的 Docker Engine 和 Docker Compose v2.24+。在仓库根目录复制 `.env.docker.example` 为 `.env`，填写自己的模型凭据，然后运行：

```bash
docker compose up -d --build
docker compose ps
```

打开 `http://localhost:8080`。默认包含前端与后端，并将历史、上传和证据保存在 Docker 数据卷中。帮助助手可通过 `docker compose --profile assistant up -d --build` 启用。首次构建需要联网获取镜像和依赖；真实分析另需有效的模型服务配置。

本次新增的根目录配置用于交付；`backend/docker-compose.yml` 保留原开发栈用途。下面的原生启动方式继续用于开发。

| 目录 | 内容 | 入口 |
| --- | --- | --- |
| `frontend/` | React / TypeScript 页面、HTTP 接入、帮助助手和测试 | [前端说明](frontend/README.md) |
| `backend/` | FastAPI、论文解析、五维评分、可信度核查、运行脚本和测试 | [后端说明](backend/README.zh-CN.md) |
| `data/` | 50 篇论文的结构化数据、标注、rubric、schema、SQL 和处理脚本 | [数据说明](data/README.zh-CN.md) |

本仓库保存 2026-10-30（悉尼）的当前工作文件，包含原后端尚未提交的解析和引用修复。来源版本、整理范围和验证记录见[合并记录](docs/REPOSITORY_SNAPSHOT.md)。报告、PPT、实验工作区及人工测试交接大文件不在此次合并范围内。

## 启动后端

需要 Python 3.10+；配套容量门控脚本使用 macOS/Linux 的文件锁，Windows 可使用 WSL。

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
[ -f .env ] || cp .env.example .env
```

在 `backend/.env` 填入自己的 API Key。模板已同步当前非密钥设置：模型请求等待 `300` 秒、可信度 worker 为 `1`；Claude/Gemini 使用 SSE，Gemini 使用 `minimal` 推理及 `0` thinking headroom。官方 OpenAI 与兼容中转使用各自的 Key 和端点。

```bash
python scripts/serve_local.py
```

这个入口同时安装中转容量门控：并发 `1`，请求超时后冷却 `150` 秒。只对配置的中转模型端点生效；`make run-openai` 可启动普通开发服务。模型请求等待与整篇论文任务耗时不同，详细含义和其他 timeout 见[运行配置](backend/docs/RUNTIME_CONFIGURATION.md)。服务地址为 `http://127.0.0.1:8000`。

仅调试界面而不调用模型时：

```bash
LLM_PROVIDER=fixture PARSER_PROVIDER=stub python -m uvicorn app.main:app --port 8000
```

## 启动前端

另开终端，使用 Node.js 22.12+ 和 npm 10+：

```bash
cd frontend
CS2_NPM_CACHE="$(mktemp -d /tmp/cs2-npm-cache.XXXXXX)"
npm ci --cache "$CS2_NPM_CACHE"
[ -f .env ] || cp .env.example .env
npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

打开 `http://127.0.0.1:5173`。前端默认连接本机后端；仅查看 Mock 页面时使用 `VITE_API_MODE=mock npm run dev`。可选帮助助手通过 `npm run assistant` 启动，并读取相邻的 `backend/.env`。

## 数据与检查

`data/data/` 中的已发布结构化数据以及 `data/sql/` 均已纳入版本管理。原始 PDF 由 manifest 的 URL、版本和校验值定位，下载与解析流程见[数据说明](data/README.md)。该项目的独立 benchmark 评分模型配置仍在 `data/.env.example`，与后端交互式核查配置分别管理。

```bash
# backend/，启用后端虚拟环境后
python -m pytest -q
python -m ruff check app tests scripts/serve_local.py scripts/relay_capacity.py

# frontend/
npm test
npm run lint
npm run build
npm run assistant:check

# data/，使用独立虚拟环境并安装 requirements.txt 后
python -m unittest discover -s tests -v
make validate
```

GitHub Actions 分别运行三个组件的检查。依赖仓库外私人 PDF 或历史实验材料的回归会在材料缺失时跳过，合成样本测试正常执行。

## 本地文件

真实 `.env`、API Key、数据库、上传文件、运行日志、依赖目录和构建缓存由 `.gitignore` 排除。新机器从模板建立配置并填写凭据；如果需要迁移本机报告，按[运行配置](backend/docs/RUNTIME_CONFIGURATION.md)复制私有运行数据。不要把密钥放入前端 `VITE_` 变量。
