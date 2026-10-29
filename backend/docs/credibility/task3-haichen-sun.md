> 历史记录，DeepSeek 已停用。以下保留当时的配置、结果和待办；当前操作见 README。

# 任务三交接：代码与公开复现线索

负责人：Haichen Sun。实现日期：2026-10-17。

## 负责范围

复用已有 ParsedDocument、CheckContext、论文证据定位和 credibility 任务入口，完成候选代码发现、仓库关联确认、可访问性检查、公开 issue/评论证据记录。无需新增前端合同或独立评分器。任务一、任务二、旧五维生产逻辑未修改。

## 本次实现顺序与文件

1. `app/credibility/code_lookup.py`：公共 HTTPS 查询客户端。进程内 TTL/LRU 缓存（成功 600 秒，失败 30 秒，最多 256 条），共享线程锁和最小 0.25 秒请求间隔；识别 timeout、not_found、rate_limited、access_denied、error。识别限流后暂停该主机后续请求。禁止凭据 URL、非 HTTPS、私网地址，并重新检查重定向目标。单响应最多 1 MB，不执行仓库代码。
2. `app/credibility/code_checks.py`：替换原占位实现，保持 `check_code(ctx)` 签名不变。扫描正文、附录和已解析补充材料；定位候选所在原文；访问论文明确标出的官方页面；关联确认后检查文件目录、公开 issue 和评论。所有外部来源记录 URL、抓取时间、缓存标志和状态。
3. `tests/test_code_checks.py`：覆盖候选误关联、截断／断行链接、官方页面上的基线链接、共享仓库、评论分页与失败、PR 过滤、作者身份依据、理论不适用、任务接口与轮询、缓存、限流、私网重定向和响应上限。
4. `tests/test_credibility_shell.py`：仅更新原先断言第三项永远 not_run 的占位测试；现在有解析内容时实际执行有限范围扫描。
5. `scripts/verify_code_checks.py`：直接使用数据组解析目录运行第三项，保存可回查 JSON。

## 判定原则

- links.json 只作候选；完整 URL 也不是论文归属证明。
- 论文原文明确写出的本论文代码链接，或仓库 README 开头明确声明实现当前论文，可建立关联。官方页面必须匹配当前论文，且链接明确标为 Code/Repository 等，不能把页面上的基线链接全部归给当前论文。
- `https://github.com/` 本身不会被确认为仓库。只有原文紧随其后确实包含 owner/repo 时，才恢复这种 PDF 空格／断行形式；证据保留未修复的原文和真实 chunk/page。
- `code_availability=available` 要求关联确认、仓库可访问且指定 revision 的文件目录中找到实现文件线索。这不证明实现完整或可运行。
- issue 的 `pull_request` 条目跳过；同时查询 open/closed issue。评论单独分页，不能只检查 issue 标题。
- 成功／失败分类采用保守英文规则；提问不算成功，关闭 issue 不算问题解决。同一线程同时有成功和失败时保留原文并写明，不抵消两种报告。
- 共享仓库支持多篇论文时，线程没有明确论文标识则 `relevance=undetermined`，不汇总成当前论文的成功／失败。没有相关反馈只能是实际完成限定列表查询后的结果；超时或漏页不能写成没有反馈。
- 维护者回复保留账号和仓库角色。只有 README 中全名 GitHub 资料链接匹配论文作者元数据时才填 `author_response_source_ids`；未能证明身份时保持空数组。独立性不凭仓库角色推断。
- 理论不适用采用保守规则：原文明确声明纯理论、可定位，且未发现实验／结果等相反线索。其他情况保持 applicable 或 undetermined，不能用查询失败推断不适用。
- 不运行论文代码。分数和评分规则 ID 保持空，仍交由现有后端计分器处理总评；所有讨论 `scoring_eligible=false`，等待 Rubric 正式确认。

## 接口接入

原有 `POST /v1/credibility/assessments` 和 `GET /v1/credibility/assessments/{id}` 自动调用新实现，不新增 API。

前端读取：

- `report.checks.code`：仓库、讨论、各检索范围和限制。
- `report.dimensions` 中的 `code_reproduction`。
- `report.evidence`：论文证据使用原始 chunk/page；外部证据关联 `source_id`。
- `report.sources`、`report.findings`、现有总评与 alerts。

任务完成后轮询只读已保存快照，不重复运行查询。已有报告组装器继续验证所有证据和来源 ID 引用闭合。

## 验证结果

