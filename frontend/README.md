# PaperTrace 前端（HTTP 联调版）

开发交接基线：`r2c-sync-2026-10-01`，见[版本与交接说明](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/r2c-sync-2026-10-01/docs/DEVELOPMENT_HANDOFF.zh-CN.md)和[当前项目文档](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/main/docs/project/README_%E9%A1%B9%E7%9B%AE%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md)。对接后端 v1.0：三维可信度核查（合同 `credibility-0.5.0-draft`）是主入口，五维 Assessment v0.4 作为并列功能保留。基线标签保持不变。

## 页面结构（v1.3 界面重置）

一个顶栏，三栏导航（按决策 D-029，可信度为主线）：

- **Credibility check**（首页，`/#check`，旧地址 `/#credibility` 仍可用）：输入 arXiv 或 PDF 发起核查，可勾选"同时做五维评分"；下方是本机已完成核查的例文报告。
- **等待页**：核查通常 5–25 分钟，进度在 60% 停留到三项检查都结束。旁边是五维快评分（约 1 分钟）和可读的例文；切到别的栏目或打开例文时核查继续轮询，顶栏胶囊显示进度并可点回。
- **报告页**：总分与三项检查，新增 **How this check ran**，展示三条并行检查的耗时与状态、模型步骤、引用 agent 核实数和代码搜索轨迹（报告完成后才有，后端不实时推送）。
- **Paper scoring**：原五维流程，落地页与报告不变。
- **Reports**：合并原 `My reviews`，同时列出可信度核查与五维评分，可按类型筛选和搜索。

Mock 模式（`VITE_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 5174 --strictPort`）保留原型场景：选择的场景决定输出，输入不上传，不调用模型、解析器或外部查询。完整说明见 [CREDIBILITY_PROTOTYPE.md](docs/CREDIBILITY_PROTOTYPE.md)。

这是 PaperTrace 论文尽调产品的 React + TypeScript + Vite 前端。默认使用真实 HTTP API，页面组件通过统一 `AssessmentApi` 接口读取数据。联调和演示均使用 `make run-openai`（GPT + 通用 arXiv/PDF 解析）；`make run-real` 是受限的 `2307.08122v3` 回归；fixture/stub 只是示例报告。启动与验收见 [HTTP 联调指南](docs/HTTP_INTEGRATION.md)。

## 当前版本

- 日常开发入口：`main`，包含历史报告功能与可信度页面（HTTP + Mock 原型）；固定交接标签 `r2c-sync-2026-10-01` 保留原快照
- 具体提交版本：运行 `git log -1 --oneline` 查看
- 旧五维默认接口模式：真实 HTTP（浏览器请求本机后端）；可信度页面同样默认 HTTP，`VITE_API_MODE=mock` 时切到本地原型场景
- 界面语言：英文。后端返回的 `message`、`summary` 等文本原样展示，不做前端翻译。
- 当前后端能力：Fixture 示例流程；`benchmark` 单样本真实流程；`generic` 通用 arXiv/PDF 流程

## 环境要求

- Node.js 20.19 或更高版本，或 Node.js 22.12 及以上版本
- npm 10 或更高版本
- 如需 HTTP 联调，先启动后端并占用 `127.0.0.1:8000`

## 本地运行（推荐：连接真实后端）

先在另一个终端按后端仓库的 [`README.zh-CN.md`](../backend/README.zh-CN.md) 启动后端，并确认
`http://127.0.0.1:8000/health` 可以访问。然后在本仓库运行：

```bash
CS2_NPM_CACHE="$(mktemp -d /tmp/cs2-npm-cache.XXXXXX)"
npm ci --cache "$CS2_NPM_CACHE"
VITE_API_MODE=http npm run dev -- --host 127.0.0.1 --port 5173 --strictPort
```

这里默认使用一次性 npm 缓存，避免本机 `~/.npm/_cacache` 权限异常。若先运行
`npm run dev` 并看到 `vite: command not found`，说明依赖尚未安装成功，请完整执行上面
三条命令。不要使用 `sudo npm ci` 或 `npm ci --force`。

打开 `http://127.0.0.1:5173/`。开发服务器会把 `/v1` 请求转发到
`http://127.0.0.1:8000`；HTTP 请求失败时不会回退到 Mock。

后端按后端组的正式流程启动：在 backend 目录先 `source .venv/bin/activate`，再运行 `make run-openai`（GPT + 通用解析，需要 `OPENAI_API_KEY`）。GPT 默认型号为 `gpt-6.1-sol`，推理强度为 `medium`；实际可用选项以 `/v1/models` 为准。
Fixture/stub 只返回固定示例报告，仅用于不想消耗模型额度的界面调试。
仅在回归固定单样本时使用 `make run-real`，输入 `2307.08122v3`。如果模型下拉框为空，检查后端 `/v1/models`；GPT 返回
`is_available: false` 通常表示后端没有读到 `OPENAI_API_KEY`，修正后需重启后端并刷新页面。

完整请求流程、验收记录和跨电脑联调注意事项见
[`docs/HTTP_INTEGRATION.md`](docs/HTTP_INTEGRATION.md)。

