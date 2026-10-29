# PostgreSQL 数据库说明

## 应该使用哪两个文件

1. `001_initial_schema.sql`：创建所有数据表、外键、约束和索引。
2. `020_seed_all_structured_papers.sql`：导入 30 篇论文的结构化数据及当前评分状态。

`002_seed_paper_001.sql` 仅用于单篇演示；`010_seed_papers.sql` 是早期仅含清单的兼容文件。完整数据库不要再把三个种子文件一起运行，以免理解混乱。

## 导入命令

```bash
createdb cs2pilot
psql -v ON_ERROR_STOP=1 -d cs2pilot -f sql/001_initial_schema.sql
psql -v ON_ERROR_STOP=1 -d cs2pilot -f sql/020_seed_all_structured_papers.sql
```

在 pgAdmin 中，先连接 PostgreSQL，创建数据库 `cs2pilot`；然后打开 Query Tool，依次载入并执行上面两个文件。

## 完整种子包含

| 表 | 行数 |
|---|---:|
| papers / paper_versions | 30 / 30 |
| paper_sections | 908 |
| paper_text_chunks | 1,274 |
| paper_elements | 741 |
| assessments / dimension_assessments | 30 / 150 |
| dataset_releases / benchmark_memberships | 1 / 30 |

种子脚本使用事务和 `ON CONFLICT DO NOTHING`。它已在隔离 PostgreSQL 引擎中从空库真实执行成功，并通过外键和检查约束。

## 常用查询

查看 30 篇及其真实生命周期状态（推荐后端首先使用）：

```sql
SELECT p.paper_id, p.title, m.annotation_status, a.overall_score
FROM benchmark_memberships m
JOIN paper_versions v USING (paper_version_id)
JOIN papers p USING (paper_id)
LEFT JOIN assessments a ON a.assessment_id = m.ai_assessment_id
ORDER BY p.paper_id;
```

只有 `annotation_status = 'ai_provisional'` 才表示已关联暂定 AI 初评；`parsed` 表示结构化已完成、真实模型评分仍待运行。

查看仓库内全部评分记录（包括明确标记为 draft 的模板）：

```sql
SELECT p.paper_id, p.title, a.overall_score, a.overall_rating
FROM papers p
JOIN paper_versions v USING (paper_id)
JOIN assessments a USING (paper_version_id)
ORDER BY p.paper_id;
```

查看某篇章节与正文块：

```sql
SELECT s.sequence_index, s.section_number, s.title,
       count(c.chunk_id) AS chunk_count
FROM paper_sections s
LEFT JOIN paper_text_chunks c USING (section_id)
WHERE s.paper_version_id = 'paper_001_v3'
GROUP BY s.section_id
ORDER BY s.sequence_index;
```

查看一个评分维度及其证据：

```sql
SELECT d.dimension_id, d.score, l.stance, e.page_number,
       e.section_title, e.excerpt
FROM dimension_assessments d
JOIN assessment_evidence_links l USING (dimension_assessment_id)
JOIN evidence_references e USING (evidence_id)
WHERE d.assessment_id = 'assessment_ai_paper_001_v3'
ORDER BY d.dimension_id, l.stance;
```