独立 Python 3.12 环境执行：

```sh
python -m pip install -e '.[dev]'
python -m pytest -q
ruff check app/credibility/code_checks.py app/credibility/code_lookup.py tests/test_code_checks.py scripts/verify_code_checks.py tests/test_credibility_shell.py
git diff --check
```

结果：213 passed，9 skipped；新改文件 Ruff 和 diff whitespace 检查通过。9 个跳过项依赖旧测试指定的联仓数据路径，本机数据目录布局不同。出现一个 FastAPI/Starlette TestClient 依赖弃用警告；测试通过。未修改项目依赖声明。

注意：当前 `CheckContext` 的默认 benchmark 路径是 `数据/cs2-paper-benchmark/data`；本机实际是同级 `cs2-paper-benchmark/data`。此处没有顺手更改任务一的数据路径。真实样本采用下面的脚本显式指定目录；前端端到端真实数据联调仍需对齐既有部署目录或启用既有 live parser。本次 API 联调测试注入了相同结构的已解析文档，并非浏览器人工验收。

## 真实 paper_001 只读检查

```sh
python scripts/verify_code_checks.py \
  --parsed-dir ../cs2-paper-benchmark/data/parsed/paper_001/v3 \
  --arxiv-id 2307.08122v3 \
  --output /tmp/paper_001-code-check.json
```

本次结果：

- 摘要第 1 页，`paper_001_v3_chunk_0001`，原文是 `Our code is available at: https://github.com/ tianyu139/tangent-model-composition`。
- 恢复并确认 `https://github.com/tianyu139/tangent-model-composition`；README 明确列出 arXiv 2307.08122，同时还支持另一篇论文 2307.08114。
- 检查 revision `1f282134c7d57ea20dbbfa5243909eb50d698c35` 的目录，发现实现文件，`code_availability=available`。
- 找到 issue #1 和两条评论，其中有 OWNER 角色的维护者回复。内容是模型组合问题的讨论，不是明确的复现成功／失败报告。
- 由于仓库关联两篇论文，而该线程未明确指定本篇，讨论状态为 `discussion_only`，相关性为 `undetermined`；总复现信号为 `unable_to_verify`。
- 共 1 个仓库、1 个讨论、9 个来源。没有执行代码，没有填分数，没有声称系统已复现。

## 明确的剩余范围

这是可运行的保守第一版，`scope_complete=false`。目前支持 GitHub，未接 GitLab、Bitbucket 等托管平台，也没有查询 GitHub Discussions。只访问论文明确标出的官方文本页面；不递归抓取整个网站，不另行下载和解析 PDF/ZIP 附件。

每次最多 4 个候选仓库、4 个官方页面、每仓库 2 页 issue（每页 20 条）、每 issue 2 页评论（每页 100 条）、总计 40 次外部查询。超过上限、分页不完整和查询失败会留在报告限制中。

英文规则不能覆盖所有复现表述。混合意见、条件细节、论文作者身份和理论论文类型仍需人工复核；现有合同没有单独的人审写入字段，本次没有自行添加。缓存与任务表沿用进程级生命周期，未实现分布式持久缓存。下一步是前端真实数据验收、团队 Rubric/合同确认，再扩展平台和分类规则。


## 2026-10-19 代码可用性专项：最新六篇有界技术验证完成

本节补充当前实现，前文日期、计数及原占位／早期完成语义作为历史保留，不套用为此次验收结论。使用者已授权代码专项修复及真实 DeepSeek 验证；本轮没有安装依赖或执行论文仓库代码，原 `0.2-provisional-complete` 规则字节、映射和数值计算保持不变。

当前默认合同升级为 `credibility-0.4.0-draft`，公开字段与 v0.3 相同；显式 0.1／0.2／0.3 请求继续保留原响应形状。v0.4 合同区分有界计划 completed 与 `scope_complete=false`：成功执行声明范围可完成，来源访问失败、必要语义未完成或预算不足仍 partial；没有有效解析输入保持 not_run／failed。此前“有试验分／模型返回／代码分支执行”不能单独代表本轮技术验收通过。

