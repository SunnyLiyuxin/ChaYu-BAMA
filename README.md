# 中国茶 AI 表达 Demo

面向飞书 AI 创赛的 Demo 原型：用结构化茶品知识、风味坐标和表达规则，生成面向国内消费者与海外受众的茶文化表达与营销物料数据。

当前主路径：

```text
1 款茶（铁观音）× 图片物料 ×（国内链 + 跨文化链）
```

项目状态、四层架构、数据约定、API 优先级、fallback 规则等设计细节见下「文档」各篇，README 不重复。

## 本地复现

环境要求：`Python 3.11+`

```bash
cd backend
pip install -r requirements.txt
python scripts/seed.py --reset   # 灌表（fresh clone 必跑一次，生成 data/tea.db）
uvicorn app.main:app --reload
```

启动后访问：

```text
http://localhost:8000/docs      # Swagger，可直接调试接口
http://localhost:8000/api/demo-routes
```

运行测试：

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -v
```

## Docker 复现

环境要求：Docker Desktop / Docker Engine + Docker Compose。

```bash
docker compose up -d --build backend     # 镜像构建时自动跑 seed.py --reset 灌表
docker compose logs -f backend
docker compose down
```

启动后访问 `http://localhost:8000/docs`。

> Windows 上若报 `failed to connect to the docker API ... dockerDesktopLinuxEngine`，先打开 Docker Desktop 等其 Linux Engine 运行完成再执行 compose。

## 文档

| 文档 | 职责 |
|---|---|
| [docs/系统架构.md](./docs/系统架构.md) | 赛题理解与设计依据（why） |
| [docs/技术架构.md](./docs/技术架构.md) | 技术架构、数据流、实现原则（how） |
| [docs/接口文档.md](./docs/接口文档.md) | 前后端 API 协作基准（契约） |
| [docs/赛题录屏.txt](./docs/赛题录屏.txt) | 赛题原始素材（参考） |

当前限制：真实视频生成、前端服务、生产鉴权与安全配置尚未接入；CORS 为 Demo 联调期放开，上线前需收紧。其余能力边界见接口文档 §8 / §10。

## License

NO LICENSE。除团队内部协作和赛事提交用途外，未经团队明确许可，不默认授权复制、分发、修改或商业使用。
