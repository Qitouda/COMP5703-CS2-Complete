# 变更日志

## 未发布

- Keep normal public-source GET query strings in the fresh verifier and audit, while retaining exact
  model/search POST endpoints and credential/SSRF/redirect guards. Reference-agent input snapshots
  now recursively omit nested opaque tool signatures without changing the next-turn request.

- Remove the retired provider client, model option and configuration fields. GPT, Claude and Gemini share
  provider-neutral diagnostics and bounded discovery safety logic. A tracked network denylist still rejects
  the retired host before initial requests or redirects. Audit snapshots and observers recursively omit opaque
  reasoning/signatures while preserving the in-memory tool transcript needed for the next request.
- Cleanup validation is performed in an isolated worktree. Published A/B/C experiment records continue to
  identify backend `5a7772c`; subsequent cleanup commits and tests do not change that execution provenance.

- 付费评测遇到认证／权限失败或余额／硬额度耗尽时不重复发送相同请求，并对整批触发断路。
  普通速率 429 仍按原退避策略重试；重试耗尽后停止批次。50 篇运行器滚动调度，未启动篇目保持 pending，
  run_record 写明 stopped_reason；禁用域名检查覆盖同步／异步 HTTP 的每次重定向。

- DeepSeek disabled by default; GPT is the default model (`gpt-6.1-sol`, medium).
  通用启动、五维评测与可信度验收入口默认使用 GPT；50 篇运行器支持 OpenAI/Claude/Gemini，
  禁止旧模型输出回放，并记录各次尝试的实际用量、重试与独立的中转计费单位。

- 五维评分新增可选字段 `credibility_assessment_id`：创建时带上同一次运行的可信度核查 ID，服务端记录并在详情与历史列表中返回。
  前端据此配对，不再只靠"发起的浏览器的本地记录 / 同标题 10 分钟内"推断。不带该字段的旧请求不受影响。

- 新增 `POST /v1/credibility/assessments/{id}/checks/{check}/stop`：单独停止三项检查中的一项（例如跑得特别久的代码检查），
  其余检查继续。被停止的检查记为失败、得兜底分，`summary` 与 `execution.checks` 写明由用户停止（`STOPPED_BY_USER`），
  不推断任何发现；检查点带 `STOPPED_BY_USER` 备注，服务重启续跑时不会重新执行。`/progress` 增加 `stop_requested` / `stopped_by_user`。
- 停止立即生效：新增 `app/llm/interrupt.py`，检查内的模型调用在辅助线程上进行，停止标志每 0.5 秒检查一次，
  正在等待的调用被放弃（其结果丢弃、不记录）。整份取消同样受益，不再等当前调用（最长 2–5 分钟）返回。
- Gemini 单次调用的超时下限提高到 300 秒（`ModelProfile.min_timeout_seconds`）：代码审读一次约 12k 思考 token、90 秒左右，
  原先 120 秒的通用超时会把较长的调用掐断再从头重试，实测一次代码检查因此多耗时约 6 分钟。

- 新增删除接口：`DELETE /v1/credibility/assessments/{id}`（连同检查点）与 `DELETE /v1/assessments/{id}`，只删已结束的记录，
  运行中返回 409。
- 新增 `POST /v1/credibility/assessments/{id}/cancel`：用户可终止排队或运行中的核查，立即记为 `CANCELLED`（可重试）
  并留在历史中；运行中的检查在下一次模型调用前停止（`live.Cancelled` 为 BaseException，不会被检查内部的兜底捕获吞掉）。
  任务租约同时清除，已取消的任务不会被后台写回。
- 思考型模型（Gemini）的输出额度另加思考余量并把思考强度设为 medium：此前代码审读的长 JSON 被思考占满额度而截断，
  每次重试都同样失败，导致代码检查长时间无进展。
- 标题解析修复：首行以冒号或破折号结尾（"主标题:"）时继续接下一行副标题，即使副标题的词在正文中少见。
  实测 Instance Normalization 一文原先只得到 "Instance Normalization:"，现为完整标题；作者行仍不会被接入。新增回归测试。
- 新增 Claude 与 Gemini 模型（`model_claude_v1`、`model_gemini_v1`），经 OpenAI 兼容的 `/chat/completions` 调用
  （`app/llm/compatible.py`）。每个厂商一份能力档案：是否严格 JSON（Claude 的 Markdown 代码块会被去掉）、
  思考模型的最低输出额度、上下文上限。两者没有可用的内置联网搜索，代码检索借用 OpenAI 搜索，调用照实记录。
- 模型客户端声明自己的 `provider`，报告里的模型来源不再靠类名推断。
- `DEEPSEEK_ENABLED=false` 时 DeepSeek 不再出现在模型列表中；各模型的 `description` 改为给用户看的一句简介。