当前后端 `.env.example` 的模型等待上限为 300 秒；Claude/Gemini 使用 SSE，Gemini
为 `gemini-3.1-flash-lite`／`minimal`。需要复现本机中转的并发 1、超时后冷却 150 秒时，
在 backend 目录使用 `.venv/bin/python scripts/serve_local.py`。具体配置见
[后端运行配置](../backend/docs/RUNTIME_CONFIGURATION.md)。前端每次 HTTP 请求仍为
30 秒超时；创建任务后持续轮询，任务总耗时可长于一次模型请求。

## 帮助助手（可选）

右下角的帮助助手由一个独立的小服务回答（`assistant/server.mjs`，Node 20+，无依赖），开发时 Vite 会把 `/assistant`
代理到它的 8020 端口。它读取 `ASSISTANT_API_KEY` / `ASSISTANT_BASE_URL` / `ASSISTANT_MODEL`，没有设置时沿用
`OPENAI_API_KEY` / `OPENAI_BASE_URL` / `OPENAI_MODEL`，因此可以直接复用后端的环境文件：

```bash
npm run assistant
```

助手的知识来自 `assistant/guide.md`，保存后自动生效。改动界面或流程时请同步更新，并运行 `npm run assistant:check`：它会核对指南里引用的按钮名是否还在界面上。维护方法见 [assistant/README.md](assistant/README.md)。不启动这个服务时，助手会提示暂不可用，其他功能不受影响。

## 可用命令

```bash
npm run dev      # 启动开发环境
npm test         # 运行自动化测试
npm run lint     # 运行代码检查
npm run build    # 类型检查并生成生产构建
npm run preview  # 预览生产构建
npm run assistant        # 启动帮助助手服务（8020）
npm run assistant:check  # 检查助手知识库与界面是否一致
```

## 不启动后端：使用 Mock 场景

仅需检查页面交互时，可显式启动 Mock：

```bash
VITE_API_MODE=mock npm run dev -- --host 127.0.0.1 --port 5173
```

输入页面可以选择四种返回场景：

- 完整报告
- 含 `uncertain` 维度的临时报告
- 模型超时，可重试
- PDF 解析失败，不可重试

Mock 数据在 `public/mock-data.js`，内容与界面同为英文，可直接用于无后端的演示。

Mock API 会依次模拟 queued、七个 processing stage，以及 completed 或 failed。可重试错误点击“重新尝试”后会重新进入队列并生成完整报告。

## 主要代码位置

- `src/types/assessment.ts`：字段合同 v0.4 对应的前端类型。
- `src/api/assessmentApi.ts`：页面依赖的 API 接口。
- `src/api/httpAssessmentApi.ts`：真实 HTTP 适配、上传、创建任务和查询实现。
- `src/api/mockAssessmentApi.ts`：仅供显式 Mock 模式使用的实现。
- `src/hooks/useAssessment.ts`：创建任务、轮询和重试流程。
- `src/utils/arxiv.ts`：arXiv 输入归一化，与后端 `app/parsing/arxiv.py` 保持同一套规则。
- `src/constants/labels.ts`：枚举文案、错误码标题、五个维度和分数色带。
- `src/index.css`：设计令牌与全部页面样式，没有 UI 框架依赖。
- `src/components/`：可信度工作区（`CredibilityWorkspace`）、报告（`CredibilityReport`）、核查过程（`CredibilityProcess`）、例文（`ExampleReports`）、合并报告列表（`ReportsPage`），以及五维的落地页、输入、进度、错误、报告和证据侧栏。
- 顶栏 `Reports`：搜索并打开后端保存的两类报告；打开旧报告不会重新调用模型。
- `public/mock-data.js`：完整报告、临时报告和错误示例数据。
- `docs/API_INTEGRATION_DRAFT.md`：供前后端讨论的接口草案。

## 旧五维界面约定

- **分数是页面主角。** 总分用大号数字加十格刻度条呈现，五个维度各有独立分数、权重和
  进度条；色带在 `scoreBand()` 里统一定义，报告各处不得各写一套。
- **无法判断不等于 0 分。** `score` 为 `null` 的维度显示 `—` 和评级词，并单独说明排除
  原因；总分下方标出实际参与计算的维度数。
- **每条判断都能回到原文。** 证据 chip 直接显示页码和定位（如 `Supports · p. 7 · Table 2`），
  点击打开右侧抽屉，可用 `←` `→` 在同一判断的多条证据间切换，`Esc` 关闭。
- **示例数据必须自报家门。** Mock 模式和后端 `model_fixture_v1` 都会在页面顶部提示报告
  为固定示例，避免会议上把示例分数当成真实结论。落地页上的评分卡是静态插图，同样标注
  为 Example report。
- **落地页只是入口。** 进行中或已完成的任务始终优先展示，落地页不会挡住轮询结果。
  它属于 MVP 基线之外的范围变更，记录见
  [docs/SCOPE_CHANGE_LANDING_PAGE.md](docs/SCOPE_CHANGE_LANDING_PAGE.md)。

## 接口模式与部署说明

`src/App.tsx` 默认选择 `httpAssessmentApi`；只有 `VITE_API_MODE=mock` 才会选择
`mockAssessmentApi`。不要把模型 API key 放入前端或任何 `VITE_` 变量，模型密钥只能由后端读取。

Vite 代理只在 `npm run dev` 时生效。生产构建或 `npm run preview` 不会自动代理 `/v1`，
部署服务器需要另行配置反向代理。

接口返回字段必须遵守项目的《统一字段合同 v0.4》。Overall Score、rating、阅读建议、EvidenceLink 关系和可用模型/Venue 均由后端提供，前端不重新计算。
