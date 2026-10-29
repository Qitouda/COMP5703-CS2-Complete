# BE-07 六篇样本的不可变选样来源

`task3-haichen-sun.source.md` 保存原 2026-10-17 任务三交接原文，不在本归档追加状态。其 SHA256 仍为 `5def1e801d8ad9e18dcd69ec928301e761a4e0f993f8e72339d45395574fe0e7`，与选样时 hash、Git HEAD 和后续追加前原文字节完全相同。当前操作文档仍为上两级的 `task3-haichen-sun.md`，允许维护。

`acceptance-samples.original.json` 保留迁移前完整清单和原 `selection_sha256`，仅用于历史追溯；其旧路径指向可编辑交接文档，不能作为当前运行入口。当前入口仍为 `docs/credibility/acceptance-samples.json`，只将 paper_001 的一项来源路径迁到本归档，来源 hash、摘录、样本事实、人工预期、类别和非 Gold 标识均未变。

路径变化会改变清单规范 JSON 的摘要，因此当前清单重新计算了外层 `selection_sha256`；这不刷新来源 hash，也不将改后的说明文档替换为原冻结证据。`provenance-relocation.json` 记录前后清单摘要、迁移路径和原来源 hash。既有历史运行记录保持原清单身份。