- 新增 `GET /v1/credibility/assessments/{id}/progress`：三项检查各自的完成状态（来自检查点）和进行中的小步
  （按用途统计的模型调用，`app/credibility/live.py` 进程内记录，检查结束即清除），供前端等待页显示。只读，不影响报告。
- 参考文献字段解析的线程池携带调用方上下文，使批量模型调用计入对应检查的进度。
- 验收修正：复现报告补查在搜索不可用（无 Search 凭据或模型不支持原生工具）时记为 `disabled`，只写局限说明，不再把代码维度标为 partial，与代码发现一致；同一候选的近似重复摘要（一段完整包含于另一段）只保留较长的原文作为一条证据；`.env.example` 的 40 次读取注释改为配置项说明。2178 项测试与 Ruff 通过。

- 新增独立的外部复现报告线索补查：已有官方代码也执行最多两条身份查询；仅对规则筛出的命中做一次模型分类，复用现有 Search 与共享来源预算。候选保留为 `third_party_reproduction` / `candidate` / 无仓库绑定，明确标为搜索摘要级、未核实，不改变代码可用性、反馈信号或评分。
- 报告补查使用候选专属的摘要片段引用，合并同一 OpenReview ID 的 PDF / forum 命中及同一 GitHub 仓库首页／根 README 命中；查询、模型尝试、来源及分类进入独立审计链，继续已保存事实时复用记录。新增开关 `CREDIBILITY_CODE_REPRODUCTION_SEARCH_ENABLED`，并将模块版本、开关和讨论批次配置纳入任务指纹。内部 fixture 客户端沿用工具能力门控，不借用真实检索密钥。
- 代码语义 Prompt 升至 `credibility-external-code-1.15`：兼容整份响应为单一 Markdown JSON 围栏的输出，原始响应继续留档；前导说明、多代码块、非法字段及数值／来源引用仍按原有校验处理。真实 S01 响应离线重放表明，去掉围栏后暴露的数值来源问题仍被拒绝。
- DeepSeek 官方文档与真实 `/models`、Search、Fetch 核对完成，当前 `deepseek-flash`、thinking 和 reasoning 配置保持。代码语义输出默认仍为 16000 tokens，可配置上限由 16000 放宽至 65536，已通过小输出真实请求验证。
- 代码讨论语义 Prompt 升至 `credibility-external-code-1.13`：只有 `repository_supported_paper_ids` 含两个及以上论文 ID 时，才要求帖子内出现论文身份；单论文仓库的讨论保留规则层的 relevant，除非模型引用同帖原文证明讨论的是其他论文、fork 或无关软件。
- 新增服务端保护 `SINGLE_PAPER_REPOSITORY_RELEVANCE_RETAINED`：已确认的单论文仓库中，模型把规则层 relevant 改为 undetermined 时恢复为 relevant，原判断留在审计中。共享仓库规则不变。
- 人工复核对照中，S03（MiN）和 B01 的失败反馈此前因相关性降级未进入顶层 `reproduction_signal`，修复后均为 `failure_reported`；S02 共享仓库仍为 undetermined。
- 讨论采集与复核排队新增“结果差距”识别 `reports_result_gap`：帖子同时出现指标数值（mAP、AP、accuracy、top-1、F1 等）和比较说法（only get、higher than、gap 等）时，即使没有 reproduce 一词也会被采集并排入第一档。只影响采集和排队，不据此判定 signal。语义复核失败或超出 8 条上限时，未复核的第一档帖子会在局限说明里逐条列出。
- 论文中“代码在补充材料中”的声明（排除 checklist 问句和否定回答）作为原文证据记录到 `supplement` 检索范围，并在局限说明中注明未检查补充文件。不下载、不解析补充材料，`code_availability` 和计分不变。
- Prompt 升至 `credibility-external-code-1.14`：在不公开标注的测试集（如 COCO test-dev）上本地评测得到 -1、0 等无效值，判为评测用法问题（discussion_only），不算复现失败；条件中比较数值时须写明每个数值出自论文、本仓库还是其他实现。
- 代码检查器版本升至 `code-checks-2.7-result-gap-supplement-claim`，使讨论采集口径变化进入任务指纹，旧检查点不会被新版本复用。
- 代码核查来源读取总上限改为配置项 `CREDIBILITY_CODE_MAX_SOURCE_READS`，默认由固定 40 提高到 60（范围 1–200），GitHub、项目页、Search、Fetch 共用；该值进入任务指纹。自动测试固定为 40 以保持原预算耗尽用例，另有用例覆盖默认 60。
- 讨论覆盖：采集不再按话题过滤，所有 issue 都收录（评论本来就逐条读取，不增加请求）；新增 `maintainer_response_source_ids`，记录 GitHub 标为 OWNER/MEMBER/COLLABORATOR 的回复，不等同论文作者回复。讨论采集不完整（评论读取失败或翻页上限）时，顶层不再给出 `discussion_only`，改为 `unable_to_verify`。
- 讨论语义复核分批：每批 `CREDIBILITY_CODE_DISCUSSION_BATCH_SIZE`（默认 5）条，最多 `CREDIBILITY_CODE_MAX_REVIEWED_DISCUSSIONS`（默认 30）条，后续批次各有 `CREDIBILITY_CODE_DISCUSSION_BATCH_ROUNDS`（默认 2）轮独立额度；共享轮次已耗尽时不追加批次，保留原有缺口记录。用于避免一次送入过多长帖导致输出被 16000 tokens 截断。
- 标题解析：混合大小写标题可跨行续接（排除作者/机构行；续行实词须在参考文献前的正文中出现至少 3 次，或上一行以介词结尾、续行小写开头；合并后不超过 20 词）；修正行尾带空格的连字符、小型大写字母词内断开（按词频比较）以及冒号后空格。8 个交接样本标题全部正确，工作区 19 份 PDF 对比另修好 2 篇、无回退。
- 接续前 2081 项测试通过；本轮新增报告补查、续跑、配置、去重、fixture 隔离与 JSON 围栏回归后，全量 2177 项测试及 Ruff 通过。

