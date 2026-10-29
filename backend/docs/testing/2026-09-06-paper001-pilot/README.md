> 历史记录，DeepSeek 已停用。以下保留当时的配置、结果和待办；当前操作见 README。

# paper_001 首次受限试跑记录

日期：2026-09-06  
分支：`v1.0`

## 目标

验证后端是否能在不实现通用 PDF/arXiv 解析的前提下，只对
`2307.08122v3` 加载数据组 `paper_001/v3`，并将真实结构化正文送入现有模型流程。

## 配置

- Parser：`benchmark`
- Benchmark arXiv：`2307.08122v3`
- Benchmark 数据：`data/data/parsed/paper_001/v3`
- LLM：`deepseek-v4-flash`
- Schema：`0.4`
- Rubric：`0.1-draft`
- Prompt：`analysis-v0.1`

未记录 API Key、授权头、完整 Prompt 或原始论文 PDF。

## 结果

### 解析与 API

使用 Fixture 模型时任务完成，后端返回：

- `paper_id`：`paper_001`
- 标题：`Tangent Transformers for Composition, Privacy and Removal`
- 作者：Tian Yu Liu、Aditya Golatkar、Stefano Soatto
- 页数：18
- arXiv：`2307.08122v3`

提交其他 arXiv ID 会产生 `BENCHMARK_SOURCE_MISMATCH`；Benchmark 模式不接受 PDF，避免将其他输入错误映射为 `paper_001`。

### DeepSeek 尝试一

- assessment ID：`asmt_d5ab033349f1`
- 三次请求均为 HTTP 200，但最终 `content` 为空
- 原因：当前 DeepSeek 默认启用思考模式，8,000 个生成 token 未留下最终 JSON
- 处理：在 JSON 报告模式中显式设置 `thinking.type=disabled`

### DeepSeek 尝试二

- assessment ID：`asmt_1f8d5357cb9a`
- DeepSeek 成功返回非空内容
- 初始输出包含 8 个阻塞性结构问题
- 执行两轮 repair 后仍有 110 个校验问题
- 最终状态：`failed / finalizing_report`
- 错误：`MODEL_OUTPUT_INVALID`

失败被后端正确拦截，没有向前端返回不符合字段合同的报告。本次结果证明真实论文已进入模型通路，但不能证明模型分析功能已经完成。

## 自动验证

- 后端测试：88 项通过
- Ruff：通过
- 两项第三方弃用警告，不影响本次功能

自动测试固定使用 Fixture/Stub，不会读取本机真实模型配置或产生 API 费用。

## 下一阻塞项

`build_analysis_prompt()` 尚未包含数据组完整评分指南和 Assessment v0.4 的精确输出模板。下一步应先补齐 Rubric、字段结构和示例，再重新进行一次显式真实模型试跑；不应靠增加 repair 次数掩盖 Prompt 合同缺失。
