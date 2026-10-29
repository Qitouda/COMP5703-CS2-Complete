# 变更日志

## 未发布 — 模型适配清理

- Both report views show the score formula to two decimal places with an approximation sign;
  headline scores retain one decimal place. The recorded scores and categories are unchanged.
- Explain partial reference scores using their recorded item-average rules; reserve numerical fallback
  wording for explicit no-item fallback. Coverage flags remain separate from execution failure.

- Removed the retired provider UI branch and timing multiplier; models come from the backend.
- Three fresh GPT response fixtures replace the old fixtures without content changes; source paths and hashes are recorded in `docs/GPT_TEST_FIXTURES.md`.
- Score explanations distinguish unresolved evidence from execution failures and code availability caps.
- Historical entries below retain their original models and validation results.

## v1.5（未发布）

- 模型：后端新增 Claude 与 Gemini；前端只按后端列表展示，任何可用的真实模型都能发起核查。DeepSeek 由配置隐藏。
  输入卡底部改为显示所选模型的一句简介，不再重复模型名和评分规则版本。
- 开始页一屏放下：去掉与 History 重复的最近报告列表；等待页同样去掉。
- 三维与五维并行：等待页细分列表新增 "Quality" 一行（计入总进度 10%），完成即可 "View"。
  配对在发起的浏览器里记录；其他浏览器按同标题、10 分钟内先后发起自动识别（`src/app/pairing.ts`）。
- 报告页新增视图切换：Paper（原文与组件）/ Report（整份报告文档，含五维第二部分，左侧分组目录随滚动高亮）。
  打印版与 Report 视图共用 `documents.tsx`，五维第二部分另起一页。
- History 把同一篇论文的核查和五维合成一行。
- 同一次运行的两部分改为同级：运行页顶部显示 Credibility / Quality 两部分和各自状态
  （分数、进度、Failed、Not run），右端写模型和开始时间。Quality 标签内直接显示五维报告，失败可重试、没跑可发起；
  属于某次运行的 `/score/$id` 会跳到该运行的 Quality 标签。组件区去掉了五维组件，Report 视图只放可信度部分。
- 等待页去掉 "Continue in background"（标签页已保留运行）；下方新增醒目的五维卡片（说明、进度、完成后 "Read" 主按钮）
  和 "While you wait" 最近报告。
- History 改为一行一次运行：Paper、Model、Credibility、Quality、Started，两部分各自显示状态，五维失败可 "Retry"、
  没跑可 "Run"。配对改为一对一、按时间就近，同一篇论文的不同批次不再混在一起，失败的五维也归入它的运行。
- 标题栏标签显示所用模型的标志；同一篇论文的多个标签附开始时间。
- 导出：PDF 结尾新增 "Run details"（两部分各自的模型与版本号、开始与完成时间）；JSON 改为同一次运行的两份记录打包。
- Gemini 使用官方四角星标志。修复助手在开发服务器未加载代理时无法使用的问题，并在服务未运行时给出明确提示。
- 运行栏改为两个大号滑动开关：Credibility / Quality 与 Paper / Report（取代原来的部分标签和左侧竖排视图栏）。
  所有分段按钮都换成滑块式（选中项下面的白色滑块会滑过去）；只有可信度报告有两种读法，其他时候视图开关自动收起。
- 等待页的五维卡片不再画第二根进度条，改为带小饼图的 "Opens when ready · n%" 按钮，完成后变成阅读按钮；下方两块等宽。
- 手动停止：等待页 "Cancel assessment"（原地确认）。停止的运行记为 "Cancelled"，在页面和 History 里中性显示，可重试。
  后端新增 `POST /v1/credibility/assessments/{id}/cancel`。
- History 可删除一次运行（原地确认，先删五维再删可信度）；同时关闭它的标签、忘掉配对、删掉本地 PDF。
  后端新增两个 `DELETE` 接口，运行中的记录返回 409。
- 关闭当前查看的标签时跳到相邻标签（右边优先），不再回到第一个。
- 单项停止：等待页细分列表里运行中的检查可以单独停止（原地确认 "Stop check"），其余检查继续。被停止的一项如实记为
  "stopped by you"、得兜底分；报告的 Process record 写 "Stopped by the user"。后端新增 `…/checks/{check}/stop`。
