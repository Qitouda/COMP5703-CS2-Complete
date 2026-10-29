# 项目与数据规范文档

当前团队需求与排期见[项目文档总览](project/README_项目文档总览.md)，开发版本见[交接说明](DEVELOPMENT_HANDOFF.zh-CN.md)。以下文档解释现有数据结构和旧五维阶段库，不替代新 R2C 合同或 Rubric。

建议阅读顺序：

1. `第二轮_可信度核查接入与运行说明.md`：已经落地的代码、真实证据链、SQL 顺序和后端运行方式。
2. `第二轮_50篇AI可信度核查结果说明.md`：50 篇试验性 AI 核查统计、空分原因和整库 SQL。
3. `第二轮_可信度核查实施大纲与组员指引.md`：第二轮信度核查的完整实施顺序、数据结构、SQL 表设计和跨组交接。
4. `backend_integration_and_visual_assets.zh-CN.md`：后端导入、处理新论文、调用自有 AI 与图表交付。
5. `workflow.md`：数据组与后端组的责任边界和处理流程。
6. `data_sources.md`：arXiv、OpenReview和其他数据源的使用范围。
7. `data_dictionary.md`：论文清单字段及枚举含义。
8. `paper_structuring_spec.md`：如何把PDF转换成章节、正文块、图表和语义描述。
9. `automation_pipeline.zh-CN.md`：批量下载、结构化和可选重新评分入口。

这些文档描述数据应该是什么样。自动下载、PDF解析、在线任务和数据库写入程序由后端实现，数据组负责提出要求并检查结果。