## v1.0 标准版 — 2026-10-21

- 应用版本统一为 `1.0.0`，发布标签为 `v1.0`；接口 schema 与评分 Rubric 保持各自的版本号。
- 集成实时主张核查、参考文献多来源核验与工具 Agent、论文链接分类、代码发现与证据核对。
- 提供可信度任务持久化、历史查询、检查点与服务重启中断处理。
- 完善 arXiv/PDF 解析、标题修复、输入校验与英文错误响应；PDF 页数上限提高至 120 页。
- 补充前端接口说明、离线回归测试与批量评测脚本。
- 排除环境配置、密钥、数据库、PDF、日志、缓存及临时产物。
- 发布准备检查：2059 项自动化测试通过，Ruff 检查通过。

## 2026-10-01 开发交接

- 持久化完整任务／报告快照，支持历史列表与按 ID 恢复；单实例重启将未完成任务标记为失败。
- generic-pypdf-v2 修复多行标题、摘要边界、页内章节和 caption 页码；paper_002 来源验证 17／17 通过，通用表格单元格仍未验证。
- 统一当前 R2C 文档入口；新可信度核查 Agent、接口和评分尚未实现。


## v1.0 — 2026-09-06

### paper_001 Benchmark 真实模型试跑

- 新增受限 `benchmark` 解析模式，只允许 `2307.08122v3` 加载数据组 `paper_001/v3`；其他 arXiv 和 PDF 明确失败，避免固定样本冒充任意输入。
- 合并数据组来源快照，返回真实标题、作者、arXiv 版本、18 页正文块和图表定位。
- 自动测试强制使用 fixture/stub，避免本机 `.env` 意外消耗模型额度；真实 benchmark 场景单独覆盖。
- DeepSeek JSON 报告显式关闭默认思考模式，防止生成额度被推理内容耗尽后最终 `content` 为空。
- 真实 DeepSeek 请求已到达并返回内容，但当前 Prompt 仍无法生成符合 Assessment v0.4 的完整报告；两轮修复后被校验层拒绝，未伪装为成功。

后续在同一 v1.0 收尾中，Prompt 已升级到 `analysis-v0.2` 并完成 `paper_001` 真实报告闭环；该结果不改变 Benchmark 仅支持单篇的限制。第二轮将处理任意机器学习 arXiv/PDF，见 `docs/ROUND_2_DEVELOPMENT_PLAN.zh-CN.md`。

### 支持前端 HTTP 联调

- queued/completed/failed 快照包含 source、venue、model、空值及时间字段，查询使用完整 Assessment 响应校验。
- 检查 schema 版本、可用模型/venue、arXiv 格式及 PDF 来源互斥字段。
- 上传检查文件类型、空文件、大小、PDF 结构、加密和页数，使用 pypdf 读取验证。
- 私有保存 PDF，文件权限 0600，返回上传 ID、页数和 SHA-256；解析前映射上传 ID 为实际路径。
- 示例模式在任务中保留明确警告，PDF 示例标题不再包含服务器路径。
- 添加 HTTP 集成测试和中文说明；归档本轮审计与实施方案。

### 验证

- 83 项测试通过，1 项历史真实数据目录测试跳过；ruff 静态检查通过。
- 新测试覆盖完整状态快照、真实上传字节和权限、无效输入、不可用模型和安全错误响应。
- 浏览器与前端实际联调完成 arXiv/PDF 示例流程及损坏文件提示。

### 当前边界

真实论文解析与模型 Prompt 尚未完成；默认 fixture/stub 仅用于接口联调。任务内存存储，重启后丢失；上传文件不会自动清理。无多用户认证，不应直接作为公网服务部署。审计归档是修改前快照记录，其中已修问题以本日志及前端 HTTP_INTEGRATION.md 为准。