- 运行栏与阅读器工具栏合并为一层：Paper 视图的翻页、缩放、搜索、高亮图层等放进开关之后；模型和开始时间移到状态栏。
- 五维卡片列出五个维度：运行中是带流光的空槽，完成后按分数填满。
- 修复：五维先完成、可信度还在跑时，History 把五维当成单独一行（"Credibility: Not run"），在那里删除后运行页一直卡在
  4% / 0%。现在运行中的运行在 History 有自己的一行（"Running · n%"，不能删除）；已不存在的五维会被自动忘掉，运行页显示 "Not run"。
- 配对改由服务端记录：发起五维时带上同一次运行的可信度核查 ID（`credibility_assessment_id`），任何浏览器都按它配对；
  本地记录和"同标题 10 分钟内"只用于旧记录。后端不认识该字段时自动退回只在本地记录。
- 帮助助手改版（参照 Ant Design X 与 Copilot，保持本系统风格）：欢迎区说明能做什么、不做什么；按页面分组的起步问题；
  回答前的 "Thinking"；每条回答可复制、评价有用 / 没用；输入区上方写明分享了什么，下方一行免责说明。
- 助手知识库维护：`guide.md` 保存即生效；`npm run assistant:check` 核对指南里引用的按钮名与界面是否一致；评价写入
  `assistant/feedback.jsonl` 供维护时查看。方法见 `assistant/README.md`。
- 帮助助手：右下角的对话窗，按操作指南回答使用问题，报告页附带当前报告摘要。后端为独立小服务
  `assistant/server.mjs`（Node，无依赖，SSE），开发时由 Vite 代理 `/assistant`。

## v1.4 — 2026-10-22

### UI 重建

- 新视觉：Outlook 蓝 + 偏蓝白底、Shippori Mincho / Zen Kaku Gothic New、6px 圆角、玻璃只用于浮层。
  规范写在 `docs/design/DESIGN_SYSTEM.zh-CN.md`，样式变量在 `src/styles/theme.css`（Tailwind v4 `@theme`）。
- 自有组件库 `src/ui/`：总分仪表（Apple 细弧样式）、三种小分（旋钮 / 温度管 / 光珠）、组件卡片、
  进度日志、上手清单、开关、分段控件；图标统一为 Fluent UI System Icons（MIT，嵌入代码）。
- 路由改为 TanStack Router，每份报告有自己的地址：`/`、`/check/$id`、`/reports`、`/score/$id`；
  旧的 `#check` / `#reports` 等地址自动跳转。轮询改为 TanStack Query（网络中断时退避重试）。
- 开始页 → 等待页 → 报告页之间用浏览器原生 View Transitions 做放大缩小；后台标签页和
  "减少动态效果"时不做动画。
- 等待页：进度日志逐行对应真实阶段；后端提供 `/progress` 时显示三项检查各自何时完成，
  否则按经验时长估计（最多到 90%，并标明 estimated）。
- 报告页改为阅读器：中间是 pdf.js 渲染的原文，证据按页码和原文定位高亮；左侧目录 / 缩略图 / Skills；
  右侧组件可折叠、拖动排序、移除和添加，另有组件导航栏；支持论文内搜索、复制引文、标记已看。
  上传的 PDF 存在浏览器的 IndexedDB 里（保留最近 12 份），刷新或从历史打开都能显示原文；
  这个浏览器没有副本时显示摘录列表，并可以选回同一个文件。
- 五维评分页 `/score/$id` 按新视觉重做（文档式单列）：小号总分仪表、五个维度的分带细条、优点与问题两栏、
  主张核对、贡献、可复现性、待解问题、局限；左侧章节目录随滚动高亮；证据点开在原处展开引文卡。
  进行中和失败状态与可信度核查同一样式。旧版报告组件和 1700 多行的旧全局样式（`index.css`）不再加载。
