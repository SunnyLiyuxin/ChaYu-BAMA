# CLAUDE.md

本文件用于 Claude Code 在本仓库中协作开发时快速理解**工程边界与协作约束**。
项目设计、数据约定、API 契约、fallback 规则等细节不在本文件重复——读对应权威文档。

## 必读文档（按需阅读，各司其职）

| 文档 | 职责 | 何时读 |
|---|---|---|
| [README.md](./README.md) | 项目入口、本地复现、文档索引 | 新进仓库 |
| [docs/系统架构.md](./docs/系统架构.md) | 赛题理解、设计依据（why） | 需理解设计动机时 |
| [docs/技术架构.md](./docs/技术架构.md) | 四层架构、数据流、技术栈、数据策略、追溯机制（how） | 改后端结构/数据/规则前 |
| [docs/接口文档.md](./docs/接口文档.md) | API 契约、字段定义、P0/P1/P2、fallback 接口 | 改任何 API / 联调前 |

指针速查（详见对应文档）：
- 四层架构 / 总体设计 → `docs/技术架构.md §2 / §3`
- 技术栈 → `§4`；数据策略（seed / SQLite / 证据字段 / 规则数据）→ `§6`
- LLM 调用边界与降级 → `§9`；fallback 设计 → `§10`；API 分层 → `§11`；可追溯机制 → `§12`
- API 字段 / 请求响应 / 优先级 / fallback 接口 → `docs/接口文档.md`（§6.2 生图、§7 追溯、§8 fallback、§10 优先级）
- 赛题理解 / 风味轮研究 / 跨文化类比依据 → `docs/系统架构.md`

**接口字段变更必须同步更新 `docs/接口文档.md`。**

## 项目状态

可运行后端 Demo，项目名未定。主路径与当前进度见 README「文档」与下「实现进度」；四层架构、数据流、生图、降级、fallback 等设计细节见技术架构 / 接口文档，本文件不重复。未开放能力返回 fallback；不默认扩展到多茶品 / 其他市场 / 其他受众 / 真实视频。

## 协作约束（代码不可推断的红线，必守）

- **不要引入未确定项目名。**
- **不要把代理数据写成八马单品实测数据。**（成分代理数据须标注为"公开文献代理数据"，见技术架构 §3.1 / §14.1）
- **不要手动维护 SQLite `.db`。**（`data/tea.db` 由 `seed.py --reset` 从 YAML 灌表，被 gitignore）
- **不要把缓存结果提交到 Git。**（`.db` / 生图 URL 缓存均不入库）
- **不要把所有规则硬编码进 Python 或超长 prompt。**（规则结构化存 `backend/data/seeds/generation_rules.yaml`，按任务/市场/受众/术语筛选后注入，见技术架构 §6.4）
- **不要随意修改 API 字段。**（改了须同步 `docs/接口文档.md`）
- **不要接真实视频 API。**（`video-asset` 等保持 P2 fallback）
- 保持实现范围围绕主路径，其他能力用 fallback 预留。

## 密钥约定

- LLM / API key 只在 `backend/.env`（gitignored），**绝不**进被跟踪文件或 Docker 镜像。
- `backend/.env` 原则上不得由助手读取。
- `health-llm` 调试接口不输出明文 key，`base_url` 仅回显 scheme + host。
- 生图凭证独立走 `IMAGE_*`（指向火山方舟 Ark），与 `LLM_*` 相互独立、不回退——ARK key 需在控制台开通模型并关闭"安全体验模式"推理限额，否则 429。

## 实现进度

已完成：FastAPI 路由 / SQLAlchemy models（13 表）/ `seed.py --reset` / 读路径切库 / LLM service + Prompt + JSON 校验 / 真实生图（豆包 Seedream）/ output_store 缓存 / pytest 覆盖 / Dockerfile + compose。

后续优先顺序：

1. ~~搭建 FastAPI 项目结构。~~ ✅
2. ~~建 SQLAlchemy models，`seed.py --reset` 从 YAML 生成 SQLite。~~ ✅
3. ~~内存查询替换为数据库查询。~~ ✅（读路径已切库）
4. ~~接入 LLM service、Prompt 模板和输出 JSON 校验。~~ ✅
5. ~~接入真实生图。~~ ✅（图源后已切豆包 Seedream 并修复出图质量，见下第 6、7 项）
6. ~~修生图出图质量——清商务信号词 + style 风格维度 + scene 镜头维度，seed 退化为纯画面物体。~~ ✅
7. ~~图源切豆包 Seedream + 图内渲染中文知识文字。~~ ✅（详见接口文档 §6.2）
8. 增加测试覆盖与前端联调。（测试覆盖已完成，前端联调待办）
9. 按部署环境收紧 CORS、文档入口和密钥配置。

> fresh clone 后须先跑 `python scripts/seed.py --reset` 灌表，否则启动打印警告、读路径返回空 / 404。未灌表不 crash、不自动灌。
