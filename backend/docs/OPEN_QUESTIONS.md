> 历史记录，DeepSeek 已停用。以下保留当时的配置、结果和待办；当前操作见 README。

# 待确认清单

> 编号按组分前缀（PM / DATA / FE / BE），开会时直接报编号。

契约 v0.4 已锁定字段结构，但以下几点在实现时发现没有规定。代码里已经做成
可配置或按最保守方式处理，确认后请回写契约并升版本。

## 需要产品 / PM（曾博成）确认

PM-1. **证据校验失败后维度如何降级。**
   契约 §15.4 要求每个有数字分数的维度至少绑一条 `evidence_link`。若校验发现
   该引用无效并将其删除，这个维度就不再满足契约。
   - 方案 A（当前默认）：维度降为 `uncertain`，`score` 置 `null`
   - 方案 B：保留分数，`confidence` 压到 `low`
   两者产品含义不同，需要产品拍板。配置项：`EVIDENCE_DEGRADATION_POLICY`。

PM-2. **partial report 是否仍需补齐 5 个维度 / 6 项 checklist。**
   §17.2 允许失败时返回部分结果，但 §11 规定 `dimensions` 是 `array[5]`。
   当前按「必须补齐、缺的填 uncertain」实现，下游只有一条规则。

PM-3. **确认 `overall_score` / `rating` / `is_provisional` 一律由后端计算。**
   当前实现直接丢弃模型返回的数值部分。契约 §10.5 支持这一做法，但建议明写。

PM-4. **可用的 DeepSeek API key 与权限。**
   契约 §22 规定验证通过前不得把该模型标为 `is_available: true`，当前
   `/v1/models` 已按此实现。

## 需要数据处理组（刘文杰）确认

> 已读过 `cs2-paper-benchmark` 的 `paper_structuring_spec.md` v0.1、
> `sql/001_initial_schema.sql`、`rubrics/v0.1/rubric.yaml` 与 `paper_001/v3` 的真实产物。
> 后端已按这套形状改完并跑通（`app/parsing/benchmark.py`，有对着 paper_001 的测试）。
> 下面是改完之后仍然要你们确认的。

DATA-1. **anchor 格式已按你们的产物改掉，请确认。** ~~`[p7|sec_04]`~~ → `[p1-3|<chunk_id>]`
   见 `app/parsing/anchors.py`。原来的假设有两个问题：真实 `section_id` 是
   `paper_001_v3_sec_3_1`（带 paper_version 前缀），旧正则一个都匹配不上；而且
   真正稳定的定位单元是 chunk 不是 section。现在 anchor 里放 **chunk_id 原文**，
   模型把它填进 `locator_label`，后端就能反查到具体是哪一块。
   **要确认的是：`chunk_id` 在一篇论文的一个版本内是否保证唯一且稳定。**

DATA-2. **表 / 图 / 公式清单会单独发给模型。**
   正文 anchor 里没有表格编号，不给清单模型只能凭空写「Table 3」。后端现在把
   `elements.json` 的 label + caption + page 列成一份清单塞进 prompt，并在校验时
   要求编号必须能在清单里查到。**要确认：`label` 的书写是否稳定为「Table 1」
   「Figure 2」这种形式**（后端能容忍 `Tables 4–6` 这类区间写法）。

DATA-3. **`location_confidence` 被当作上限使用。**
   chunk 自评 `low` 时，证据的 `location_confidence` 会被压到 `low`。请确认这个
   字段的语义确实是「这一块的位置可不可信」，而不是别的意思。

DATA-4. **`parse_quality: poor` 的处理。**
   按你们 spec 的验收闸门，后端现在遇到 `poor` 会把报告强制标成
   `is_provisional: true`，但**不推翻分数**。请确认这个力度够不够 —— spec 里写的是
   「partial or unable-to-assess」，如果要更硬（例如直接拒绝出分），需要产品一起定。