已实现 GeoFAR 类 `dataset and code are available at` 项目页声明、HTML 嵌套／无引号／相对链接解析和基线区域排除；保留论文／官方 Code 入口指定的 ref、固定 SHA 和子目录，显式 SHA 不一致拒绝读取，未指定才使用默认分支。实现文件限定在原引子目录，明确 vendor／third_party／docs／tutorial／tests 及已知空文件不作实现证据。新增 `code_implementation_inspection` 观察快照记录入口候选、依赖清单、README 数据／权重说明、实际抽读路径与 source_id／状态，始终 `runnable_status=not_executed`。这些观察不新增强制评分条件。`setup.py` 只作为包装／依赖清单；唯一且实际读取后只含注释、docstring、导入或字面量包元数据的 `__init__.py` 不构成研究实现，含真实逻辑的初始化文件仍保留。实际抽读优先可见入口，再优先非 `__init__.py` 模块。

经证据校验后的模型新确认仓库，会触发尚未完成的固定版本实现／讨论补查；有新增讨论时最多再进行一次有界语义解释。两次语义及基础／后续采集共享每次执行 40 次 `LOOKUP.get` 来源读取预算和配置的模型轮次／工具预算，40 次包括缓存命中；实际网络 HTTP 包含有界重定向并另行审计。原来源、失败和所有模型阶段保留，不重复覆盖旧证据，也不借同仓库不同 SHA／子目录 README 或其他帖子确认当前目标。HTTP 200 下的损坏 base64、缺失内容编码或错误目录 payload 仍保持采集 partial，补查不能只凭 HTTP 成功抹去这些缺口。

每个语义阶段最多 4 个待关联仓库、8 条讨论目标；讨论根据原文中复现困难投诉、其他执行困难、其余目标的顺序选入，同级保留采集顺序。该队列只决定优先级，不自动给失败结论；未选目标不冒充已经语义核查。多论文仓库仅按明确 Paper 标签、代码归属句及紧邻论文链接块或 Supported／Implemented Papers 节确认支持范围，不将长引言、基线／骨干模型表中的所有 arXiv 引用当作受支持论文。

实现及操作手册：`backend/docs/credibility/code-usability.md`；代码入口 `code_checks.py / code_repository_scope.py / code_model.py / external_tools.py / execution.py`。固定检查器版本 `code-checks-2.3-implementation-shells`、pipeline `credibility-0.7-code-evidence`、外部核查 Prompt `credibility-external-code-1.7` 进入指纹。原 v0.4 统一字段合同与本独立可信度 v0.4 合同分别管理，不据名字相同混为同一版本。

针对性自动测试已覆盖声明／HTML／基线、显式 SHA／斜杠分支／子目录、实现与来源失败、标准 GitHub 换行 base64、HTTP 200 坏 payload 不丢 partial、包装空壳排除及实际模块抽读、模型确认后续查、幂等及共享预算、无输入不误标完成、语义证据权限和多阶段审计；最新本地全量回归为 1,471 passed，2 条既有依赖弃用警告，未修改原 0.2 Rubric。Prompt 1.7 增加来源数字／架构标识的原拼写提示，并允许数字条件错误在剩余轮次内做最多一次无工具输出修复；最终仍通过原强校验，共享模型／工具／来源预算不增加。

真实专项脚本 `backend/scripts/verify_code_usability.py` 使用 `--execute`、`--mode native_tools`，按 `outputs/code-usability-20261019/samples-frozen.json` 的 PDF SHA 重新解析，每篇新进程／新输出目录，不读取旧代码结论或模型输出，只执行代码分支及既有代码计分，不重跑主张／引用或声称得到整篇新总分。六篇为 LoRA v2、paper_001、GeoFAR paper_038、DataMIL paper_037、CoT paper_005、paper_013_arxiv_v2；预期清单 `is_human_gold=false`。

**当前状态：2.3／Prompt 1.7 的最新六篇有界技术执行均 completed，选用原 1.7 的五篇已完成运行及 LoRA 一次同配置 fresh 独立重试；不是首次同批六篇全部通过。** 最新原 0.2 代码试验分：LoRA／paper_001／GeoFAR 各 7，DataMIL／Object-Centric 各 3，CoT 为 4。available 只表示关联实现证据，unable_to_verify／not_found_in_scope 不冒充代码不存在或复现失败。

两轮原始失败都保留：`acceptance-final/`（1.6）原六篇 5 completed、LoRA partial，`resnet18` 被模型重写为 `ResNet-18` 触发数字条件 guard；`acceptance-rerun-v1_7/` 原六篇同为 5 completed、LoRA partial，客户端 LLMOutputInvalid 未取得可验证原始 JSON，上游具体原因未知。唯一追加 LoRA 重试在 `acceptance-rerun-v1_7-retry/`，两次 finish_reason=stop、第一次完成 14,396 tokens 未截断，数字条件 code_disc_13 触发一次无工具修复后通过原强校验；不能据此追溯断言先前失败为长度截断。

