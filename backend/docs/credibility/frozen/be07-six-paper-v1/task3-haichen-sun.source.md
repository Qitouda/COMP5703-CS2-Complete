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
