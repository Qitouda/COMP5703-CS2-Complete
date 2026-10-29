"""论文解析层。

- base.py      解析结果的形状（chunk / element / link）与证据回查用的 SourceIndex
- anchors.py   送进模型的位置 anchor 约定，格式 [p1-2|<chunk_id>]
- benchmark.py 读数据处理组 cs2-paper-benchmark 的解析产物
- grobid.py    真实解析实现（TODO，BE-01）
"""