- 新增 404 页和页面出错兜底页；打不开的核查地址不再在标题栏留下 "Opening…" 标签。
- 总分仪表各部分改为按实际宽度等比缩放，任何尺寸下数字都不会压到弧上（五维页的小号仪表曾出现这个问题）。
- 窄屏修复：报告页在手机和竖屏平板上不再被工具栏或 PDF 页面撑出横向滚动，PDF 页宽跟随屏幕；
  标题栏标签在 900px 以下改为可横向滑动的标签条。
- 修复动画首帧可能显示 "-0.0" 的问题；流光遮罩改为已填充弧的准确形状（含两端圆头），光带对称渐变并按底色补偿亮度。
- 加载页改用测速表式的进度表盘（`src/ui/ProgressDial.tsx`）：整块 SVG 等比缩放，弧线填充加指针，
  数值只增不减；核查阶段按三项检查的通常耗时加权估计。
- 加载页一屏放得下：表盘显示总进度，三项检查改成紧凑的细分条；日志改为只显示最近 4 条大事件的滚动日志，
  按实际时间排序，未发生的步骤不显示。检查内部的小步（后端 `/progress` 按用途统计的模型调用）只出现在表盘下
  一行轮换的字幕里；剩余时间显示为区间（"About 5–10 min left"）。表盘和细分条上的流光改为柔和白光间歇流过已完成部分。
- 标题栏标签页：每个打开过的核查保留一个标签，切到别处也不丢；进行中的标签显示饼状进度、百分比和呼吸光圈，
  与等待页共用同一进度（只增不减）。等待页的"Continue in background"回到开始页，核查在标签里继续。取代原来的右上角小窗。
- 导出：标题栏 Export 菜单提供"Report (PDF)"（`/check/$id/print`，A4 排版：判决与分数推导、逐条主张及原文引文、
  未核实引用表、代码检索范围、问题汇总、局限说明，打开后自动弹出打印对话框，选"另存为 PDF"）和"Raw data (JSON)"。
- 分数动画在每次重新出现时重播：滚动回来、展开折叠的组件、切回浏览器标签页（总分仪表与三种小分）。
- 修复组件导航栏：点击底部组件后高亮停在该组件，直到用户自己滚动；滚到底时高亮最后一个组件。
- 文案改为学术口吻（例："Credibility assessment for machine learning papers"、"Scope of the assessment"、
  "Not supported in scope"）；引用未核实原因显示为可读说法（如"Source unavailable"），不再显示内部代码。
- 进度表盘的流光重写：原来是三段虚线叠加再模糊，看起来一颗一颗。现在是一条锥形渐变光带整体匀速旋转，
  两张静态遮罩把它限定在已填充的弧段内；动画只改 `transform`，由 GPU 合成。细分条的光带同样只移动 `transform`。
- 模型选择改为自有组件 `ModelPicker`：显示厂商标志（Claude / OpenAI / DeepSeek）和后端给的说明，支持键盘操作。
  列表仍只来自 `/v1/models`；后端列出但不可用的模型置灰并标 "Unavailable"。
- 去掉报告页的 Orientation（上手清单）组件；旧的组件布局存档里如有它会被自动忽略。
- 去掉冗余：判定组件的动画重放、上手清单的提示行、添加组件菜单的说明、报告页左侧与标题栏重复的导航栏、
  组件标题旁与导航栏重复的计数、没有高亮的 Code 图层开关、加载页重复的说明文字。
- 依赖：tailwindcss 4.3.3、@tanstack/react-router 1.170.41、@tanstack/react-query 5.104.1、
  pdfjs-dist 6.4.299、react-resizable-panels 4.14.3。npm 安装需加 `--legacy-peer-deps`（npm 的 peer 解析有 bug）。

## v1.3 — 2026-10-21

### 对接后端 v1.0 标准版（可信度合同 0.5）

- 可信度请求改为 `credibility-0.5.0-draft` + Rubric `0.2-provisional-complete`，后端给出试验分；
  `model_id` 取自 `/v1/models`。可信度接口只接受 OpenAI / DeepSeek 模型，Fixture 后端退回
  `not_called` 离线样例；没有可用模型时禁用提交并提示原因。
