# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AwardIE-AgentFlow (信息抽取与多智能体协作的奖状智能管理系统) - A Flask-based web application for managing student competition activities, award records, and related statistical information, powered by LLM-driven information extraction, RAG knowledge base, and multi-agent collaboration.

## Recent Changes

### doc_rec Module Migration (2026-01-14)
- Old extraction code in `backend/utils/` has been replaced
- Use `doc_rec.context.get_context()` for document extraction
- OCR cache migrated to `doc_rec/ocr_core/data/cache/ocr_cache.db`
- Detection rules module added for anomaly detection
- Template management moved to doc_rec Flask app (port 5000)
- Database cleanup completed (removed redundant tables)

### Integration Guide
```python
# Old way (removed):
from backend.utils.document_engine import DocumentEngine
engine = DocumentEngine(config)
text = engine.get_text(file_path)

# New way:
from doc_rec.context import get_context
extractor = get_context().universal_extractor
result = extractor.extract_from_file(file_path)
data = result.data
```

## Common Development Commands

### Setup and Running
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (default port: 5001)
python run.py

# Run with custom port
PORT=8000 python run.py

# Set environment
FLASK_ENV=production python run.py
FLASK_ENV=testing python run.py
```

### Database
- Database location: `database/competitions.db`
- Migrations: `database/migrations/`
- Use SQLite tools for direct database inspection

### Testing
Automated test suite is available in `tests/`:
- **Unit tests**: `tests/unit/` - Detection rules, regression tests
- **Integration tests**: `tests/integration/` - API tests for extraction and detection
- **UI tests**: `tests/ui/` - Flask test_client based UI tests

Run tests:
```bash
# Run all tests
python -m pytest tests/ -v

# Run specific module
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/ui/ -v