LoRA 保留 15 帖、其中仅 8 帖模型语义审核：5 条 failure_reported、10 条 discussion_only，后者包含 7 条仅基础规则的帖子，其相关性／条件／解决状态未据此全部完成语义验收；所有讨论仍不计分。实际抽读 loralib/layers.py 与 examples/NLU/docker/transformers-cpu/Dockerfile，前者为实现、后者为容器依赖观察；setup.py 仍只作为通用包装清单，不能单独证明实现。真实“模型新确认→新增讨论→第二语义阶段”正向闭环仍只由自动化回归覆盖，额外 paper_009 因原 PDF 403 未补入。运行、不可变来源、逐篇复核、最新选择及机器审计保留在 `outputs/code-usability-20261019/`；最新 acceptance-latest-six-artifact-audit.json 六项均通过；以其 README、根报告和汇总为准。正式人工 Gold、前端人工联调、非 GitHub 平台及实际论文代码执行仍分别待办，没有据此声明 BE-07 整体验收、部署、远端推送或共享盘上传。


## 2026-10-19 自动外部代码发现 0.5：实现已接入，真实验收待完成

本节为新任务追加，前文 2.3／Prompt 1.7 的原六篇、独立重试、失败原因和计数不改。新默认合同 `credibility-0.5.0-draft` 在报告顶层新增 `code_discovery`；显式 0.1–0.4 仍投影旧公开结构。计分继续使用原 `0.2-provisional-complete`，没有改变既有代码／讨论字段、数值映射或独立性权限。

新实现为检查器 `code-checks-2.4-discovery-intake`、仓库语义 Prompt `credibility-external-code-1.8`、发现器 `code-discovery-1.0`／发现 Prompt `credibility-code-discovery-1.0`，pipeline `credibility-0.8-code-discovery`。缺少可确认实现时，由模型选择服务端按当前论文身份登记的 query_id 作 Search，再选本次搜索命中或实际页面链接登记的 candidate_id 作 Fetch；不能提交任意查询、URL、仓库或执行命令。搜索片段只是线索，候选分类用实际已取正文原引文，阅读列表／相关基准、真正第三方复现、官方声明分别记录。

`intake_discovered_repositories` 验证来源／证据与不可变快照，按仓库身份和原 ref／子目录去重；新增仓库一律 uncertain，不把搜索引文或 README 相邻引用自动当官方关联。后续沿用实际 GitHub 元数据、固定 SHA／子目录 README、语义关联、实现抽读与讨论补查。只有既有来源校验确认关联并取得实现材料才走原代码计分；明确第三方复现保留发现记录，不自动取得官方代码分。否定、跨论文／比较语句及选择性省略第三方声明的引用不能建立官方归属。

发现默认最多 3 查询、4 页面、20 候选、4 轮模型／8 次工具；仓库语义仍共用原 3 轮／6 次工具。两阶段与基础采集／确认后补查共享 40 次来源操作，Search／Fetch 供应商请求与 LOOKUP.get 一起计数，实际 HTTP 跳转及模型调用另记。Fetch 的 Markdown 是供应商提取内容，不能冒充原站 raw body、origin HTTP 或已核跳转链；失败、限流、预算、不可读及未完成目标保留原因，恢复／GET 不无故重搜，也不把失败转成无代码。

操作说明见 `backend/docs/credibility/code-discovery.md`、`external-tools.md` 与 `code-usability.md`。新增回归覆盖发现权限链、第三方／阅读列表负例、来源和引文拒绝、原 SHA／子目录、共享预算、模型确认后补查及旧版本兼容；**本新版本真实验收仍待完成，不预填通过数。** 真实 CoT 为 Merrill／Sabharwal 的 arXiv 2310.07923v5，DavidFarago/state_tracking_llm_benchmark 只是引用相关基准、PromtEngineer/system1-vs-system2 为负例；不能凭搜索相关性确认为本论文官方实现。后续从固定原 PDF fresh 解析，独立保存新运行，并分别报告是否找到官方仓库、工具链是否完成和未解决原因。未执行论文仓库代码；人工 Gold、前端联调及实际复现实验仍单独验收。

## 2026-10-19 自动外部代码发现 1.3：真实验收与保留缺口

