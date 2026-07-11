"""服务层（业务逻辑）：被 routers 调用，不碰 HTTP / JSON 响应格式。

阶段一：数据来自 YAML seed 文件（经 data_loader 加载到内存 registry）。
后续接 SQLite / LLM 时只改这里：data_loader 可由 seed.py 调用把数据灌进 DB，
services 改为查 DB。
"""