# Generate HTML report
python -m pytest tests/ --html=tests/reports/report.html --self-contained-html
```

See [guide.md](guide.md) for detailed testing documentation.

## Architecture

### Technology Stack
- **Backend**: Flask 3.0+, SQLite, Werkzeug (password hashing)
- **Frontend**: Bootstrap 5, Jinja2 templates
- **Document Processing**: PyMuPDF (PDF), Pillow (images), custom OCR engine, LLM integration

### Directory Structure

```
AwardIE-AgentFlow/
├── app/                     # Flask web application
│   ├── __init__.py         # App factory with blueprint registration
│   ├── auth.py             # Authentication decorators and utilities
│   ├── routes/             # Flask blueprints by role
│   ├── templates/          # Jinja2 templates organized by role
│   └── static/             # CSS, JS, images
├── backend/                # Business logic layer
│   ├── models/             # Data models with manager classes
│   ├── utils/              # LLM engine, OCR engine, PDF engine
│   ├── agent/              # AI Agent & Multi-Agent (LangChain + LangGraph)
│   │   ├── llm_adapter.py # LLM Provider -> LangChain ChatModel
│   │   ├── tools/         # Function Calling tools (query/stats/extract/export)
│   │   ├── graph/         # LangGraph multi-agent workflow (Supervisor pattern)
│   │   ├── service.py     # AgentService (single agent entry)
│   │   └── state.py       # Multi-agent shared state
│   ├── rag/                # RAG knowledge base (Chroma + bge-m3)
│   │   ├── embeddings.py  # SimpleOpenAIEmbeddings (symmetric encoding)
│   │   ├── vectorstore.py # Chroma vector store
│   │   ├── indexer.py     # Knowledge indexing (docx -> vectors)
│   │   └── retriever.py   # MMR retrieval
│   └── config.json         # Backend configuration
├── doc_rec/                # Document recognition subsystem
│   ├── document_extract/   # Core extraction logic
│   │   ├── core/          # Extractor classes (award/patent/software)
│   │   ├── templates/     # Award templates for matching
│   │   ├── validation/    # Result validation rules
│   │   └── llm/           # LLM provider integration
│   ├── ocr_core/          # OCR engine
│   └── app.py             # Mini Flask app for doc processing
├── tests/                  # Automated test suite
│   ├── unit/              # Unit tests
│   ├── integration/       # Integration tests
│   ├── ui/                # UI tests
│   ├── fixtures/          # Test data and fixtures
│   ├── config/            # Test configuration
│   └── scripts/           # Test utility scripts
├── database/              # SQLite database and migrations
├── tools/                 # Standalone utilities (export, cleanup)
├── files/images/          # Certificate storage (awards, patents, software copyrights)
└── temp/uploads/          # Temporary file uploads
```

### Key Design Patterns

**Model-View-Controller with Service Layer**
- Routes in `app/routes/` handle HTTP requests
- Manager classes in `backend/models/` encapsulate business logic
- Database operations use SQLite directly

**Flask Blueprints**
- `app/routes/auth.py` - Login/logout
- `app/routes/admin.py` - Admin dashboard
- `app/routes/teacher.py` - Teacher functionality
- `app/routes/student.py` - Student functionality
- `app/routes/api.py` - API endpoints

**Document Processing Pipeline**
1. Upload → OCR text extraction
2. Type detection (award/patent/software)
3. Template matching against known patterns
4. LLM-based structured extraction
5. Validation and caching

### User Roles and Authentication

Three roles with separate login tables:
- **Admin**: `admins` table, default `admin`/`Mayy123`
- **Teacher**: `teachers` table, login with employee_id, default password `P@ss301`
- **Student**: `students` table, login with student_id, default password `P@ss301`

Session cookies: 31-day expiration, HTTPOnly flag.

**Password Management**:
- Default password is configured in `config/settings.json` under `system.default_password`
- Students are forced to change password on first login with default password
- Admins can reset user passwords in edit pages (resets to default password)
- Default password can be viewed in "System Settings → General Settings"

### Core Data Models

**Student**: id, student_id, name, major, grade, contact, skills
- Brief format: "李家鸿(22计科)"

**Award/Certificate**: Supports awards, patents, software copyrights
- JSON-based structured data storage
- Fields: competition_name, track, issuer, province, group_name
- Multi-name support for winners and supervisors

**Competition**: name, tracks, time_range, description, whitelist_status
- Grade categories (A类, B类, etc.)
- Month-based time tracking
- Competition aliases for fuzzy matching

### Document Recognition System (`doc_rec/`)

The document recognition subsystem is a sophisticated pipeline for extracting structured data from award certificates, patents, and software copyrights:

- **OCR Engine** (`ocr_core/`): Custom OCR for text extraction from PDFs/images
- **Extractors** (`document_extract/core/`): Specialized extractors for each document type
- **Templates** (`document_extract/templates/`): Predefined patterns for matching known award formats
- **LLM Integration** (`document_extract/llm/`): Uses LLM for unstructured text extraction
- **Validation** (`document_extract/validation/`): Rule-based validation of extracted data

### AI Agent & Multi-Agent System (`backend/agent/`)

基于 LangChain + LangGraph 的 AI Agent 能力层，复用现有 `config/settings.json` 的多 Provider 配置。

- **LLM Adapter** (`llm_adapter.py`): 把现有 LLM Provider 配置适配为 LangChain ChatModel（原生支持 Function Calling / 流式 / 结构化输出）
- **Tools** (`tools/`): 10 个 Function Calling 工具，封装现有 Manager 的查询/统计/抽取/导出能力
  - `query_tools.py`: 查奖状、匹配竞赛、查详情、白名单判断
  - `stats_tools.py`: 竞赛清单、贡献度排名、获奖趋势、热力图
  - `extract_tools.py`: 触发智能抽取（OCR + LLM）
  - `export_tools.py`: 导出年度成果报表
  - `context.py`: ToolContext 依赖注入容器（复用 ServiceContext 的 extract_framework，含已注册抽取器）
- **Single Agent** (`service.py`): AgentService —— 单 Agent 统一入口（用 langchain 1.x `create_agent`）
- **Multi-Agent Graph** (`graph/`): LangGraph Supervisor 模式多智能体编排
  - `supervisor.py`: 主管 Agent，规则路由优先 + LLM 意图理解兜底，含已执行节点去重防死循环
  - `extraction_agent.py`: 抽取节点（封装 ExtractFramework）
  - `review_agent.py`: 审核节点（规则校验 + RAG 交叉校验）
  - `qa_agent_node.py`: 问答节点（接 RAG）
  - `workflow.py`: StateGraph 装配（含 checkpoint 断点续跑）
- **State** (`state.py`): 多智能体共享状态（TypedDict + add_messages reducer）

**关键设计**：所有 AI 模块采用惰性导入，未安装 langchain 时整个项目原有功能不受影响。

### RAG Knowledge Base (`backend/rag/`)

基于向量检索的竞赛规则知识库，支持自然语言问答。

- **Embeddings** (`embeddings.py`): 自建 `SimpleOpenAIEmbeddings`（直接调 OpenAI 兼容 API，query/document 对称编码，避免 langchain OpenAIEmbeddings 的前缀干扰导致 bge-m3 检索失真）
- **VectorStore** (`vectorstore.py`): Chroma 持久化（`database/chroma/`）
- **Indexer** (`indexer.py`): 解析竞赛等级分类表 docx 入库（逐行切分，分批 32/批避免 API 上限）
- **Retriever** (`retriever.py`): MMR 检索（解决竞赛名相似导致重复召回）

**初始化**：`python tools/init_rag_vectorstore.py`（需配置 embedding provider）

**默认配置**：硅基流动 `BAAI/bge-m3`（免费），可通过 `rag.default_embedding_provider` 切换智谱 embedding-3。

### AI Assistant 对话系统 (`app/routes/chat.py` + `templates/assistant/`)

整合 RAG 问答 + 单 Agent 工具调用 + 多智能体协作的对话界面。

- **路由**：`/assistant`（页面）、`/assistant/chat`（同步对话）、`/assistant/health`（能力检测）
- **认证**：复用 `@require_user_type`，admin/teacher/student 均可访问
- **前端**：`templates/assistant/chat.html`，三种模式切换（智能路由/知识问答/数据操作），含 Agent 思考过程可视化与引用来源卡片
- **降级**：依赖未安装时页面显示能力警告，不阻断其他功能

**运行**：启动 Flask 后访问 `http://localhost:5001/assistant`（需登录）。

