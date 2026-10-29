# HTTP 联调指南

旧五维评分默认 HTTP；其 Mock 仅显式配置 VITE_API_MODE=mock 时启用，HTTP 失败不会回退 Mock。可信度核查（首页 /#check，旧地址 /#credibility 仍可用）在 HTTP 模式下调用后端 POST/GET /v1/credibility/assessments，PDF 走 /v1/uploads；Mock 模式下使用本地原型场景。说明见 [CREDIBILITY_PROTOTYPE.md](CREDIBILITY_PROTOTYPE.md)。

## 本机启动

终端一，在 backend 目录（需 Python 3.10+）。首次运行先建虚拟环境并安装依赖：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
```

日常联调和演示均使用 GPT + 通用 arXiv/PDF 解析（需 `.env` 已配置 `OPENAI_API_KEY`）。GPT 默认型号为 `gpt-6.1-sol`，推理强度为 `medium`。`make` 用的是当前 shell 的 `python3`，必须先激活 `.venv`：

```sh
source .venv/bin/activate
make run-openai
```

可信度核查使用后端 `/v1/models` 返回的可用模型（GPT、Claude、Gemini）；Claude 和 Gemini 需在后端配置并通过小样本核查后启用。核查耗时取决于论文和外部检索；Crossref 全局每秒 1 次，同时跑多篇会排队变慢。

复测固定样本 `2307.08122v3` 时改用 `make run-real`（benchmark 解析）。只调界面、不想消耗模型额度时才用 Fixture，它返回固定示例报告，不分析真实论文：

```sh
LLM_PROVIDER=fixture PARSER_PROVIDER=stub .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

不要在已有 `.env` 上重新执行 `cp .env.example .env`，否则会把 Key 覆盖为空。

终端二，在 frontend 目录：

```sh
npm ci
VITE_API_MODE=http npm run dev -- --port 5173 --strictPort
```

`npm ci` 遇到 `~/.npm/_cacache` 权限错误时，使用项目无关的临时缓存：

```sh
CS2_NPM_CACHE="$(mktemp -d /tmp/cs2-npm-cache.XXXXXX)"
npm ci --cache "$CS2_NPM_CACHE"
VITE_API_MODE=http npm run dev -- --port 5173 --strictPort
```

打开 http://127.0.0.1:5173。后端接口文档 http://127.0.0.1:8000/docs。

Vite 将 /v1 转发到 127.0.0.1:8000。跨电脑联调需按实际后端地址修改代理 target；模型密钥只放后端。生产构建和 npm run preview 不包含开发代理，需要部署服务器另行配置 /v1 反向代理。当前版本仅用于本机单实例联调，没有账号认证，不应直接公开部署。

## 请求流程

- GET /v1/venues 与 GET /v1/models：合并可用选项，没有可用项时禁用提交。
- PDF：POST /v1/uploads，multipart 字段 file，后端校验并私有保存；返回 upload_id 后再创建任务。
- POST /v1/assessments：把页面 source_type 转为嵌套 source，取得创建回执。
- GET /v1/assessments/{id}：创建后立即查询完整快照，然后每 2 秒轮询。完成或失败停止。
- GET /v1/assessments：列出本地保存的完成或失败记录，可搜索、排序与分页；打开旧报告仍用按 ID 查询，不会触发新分析。
- 查询失败按 4/8 秒退避，连续三次失败暂停；保留 ID 并显示继续查询按钮。404/不兼容响应直接暂停。
- 可重试业务错误：先读取旧任务，确认 error.retryable，再用旧 source/venue/model 创建新 ID。上传文件不存在时要求重新上传。
- POST 不自动重发，避免重复任务；请求超时不能断言后台未收到提交。
- 返回输入页会停止查询，不取消后台已经创建的任务。

## 完整响应边界

创建回执 AssessmentReceipt 与完整 Assessment 分开。完整任务必须包含 source、venue、model、warnings、paper/report/error 及时间字段。前端 Ref 类型不再要求模型快照具备选项目录专用字段。HTTP 层兼容 FastAPI detail 错误包裹，组件只显示统一错误消息。

前端会检查顶层版本/必需对象/终态，后端 GET 使用 Pydantic Assessment 校验完整结构。收到缺字段响应应修后端，不能在页面填假模型或假论文。

## 2026-09-06 已验证