- 类型补齐 0.5 新字段：`coverage`、`execution`、`external_review`、`reference_verification_summary`、
  `code_discovery`、主张 `reconciled_from`、试验计分 `fallback_dimension_ids`。响应校验同步升版。
- 新增 `GET /v1/credibility/assessments` 历史接口的适配（HTTP 与 Mock）。
- 失败页按错误码显示标题，超出评估范围（`UNABLE_TO_ASSESS`）中性显示并带论文标题；补充
  `PAGE_LIMIT_EXCEEDED`、`ARXIV_NOT_FOUND`、`SERVICE_RESTARTED` 等新错误码的标题，五维共用。
- 测试夹具换成后端 v1.0 + DeepSeek 的真实响应（paper_002、paper_001）。
- 本机启动：内部测试用 `make run-deepseek`，演示用 `make run-openai`（GPT，需要 `OPENAI_API_KEY`）。

### 界面重置（D-029：可信度为主线）

- 栏目合并：两个独立顶栏合成一个，导航为 Credibility check / Paper scoring / Reports；
  `My reviews` 并入 Reports，同时列出可信度核查与五维评分，可筛选、搜索。
- 首页即可信度核查入口，下方展示本机已完成核查的例文报告（`GET /v1/credibility/assessments`）。
- 等待期内容：核查时可勾选同时做五维评分（约 1 分钟出结果），并可阅读例文；各栏目常驻，
  切换或阅读时核查继续轮询，顶栏胶囊显示进度。等待页标明耗时预期和 60% 停留说明。
- 报告新增 How this check ran：三条并行检查的耗时与状态、模型步骤、引用 agent 核实数、
  代码搜索轨迹与预算用量。
- 长时间核查的轮询遇到网络中断会退避重试（最多 5 次），永久错误时停下并提供 Resume polling。
- 手机端页边距统一为 16px；修复 Reports 搜索框在窄屏下被压扁。

## v1.2 — 2026-10-19

### 整合第二轮组员更新（只接功能，不改版）

- 合入 `feat/credibility-http`（Jin）：`/#credibility` 在 HTTP 模式下连接后端
  `/v1/credibility/assessments`，PDF 走 `/v1/uploads`；Mock 模式保留原型场景。
- 已在 `main` 的组员功能一并核对：GPT 模型可选、历史报告（My reviews）恢复、可信度 Mock 原型。
- 跟进后端参考文献核查（Task 2）：References 计数补上 Matched 与 Metadata conflict，
  参考文献结论按 matched / metadata_conflict 着色，计数行窄屏换行。
- 跟进后端代码与复现检查（Task 3，haichen，后端 `haichen-stage2` 分支）：仓库卡片显示 `owner/repo`
  并链接到 GitHub 页面、显示检查的 revision；讨论卡片补上相关性、解决状态、独立性和是否计分。
  新增 paper_001 真实响应夹具与对应测试。合同未变，后端未合入 main 时前端照常工作。
- 文档：README、联调指南、可信度说明改为“默认连真实后端”；本机启动改为与后端组一致的
  `make run-generic`（DeepSeek + 通用解析），Fixture 仅作无费用界面调试。

## v1.1 — 2026-09-13

### 新增落地页（范围变更）

- 四个功能页之前增加一个落地页：产品定位、五维 rubric 说明、四步流程，以及
  「明确不做什么」（不跑代码、不预测录用、不证明原创性、不替代同行评审）。
- 页面上的评分卡是写死的静态插图，不读接口；示例数字不会被误认为真实结果。
- 只新增一个 `hasEntered` 路由状态，不改字段合同、不新增接口调用。进行中或已完成
  的任务始终优先于落地页，轮询结果不会被挡住。
- 按 MVP 产品基线 §15 登记于 [docs/SCOPE_CHANGE_LANDING_PAGE.md](docs/SCOPE_CHANGE_LANDING_PAGE.md)，
  合并后需产品组同步回基线文档。

### 界面改版

- 重写设计系统（`src/index.css`）：暖底色纸面 + 单一墨色主色，衬线标题配无衬线正文，
  去掉侧边栏改为 56px 顶栏，报告页加左侧章节导航与滚动高亮。