### AI 能力联调与测试

```bash
# 单元测试（默认运行，离线，验证配置解析/路由逻辑/序列化等）
python -m pytest tests/unit/agent/ -v

# 集成测试（需真实 API + 已入库向量库）
RUN_AGENT_INTEGRATION=1 python -m pytest tests/integration/agent/ -v

# 初始化 RAG 知识库（首次使用或更换 embedding 模型后运行）
python tools/init_rag_vectorstore.py
```

**注意**：本机环境存在失效代理 `ALL_PROXY=http://127.0.0.1:7890`，运行 AI 调用前需先执行 `unset ALL_PROXY`，否则 API 请求会被代理拦截。

## UI/UX Design Guidelines

**CRITICAL**: All UI changes must follow the design rules in `.cursor/rules/ui-design.mdc`:

- **Style**: Modern, clean, enterprise education SaaS (reference: EasyEdulab.com)
- **Colors**: Blue/purple primary, light backgrounds, subtle shadows
- **Components**: Card-based design, rounded buttons, consistent table styles
- **Typography**: System fonts, limited heading levels (H1-H3), concise copy
- **Avoid**: Flashy elements, inconsistent styling, overly long text blocks

When creating or modifying pages:
- Use card layouts for feature sections and statistics
- Maintain consistent button styles (primary: filled, secondary: outlined)
- Keep tables clean with sortable headers
- Use Bootstrap 5 classes consistently

## Important File Locations

- **Config**: `config.py` - Environment-based configuration (dev/prod/test)
- **Entry point**: `run.py` - Flask application factory pattern
- **Backend config**: `backend/config.json` - Feature flags and settings
- **UI rules**: `.cursor/rules/ui-design.mdc` - Mandatory design guidelines

