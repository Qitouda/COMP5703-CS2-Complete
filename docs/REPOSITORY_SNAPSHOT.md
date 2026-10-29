# 三仓库合并与整理记录

日期：2026-10-30（Australia/Sydney）。GitHub 仓库为 `Qitouda/COMP5703-CS2-Complete`，可见性为私有。

## 内容来源

| 组件 | 原仓库 | 合并时的分支 | 原 HEAD |
| --- | --- | --- | --- |
| backend | `kanekogaido/cs2-capstone--backend` | `chore/gpt-provider-cleanup` | `e1270f4715c364724aec59b0828384d62e23253f` |
| frontend | `Qitouda/COMP5703-CS2-Frontend` | `chore/gpt-provider-cleanup` | `2225005f6fcbe120bf7e72db3db76688a8e2a263` |
| data | `eden-eden-new/cs2-paper-benchmark` | `test` | `232ff65bff93db88c8bd252265ba9981c4c601c7` |

合并复制当前磁盘上的已跟踪文件和未忽略的新源码，包含后端尚未提交的通用解析、引用提取及对应回归测试。没有只复制原 HEAD，也没有把三个目录作为 Git submodule。新仓库建立独立的提交历史；原仓库、分支及注册工作副本保留原位，原提交历史继续在原仓库中查询。各子项目文档里保留的旧标签、原仓库链接与历史证据路径仍表示原项目来源。

[SOURCE_SNAPSHOT.json](SOURCE_SNAPSHOT.json) 记录每个组件的来源版本、工作区变更列表以及每个纳入文件的 SHA-256，便于核对合并范围。原 `backend/.github/workflows/ci.yml` 已由根目录的三个组件检查任务替代。

## 配置同步

- 后端 `.env.example` 与当前运行的非密钥设置同步：`LLM_TIMEOUT_SECONDS=300`、`CREDIBILITY_WORKERS=1`、generic 解析、Claude/Gemini SSE、Gemini Flash-Lite/minimal/headroom 0。
- 从原实验运行目录迁入 `backend/scripts/serve_local.py` 与 `relay_capacity.py`，并发容量为 1，超时后冷却 150 秒；去除私人绝对路径及过时的端点断言。
- 数据库、上传、缓存、Crossref 状态及 SSE 审计路径改为新仓库内的相对路径。真实 Key、联系邮箱、旧数据库和原 `.env` 保留本机，不进入版本管理。
- 独立数据评分流程保留自己的模型配置。前端单次 HTTP 等待仍为 30 秒，长任务通过轮询获取结果。
- 修正旧 README 对 fixture 启动模式的描述；测试显式隔离本机启用开关、传输和 Gemini 配置，避免私有 `.env` 干扰回归。
- 安装检查发现 5 个前端依赖包受已知安全问题影响，已在原有依赖版本范围内更新锁文件；`package.json` 保持不变。Vite 为 `8.3.5`、Vitest 为 `4.1.12`、source-map-js 为 `1.2.2`、undici 为 `7.30.1`，并同步必要的依赖更新。

完整值、端点、timeout 含义和旧数据迁移见[运行配置](../backend/docs/RUNTIME_CONFIGURATION.md)。

## 清理范围

原三个仓库共删除 335 个缓存、系统临时文件和旧构建文件，约 10.56 MiB；路径及大小见 [LOCAL_CLEANUP.json](LOCAL_CLEANUP.json)。未发现需要删除的重复已跟踪源码或文档，数据、SQL、测试 fixtures 与项目说明均保留。

新仓库排除各组件的 Git 内部目录、`.env`、数据库、运行证据、依赖和构建输出。原本机运行存储、`.venv`、`node_modules` 继续保留用于现有开发环境；新仓库内安装的依赖和验证构建同样由 `.gitignore` 排除。

报告、PPT、整个 `outputs/` / `tmp/` 工作区、人工测试交接包不属于本次三仓库合并范围；仅将运行必需的两个脚本从实验目录迁入后端。

## 验证

在合并后的目录中执行：

| 检查 | 结果 |
| --- | --- |
| 后端完整 pytest | 2,377 passed，1 skipped |
| 后端 Ruff，包括迁入的启动与容量脚本 | 通过 |
| `.env.example` 配置预检 | 通过；300 秒等待、150 秒冷却、worker/容量均为 1 |
| 前端 Vitest | 106 passed |
| 前端 lint / build / assistant:check | 通过 |
| 前端依赖 npm audit | 0 vulnerabilities |
| 数据 unittest | 49 passed |
| 50 篇 manifest 和完整数据校验 | 0 errors，0 warnings |

跳过项为 Graphon 的真实 PDF 回归，该 PDF 位于本次范围外的人工交接包。对应合成回归已通过。验证不调用付费模型；新机器需自行配置有效凭据后进行真实模型核查。
