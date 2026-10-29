> 历史记录，DeepSeek 已停用。以下保留当时的配置、结果和待办；当前操作见 README。

# BE-07 本地实现与验证记录（2026-10-19）

R2C-BE-07-01～05 已有本地实现及自动化验证。全量测试 **752 项通过，0 失败、0 跳过**；`make lint` 与 `scripts` Ruff 检查通过。六篇原生模式真实回归及预取对照已有结果，正式验收未通过；07 尚未实施。本记录不将任务 `completed`、成功出分或一次工具探测等同于全部核查通过，也不据此声明合入或部署。

日常操作见[任务持久化、恢复与证据重放](durable-evidence.md)、[外部证据工具操作说明](external-tools.md)、[主张核查说明](live-claims.md)及[0.2 试验计分说明](provisional-scoring.md)。业务要求与完整验收标准见 data 仓库 `docs/project/02_各组任务/第二轮_大模型工具调用与外部证据核查任务.md`，进度统一维护在该仓库的第二轮交付任务清单。

## 01～05 实现摘要

| 子任务 | 已实现行为 | 主要代码与回归入口 |
| --- | --- | --- |
| 07-01：持久化与阶段恢复 | 使用现有 SQLAlchemy 数据库，新增独立任务与 checkpoint 表；GET 从持久记录读取。attempt、token、revision 和定期续租约束写回，显式恢复校验输入与版本指纹，旧执行者不能覆盖新尝试。解析、主张抽取、证据判断及各分项分别保存。 | [任务存储](../../app/storage/credibility_tasks.py)、[执行上下文](../../app/credibility/runtime.py)、[恢复命令](../../scripts/credibility_tasks.py)；`test_credibility_task_storage.py`、`test_credibility_durable_pipeline.py` |
| 07-02：不可变证据与重放 | 响应、规范化内容、模型实际输入和审计以 SHA256 寻址，原子写入并校验读取；报告来源保存快照引用。离线重放校验来源身份与内容、审计引用和确定性计分，不重新联网或推理。 | [快照存储](../../app/credibility/snapshots.py)、[重放入口](../../app/credibility/runtime.py)；`test_credibility_snapshots.py`、`test_credibility_durable_pipeline.py` |
| 07-03：分项隔离、受限并行与局部重试 | 解析完成后以 1～3 个 worker 独立运行主张、引用和代码检查；单项失败保留其他结果。引用恢复保留已完成且快照有效的条目，仅补查未检查项；代码事实读取成功而语义失败时可复用事实。外部服务重试及等待均有预算。 | [分项执行](../../app/credibility/execution.py)、[引用核查](../../app/credibility/references.py)、[公开来源读取](../../app/credibility/code_lookup.py)；`test_credibility_durable_pipeline.py`、`test_reference_recovery.py` |
| 07-04：按疑点进行模型外部核查 | 对不确定仓库关联和待解释讨论触发补查；`prefetch` 与 `native_tools` 显式选择。后端执行受控只读工具、保存来源并按原调用 ID 回传，模型结论须引用本次证据且通过来源／线程／引文校验；轮次、请求和文本均受限。 | [外部模型核查](../../app/credibility/code_model.py)、[工具层](../../app/credibility/external_tools.py)、[DeepSeek 适配](../../app/llm/deepseek.py)；`test_credibility_external_tools.py`、[真实协议探测](../../scripts/probe_credibility_tools.py) |
| 07-05：发现、覆盖与失败分别解释 | 新报告增加 `coverage`、`execution`、`external_review`，分别展示范围、实际执行与模型补查。缺口、未知、技术失败与论文负面发现分别记录；仓库总体分母未知时不虚填覆盖率。 | [覆盖解释](../../app/credibility/coverage.py)、[报告汇总](../../app/credibility/shell.py)、[合同模型](../../app/credibility/models.py)；`test_credibility_api_contract_versions.py`、`test_credibility_durable_pipeline.py` |

执行记录遵从检查器的真实状态：`failed / not_run / running` 不因没有外部来源而误记为完成；旧错误完成缓存会重新检查。正常的有限检索、解析覆盖不足可能保留 `dimension.check_status=partial`，而本次计划已执行完毕的 `execution` 可以是 `completed`；这与接口或模型失败需要补跑的执行 `partial` 分开判断。

