# paper_002 首例真实 PDF 来源验证

2026-10-01（悉尼）。本次完成 BE-01 的真实 PDF 解析子步骤，验证入口为生产代码 `GenericPdfParser.parse_pdf`。没有调用模型、创建 API 任务或生成新可信度报告；新接口和前端联调仍待完成。

固定来源为 `2310.01798v1`，19 页。PDF SHA-256：`f204bfe2e642ab52abbf3fa94141e644d22a23510d6d64ed8ddc0ee9823eb983`。PDF 上传入口根据实际字节生成论文 ID `pdf_f204bfe2e642ab52`，本次证据 ID 使用这个运行来源，不沿用数据组 benchmark 的旧 ID。

## 本次结果

验证运行：`r2c-p002-source-20261001T055118Z`。`generic-pypdf-v2` 实际读取 39 个文本块和 14 个表图元素，17 个来源检查点全部通过。完整机器记录见 [verification.json](verification.json)。

| 对象 | 实际解析位置与内容 |
|---|---|
| 摘要子主张 | 第 1 页；`pdf_f204bfe2e642ab52_chunk_0001`；摘要字段非空，并保留无外部反馈的定义 |
| 表 3 | 第 5 页；`pdf_f204bfe2e642ab52_chunk_0013`；归属第 3.2 节，不再归到 GPT-4 假章节 |
| GPT-4／GSM8K | 初始 95.5%，第一轮 91.5%，第二轮 89.0%；调用次数 1、3、5；两轮下降 6.5 个百分点 |
| 实验条件 | 第 3 页历史模型访问日期与 200 题设定；第 5 页移除正确标签停止；上下文仍需联合查阅第 3～5 页 |
| 其他元素回归 | Table 6 第 19 页，Figure 2 第 6 页，Figure 7 第 18 页；正文提前提及不抢占实际 caption 页 |

来源探针从表头、模型行组和方法行核对实际数字，不通过全文中出现某个数字就判通过。它只验证本案例的可读来源，不是通用表格读取器或主张判定器，也不把候选 `supported` 当作新模型输出。

## 修复与检查

原解析器的 PDF-only 标题只取第一行；摘要边界不识别小型大写间隔；同页多个章节按页归属；表格模型名被误作标题；元素使用第一次正文提及页。修复后按页内标题分段，跨页继承章节，识别明确 caption，保留原始正文。

新增 6 项黑盒回归，覆盖同页章节、小型大写、多行题名、附录、表格词与 caption 位置。来源验证当时的后端全套 **131 项测试通过**；本次改动的 Ruff 检查通过。交接整理另补模型兼容性回归后，全套 **140 项测试通过**，Ruff 检查通过。测试有两条既有 FastAPI／Starlette 弃用提示，不影响本次通过结果。

表格仍以原始文本保留，未恢复通用列结构和可靠 table cells；返回 `parse_quality=partial`、`TABLE_STRUCTURE_UNVERIFIED`。多栏阅读顺序、只保留首行的 caption、点号 caption 与段首提及的歧义仍是 generic 解析器限制。后续模型判断须核对行列与条件；无法读取必要证据时应保留技术缺口。

## 复跑

在 backend 根目录运行，使用同 SHA-256 的 PDF；下方路径对应当前三仓库工作区。

```sh
.venv/bin/python scripts/verify_paper_002_source.py \
  --pdf ../../tmp/pdfs/r2c-paper_002-v1/2310.01798v1.pdf \
  --case-record ../data/data/credibility_cases/paper_002/v1/claim_001.review.json \
  --output-dir docs/testing/2026-10-01-r2c-paper002-source
```

输入字节不匹配固定版本时直接拒绝；必要表头、模型行组或数字行不可读时验证失败。复跑会更新该目录的当前产物和运行时间，请在需要保留不同运行时指定新的输出目录。

## 交接物与下一步

- [parsed_document.json](parsed_document.json)：生产序列化形状的来源快照。
- [anchored_text.txt](anchored_text.txt)：真实文本块与页码锚。
- [element_catalog.txt](element_catalog.txt)：表图所在页及 caption。
- [来源探针](../../../scripts/verify_paper_002_source.py)：复跑入口。

接下来是 BE-02：以本次真实证据实现新主张核查接口，核对 schema、执行范围与空分状态，再进入前端回查。此验证包不批准人工 Gold，不表示旧评分已完成真实模型回归；代码与验证包纳入 `r2c-sync-2026-10-01` 固定交接标签；原验证 JSON 保留当时的 HEAD，解析实现另以 `parser_source_sha256` 固定。团队取码与待合并 PR 见数据仓库 `docs/DEVELOPMENT_HANDOFF.zh-CN.md`。
