> 历史记录，DeepSeek 已停用。本文保留当时的模型 ID 与请求示例；当前接口见 [HTTP 联调指南](HTTP_INTEGRATION.md)及后端 OpenAPI。

> 2026-09-06：以下为历史草案。当前实现已采用后端 `/v1` 路径、两步 PDF 上传及新建任务重试，详见 [HTTP 联调指南](HTTP_INTEGRATION.md)。

# CS-2 前后端接口讨论草案

## 1. 文档定位

本文件用于前端与后端讨论 MVP 接口，不是已经锁定的正式 API。字段业务含义、枚举和空值规则仍以《统一字段合同 v0.4》为准；路径、HTTP 状态码、认证方式和上传限制需要后端确认后锁定。

前端建议 MVP 使用 HTTP 创建任务并定时查询状态。第一版暂不要求 SSE 或 WebSocket。

## 2. 建议接口

| 用途 | 建议方法与路径 | 说明 |
|---|---|---|
| 读取可用选项 | `GET /api/options` | 返回 VenueOption 和 ModelOption |
| 创建 ArXiv 任务 | `POST /api/assessments` | JSON 请求 |
| 创建 PDF 任务 | `POST /api/assessments` | `multipart/form-data` 请求 |
| 查询任务 | `GET /api/assessments/{assessment_id}` | 返回完整 Assessment 快照 |
| 重试任务 | `POST /api/assessments/{assessment_id}/retry` | 仅允许重试后端标记为 retryable 的错误 |

如果后端选择“先上传、再创建任务”，需要额外提供上传接口，并在创建任务时提交 `upload_id`。两种方案需要在联调前二选一。

## 3. 选项接口

### 响应示例

```json
{
  "venues": [
    {
      "venue_id": "iclr_2027_main",
      "code": "ICLR",
      "name": "ICLR-inspired · 2027 Main",
      "year": 2027,
      "track": "main",
      "rubric_id": "iclr_inspired_due_diligence",
      "rubric_version": "0.1",
      "is_available": true
    }
  ],
  "models": [
    {
      "model_id": "model_standard_v1",
      "display_name": "标准评估模型",
      "provider": "internal",
      "model_version": "2026-08-25",
      "description": "平衡分析质量和处理速度。",
      "speed_tier": "standard",
      "is_available": true,
      "is_default": true
    }
  ]
}
```

前端只展示 `is_available: true` 的项目，并提交稳定的 `venue_id` 和 `model_id`。

## 4. 创建 ArXiv 任务

### 请求示例

```json
{
  "source": {
    "type": "arxiv",
    "arxiv_id": "2501.01234"
  },
  "venue_id": "iclr_2027_main",
  "model_id": "model_standard_v1"
}
```

### 最小响应

```json
{
  "schema_version": "0.4",
  "assessment_id": "asmt_01",
  "status": "queued",
  "stage": "validating_input",
  "progress_percent": 0,
  "source": {
    "type": "arxiv",
    "arxiv_id": "2501.01234",
    "original_url": "https://arxiv.org/abs/2501.01234",
    "upload_id": null,
    "original_filename": null
  },
  "venue": {},
  "model": {},
  "paper": null,
  "report": null,
  "warnings": [],
  "error": null,
  "created_at": "2026-08-29T03:00:00Z",
  "started_at": null,
  "completed_at": null
}
```

`venue` 和 `model` 应返回所选项目的完整快照，不建议只返回 ID，以便报告追溯。

## 5. 创建 PDF 任务

建议直接使用 `multipart/form-data`：

| 字段 | 类型 | 必填 |
|---|---|---:|
| `file` | PDF file | 是 |
| `venue_id` | string | 是 |
| `model_id` | string | 是 |

后端需要在联调前确认：

- 最大文件大小。
- 最大页数。
- MIME 类型与扩展名校验规则。
- 上传超时。
- 文件保存期限和隐私策略。

创建成功后，响应中的 `source.type` 为 `pdf`，并返回 `upload_id` 与 `original_filename`。

## 6. 查询与轮询

前端建议每 2 秒请求一次任务快照：

```text
queued / processing → 继续查询
completed / failed  → 停止查询
```

后端每次返回完整 `Assessment` 对象，以 `status`、`stage` 和 `progress_percent` 为事实来源。前端不从进度推断报告质量，不根据 stage 自行计算百分比。

需要后端确认：

- 推荐轮询间隔。
- 单任务最大处理时间。
- 任务不存在和任务过期使用的 HTTP 状态码。
- 临时网络失败是否建议客户端自动重试。

## 7. 错误约定

当任务处理失败时，HTTP 查询本身仍可返回成功响应，业务对象为：

```json
{
  "status": "failed",
  "stage": "analyzing",
  "error": {
    "code": "MODEL_TIMEOUT",
    "message": "分析模型响应超时，请稍后重新尝试。",
    "stage": "analyzing",
    "retryable": true,
    "debug_id": "dbg_01"
  }
}
```

前端直接展示 `message`、`code` 和 `debug_id`。只有 `retryable: true` 时显示重试按钮。响应不得包含堆栈、服务器路径、密钥或内部文件地址。

HTTP 层错误与任务业务错误需要分开：

- 请求体无效：`400`。
- 文件类型或大小不支持：建议 `413` 或 `422`，由后端确认。
- 任务不存在：`404`。
- 服务限流：`429`。
- 服务不可用：`503`。

无论采用何种 HTTP 状态码，建议统一返回 `{ "code", "message", "debug_id" }` 错误结构。

## 8. 联调前必须确认

1. 最终接口路径和 base URL。
2. 是否需要认证，以及开发环境的认证方式。
3. PDF 采用直接上传还是 upload_id 两步方案。
4. PDF 限制和隐私保存策略。
5. 轮询间隔和任务超时。
6. CORS 允许的前端地址。
7. 一份完整报告、一份 provisional 报告、两类错误的真实示例响应。
8. 字段合同版本不一致时的处理方式。