## 接口兼容与计分

创建仍使用 `POST /v1/credibility/assessments`，轮询使用 `GET /v1/credibility/assessments/{assessment_id}`。

- 请求 `schema_version="credibility-0.2.0-draft"`，HTTP 报告包含 `coverage / execution / external_review`。
- 显式请求旧 `credibility-0.1.0-draft`，HTTP 报告不追加这三个字段。数据库仍保留内部执行信息，可用于查询和恢复。
- 接口版本与 Rubric 版本分别管理。新增合同及说明字段不改变用户确认的 `0.2-provisional-complete` 映射、权重、聚合和类别阈值；三项分数及总分继续由后端确定性规则计算。
- 讨论继续为 `scoring_eligible=false`；模型不能自行批准帖子参与计分。解析、未知和服务失败可能触发原 0.2 试验回退分，报告同时保留具体缺口。

当前主张 Prompt 为 `credibility-claims-live-1.4`。针对唯一严格匹配的错锚点，可仅更正 chunk／element 标识并审计；多处匹配、不适用来源或无匹配不自动猜测。原引文、条件和结论不由该步骤改写，后续角色、数值和引用校验继续执行。小数点内水平空格及明确单位符号前空格已做有限规范化，原始引文仍保留来源文本。

## 自动化与冻结核对

本地证据位于工作区 `outputs/be07-implementation-20261019/`；这些运行产物不等同于已发布的仓库文件。

| 检查 | 已观察结果 | 证据 |
| --- | --- | --- |
| 全量 pytest | 752 passed，0 failures，0 errors，0 skipped；两条现有依赖弃用 warning | [JUnit XML](../../../../outputs/be07-implementation-20261019/tests-final.xml)、[完整日志](../../../../outputs/be07-implementation-20261019/tests-final.log)、[统计 JSON](../../../../outputs/be07-implementation-20261019/tests-final-summary.json) |
| 静态检查 | `make lint` 检查 `app / tests`，另检查 `scripts`，均通过 | [lint 日志](../../../../outputs/be07-implementation-20261019/lint-final.log) |
| 源码与运行版本 | 六篇运行时按原冻结清单核对 73 个源文件；后续只补冷进程认证恢复的两个模块，另以补丁清单记录并完成全量回归；`.env` 哈希不变 | [运行时核对](../../../../outputs/be07-implementation-20261019/source-manifest-native-batch-verification.json)、[原批次源码清单](../../../../outputs/be07-implementation-20261019/native-final/code-manifest.json)、[后续窄补丁与当前源码清单](../../../../outputs/be07-implementation-20261019/post-recovery-fix.json) |

自动化包含真实 SQLite 事务与并发领取、重启读取、过期／强制接管后旧 token 拒写、checkpoint 回滚与复用、来源及产物篡改拒收、新旧合同、原计分回归、模拟响应下串并行一致及工具边界测试。自动化模型／网络响应使用受控替身，不将其统计为真实模型论文通过数。

## 已完成的真实机制验证

以下机制证据来自 `native-current` 运行，主张 Prompt 为 1.3；它们与当前 1.4 的最终 fresh 回归分开留档。

| 机制 | 已观察事实 | 可回查证据 |
| --- | --- | --- |
| 服务重启后 GET | 同一任务重启前后返回一致，模型审计数量不增加；该证明查询的是已持久化的处理中任务 | [restart-get-proof.json](../../../../outputs/be07-implementation-20261019/native-current/restart-get-proof.json) |
| 已完成阶段复用 | 恢复后的 parsing、claim_extraction 保留 attempt 1；失败判断重新执行为 attempt 2，没有再次生成解析和抽取。恢复报告仍如实保留主张失败，不据此宣称整篇分析成功 | [checkpoint-recovery-proof.json](../../../../outputs/be07-implementation-20261019/native-current/checkpoint-recovery-proof.json) |
| 禁网络／模型离线重放 | 在网络及模型调用被硬阻断时，重放返回；实际观察两类调用均为 0 | [recovery-replay-proof.json](../../../../outputs/be07-implementation-20261019/native-current/recovery-replay-proof.json) |
| DeepSeek 原生工具协议探测 | `deepseek-flash` 的真实函数请求、后端公开 README 读取、原调用 ID 回传及一次性 token 回读通过，`token_round_trip_verified=true` | [deepseek-tool-probe.json](../../../../outputs/be07-implementation-20261019/deepseek-tool-probe.json) |
| 论文任务中的真实工具执行 | LoRA fresh 任务 `cred_564f9017081247d6aef0639e5b617ad2` 实际请求并成功执行 `read_repository_readme`，审计保留原 `call_id`；该次外部语义最终为 `failed`，不能计作语义验收通过 | [当次 assessment](../../../../outputs/be07-implementation-20261019/native-current/suite-a/lora_2106_09685v2/assessment.json)，其中审计引用为 `snapshot:v1:4894d95a8aa3283cf754b19b191c87718365e812fe0886331553ef1d4b4c703a` |

