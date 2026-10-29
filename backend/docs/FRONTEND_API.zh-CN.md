# 前端对接接口（2026-10-21）

对应后端 `v1.0 标准版`（应用版本 `1.0.0`，发布标签 `v1.0`，主分支 `main`）。所有接口的完整 schema 以运行中的 `/openapi.json` 为准；本文只列前端需要关心的约定和本轮变化。

## 1. 模型选项

`GET /v1/models`

| model_id | provider | 默认 | 用途 |
|---|---|---|---|
| `model_gpt_v1` | openai（`gpt-6.1-sol`） | 是（`LLM_PROVIDER=openai`） | 演示与交付 |

- 前端用 `is_default=true` 的选项作为初始值，提交时把用户选择的 `model_id` 原样传给五维和三维接口。
- 只有 `is_available=true` 的选项可以提交，否则返回 400 `OPTION_UNAVAILABLE`。

- 模型选项（2026-10-24 起）：`model_gpt_v1`（GPT）、`model_claude_v1`（Claude）、`model_gemini_v1`（Gemini）。Claude / Gemini 只在配置了 Key 时列出，`*_ENABLED=true` 后才 `is_available=true`。`description` 是一句给用户看的模型简介。

## 2. PDF 上传

`POST /v1/uploads`（multipart，字段名 `file`）→ `201 {upload_id, original_filename, page_count, sha256}`

| code | HTTP | 含义 |
|---|---|---|
| `UNSUPPORTED_FILE_TYPE` | 400 | 不是 .pdf |
| `EMPTY_FILE` / `INVALID_PDF` | 400 | 空文件、损坏 |
| `PDF_ENCRYPTED` | 400 | 加密 PDF |
| `FILE_TOO_LARGE` | 413 | 超过 `MAX_UPLOAD_MB`（默认 30 MB） |
| `PAGE_LIMIT_EXCEEDED` | 413 | 超过 `MAX_PAGE_COUNT`（现为 120 页） |

## 3. 五维评分

- `POST /v1/assessments` → 202 `{assessment_id, status, stage, progress_percent, created_at}`
- `GET /v1/assessments/{id}`：轮询
- `GET /v1/assessments?search=&sort=date|title|author&offset=&limit=`：历史列表（completed / failed）
- **新增（可选字段）** 请求体可带 `credibility_assessment_id`（`cred_` + 32 位十六进制）：这份五维是和哪次可信度核查一起发起的。
  服务端原样记录，并在详情和历史列表的每一项里返回同名字段（单独发起的五维为 `null`），任何客户端都能据此把两者显示为同一次运行。
  该核查不存在时返回 404 `CREDIBILITY_ASSESSMENT_NOT_FOUND`，格式不对返回 422。不带这个字段时行为与以前完全相同。

## 4. 三维可信度核查

### 4.1 创建

`POST /v1/credibility/assessments` → 202，返回完整排队快照

```json
{
  "analysis_mode": "credibility",
  "schema_version": "credibility-0.5.0-draft",
  "rubric_version": "0.2-provisional-complete",
  "model_id": "model_gpt_v1",
  "source": {"type": "arxiv", "arxiv_id": "2106.09685", "upload_id": null}
}
```

- `source` 也可以写成 `{"type": "arxiv", "arxiv_id": null, "original_url": "https://arxiv.org/abs/2106.09685", "upload_id": null}`，后端规范化后存为 `{"type", "arxiv_id", "upload_id"}`。
- PDF：`{"type": "pdf", "arxiv_id": null, "upload_id": "upl_..."}`。
- `schema_version` 省略时为 `credibility-0.5.0-draft`，`rubric_version` 省略时为 `0.2-provisional-complete`（出试验分）。**显式传 `0.1-draft` 则不出分。**
- 无效 arXiv ID → 400 `INVALID_ARXIV_ID`；upload 不存在 → 404 `UPLOAD_NOT_FOUND`。两者都在提交时返回，不再排队后失败。

### 4.2 轮询与历史

- `GET /v1/credibility/assessments/{id}`：`status` 为 `queued | processing | completed | failed`；`stage` 为 `queued | retrieving | parsing | checking | finalizing | done | failed`。
- `checking` 阶段进度固定为 60%，持续 2–5 分钟。细分进度见下面的 `/progress`。
- **新增** `GET /v1/credibility/assessments/{id}/progress`：只用于等待页显示，报告仍以详情接口为准。返回三项检查各自的状态，以及进行中检查按用途统计的模型调用次数（进程内记录，检查结束后清除）：

```json
{"assessment_id": "cred_...", "status": "processing", "stage": "checking", "progress_percent": 60,
 "started_at": "...",
 "checks": {
   "claim_check": {"status": "completed", "finished_at": "...", "started_at": "...",
                   "steps": {"claim_extraction": 1, "claim_judgment": 4}, "last_step": "claim_judgment", "last_at": "..."},
   "reference_check": {"status": "running", "finished_at": null, "started_at": "...",
                       "steps": {"reference_field_parsing": 3}, "last_step": "reference_field_parsing", "last_at": "..."},
   "code_check": {"status": "waiting", "finished_at": null, "started_at": null, "steps": {}, "last_step": null, "last_at": null}}}
```

  用户要求停止、尚未结束的检查带 `"stop_requested": true`；因用户停止而结束的检查带 `"stopped_by_user": true`（`status` 为 `failed`）。

  `status` 为 `waiting | running | completed | partial | failed`；不存在的 ID 返回 404 `ASSESSMENT_NOT_FOUND`。
- **新增** `GET /v1/credibility/assessments?search=&offset=&limit=`：本地已完成 / 失败的核查，按时间倒序：