- 前端 13 用例通过，build/lint 通过。
- 后端 91 用例通过，ruff 通过。
- 浏览器提交 arXiv 2307.08122v3，得到后端 ID 并显示示例报告与贡献列表，证据抽屉可打开。
- 浏览器上传合成的一页 PDF，经后端上传和创建任务显示示例报告。
- 浏览器提交损坏 PDF，显示“文件内容不是有效 PDF”。
- 关闭后端并重新加载页面，显示无法载入与 502 错误，不显示 Mock 结果；后端恢复后可重新加载。
- 自动测试覆盖首次查询失败保留 ID/自动恢复、旧任务延迟响应不覆盖新页面、上传失败不创建任务、完整 queued/completed/failed 快照、私有文件字节和权限。

上述验收是历史 Fixture 记录。当前真实评测使用 GPT，结果以本次运行保存的报告 JSON、模型版本和运行记录为准；Fixture 示例分数不能用于真实评测。

### 模型下拉框为空

先访问 `http://127.0.0.1:8000/health`，确认 `llm_provider=openai`、
`parser_provider=generic`（固定样本回归时为 `benchmark`）；再访问 `/v1/models`，确认 GPT 的 `is_available=true` 且 `is_default=true`。如果为
`false`，通常是后端 `.env` 中 `OPENAI_API_KEY` 为空。填入 Key 后必须重启后端，前端再刷新页面。

## 第二轮接口变更（后端 94fa8d8）

后端已合入通用 arXiv 抓取、通用 PDF 解析、机器学习论文门控和版本化 Rubric。对前端有
影响的部分只有三处，已在本仓库同步：

1. **arXiv 输入放宽。** 后端 `normalize_arxiv_id` 现在接受现代 ID、`arxiv:` 前缀、
   `abs/` 与 `pdf/` 链接，以及 `archive/YYMMnnn` 旧式 ID，并统一转小写。
   `src/utils/arxiv.ts` 按同一套规则实现，输入框实时回显将要提交的规范 ID；两边规则
   必须一起改，否则前端放行的输入会在后端被拒。
2. **新增错误码 `UNABLE_TO_ASSESS`。** 门控判定论文不属于机器学习范围时，任务以
   `status=failed`、`report=null` 结束，但 `paper` 有值。这不是故障，错误页按“超出
   评估范围”的中性样式呈现，并显示已解析出的论文标题，不显示重试按钮
   （`retryable=false`）。
3. **`/health` 增加 `rubric_sha256`，`/v1/venues` 的 rubric 版本改为从实际加载的
   Rubric 读取。** 前端不调用 `/health`，仅照常展示 venue 返回的 `rubric_version`。

维度权重现在由后端按当前 Rubric 覆盖后重算总分，前端继续直接展示后端返回的
`weight` 与 `overall_score`，不自行计算。

## 当前研发边界

本指南同时覆盖旧五维 v0.4 与现行可信度接口。现行默认可信度合同为 `credibility-0.5.0-draft`，主张／引用／代码结果与执行覆盖分别记录；前端只展示后端 `/v1/models` 返回的可用模型。实际实验状态以对应报告和运行记录为准。当前需求以[项目文档](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/r2c-sync-2026-10-01/docs/project/README_%E9%A1%B9%E7%9B%AE%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md)为准，版本以[交接说明](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/r2c-sync-2026-10-01/docs/DEVELOPMENT_HANDOFF.zh-CN.md)为准。

## 基础链路与待完成项

数据组远端现有 50 篇结构化阶段库（30 篇校准、20 篇时间测试材料）；用于调试和回归，不是运行时白名单，旧五维 AI 参考评分不等于新可信度人工 Gold。后端已完成真实 arXiv 获取、通用 PDF 全文解析和机器学习论文判断；前端复用现有失败页显示“无法得出评估结果”。扫描版 PDF 的 OCR、更多样本及逐证据人工验收仍待完成，人工基准和准确率调优当前延期。新任务和完整报告快照保存于本地 SQLite，重启后可读取已完成报告；重启时未完成任务会标记失败。上传文件保留在 backend/data/uploads，尚无自动清理或多用户授权机制。旧版本未保存的报告不能自动恢复。

原 API_INTEGRATION_DRAFT.md 保留作历史记录，当前接口以本指南和后端 OpenAPI 为准。