协议探测证明工具链能够运行；真实工具执行记录证明论文任务确实读取过内容。仓库归属、讨论解释和引文是否正确，仍需逐篇检查最终语义状态和证据，不能从上述两项推出跨论文准确率。

## 06、07 与后续任务

07-06 当前已备六例来源固定候选、验收脚本及真实运行材料；`native-final` 的六篇 fresh 任务已结束，`prefetch` 对照及一次显式恢复分别留档。候选预期仍为 AI 辅助待复核，尚未满足正式人工 Gold、全部要求类别覆盖及同样本真实串行／并行对照，因此 **06 formal 验收未完成**。模拟响应的串并行一致性已验证，与真实串并行效果对照分别记录。

07-07 评分校准尚未实施。后续如调整数值口径，需要独立 Rubric 版本及对照，不能覆写 0.2 历史结果。

后续边界任务：

- 完成人工预期、争议复核和全类别材料，按样本数、分母、失败与未知清单完成 06；最终真实结果由运行记录补入下节。
- 继续完善受限来源与复杂论文的解析、引文／锚点修复；保持实际失败、未知与覆盖缺口，不能以试验分代替核查成功。
- 数值守卫尚非完整物理单位校验；`m/s`、`m²` 等复合／指数单位及范围共享单位需另列有界规则和反例测试，不能宣传为通用单位校验。
- 当前工具读取公开 GitHub 和已发现的论文关联页面，不执行代码、安装依赖或运行复现实验；公开帖子不自动成为独立复现或可计分证明。
- 前端真实联调、正式人工验收和新评分校准分别接续；本地代码验证不替代这些交付。

## 真实回归结果

六个新 POST、六个新任务 ID，均使用 DeepSeek 和固定 PDF 哈希；未将已有模型结果重算为新运行。三项评分及总分 **6/6 返回**，代码执行分支 **6/6 完成**；四篇触发原生模式语义解释并完成，两篇为 `not_needed`。主张分支 3/6 完成，引用分支 0/6 完整完成，整篇严格技术验收 **0/6 通过**。下表评分仍为 0.2 试验分，失败或材料不足触发的回退分不能视作核查成功。

| 论文 | 主张／引用／代码试验分 | 总分 | 三项执行状态（主张／引用／代码） | 外部语义 |
| --- | --- | ---: | --- | --- |
| LoRA | 3.00 / 3.37 / 7.00 | 4.46 | failed / partial / completed | completed |
| CoT 理论论文 | 3.00 / 4.50 / 4.00 | 3.83 | failed / partial / completed | not_needed |
| Tangent | 3.00 / 3.69 / 7.00 | 4.56 | failed / partial / completed | completed |
| GeoFAR | 7.00 / 3.66 / 4.00 | 4.89 | completed / partial / completed | not_needed |
| Object-Centric（arXiv v2） | 3.00 / 3.00 / 3.00 | 3.00 | completed / failed / completed | completed |
| DataMIL | 7.00 / 3.36 / 3.00 | 4.45 | completed / partial / completed | completed |

五篇引用查询因限流／预算留下 `partial`，新版 Object-Centric 的引用文本不能安全拆分而为 `failed`；LoRA、Tangent、CoT 的主张输出未通过校验。具体错误、条目数和来源状态保存在各自报告与汇总中，没有根据这些技术失败推断论文造假或复现失败。

本批次共 20 次成功返回的模型响应，原生模式的额外函数请求为 0：模型直接使用已抓取的有效快照。该事实与上节的真实函数请求／回传证据分别记录，不能把本批次描述为六篇都主动调用工具。所有讨论继续不具备计分资格。