本节更新前述初版“待真实验收”状态，原六篇 2.3／Prompt 1.7、原轮失败与重试、自动发现 1.1／1.2 的原始运行分别保留。当前实现为 `code-checks-2.4-discovery-intake`、仓库 Prompt `credibility-external-code-1.10`、发现器 `code-discovery-1.3`／发现 Prompt `credibility-code-discovery-1.3`、供应商适配器 `deepseek-code-discovery-1.1`，pipeline `credibility-0.8-code-discovery`，默认合同 `credibility-0.5.0-draft`。原 `0.2-provisional-complete` 规则不改。

真实验证从固定原 PDF fresh 解析，不重算旧代码结论；使用真实 DeepSeek 原生 Search／Fetch 调用与后端 GitHub 读取。最新两篇均通过来源机器审计，但只有 CoT execution completed，不能称两篇全部执行完成：

| 样本 | 实际 Search／Fetch | 登记 URL／模型调用 | 关联结果与原代码试验分 | execution |
|---|---|---|---|---|
| CoT／paper_005，Merrill／Sabharwal 的 2310.07923v5 | 3／3 | 18／4 | 本次范围未确认官方实现，4 | completed |
| DataMIL／paper_037 | 2／4 | 8／7 | UT-Austin-RobIn/datamil 官方实现 verified，7 | partial：一项 Fetch 供应商 404 |

DataMIL 固定 SHA `f8fc4abccacd1e2b070e68128a7f2bce98f4b303`，实际抽读 `datamil/eval_libero_parallel.py` 与 `pyproject.toml`。三个原基线仓库均 rejected；本次真实覆盖“新发现候选→仓库语义确认→补查实现／两条新讨论→第二次语义”正向闭环。仓库阶段 completed（1 模型／0 工具），新增讨论阶段 completed（2 模型／0 工具，含一次预算内输出修复）；旧 garage 重复 README／datamil 文本预算错误未重现。共 23 次来源操作＝17 GitHub＋2 Search＋4 Fetch，27 个来源／84 个可达快照；4 个登记 URL 未读，保留未知，不断言无实现。官方 issue #3 为 failure_reported／relevant／open，条件只保留原帖 reported values、指标未命名；#2 数据集托管建议为 discussion_only／relevant／unknown。两条讨论均不计分，未执行论文代码。

发现公开摘要改为服务端实际查询／读取／候选计数，模型自由理由仅在审计中标记 `model_rationale_unverified`，不把未读页面的推测发布成事实。Prompt 1.10 优先使用已有固定版本 README，并保留未命名指标；有界修复仍经过原引文／范围／数字校验，原 4＋3 模型轮次、8＋6 工具、全流程40次来源预算不增加。供应商 Fetch 404 只证明该次读取失败，不是原站原始 HTTP／不存在证明。

本地全量回归 **1,706 passed**，Ruff 与来源审计通过。最终 summary、frozen implementation、artifact-audit.json、DataMIL 独立 proof review 保存在 `outputs/code-external-discovery-20261019/backend-discovery-v1_3/`；总报告与操作说明见该输出根目录和 `backend/docs/credibility/code-discovery.md`。CoT 未确认官方代码不等于全网无代码；人工 Gold、前端人工联调、非 GitHub 平台、依赖安装／实际运行及独立复现实验仍分别待办。

## 2026-10-19 同版本六篇回归与四篇新样本：测试完成，稳定性验收仍有缺口

按用户确认，仅执行代码专项及并行参照证据复核，未启动整篇三维／总分、API端到端或前端联调。当前 90 个运行相关文件冻结，十篇全部使用本节之前的 2.4／discovery-1.3／prompt-1.10，0.2 规则字节和评分映射不改。从原始固定 PDF fresh 解析，独立进程与全新目录，不读取旧代码结论或旧模型输出；新四篇使用纯解析 bootstrap 输入，不带数据组评分和仓库标签。

原六篇：LoRA／Tangent／GeoFAR 各 7 且 execution completed；DataMIL 7、CoT 4、Object-Centric v2 3，均保留 partial。新增四篇：Distributional Unlearning（045）7 completed；Ctrl-World（042）7 partial；Limits to Scalable Evaluation（047）4 partial；Fairness via Independence（043）3 partial。九篇实际调用 DeepSeek，共30个模型响应、12次Search、13次Fetch；045规则短路径已具实现证据，模型调用0，不冒称十篇逐篇实调。GitHub HTTP116、公开页HTTP2；来源操作137，与HTTP次数单位不同。

