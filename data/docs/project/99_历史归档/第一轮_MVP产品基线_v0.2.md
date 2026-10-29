# 第一轮归档：MVP 产品基线 v0.2——基于证据的论文尽职调查评分卡

本文件保存第一轮已锁定的评分卡基线。第二次 client 会议后的当前产品方向见 [MVP 产品基线](../00_项目总览/MVP产品基线.md)。本页原有决定、字段和范围仅作历史追溯，不再作为第二轮新增功能的范围依据。

## 0. 文档信息

| 字段 | 内容 |
|---|---|
| 项目 | CS-2 Research Due Diligence |
| 文档版本 | v0.2 |
| 状态 | PM 已锁定为团队三周原型基线；client 未确认事项继续待确认 |
| 产品负责人 / 总负责人 | 曾博成 |
| 技术负责人 | 尚未单独指定；由曾博成负责跨组协调 |
| 原型周期 | 3 周；具体起止日期待排期确认 |
| 生效日期 | 2026-08-25 |
| 下次复审 | 下一次 client meeting 后 |

## 1. 背景

研究人员面对大量计算机科学和机器学习论文时，很难在短时间内判断一篇论文是否值得继续精读、引用或作为后续研究的基础。仅阅读标题和摘要可能遗漏方法、实验和论证中的关键问题，而完整专家审阅需要较高时间和专业成本。

本项目第一阶段不尝试复现论文代码，也不尝试替代正式同行评审。MVP 通过公开的 ICLR 审稿逻辑，对论文进行结构化、可追溯的价值初筛。

## 2. 产品定位

### 2.1 一句话定义

本项目参考 CSPaper，构建一个带评分和论文内证据定位的尽职调查工具。系统接收 arXiv 链接或 PDF，从研究价值、证据充分性、原创性、清晰度和可复现透明度等维度评估论文，并帮助读者判断是否值得进一步阅读、引用或使用；MVP 不运行代码复现实验。

### 2.2 产品性质

- 产品类型：Evidence-backed paper due diligence scorecard
- 初始 venue：ICLR
- 初始 rubric：ICLR-inspired due diligence rubric
- 初始论文范围：英文机器学习论文
- 输出性质：包含 1–10 分维度评分、Overall Score、证据和不确定性的阅读决策支持；不是正式 peer review 或录用预测

### 2.3 核心用户价值

帮助用户更快回答：

1. 这篇论文解决了什么问题？
2. 作者声称的贡献是什么？
3. 主要 claim 是否得到论文内证据支持？
4. 工作是否提供了值得关注的新知识或研究价值？
5. 阅读或依赖这篇论文前，需要注意哪些主要问题？

## 3. 术语约定

项目内部不使用“垃圾论文检测”作为正式表述。对应的产品概念为：

| 非正式表述 | 产品与学术表述 |
|---|---|
| 论文是不是垃圾 | Research value assessment / paper screening |
| 靠不靠谱 | Soundness and evidence support |
| 有没有意义 | Significance / value to the community |
| 是不是旧东西包装 | Originality and literature positioning |
| 写得看不懂 | Clarity |
| 最好的结果 | State of the Art（SOTA） |

## 4. 目标用户与主要场景

### 4.1 当前主要场景

需要快速理解和初筛公开机器学习论文的研究者、学生或技术人员，希望在投入大量阅读时间前获得结构化参考。

### 4.2 当前不作最终确认的次要场景

作者在正式投稿前使用系统检查论文。该场景与主要场景共享分析能力，但报告语言、隐私要求和成功标准可能不同，须经 client 确认后再决定是否作为 MVP 主场景。

## 5. MVP 输入

### 5.1 必须支持

- 有效的 arXiv 论文链接或 arXiv ID。
- 用户上传的 PDF 文件。

### 5.2 基本处理要求

- 提取标题、作者、摘要等基础元数据；匿名稿件缺失作者时不得报错。
- 提取正文、章节和页码信息。
- 解析失败时明确返回失败原因或不确定状态，不生成伪造内容。
- PDF 文件默认按私有输入处理，不默认公开原文或报告。

## 6. MVP 分析 Rubric

### 6.1 Research Value and Significance

- 论文试图解决什么具体问题？
- 研究动机是否清楚？
- 作者是否解释现有方法或知识的不足？
- 工作是否提供新的、相关的或可能有影响的知识？
- 研究者或实践者是否可能使用、引用或继续研究该结果？
- 即使没有达到 SOTA，是否仍提供新问题、新见解、负面结果、数据或分析价值？

### 6.2 Soundness and Evidence

- 论文主要 claim 是什么？
- 方法、理论或实验是否为主要 claim 提供支持？
- baseline、实验设计和比较是否基本合理？
- 是否存在明显 overclaim 或证据不足？