DATA-5. **`links.json` 目前没有产出。**
   spec §8 有 paper links（`link_type: code/data/...`），但 `paper_001/v3` 里没有这个
   文件。后端的 loader 已经支持（有就用、没有就跳过），有了之后
   `code_availability` 的判定会显著更准 —— 见下面的实测。

   > 实测：paper_001 正文里的仓库地址被解析成
   > `https://github.com/ tianyu139/tangent-model-composition`（斜杠后多了个空格），
   > 严格 URL 正则匹配不到，导致明明公开了代码却被降级成 `unable_to_verify`。
   > 后端已加断行修复兜住这一例，但结构化的 `links.json` 才是根治办法。

DATA-6. **五维评分锚点与 `uncertain` / `not_applicable` 的判定规则。**
    `rubrics/v0.1/rubric.yaml` 里写着「Detailed scoring anchors must be approved
    before gold annotation begins」，这一条还没有。

DATA-7. **3–5 篇初始样本论文**，用于解析验收与 prompt 调优（目前只有 paper_001）。

DATA-8. **`rubric_version` 的写法。** 你们 rubric.yaml 是 `"0.1-draft"`，后端原先配置写的是
    `"0.1"`。后端已改成 `"0.1-draft"` 对齐。你们的 `rubric_versions` 表拿
    `(rubric_id, rubric_version)` 做外键，差一个后缀就插不进去，改版本号时请同步通知。

DATA-9. **annotation JSON 与 API 报告是两种形状，确认这是有意为之。**
    `data/annotations/ai_trial/paper_001.json` 用的是 `dimension_assessments` /
    `reproducibility_checks` / `overall_rating`（贴着数据库表名），而契约 v0.4 和前端
    用的是 `dimensions` / `reproducibility_checklist` / `overall_assessment.rating`。
    后端理解为「库内表示 vs API 表示」，两边都对。但到了 BE-06 要把评估结果写回
    你们的库时，需要一层显式的字段映射，**这层由谁写要定一下**。

## 需要与前端组确认（来自前端仓库的 API_INTEGRATION_DRAFT）

FE-1. **接口路径前缀不一致。**
    前端草案用 `/api/...`，当前后端实现用 `/v1/...`。二选一，联调前定死。

FE-2. **选项接口的形状。**
    前端草案是一个 `GET /api/options` 同时返回 `venues` 和 `models`；
    当前后端拆成了 `GET /v1/venues` 与 `GET /v1/models`。

FE-3. **PDF 的提交方式。**
    草案列了两种：创建任务时直接 `multipart/form-data`，或先 `POST /uploads`
    拿 `upload_id` 再创建任务。当前后端实现的是后者。草案本身也写明这两种要二选一。

FE-4. **重试接口。**
    前端草案有 `POST /api/assessments/{id}/retry`（只允许重试 `retryable: true` 的错误），
    当前后端还没有这个端点，需要补。

FE-5. **`GET /assessments/{id}` 目前返回的快照字段不全。**
    前端 `src/types/assessment.ts` 的 `Assessment` 要求 `source` / `venue` / `model` /
    `paper` / `report` / `warnings` / `error` / `started_at` / `completed_at` 全部存在，
    但当前后端刚创建任务时只写了 6 个字段（实测 `keys` 只有 `assessment_id`、
    `status`、`stage`、`progress_percent`、`schema_version`、`created_at`），
    前端会取到 `undefined`。草案第 4 节的「最小响应」示例是对的，实现要补齐。
    归入向泽雨 BE-01。

## 需要后端组内确认

BE-1. **报告是一次生成还是拆多次调用。**
   契约 §19 的示例 JSON 本身近 2000 token，一次生成整份的 JSON 崩坏率与空返回率
   都更高。建议拆三次：
   - ① `paper_summary` + `claimed_contributions` + `claim_checks`
   - ② 五维 `dimensions`
   - ③ `reproducibility_checklist` + `strengths` / `concerns` / `unresolved_questions`
   evidence pool 最后全局合并去重。

BE-2. **LLM Service 的输出交接格式**：原始 JSON 字符串还是已解析的 dict。
   当前 `LLMClient.complete_json` 返回原始文本，校验层负责解析——这样模型输出
   的原样留档才有意义。

BE-3. **BE-03 的拆分与日期。**
    BE-03 的目标日期是 08-30，但它依赖 BE-02 的真实输出。建议拆成
    「schema + 用契约示例跑通校验」（已完成）与「真实模型输出校验」（随 BE-02 顺延）。
