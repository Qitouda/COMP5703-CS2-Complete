# 协作约定

## 分支

- `main`：始终可运行、测试全绿
- `feat/be-0X-<简述>`：按任务号开分支，例如 `feat/be-02-deepseek-client`
- 合并走 Pull Request，至少一人 review

## 提交信息

```
<类型>(<任务号>): <一句话>

feat(BE-03): 增加证据悬空引用校验
fix(BE-05): 空返回时不再直接判失败
docs: 补充 anchor 格式说明
test(BE-03): 覆盖不足三个维度的总分规则
```

## 三条不要

1. 不要绕过 `app/schemas/` 手拼 dict 返回给前端——契约校验就是靠它。
2. 不要在 `app/validation/` 之外自己算 `overall_score`。
3. 不要提交 `.env`、API key、论文 PDF 或任何用户上传内容。

## 跨组接口变更

字段、枚举、状态语义的任何改动都要先更新 Unified Field Contract 并升版本，
再同步前端与数据处理组。群聊里的口头约定不算数（契约 §26）。

## 本地检查

```bash
make lint
make test
```
