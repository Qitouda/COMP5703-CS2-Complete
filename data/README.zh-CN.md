# CS-2 论文评分基础数据库

当前 R2C 开发先读：[项目文档总览](docs/project/README_项目文档总览.md)、[三个仓库的版本与交接说明](docs/DEVELOPMENT_HANDOFF.zh-CN.md)。本页下文的 50 篇与 AI 最终评分描述旧五维阶段库；新可信度案例另在 `data/credibility_cases/`，按新合同和复核规则维护。首例是开发候选预期，尚未完成正式双人 Gold。

> 当前 50 篇正式库已经完成：30 篇 ICLR 2024 校准集，加 15 篇 ICLR 2026、5 篇 ICLR 2025 时间测试集。完整说明见
> 后端接入、新论文统一结构化和图表交付见
> [`docs/backend_integration_and_visual_assets.zh-CN.md`](docs/backend_integration_and_visual_assets.zh-CN.md)。

这个仓库是数据组交给后端的 50 篇论文正式库。每篇论文都使用锁定版本的真实 PDF，已经完成来源核验、章节识别、正文分块、图表记录、AI 评分、SQL 导出和全量校验。当前发布状态以 `data/manifests/release.json` 为准。

这 50 篇是开发调试、输出对比和回归材料，不是产品运行时白名单。实际后端应接受任意有效 arXiv 链接/ID 或 PDF；不在 Manifest 中的论文也必须先解析自身内容，不能映射为这里的固定样本。

## 阶段库入口

1. `data/manifests/papers.csv`：50 篇论文总清单、年份、来源和数据集划分。
2. `data/parsed/paper_001/v3/`：一篇论文结构化后究竟长什么样。
3. `data/annotations/ai_trial/paper_001.json`：一份有证据定位的 AI 评分。
4. `sql/020_seed_all_structured_papers.sql`：后端可直接导入的 50 篇完整数据。
5. `docs/backend_integration_and_visual_assets.zh-CN.md`：后端处理新论文的完整接口说明。

## 仓库骨架

| 目录 | 用途 |
|---|---|
| `data/source_snapshots/` | 论文来源、版本、页数和 SHA-256 |
| `data/parsed/` | 章节、正文块、图表、链接和语义描述 |
| `data/annotations/ai_trial/` | 50 篇有证据定位的 AI 最终评分 |
| `data/quality_reports/` | 中文质量报告和验收结果 |
| `docs/` | 数据结构和工作流程规范 |
| `rubrics/v0.1/` | 当前评分维度、锚点和约束 |
| `scripts/` | 从 PDF 到 SQL 的可重复程序 |
| `sql/` | PostgreSQL 建表和种子数据 |

## 每篇论文的结构化文件

| 文件 | 后端如何使用 |
|---|---|
| `metadata.json` | 确认 PDF 版本、哈希、页数和解析质量 |
| `sections.json` | 构建论文目录和章节范围 |
| `chunks.jsonl` | 检索、向量化和发送给 AI 的正文块 |
| `elements.json` | 查询图、表、定理及其标题和页码 |
| `links.json` | 单独查询代码、数据、项目等 URL |
| `semantic_descriptors.json` | 按问题、贡献、主张、方法、评测、可靠性、局限路由证据 |
| `parse_report.json` | 判断该论文是否允许进入评分阶段 |

正文不会被塞进一个超长表格单元。每个正文块属于一个章节，保留顺序和页码，并且绝不跨章节。PDF 仍是最终事实来源，数据库保存的是可查询表示和 PDF 对象键。

## 50 篇当前结果与边界

| 规模 | 页数 | 章节 | 正文块 | 元素 | 五维评分 |
|---|---:|---:|---:|---:|---:|
| 50 篇合计 | 1,348 | 1,584 | 2,198 | 1,151 | 250 条维度评分 |

校准集 30 篇的标签平衡为 `high_consensus`、`mixed_or_borderline`、`substantial_concerns` 各 10 篇。新增 20 篇在评分前按年份与主题多样性选自 ICLR 官方 proceedings，作为时间测试集，不事后补质量标签。逐篇清单见 `data/quality_reports/fifty_paper_completion_report.zh-CN.md`。

按项目当前约定，AI 评分是本版本的最终评分，不再等待人工复核。全部 50 篇都有五维分数和可定位证据；每个适用维度同时记录支持与限制。评分不是录取预测，也不表示实验已经被复现。`docs/human_gold_protocol.zh-CN.md` 仅保留为以后若要研究人机一致性时的可选扩展。

## 重新运行

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
./run.sh
```

执行 `./run.sh` 只检查已经发布的 50 篇结构化结果和参考评分，不调用 AI，也不需要 API Key。`make pipeline` 和 `make resume` 只负责下载、校验和结构化；只有明确执行 `make score` 或增加 `--score` 时才进入可选的重新评分路径。后端通常不应重跑参考评分，而应使用自己的评分系统并用这 50 篇校准提示词。

后端处理一篇新 PDF 时使用 `scripts/structure_new_paper.py`，核心结构化方式与本库一致。详细参数、语义增强层和图表图片按需生成方式见后端整合说明。

## PostgreSQL 导入

先建立一个空数据库，再按顺序运行：

```bash
psql -v ON_ERROR_STOP=1 -d cs2pilot -f sql/001_initial_schema.sql
psql -v ON_ERROR_STOP=1 -d cs2pilot -f sql/020_seed_all_structured_papers.sql
```

导入后可用：

```sql
SELECT p.paper_id, p.title, a.overall_score
FROM papers p
JOIN paper_versions v USING (paper_id)
JOIN assessments a USING (paper_version_id)
ORDER BY p.paper_id;
```

当前完整 SQL 已在 PostgreSQL 兼容引擎中真实执行通过：50 篇论文、2,198 个正文块、1,151 个结构化元素、50 份评分及 250 条维度评分均成功载入。

## 数据安全

不要提交账号密码、API Key 或私人论文。公开 PDF 默认不上传 Git；生产环境应将 PDF 和图表截图放入对象存储，数据库只保存来源、哈希和对象键。