MVP 只评估论文内论证和内部一致性，不声称证明数学推导绝对正确，也不运行代码验证实验。

### 6.3 Originality and Positioning

- 作者声称的原创贡献是什么？
- 论文是否清楚解释与引用文献的区别？
- 新意来自新方法、新问题、新数据、新发现，还是有意义的组合？

MVP 不进行穷尽式文献检索，因此只能判断论文对自身原创性的陈述是否清晰、合理，不能证明“世界上从未有人做过”。

### 6.4 Clarity and Usability

- 论文是否清楚说明问题、方法、实验和结论？
- 结构是否便于理解？
- 关键术语、图表和结论是否基本一致？

### 6.5 Reproducibility and Transparency

- 论文是否提供代码、数据、随机种子、超参数、硬件/运行环境和预处理信息？
- 对每项信息区分 Available、Not Available、Unable to Verify 和 Not Applicable。
- 缺少代码不自动等于论文低价值；系统需要结合论文类型和主要 claim 解释。

MVP 只检查论文内提供的复现信息，不运行代码或复现实验。完整字段、评分和证据规则见 [统一字段合同 v0.4](../01_统一规范/旧五维评分字段合同_v0.4.md)。

## 7. SOTA 声称的处理方式

MVP 不设置独立的 SOTA 专项模块或评分。若论文作者明确或隐含声称达到 SOTA、最佳已报告结果或同类最高性能，该声称与其他主要研究 claim 一样进入 `claim_checks`，检查论文内部证据对它的支持程度。

核查时可以在论文实际提供信息的范围内关注：

- 对应任务、数据集和评价指标。
- 主要比较对象和 baseline。
- 改进幅度。
- 比较条件是否从论文信息来看基本一致。
- 是否提供方差、重复实验或统计证据。
- 论文是否清楚说明比较限制。

系统不得使用以下规则：

```text
达到 SOTA = 好论文
没有达到 SOTA = 低价值论文
```

MVP 不检索外部榜单，不承诺作者的结果确实是全球真实、最新的 SOTA。没有 SOTA 声称时不生成任何占位对象。

## 8. MVP 输出报告

每份报告至少包含：

1. Paper Summary
2. Claimed Contributions and Claim Checks
3. Research Value and Significance Assessment
4. Soundness and Evidence Support Assessment
5. Originality and Positioning Assessment
6. Clarity and Usability Assessment
7. Reproducibility and Transparency Assessment and Checklist
8. Main Strengths
9. Main Concerns
10. Unresolved Questions
11. Overall Score, Overall Assessment and Reading Recommendation
12. Model Confidence and Limitations
13. Evidence References

### 8.1 证据要求

重要判断应尽可能包含：

- 判断理由。
- 论文原文片段或准确概述。
- 页码或章节。
- 判断置信度。
- 无法判断时的原因。

### 8.2 评估表达

MVP 不输出录用概率。每个维度采用 1–10 分并同时展示等级：

- 9–10：Strong
- 7–8：Good
- 5–6：Adequate
- 1–4：Weak
- `null`：Uncertain 或 Not Applicable

Overall Score 第一版按五个维度等权计算。阅读建议使用 Worth Deep Reading、Worth Reading With Checks、Selective Reading、Insufficient Evidence 或 Unable to Assess。完整计算、空值和证据规则见 [统一字段合同 v0.4](../01_统一规范/旧五维评分字段合同_v0.4.md)。

## 9. 明确不属于 MVP

- 实际运行代码或复现实验。
- GitHub 仓库健康度和代码质量分析。
- PubPeer、社区舆情或全网讨论聚合。
- 引用撤稿数据库检查。
- 穷尽式 related-work 或 prior-art 检索。
- 独立 SOTA 专项评分、外部榜单核验或全球最新 SOTA 认定。
- 学术不端、造假或抄袭判定。
- 数学证明的完整自动验证。
- ICLR accept/reject 或录用概率预测。
- 支持全部会议、期刊和全部计算机学科。
- 多 venue 选择界面。
- 账号、付费和复杂权限系统。
- 默认公开用户上传的 PDF 或分析报告。

上述内容可以进入 future backlog，但不得在未执行范围变更流程的情况下加入 MVP。

## 10. MVP 用户流程

```text
用户选择 arXiv 或 PDF
→ 系统获取并解析论文
→ 显示分析进度与错误状态
→ 根据 ICLR-inspired rubric 生成结构化评估
→ 对重要判断绑定页码、章节和证据
→ 用户查看报告与系统局限
```

## 11. 验证方案

### 11.1 数据来源

仅使用公开材料：

- 公开 ICLR / OpenReview 论文。
- 公开 reviewer comments。
- 公开 meta-review 和最终决定（可获得时）。
- ICLR 官方 reviewer guidelines。