十篇不可变来源／引文／预算／评分机器审计均通过（196条外部引文，逐运行累计550个快照校验），不代表语义准确率或全部执行完成。本轮实际为4 completed／6 partial。独立复核定位以下待修项，未在本轮中途修改生产实现或结果：

1. **README入口的实现范围**：Object-Centric已搜索确认官方实现，但 `blob/submission/README.md` 的 `target_file` 限制令同SHA真实源码全部被排除。应对README文档入口按同ref父目录核查实现，保留显式源码文件及子目录边界。
2. **共享仓库讨论相关性**：Ctrl-World README同时支持Ctrl-World/VLAW，但共享ID记录为空；#23／#14没有唯一本文锚点却标 relevant。应保留 undetermined，不能断言实际属于另一篇；7分及不计分讨论规则不变。
3. **正文可读状态**：043 OpenReview Fetch实为浏览器验证页，source仍ok、discovery completed且缺少此原因。应区分供应商传输成功和正文可读，保留验证／登录等覆盖缺口，不伪造原站HTTP。
4. **模型输出与精确引用修复**：CoT先DSML文本后修复引文转义失真，严格validator拒绝。应减少引文手工重写并明确错误阶段，不能靠放松来源／引文校验通过。

较低优先还包括guard后理由文字一致、先归属后读取无关讨论以减少预算占用，以及审计器列表缺目标issue时失败关闭。LoRA实际仅8／15帖子、Ctrl-World仅8／13帖子进入模型语义审核，其余不冒充已核实。32条公共讨论全不计分，未执行论文仓库代码。

并行参照复核保存六篇13项候选标签，固定PDF及240个所选来源／父快照核验；数据组旧参照不覆盖。CoT适用性、正式人工标签／分数仍pending，材料标为agent证据复核、非人工Gold。Object-Centric v2另建参照，不迁移旧OpenReview3分。

交付位于工作区 `outputs/code-generalization-20261019/`：`report.md`给出逐篇结果及修复验收标准，`summary.json`／`results.csv`保存调用量与原结果，`audit-original-six.json`／`audit-holdout-four.json`为机器审计，`independent-review/`／`holdout-preparation/holdout-evidence-review.json`为独立证据审查，`reference-review/`为参照候选与人工待决项。下一步先修明确断点并对固定失败样本回归；本节不声明模块稳定性验收通过。

## 2026-10-19 partial 断点修复：代码专项 1.5／1.12

本轮按用户指定优先修 Object-Centric 和 CoT，继续采用原 `0.2-provisional-complete` 评分规则。Object 的 README blob 入口现按同一 ref 的父目录读取实现，保留显式 SHA／子目录／源码文件边界；CoT 的新发现输出只允许已经读取正文的 `source_id + span_id`，后端恢复精确原文，未读搜索候选不能借摘要补分类。原始输出、失败及修复尝试均保存，旧归档继续可审。

同时补上必要来源的阅读覆盖记录、共享仓库讨论的具体论文身份校验、先关联再审核讨论、恢复任务排除已拒绝依赖的讨论，以及唯一 issue/comment 原帖来源约束。HTTP 200 的验证页面与正文可读性分开记录；网页截断、真实失败及候选上限继续保留为覆盖缺口。DeepSeek 无效输出可在原轮次内最多重试一次，不执行截断／坏工具调用；安全原因码和失败 usage 留审计，所有请求尝试与 JSON／引文修复共用原预算。

最终实现为 pipeline `credibility-0.11-span-citations`、发现器／Prompt `1.5`、仓库语义 Prompt `1.12`、检查器 `code-checks-2.5-scope-evidence`。全量 **1838 项测试及 Ruff 通过**；Rubric JSON、item_scoring.py、scoring.py、rubric.py 与修复前字节一致。

最终专项使用相同十篇原始 PDF，逐篇重新解析和查询，结果保存在 `outputs/code-partial-fixes-20261019/runs-v3/`，冻结源码在 `implementation-v3/`。根目录 `report.md`／`summary.json`／`results.csv`、`audit-v3-*.json` 与 `review-v3/` 给出最终整批结果；`runs/`、`runs-final/` 及其原始失败仅作历史诊断，不选择历史成功结果替代最终批次。操作方式见 [code-usability.md](code-usability.md) 和 [code-discovery.md](code-discovery.md)。本轮只执行代码模块，用户暂缓的第三项没有实施，论文仓库代码仍为 `not_executed`。