- 分数改为页面主角：总分大号数字 + 十格刻度条 + 评级标签；五维各有分数、权重和进度条；
  另加一条五维速览带，色带由 `scoreBand()` 统一定义。
- 无法判断的维度显示 `—` 与排除原因，不再出现会被误读成 0 分的写法；临时报告横幅说明
  实际参与计算的维度数。
- 证据 chip 改为显示页码与定位（`Supports · p. 7 · Table 2`）；抽屉支持 `←` `→` 在同一
  判断的多条证据间切换，`Esc` 关闭，焦点回到触发元素。
- 输入页重做：arXiv 输入实时回显规范化后的 ID，示例 chip 一键填入，PDF 支持拖放与移除，
  Rubric/模型改为单选卡片，`⌘↵` 提交。
- 进度页改为竖向步骤条并显示已用时；错误页按错误码给出标题，可重试与不可重试的动作不同。
- 界面文案与 Mock 数据统一改为英文；后端返回文本原样展示。
- 每个视图都是独立页面而非同一页的分段，切换视图时回到顶部，不再继承上一页的滚动位置。
- 正文证据不再把后端的 chunk 锚点（`arxiv_2307.08122v3_chunk_0000`）当作定位显示，改用
  章节名。Mock 数据里正文证据的 `locator_label` 都是 null，这个问题只在接真实后端后
  才暴露。图表公式仍显示真实标签。

### 接口对齐（后端 94fa8d8）

- `src/utils/arxiv.ts` 按后端 `normalize_arxiv_id` 重写：支持 `arxiv:` 前缀、`abs/`
  与 `pdf/` 链接、`archive/YYMMnnn` 旧式 ID，并统一转小写；校验失败区分空值、非 arXiv
  域名和格式错误三种提示。
- 新增 `UNABLE_TO_ASSESS` 处理：机器学习门控拒绝的论文按“超出评估范围”中性呈现，显示
  已解析出的标题，不显示重试按钮。
- 补充错误码标题表，未知错误码回退到通用文案。

### 修复

- Vitest 未开启 `globals`，Testing Library 的自动 cleanup 从未注册，同一文件里第二次
  `render` 会叠加在第一次之上；在 `src/test/setup.ts` 显式注册 `afterEach(cleanup)`。
- 报告页顶部粘性条改用 `boundingClientRect.top` 判断方向，并用负 margin 移出文档流；
  之前在手机视口下一进页面就显示，且在顶部留出一条空白。

### 验证

- 17 项前端自动测试通过；`npm run lint` 与 `npm run build` 通过。
- 浏览器验证输入校验、完整报告、临时报告、不可重试错误、证据抽屉，以及 375px 视口。

## v1.0 — 2026-09-06

### 前后端 HTTP 联调

- 默认使用真实 HTTP 接口；显式配置后仍可使用 Mock，连接失败不回退模拟数据。
- 增加选项加载、PDF 两步上传、嵌套来源字段转换、任务查询与新建任务重试。
- 区分创建回执与完整 Assessment，校验响应版本及关键字段。
- 查询失败保留任务 ID，支持退避重试和手动恢复；避免旧响应覆盖新页面。
- 对齐模型/venue 快照类型，增加贡献列表、无可用模型提示和 PDF 基础校验。
- 配置本地 /v1 代理，更新环境示例、启动说明和联调验收记录。

### 验证

- 13 项前端自动测试通过；生产构建及静态检查通过。
- 浏览器验证 arXiv、合成 PDF、报告/证据、损坏文件提示、后端断开和恢复。

### 当前边界

HTTP 链路已连接；后端已新增仅限 `paper_001 / 2307.08122v3` 的 Benchmark + DeepSeek
真实模型闭环。通用论文获取与全文解析仍未完成，尚未部署公网。

### 本机真实样本复测说明

- 补充真实后端模式、固定 arXiv ID 和模型可用性检查。
- 记录空 API Key 导致模型下拉框为空的排查步骤。
- 记录 npm 全局缓存权限错误的临时缓存方案，并区分 Fixture 7.2 与真实试跑 7.6。
