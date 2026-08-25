# AwardIE-AgentFlow

基于大模型的信息抽取（IE）与多智能体协作的奖状智能管理系统

## 系统简介

本系统是 AwardIE-AgentFlow——基于大模型的信息抽取（IE）与 Agent 工作流系统，用于管理学生竞赛活动、奖状记录以及相关统计信息。核心能力包括：

- **OCR + LLM 智能抽取**：奖状图片经百度 OCR 转文本、LLM 结构化抽取，自动归入获奖/创新/证书等记录
- **RAG 知识库问答**：竞赛规则/政策文档向量化入库（ChromaDB），支撑 AI 助手精准问答
- **多智能体协作审核**：LangGraph Supervisor 模式多智能体，对成果提交进行流式审核
- **管理端控制台**：数据总览看板 + 54 个管理页面统一控制台化，含日志系统（trace_id 全链路追踪）

### 技术栈

Flask 3 + SQLite(WAL) + LangGraph 多智能体编排 + ChromaDB RAG + 百度 OCR / PaddleOCR + Alembic 迁移 + Tailwind（前端样式）

## 快速开始

### 1. 准备 Python 环境

Python 3.11。建议将虚拟环境放在**英文路径**下——项目本体位于中文路径，部分库（如 ollama）对中文路径敏感。

### 2. 安装依赖

```bash
# 本机 / 无 GPU：CPU 版依赖
pip install -r requirements-cpu.txt

# RAG 向量检索依赖（requirements-cpu.txt 未包含，需单独补装）
pip install chromadb langchain-chroma langchain-text-splitters

# 如有 GPU（CUDA 12.6）：GPU 完整版
pip install -r requirements.txt
```

> 注意：本机有常驻代理时，pip 安装请先清空 `HTTP_PROXY`/`HTTPS_PROXY` 等环境变量（见 [`docs/运维指南/`](docs/运维指南/)）。

### 3. 配置 .env

```bash
cp .env.example .env   # 填入 OCR / LLM / Embedding 密钥
```

`.env` 中**百度 OCR 密钥为必备项**（`BAIDU_API_KEY` / `BAIDU_SECRET_KEY`），缺失时提交流程不可用；LLM 与 SiliconFlow Embedding 密钥按需配置。修改 `.env` 后**必须重启应用**才生效。

### 4. 启动系统

```bash
python run.py
```

系统启动后访问：`http://127.0.0.1:5001`（默认端口 5001，可用环境变量 `PORT=xxxx` 修改）。

## 登录方法

### 管理员登录

- **用户名**：`admin`
- **密码**：`Mayy123`
- **登录后**：进入管理员仪表板，可访问所有管理功能（奖状、竞赛、人员、活动管理等）

### 教师登录

- **用户名**：工号（例如：`02110606`）
- **密码**：`P@ss301`（默认密码）
- **登录后**：进入教师仪表板，可查看自己的指导成果

### 学生登录

- **用户名**：学号（例如：`212306413`）
- **密码**：`P@ss301`（默认密码）
- **登录后**：进入学生仪表板，可查看自己的获奖记录
- **首次登录**：使用默认密码首次登录后，系统会强制要求修改密码

## 账号说明

1. **管理员账号**：独立存储在 `admins` 表中，默认 `admin` / `Mayy123`
2. **教师账号**：使用工号作为用户名登录，默认密码 `P@ss301`，管理员可在教师编辑页面重置密码
3. **学生账号**：使用学号作为用户名登录，默认密码 `P@ss301`，首次登录后需修改密码，管理员可在学生编辑页面重置密码

## 测试

### 运行测试套件

```bash
# 运行全部测试
python -m pytest tests/ -v

# 按目录分层运行（unit / integration / security / extract / ocr / flask_api 等）
python -m pytest tests/unit/ -v

# 生成 HTML 报告
python -m pytest tests/ --html=tests/reports/report.html --self-contained-html
```

### ⚠️ 破坏性回归纪律

`test_main_services` / `test_files` 等回归用例会清空真实库中的 awards/软著/pending 数据并写入测试数据——**任何全量回归跑完后必须执行**：

```bash
python scripts/restore_awards_history.py --apply
```

该脚本幂等，用于还原业务数据（曾因漏跑致仪表板成果总数从 198 掉到 24）。

### 测试体系

- 权威测试方案与冻结模块纪律：[`docs/重构/设计/2026-08-19_测试方案.md`](docs/重构/设计/2026-08-19_测试方案.md)
- CI 质量门：ruff 语法级检查 + 覆盖率门禁（70%）+ pip-audit，见 `.github/workflows/ci.yml`

## 文档导航

- [`docs/README.md`](docs/README.md)：`docs/` 唯一路由入口（架构解读 / 测试方案 / 用户指南 / 运维指南等）
- [`CHANGELOG.md`](CHANGELOG.md)：近期变更记录（冻结期起逐日追加）
- 数据库结构权威说明：[`docs/重构/设计/2026-08-21_数据库结构说明.md`](docs/重构/设计/2026-08-21_数据库结构说明.md)
- 任务台账：[`docs/重构/设计/TODO索引.md`](docs/重构/设计/TODO索引.md)

## 部署

仓库内置 `Dockerfile` / `docker-compose.yml` / `deploy/` 部署素材（gunicorn + nginx + metrics），部署包与上线事项见任务台账 TODO 索引。

## 注意事项

1. **首次登录**：建议登录后立即修改默认密码；生产环境部署前务必清理默认口令
2. **账号激活**：账号的 `user_activated` 字段必须为 1（已激活）才能登录
3. **.env 生效时机**：修改 `.env` 后需重启应用
4. **数据备份**：应用内每日窗口自动备份（database/backups/ 时间戳目录），快照基线见 `database/snapshots/`