> 历史记录，DeepSeek 已停用。以下保留当时的配置、结果和待办；当前操作见 README。

# 第二轮开发计划：通用机器学习论文流程

> 历史计划，保留 2026-09-10 当时的目标、基线与未完成项。本文的 R2-BE 编号、Prompt 和 TODO 不代表当前状态。当前方向已变更为 R2C Paper Credibility Check，请从[现行文档](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/r2c-sync-2026-10-01/docs/project/README_%E9%A1%B9%E7%9B%AE%E6%96%87%E6%A1%A3%E6%80%BB%E8%A7%88.md)和[版本交接](https://github.com/eden-eden-new/cs2-paper-benchmark/blob/r2c-sync-2026-10-01/docs/DEVELOPMENT_HANDOFF.zh-CN.md)开始。

计划日期：2026-09-10。第一轮已经结束；本轮从 `v1.0` 的单篇真实闭环继续开发，不推倒现有前后端接口、报告 schema、校验与 DeepSeek 调用。

## 本轮目标

系统用户可以提交任意有效 arXiv 链接、arXiv ID 或 PDF。后端使用当前输入的真实内容完成解析：

- 能可靠识别为机器学习论文时，使用现有五维 Rubric 生成完整 Assessment；
- 非机器学习内容、非论文 PDF、正文不足或无法可靠解析时，不生成分数，返回“无法得出评估结果”及简短原因。

数据组 Manifest 中的 30 篇论文只用于调试、对比和回归，不是运行时白名单。运行时不得把未知输入映射到 `paper_001` 或其他固定样本。

## 当前基线

- 前端默认使用真实 HTTP API，已支持 arXiv、PDF 上传、任务轮询、报告和错误页面。
- 后端已支持上传校验、私有保存、任务生命周期、DeepSeek、Prompt `analysis-v0.2`、报告校验、证据降级和总分重算。
- `BenchmarkParser` 当前仍只接受 `paper_001 / 2307.08122v3`。
- `GrobidParser` 的任意 PDF/arXiv 实现仍是 TODO。
- 后端 Prompt 当前内置 Rubric 摘要，尚未从数据组版本化 Rubric 动态加载。

## 实施顺序

### R2-BE-01：通用 arXiv 获取

- 归一化 arXiv ID、abs 链接和 pdf 链接，并保留显式版本号。
- 下载实际 PDF，检查响应、大小和 PDF 有效性。
- 将下载失败和无效输入映射为现有结构化错误。

退出条件：一篇不在数据组 Manifest 中的有效 arXiv 论文能够进入通用解析器。

### R2-BE-02：通用 PDF 解析

- 实现 `GrobidParser` 或一个输出相同 `ParsedDocument` 的等价解析器。
- arXiv 下载 PDF 和用户上传 PDF 使用同一解析、anchor 和证据索引逻辑。
- 删除生产路径对固定 `BENCHMARK_PARSED_DIR`、`BENCHMARK_SOURCE_RECORD` 和 `BENCHMARK_ARXIV_ID` 的依赖；可保留旧 Benchmark 模式作为显式回归工具。
- 解析失败时不调用评分模型，不生成 Fixture 报告。

退出条件：任意有效 PDF 可产生当前后端可消费的 metadata、sections、blocks 和可选 elements/links，或者返回明确失败。

### R2-BE-03：最小 ML 相关性判断

- 在论文解析完成、模型评分之前判断正文是否属于英文机器学习研究论文。
- 只有能够从标题、摘要或正文确认机器学习问题、方法或实验时才进入评分。
- 无法确认时采用保守结果：不评分，返回 `failed + error`；用户文案为“无法得出评估结果：该文档无法确认为机器学习领域论文。”
- 不建立其他领域分类体系，也不为其他领域设计 Rubric。

退出条件：机器学习论文进入评分；明显无关 PDF 不消耗评分调用且不返回数字分数。

### R2-BE-04：版本化 Rubric 加载

- 从可配置路径加载数据组 `rubrics/<version>/`，而不是只依赖 `app/llm/prompts.py` 中的手写摘要。
- 启动时校验 Rubric 文件及版本；任务记录实际 `rubric_version` 和 `prompt_version`。
- 保留后端负责的 JSON 结构说明、产品边界和证据定位规则。

退出条件：更换 Rubric 版本不需要复制修改业务 Prompt，历史任务仍能追踪实际版本。

### R2-BE-05：功能回归与联调

- 使用数据组多篇现有论文检查解析形状和证据定位，不比较分数是否接近人工结果。
- 加入至少一篇 Manifest 外机器学习 arXiv、一份 Manifest 外机器学习 PDF 和一份无关 PDF。
- 与前端验证 arXiv 完成、PDF 完成、无法评估三条路径。

退出条件：输入内容不同则 paper metadata、正文 anchor 和证据随之变化，不再出现固定 `paper_001` 结果。

## 最小接口约定

沿用《统一字段合同 v0.4》，不新增任务状态：

- 成功评分：`status: completed`、`stage: report_ready`，返回完整 `report`；
- 无法评估：`status: failed`、`report: null`，返回可直接展示的 `error.message`；
- 可增加统一错误码 `UNABLE_TO_ASSESS`，原有 PDF 损坏、加密、下载失败等精确错误码继续保留。

前端继续直接展示后端 `error.message`，不得在 HTTP 失败或无法评估时回退 Mock/Fixture。

## 本轮不做

- 不评分机器学习以外的论文。
- 不以人工 Gold、未见测试集或专家级准确率作为本轮完成门槛。
- 不执行论文代码，不验证外部 SOTA，不预测录用结果。
- 不扩展多 Venue、账号、付费、复杂权限或公网生产部署。

## 验收清单

- [ ] Manifest 内 ML arXiv 论文通过通用路径完成，不读取固定结果。
- [ ] Manifest 外 ML arXiv 论文通过通用路径完成。
- [ ] Manifest 外 ML PDF 通过通用路径完成。
- [ ] 无关或非 ML PDF 不产生分数，返回无法评估。
- [ ] 损坏、加密或空正文 PDF 不产生伪造报告。
- [ ] 生产路径不存在 `paper_001` 白名单。
- [ ] 报告证据能够回查当前输入的 chunk、页码或元素。
- [ ] 模型、Prompt、Rubric 和解析器版本均有记录。
- [ ] 前后端自动测试、启动手册和实际运行模式一致。