Object-Centric 原 OpenReview 固定 PDF 返回 403；本表使用另行冻结、标识为 `paper_013_arxiv_v2` 的公开版本，没有把它算作原固定版本验收通过。六例预期仍非人工 Gold，不能给出准确率。

运行材料：

- [六篇汇总及任务 ID](../../../../outputs/be07-implementation-20261019/native-final/final-summary.json)、[独立冻结的最终选样](../../../../outputs/be07-implementation-20261019/final-selection.json)。
- [六份报告服务重启后 GET 一致、无新增模型调用](../../../../outputs/be07-implementation-20261019/native-final/restart-get-all-proof.json)。
- [六份报告离线重放：网络／模型被硬阻断且调用均为 0](../../../../outputs/be07-implementation-20261019/native-final/replay-all-proof.json)。

### 预取模式对照与局部恢复

LoRA 另建预取模式新任务 `cred_86ce64b702de4e7b862b3e34e051d1ae`，首次真实语义输出失败，原始报告完整保留。一次显式恢复后，`external_review=prefetch/completed`，`claim_check.reused=true`，`base_facts_reused=true`，证明重新请求模型与成功阶段复用均已实际执行；这次恢复不计作第二个 fresh 样本。

恢复报告总分为 5.18，仍未通过整篇技术验收：引用部分完成，新增评论读取出现匿名 403。该调用暴露了冷进程复用仓库事实时没有恢复公开仓库认证证明的问题，另作窄补丁验证，保留当次报告，不追改历史状态。真实对照不是固定证据质量评测，不能据两次不同模型输出和外部读取差异宣称某种模式更准确。

[预取首次报告](../../../../outputs/be07-implementation-20261019/prefetch-control/suite/lora_2106_09685v2/assessment.json)；[显式恢复报告](../../../../outputs/be07-implementation-20261019/prefetch-control/resumed.json)。

### 冷进程认证恢复补丁

预取恢复时暴露的认证缺陷已修复：仅从哈希、原始 JSON、URL／canonical ID、读取状态及公开标记均验证通过的仓库元数据快照重建公开仓库证明；不把网页、Issue 或任意 URL 登记为公开仓库。完整点路径段被拒绝，防止 HTTP 客户端规范化路径后把令牌带到其他 API。

冷进程单次真实评论 GET 现已返回 HTTP 200，实际携带认证；元数据新增请求 0、模型调用 0。原先含 403 的报告保留。补丁只影响恢复授权状态，六篇原生报告仍对应原运行时源码清单，未伪装为在补丁后全部重跑。

[冷恢复真实 HTTP 证据](../../../../outputs/be07-implementation-20261019/prefetch-control/cold-snapshot-auth-proof.json)；[预取模式与局部恢复独立核验](../../../../outputs/be07-implementation-20261019/prefetch-control/verification.json)。补丁后全量 752 项通过，静态检查通过。

## Crossref 加固补充（2026-10-19）

本节为前述六篇真实回归之后的独立引用链路修复，不覆盖原报告和 formal 验收结论。新增跨进程 FIFO 单并发、持久成功响应缓存与完整性校验、共享 Retry-After 冷却、固定主机流式读取和总 deadline；联系邮箱仅由本地配置进入 User-Agent。复查另修复 PDF 连字／ACM DOI 空白截断，原始论文文本保持不变，提取版本纳入任务 fingerprint。

LoRA 固定 60 个提取条目首次真实请求 59 次，0 个 429；DOI 窄修后仅新请求两条、其余缓存复用，60/60 checked（20 matched、40 unverified）。新进程在不同 artifactroot、禁网络条件下 60/60 cache hit、0 HTTP，60 个来源快照全部验证。该专项模型调用为 0，不计作整篇 DeepSeek 新跑或匹配准确率。全量自动化更新为 903 passed，lint 通过。配置、完整首轮失败记录和运行命令见 [Crossref 运行手册](crossref.md)及 `outputs/crossref-hardening-20261019/`。

追加 CoT 引用专项：30 次新真实 HTTP，30/30 checked（13 matched、17 unverified），0 个 429；独立进程禁网络 30/30 cache hit、30 个快照通过。与 LoRA 合计 90 个提取条目，两个集合的离线 checks/evidence 均与其 live 结果完全一致。