```json
{"items": [{"assessment_id": "cred_...", "status": "completed", "title": "...", "arxiv_id": "1706.03762",
            "source_type": "arxiv", "model_id": "model_gpt_v1", "overall_score": 8.0,
            "category": "no_significant_concerns", "error_code": null,
            "created_at": "...", "completed_at": "..."}],
 "total": 1, "offset": 0, "limit": 20}
```

首页展示预跑报告：取列表里 `status=completed` 的条目，用 `assessment_id` 调详情接口打开。

- **新增** `DELETE /v1/credibility/assessments/{id}` 与 `DELETE /v1/assessments/{id}`：从历史中删除已结束的核查 / 五维评分（204）。
  运行中的返回 409 `STILL_RUNNING`（核查需先取消），不存在返回 404。可信度核查的检查点一并删除。
- **新增** `POST /v1/credibility/assessments/{id}/cancel`：终止排队中或运行中的核查。立即记为 `status=failed`、
  `error.code=CANCELLED`（可重试），保留在历史里；后台约 1 秒内停止（正在等待的模型调用会被放弃）。不存在返回 404，已结束返回 409 `NOT_RUNNING`。
- **新增** `POST /v1/credibility/assessments/{id}/checks/{check}/stop`（`check` 为 `claim_check` / `reference_check` /
  `code_check`）：只停止其中一项检查，其余继续，整份报告照常生成。返回 202 `{assessment_id, check, stop_requested: true}`。
  被停止的检查如实记录：维度 `check_status=failed`、按兜底分计分、`summary` 写明 “stopped by the user”，
  `report.execution.checks.<check>` 为 `{"status": "failed", "stopped_by_user": true, "error": {"code": "STOPPED_BY_USER", "retryable": false}}`。
  服务重启后续跑时不会重新执行已被停止的检查。未知检查 404 `CHECK_NOT_FOUND`，核查不存在 404，已结束 409 `NOT_RUNNING`，
  该检查已完成 409 `CHECK_FINISHED`。

### 4.3 失败码（`status=failed` 时 `error.code`）

| code | retryable | 前端建议 |
|---|---|---|
| `UNABLE_TO_ASSESS` | 否 | 非英文 ML 研究论文，与五维相同，按“超出评估范围”中性显示；`paper` 字段有论文信息 |
| `PAGE_LIMIT_EXCEEDED` / `FILE_TOO_LARGE` | 否 | 显示 message |
| `ARXIV_NOT_FOUND` / `INVALID_ARXIV_ID` | 否 | 提示检查输入 |
| `PDF_PASSWORD_PROTECTED` / `EMPTY_TEXT` / `PDF_PARSE_FAILED` / `PARSE_FAILED` | 否 | 显示 message |
| `UPLOAD_NOT_FOUND` | 否 | 提示重新上传 |
| `ARXIV_FETCH_FAILED` | 是 | 可重试 |
| `SERVICE_RESTARTED` | 是 | 服务重启中断，重新提交 |
| `CANCELLED` | 是 | 用户手动终止；中性显示“已取消”，可重新提交 |
| `MODEL_UNAVAILABLE` / `MODEL_TIMEOUT` / `MODEL_OUTPUT_INVALID` / `INTERNAL_ERROR` | 视 `retryable` | 可重试 |

五维的 `error.code` 同样改为具体码：页数超限 `PAGE_LIMIT_EXCEEDED`（不可重试），其余同上表。

## 5. 统一错误格式

所有错误都是 `{"detail": {"code": "...", "message": "...", "debug_id": ...}}`，`message` 均为英文。

- 请求体校验失败：422 `INVALID_REQUEST`，另有 `detail.errors`（字段级明细）。
- 未知路由或方法：`HTTP_404` / `HTTP_405`。

## 6. 报告中可展示的新内容（0.5.0）

- `report.versions.model_calls`：每次模型调用的 `purpose`（如 `claim_extraction`、`paper_link_classification`、`reference_source_agent`、`external_code_discovery_native_tools`），可做成简易的 agent 步骤列表。
- 引用条目 `reason` 前缀：`[agent_verified_source]` 表示由引用 agent 找到并经程序验收；`[non_scholarly_official_page]` 表示数据集、系统卡等非学术来源，已找到官方页面。
- `report.code_discovery.queries[].provider`：`openai_web_search`（GPT、Claude和Gemini均使用配置的OpenAI搜索）；未执行查询可为中性`external_search`。
- 主张条目 `reconciled_from`（仅 0.5.0）：被代码维度证据改判的原始判断。

## 7. 当前前端需要改的地方

`src/components/CredibilityWorkspace.tsx` 的 live 模式目前发送：

```ts
schema_version: 'credibility-0.1.0-draft', model_id: 'not_called', rubric_version: '0.1-draft'
```

后端在真实模型下会返回 400 `OPTION_UNAVAILABLE`（`not_called` 只在 fixture 后端可用），且 0.1 版本不出分。需要改为：

1. `model_id` 使用 `/v1/models` 中选中的模型（默认 `model_gpt_v1`）。
2. `schema_version: 'credibility-0.5.0-draft'`、`rubric_version: '0.2-provisional-complete'`，并同步 `src/types/credibility.ts`（`CREDIBILITY_SCHEMA_VERSION`、新增的 `coverage`、`execution`、`external_review`、`reference_verification_summary`、`code_discovery` 等字段）。`httpCredibilityApi.ts` 的 `checked()` 会比对 `schema_version`，要一起改。
3. 首页历史：五维用 `GET /v1/assessments`，三维用新的 `GET /v1/credibility/assessments`。