## Development Notes

### File Uploads
- Max size: 16MB
- Supported: PDF, images
- Permanent storage: `files/images/`
- Temporary: `temp/uploads/`

### Database Migrations
- Manual migration scripts in `database/migrations/`
- Check existing migrations for patterns when adding new schema changes

### Security
- Password hashing via Werkzeug
- Session cookies with HTTPOnly
- Input validation on all forms
- CSRF protection via Flask-WTF forms

## Local Model Support (Ollama/PaddleOCR)

The project supports using local models as an alternative to cloud APIs, reducing testing costs.

### PaddleOCR for OCR

Local OCR using PaddleOCR PP-OCRv5 model.

**Configuration:**

In `apikey/apikey.json`:
```json
{
  "ocr": {
    "paddle": {
      "device": "gpu",  // or "cpu"
      "lang": "ch",
      "ocr_version": "PP-OCRv5"
    }
  }
}
```

**Installation:**
```bash
pip install paddleocr
```

### Ollama for LLM

Local LLM using Ollama with models like qwen3-nothink:30b.

**Configuration:**

In `apikey/apikey.json`:
```json
{
  "llm": {
    "ollama": {
      "base_url": "http://localhost:11434",
      "model": "cnshenyang/qwen3-nothink:30b",
      "temperature": 0.1,
      "timeout": 300
    }
  }
}
```

**Installation:**
1. Download Ollama from https://ollama.ai
2. Run `ollama serve`
3. Pull models: `ollama pull cnshenyang/qwen3-nothink:30b`

### Switching Providers

Edit root `config.json`:
```json
{
  "ocr": {
    "default_provider": "paddle"  // or "zhipu", "baidu"
  },
  "llm": {
    "default_provider": "ollama"  // or "zhipu", "moonshot"
  }
}
```

### Running Comparison Tests

```bash
# Run provider comparison test
python tests/scripts/compare_providers.py

# Generate HTML report
python tests/scripts/html_report_generator.py <results.json>
```

See [docs/tests/comparison-test-guide.md](docs/tests/comparison-test-guide.md) for details.

## Configuration & Hardcoding Rules（配置与硬编码规范）

本项目对配置管理有严格约束，请 Claude 在编写或重构代码时 **必须遵守**：

1. 禁止硬编码路径 / URL / API key
   - 所有路径、URL、API key、数据库连接字符串等，禁止在业务代码中硬编码。
   - 这些信息必须统一来自：
     - 配置文件（如 `config/*.json`、`config/*.yaml`）；
     - 配置模块（如 `config.py` 或 `backend/config.json` 的加载结果）；
     - 环境变量（通过统一的配置加载层封装）。
   - 如果发现旧代码中存在硬编码路径（例如早期目录结构下的路径），应主动提出并执行重构：改为基于项目根目录 + 配置项的方式。

2. 外部参数缺失时的处理
   - 当重要参数（如 `db_path`、`data_dir`、`ocr_cache_path`、模型目录等）未传入且配置中也缺失时：
     - 必须抛出清晰的异常（例如 `ValueError`、`RuntimeError`），说明缺失内容；
     - 禁止为了所谓“健壮性”在内部静默使用硬编码默认值或自动创建默认路径。
   - “宁可失败也不要悄悄兜底”：遇到配置问题，要让错误尽早暴露。

3. 配置驱动而非 if-else 驱动
   - 优先通过配置文件、映射表或策略模式实现行为切换，而不是在业务代码中堆叠大量 `if-else`。
   - 在重构旧代码时：
     - 如发现相似逻辑通过多处 `if-else` 实现，应考虑抽取为配置映射或策略表；
     - 如发现同一路径 / 常量在多文件重复出现，应抽取到统一配置源。

4. 迁移与路径变更
   - 在模块迁移或目录调整时：
     - 应优先检查并消除老路径的硬编码，确保路径只从统一配置源获取；
     - 确保“改一次配置，全局生效”，不要留下多个不一致的副本。
