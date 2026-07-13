# 中国茶 AI 表达 Demo

本项目是一个面向飞书 AI 创赛的 Demo 原型，用结构化茶品知识、风味坐标和表达规则，生成面向国内消费者与海外受众的茶文化表达和营销物料数据。

当前 Demo 聚焦一条可复现主路径：

```text
铁观音 × 图片物料 ×（国内链 + 跨文化链）
```

后端已实现 P0 Demo 接口。数据源头是 `backend/data/seeds/*.yaml` 静态 seed；运行时读路径查 `backend/data/tea.db`（由 `seed.py --reset` 灌表），写路径经 `output_store` 查/写 `generated_outputs` 表作 LLM 输出缓存。三个文本生成接口（国内表达 / 跨文化表达 / 营销物料）已接入 LLM（基于 OpenAI 兼容 SDK，默认指向 GLM，可经 `.env` 切换），未配置 LLM key 或调用失败时透明退回 seed 预置表达（mock 兜底）。真实生图已接入（`POST /api/image/generate`，智谱 CogView-4，与 `marketing-asset` 两步联调），未配置 / 失败走 fallback（生图无 seed 兜底）；视频生成仍走 fallback。

**注意（生图效果待修）**：CogView-4 生图链路已通（`quality=hd` + 关闭水印 + 确定性 prompt 富化），但当前 `marketing-asset.image_prompt` 文案偏"海报排版"描述、画面物体（茶具 / 茶汤 / 道具 / 场景）描述不足，出图质量未达预期。后续大概率调整 seed `image_prompt` 文案为画面物体描述，而非改生图逻辑。

## 当前能力

已支持的主要接口：

```http
GET  /api/demo-routes
GET  /api/teas
GET  /api/teas/{tea_id}/knowledge
GET  /api/teas/{tea_id}/flavor-profile
GET  /api/teas/{tea_id}/component-flavor
POST /api/teas/{tea_id}/domestic-expression
POST /api/teas/{tea_id}/cross-cultural-expression
POST /api/teas/{tea_id}/marketing-asset
POST /api/image/generate
GET  /api/trace/{output_id}
GET  /api/markets
GET  /api/audience-references
GET  /api/fallback
POST /api/fallback
POST /api/natural-expression
GET  /api/health-llm        # 调试：确认 LLM 是否接上
```

暂未开放的功能会返回统一 fallback JSON，避免前端白屏或默认 404。

## 目录说明

```text
backend/
  app/                 FastAPI 后端代码
  data/seeds/          当前 Demo 的 YAML seed 数据（数据源头）
  scripts/seed.py      从 YAML 灌表到 SQLite（运行前置步骤）
  tests/               pytest 测试套件
  requirements.txt     运行时 Python 依赖
  requirements-dev.txt 开发/测试依赖（pytest、httpx）
  Dockerfile           后端容器镜像定义
docker-compose.yml     本地 Docker Compose 配置
docs/
  接口文档.md           前后端接口约定
  技术架构.md           系统设计说明
```

## 本地复现

环境要求：

```text
Python 3.11+
```

安装依赖并启动后端：

```bash
cd backend
pip install -r requirements.txt
python scripts/seed.py --reset   # 灌表（fresh clone 必跑一次，生成 data/tea.db）
uvicorn app.main:app --reload
```

运行测试：

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -v
```

启动后访问：

```text
http://localhost:8000/docs
http://localhost:8000/health
http://localhost:8000/api/demo-routes
```

`/docs` 是 FastAPI 自动生成的 Swagger UI，可直接调试接口。

## Docker 复现

环境要求：

```text
Docker Desktop 或 Docker Engine
Docker Compose
```

在项目根目录运行：

```bash
docker compose up --build backend
```

镜像构建时会自动跑 `python scripts/seed.py --reset` 灌表，容器内 `data/tea.db` 自带，无需宿主机预灌。

后台运行：

```bash
docker compose up -d --build backend
```

查看日志：

```bash
docker compose logs -f backend
```

停止服务：

```bash
docker compose down
```

启动后访问：

```text
http://localhost:8000/docs
http://localhost:8000/health
```

如果 Windows 上出现 `failed to connect to the docker API ... dockerDesktopLinuxEngine`，说明 Docker Desktop 的 Linux Engine 尚未启动。先打开 Docker Desktop，等待其运行完成后再执行 compose 命令。

## 当前限制

当前版本用于 Demo 联调，尚未接入：

```text
真实视频生成 API
前端服务容器
生产环境鉴权与安全配置
```

真实生图（CogView-4）已接入 `POST /api/image/generate`，但出图质量未达预期、待修（详见上「注意（生图效果待修）」）。

SQLite 持久化已接入（读路径查 `data/tea.db`、写路径缓存 `generated_outputs` 表）；`data/tea.db` 由 `seed.py --reset` 生成、被 gitignore，不手动维护。

LLM 已接入但可选：未在 `backend/.env` 配置 `LLM_API_KEY` / `LLM_BASE_URL` 时，三个文本生成接口自动走 seed 兜底，行为与未接 LLM 时一致。生图凭证独立走 `IMAGE_*`（同一 `backend/.env`，与 `LLM_*` 相互独立），未配置时生图接口走 fallback。

## 文档

- [docs/接口文档.md](./docs/接口文档.md)：接口字段和前后端协作基准
- [docs/技术架构.md](./docs/技术架构.md)：系统架构、数据流和后续扩展说明

## License

NO LICENSE

当前仓库未声明开源许可证。除团队内部协作和赛事提交用途外，未经团队明确许可，不默认授权复制、分发、修改或商业使用。
