# 2026-10-01 开发版本与交接说明

2026-10-01，用户已授权将交接改动合入三个仓库的 main。日常开发直接拉取 main，可取得最新文档、候选样本、历史报告功能和可信度前端原型。原交接分支 chore/r2c-sync-2026-10-01 与固定标签 r2c-sync-2026-10-01 保留用于追溯；标签仍是原快照，不包含之后的文档更新和前端原型。

| 仓库 | 当前开发入口 | 已合并 PR／合并提交 |
|---|---|---|
| data | [main](https://github.com/eden-eden-new/cs2-paper-benchmark/tree/main) | [#1](https://github.com/eden-eden-new/cs2-paper-benchmark/pull/1)，5d596bd；之后的取码说明修订见当前 HEAD |
| backend | [main](https://github.com/kanekogaido/cs2-capstone--backend/tree/main) | [#1](https://github.com/kanekogaido/cs2-capstone--backend/pull/1)，fab6300；合并后 CI 通过 |
| frontend | [main](https://github.com/Qitouda/COMP5703-CS2-Frontend/tree/main) | [#2](https://github.com/Qitouda/COMP5703-CS2-Frontend/pull/2)，82bc195；[#3](https://github.com/Qitouda/COMP5703-CS2-Frontend/pull/3)，af529ca；55 项测试、lint/build 通过 |

可信度页面是独立 Mock 原型，旧五维 HTTP 流程保留。后端新核查 Agent/API、独立案例复核及真实集成验收仍待完成。

## 原固定交接快照

| 仓库 | 固定交接入口 | 提交／基线 | 本次内容 |
|---|---|---|---|
| backend | [交接标签](https://github.com/kanekogaido/cs2-capstone--backend/tree/r2c-sync-2026-10-01) | `1ae578b9ad12697838f6fbc039101fcef012f2cb` | 历史报告快照和列表、模型配置与旧模型兼容、generic-pypdf-v2、首例来源验证及回归 |
| frontend | [交接标签](https://github.com/Qitouda/COMP5703-CS2-Frontend/tree/r2c-sync-2026-10-01) | `54cc58a6ca4c97bea9a915e1952843ab9995c891` | My reviews 搜索／排序／分页／恢复、禁选不可用模型、取消过期请求和回归 |
| data | [交接标签](https://github.com/eden-eden-new/cs2-paper-benchmark/tree/r2c-sync-2026-10-01) | 数据基线 `ae990db`，本次提交由标签确定 | 保留远端 50 篇阶段库，补首例核查记录和项目文档快照 |

## 开始开发前

在每个仓库先运行 `git status --short`，确认当前工作已保存，再更新 main：

```sh
git fetch origin --prune --tags
git switch main
git pull --ff-only
git log -1 --oneline
```

开发自己的改动从更新后的 main 另开分支。只有需要复现原交接快照时才从固定标签开始：

```sh
git switch -c your-work-branch main
# Reproduce the original handoff only:
# git switch --detach r2c-sync-2026-10-01
```

本次标签固定后不移动；后续进展通过新提交和 PR 维护，已合并改动在 main 取得。复现时同时记录三个仓库的 `git rev-parse HEAD`，后端还记录 `/health` 的实际 parser、schema、model、prompt 和 rubric 配置。标签固定代码与文档，不包含本地 `.env`；本地密钥与运行数据各自配置。

标签之后的文档更新：本分支已同步展示、引用提醒、重试及汇总口径；主张范围以 D-041 为准，已回退摘要／引言关键主张，D-038 全文范围已被取代。最低有效分与总体不封顶保留，见[决策记录](project/03_过程与交付/决策记录.md)。`handoff-2026-10-01.json` 的文档哈希对应所在 Git 提交的 `docs/project/`；复现原交接快照使用固定标签，读取这些后续决定则使用最新 main 或记录的具体提交。产品行为已确认，数值校准、实际实现与验收仍待执行。

## 需求与文件入口

先读[项目文档总览](project/README_项目文档总览.md)，再按组查看任务。`docs/project/` 按原来的五分区保存项目资料，`99_历史归档` 保留历史目标。旧 ZIP、目录外备份、系统缓存和含成员学号的课程 DOCX 不入 Git；原受控副本保留原位置。

共享 Drive 文件仍用于原位阅读与协作；Git main 保存当前文档，固定标签保存原交接快照。文档变更同步现有文件，沿用原文件名及五分区；不另建“最新版”。执行人、日期和任务状态只在[任务主表](project/03_过程与交付/第二轮_交付任务清单.md)维护。

- 新需求：[可信度合同 v0.1](project/01_统一规范/可信度核查报告字段合同_v0.1.md)、[Rubric v0.1](project/03_过程与交付/数据样本与%20Rubric/可信度核查_Rubric_v0.1.md)，均为评审草稿。
- 首例：[样本记录](project/03_过程与交付/数据样本与%20Rubric/第二轮_可信度核查样本与复评记录.md)、[数据交接 JSON](../data/credibility_cases/paper_002/v1/claim_001.review.json)、[后端来源验证包](https://github.com/kanekogaido/cs2-capstone--backend/blob/r2c-sync-2026-10-01/docs/testing/2026-10-01-r2c-paper002-source/README.zh-CN.md)。
- 首批样本（D-042）：按旧分辅助选择 P002／P004／P030／P005 四篇，见同一份样本记录及[机器可读候选包](../data/credibility_cases/pilot_v0.1.selection.json)。P030 原 PDF 当前受阻，其问题预期还待原表复核；四篇均非正式 Gold，完整范围和真实验收待补。此包位于标签之后的分支提交。
- 后端已实现接口仍为旧五维 `/v1/assessments`。前端 main 含独立三维 Mock 原型及 draft 类型，见[原型说明](https://github.com/Qitouda/COMP5703-CS2-Frontend/blob/main/docs/CREDIBILITY_PROTOTYPE.md)；新主张 Agent、真实三维报告和 `/v1/credibility-assessments` 尚未实现。
- 50 篇阶段库及其 AI 最终评分政策仅用于旧五维流程；新可信度首例 `is_gold=false`，Bocheng 的 U01 是 AI 辅助确认，正式独立双人复核未完成。
- 首例只检查一个子主张，`scope_complete=false`，维度／总分／类别均留空；引用与代码检查未运行。

## 本次检查与复跑边界

- 后端：140 项 pytest 通过；app、tests、scripts 的 Ruff 通过。
- 前端：22 项 Vitest 通过；lint、TypeScript 和 Vite build 通过。
- 数据：50 条 manifest／source record 检查通过；50 篇结构化数据全量跨文件检查无错误或警告。
- 首例：原来源运行 `r2c-p002-source-20261001T055118Z` 的 17／17 检查通过，pypdf 6.17.0，解析源 SHA-256 固定；没有新 Agent/API 或付费模型评测。

PDF 不入 Git。复跑首例先下载 [2310.01798v1](https://arxiv.org/pdf/2310.01798v1)，核对 SHA-256 `f204bfe2e642ab52abbf3fa94141e644d22a23510d6d64ed8ddc0ee9823eb983`，再按后端验证包的脚本传入实际 PDF 路径。原解析快照保留不变；本次新 parser 仍标记表格 `partial`，不保证通用单元格、OCR 或所有多栏版式正确。