不主动索取或使用 client 的未公开论文。

### 11.2 样本组成

目标验证集约 30–50 篇，尽量包含：

- 高度一致认可的论文。
- 因 soundness 或 significance 问题受到一致质疑的论文。
- reviewer 分歧较大的 borderline 论文。
- 没有 SOTA、但因新见解或重要分析获得积极评价的论文。

接受或拒绝结果不能单独作为“论文是否有价值”的真值标签。

### 11.3 初步验证问题

- 系统是否正确概括研究问题和核心贡献？
- 是否识别人工 reviewer 提出的主要 strengths？
- 是否识别人工 reviewer 提出的主要 weaknesses？
- 是否生成论文中不存在的事实或引用？
- 是否为主要判断提供可检查的证据？
- 是否错误地把“没有 SOTA”解释为没有价值？

## 12. MVP 验收标准

### 12.1 功能验收

- 用户可以提交有效 arXiv 链接或 PDF。
- 系统能够返回完整报告或明确的失败状态。
- 报告覆盖五个核心 rubric 维度。
- 作者提出 SOTA 声称时，将其作为普通 `claim_check` 检查；不生成独立 SOTA 模块。
- 报告展示 strengths、concerns、overall assessment 和 confidence。
- 关键结论能够链接到页码、章节或论文证据。

### 12.2 质量验收

- 不生成不存在的论文标题、作者、实验结果或引用。
- 无法确定的信息显示 Uncertain，而不是猜测。
- 不声称系统是官方 ICLR reviewer。
- 不输出确定性的 accept/reject 结论。
- 使用公开样本完成记录清晰的人工对比验证。

### 12.3 交付验收

- 可运行的前端和后端。
- 可演示的端到端流程。
- 基本部署环境。
- 源代码和技术文档。
- 测试与验证结果。

## 13. 风险与约束

| 风险 | 初步处理原则 |
|---|---|
| PDF 解析错误 | 显示失败或 Uncertain，保留解析日志 |
| LLM hallucination | 结构化输出、证据绑定、事实检查 |
| Rubric 主观性 | 使用公开 ICLR 标准并展示置信度 |
| 不同论文类型标准不同 | MVP 限定英文机器学习论文，并允许 Not Applicable |
| SOTA 比较不可比 | 作为普通 claim 检查论文内支持情况，不设置专项评分或全球验证 |
| 评分被误解为录用预测 | 不输出录用概率，突出 decision-support 定位 |
| 上传 PDF 涉及隐私 | 默认私有、限制存储、后续确认数据保留策略 |

## 14. 待 client 确认

以下内容不得在确认前写成客户要求：

1. 主要用户是论文读者，还是投稿前作者？
2. 第一版只针对 ICLR 是否符合预期？
3. 是否明确使用 ICLR 2027 作为 rubric 版本？
4. 评分权重和阅读建议是否需要在 client 反馈后调整？
5. 报告是否需要导出或通过链接分享？
6. 对单篇论文可接受的处理时间和模型成本是多少？
7. PDF 与分析结果应保留多久？
8. Client 认为 MVP 成功的最重要三个标准是什么？

## 15. 范围变更流程

任何新增范围必须记录：

```text
变更内容：
用户价值：
提出人：
影响模块：
时间与成本影响：
替换或延后的现有工作：
决定人：
决定日期：
```

如果没有说明“替换或延后的现有工作”，新增需求默认进入 future backlog，不加入 MVP。

## 16. 版本历史

| 版本 | 日期 | 变更 | 状态 |
|---|---|---|---|
| v0.1 | 2026-08-21 | 建立 ICLR-first MVP 工作基线 | Working draft |
| v0.1 | 2026-08-24 | PM 批准为三周原型的团队锁定基线；不改变 client 待确认项 | Team Locked / Client Pending |
| v0.2 | 2026-08-25 | 锁定参考 CSPaper 的证据型尽调评分卡定位、五维 1–10 分评分、可复现透明度检查、venue/model 选择和统一字段合同 | Team Locked / Technical Review Pending |

## 17. 参考来源

- ICLR 2027 Reviewer Guidelines: https://iclr.cc/Conferences/2027/ReviewerGuidelines
- ICLR 2027 Author Guidelines: https://iclr.cc/Conferences/2027/AuthorGuidelines
- ICLR 2027 Call for Papers: https://iclr.cc/Conferences/2027/CallForPapers
- ICLR 2027 AI Policy for Authors: https://iclr.cc/Conferences/2027/AIPolicyForAuthors
- CSPaper Agentic Review reference: https://cspaper.org/agents

引用这些来源不代表本项目获得 ICLR、OpenReview 或 CSPaper 的认可或授权。
