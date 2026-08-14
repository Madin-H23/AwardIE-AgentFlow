"""
AI 智能助手路由（对话系统）

提供对话界面 + 后端接口，整合：
- RAG 问答（竞赛规则咨询）
- 单 Agent 工具调用（查询/统计/导出）
- 多智能体协作（上传材料自动抽取+审核）

接口：
- GET  /assistant        对话页面
- POST /assistant/chat   同步对话（返回完整结果）
- GET  /assistant/health 健康检查（Agent 能力是否就绪）
"""
from __future__ import annotations

import logging

from flask import Blueprint, render_template, request, jsonify, session, current_app

from app.auth import require_user_type

bp = Blueprint('chat', __name__)
logger = logging.getLogger(__name__)


@bp.route('/assistant')
@require_user_type('admin', 'teacher', 'student')
def assistant():
    """AI 智能助手对话页面。"""
    from flask import flash

    # 检查 Agent 能力是否就绪（langchain 是否安装）
    capability = _check_capability()
    if not capability["ready"]:
        flash(f"AI 助手未就绪：{capability['reason']}。请先安装依赖：pip install -r requirements.txt", "warning")

    return render_template(
        'assistant/chat.html',
        capability=capability,
    )


@bp.route('/assistant/chat', methods=['POST'])
@require_user_type('admin', 'teacher', 'student')
def chat():
    """
    同步对话接口。

    请求体 JSON：
        {
            "message": "用户消息",
            "mode": "auto" | "qa" | "tools"    // 可选，默认 auto
        }

    返回：
        {
            "answer": str,
            "sources": [...],
            "steps": [...],      // Agent 思考过程
            "mode_used": str
        }
    """
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    mode = data.get("mode", "auto")

    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    # 构造用户上下文（从 session）
    user_context = {
        "role": session.get("role"),
        "name": session.get("user_name"),
        "user_id": session.get("user_id"),
        "user_type": session.get("user_type"),
    }

    try:
        result = _dispatch(message, mode, user_context)
        return jsonify(result)
    except ImportError as e:
        logger.warning("Agent 依赖未安装: %s", e)
        return jsonify({
            "error": "AI 助手依赖未安装",
            "detail": str(e),
            "hint": "请运行: pip install langchain langchain-openai langgraph langchain-chroma",
        }), 503
    except Exception as e:
        logger.exception("对话处理失败: %s", e)
        return jsonify({"error": f"处理失败: {e}"}), 500


@bp.route('/assistant/health')
def health():
    """健康检查：Agent 能力是否就绪。"""
    return jsonify(_check_capability())


@bp.route('/assistant/extract', methods=['POST'])
@require_user_type('admin', 'teacher', 'student')
def extract():
    """上传奖状文件 → 多智能体抽取 + 审核。

    走 extract_and_review 工作流：Supervisor → 抽取 Agent → 审核 Agent，
    让 extraction/review 两个 Agent 在对话场景真正串联起来。
    """
    file = request.files.get('file')
    if not file or not file.filename:
        return jsonify({"error": "未上传文件"}), 400

    # 落盘到 files/agent_upload/
    import uuid
    from pathlib import Path
    from werkzeug.utils import secure_filename

    files_dir = Path(current_app.config.get('FILES_DIR')
                     or (Path(current_app.root_path).parent / 'files'))
    upload_dir = files_dir / 'agent_upload'
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secure_filename(file.filename) or 'upload'
    file_path = upload_dir / f"{uuid.uuid4().hex[:8]}_{safe_name}"
    file.save(str(file_path))

    user_context = {
        "role": session.get("role"),
        "name": session.get("user_name"),
        "user_id": session.get("user_id"),
        "user_type": session.get("user_type"),
    }

    try:
        from backend.agent.graph.workflow import MultiAgentWorkflow
        from config.loader import get_config
        config_loader = get_config()
        wf = MultiAgentWorkflow.from_config(config_loader)
        state = wf.run(
            task_type="extract_and_review",
            file_path=str(file_path),
            user_context=user_context,
        )
        return jsonify({
            "extraction": state.get("extraction_result"),
            "review": state.get("review_result"),
            "steps": state.get("steps", []),
            "mode_used": "extract_and_review",
        })
    except ImportError as e:
        logger.warning("Agent 依赖未安装: %s", e)
        return jsonify({
            "error": "AI 助手依赖未安装",
            "detail": str(e),
            "hint": "请运行: pip install langchain langchain-openai langgraph langchain-chroma",
        }), 503
    except Exception as e:
        logger.exception("抽取审核失败: %s", e)
        return jsonify({"error": f"抽取审核失败: {e}"}), 500


# ==================== 内部实现 ====================

def _check_capability():
    """检查 Agent 能力是否就绪（依赖是否安装、配置是否完整）。"""
    checks = {}
    try:
        import langchain  # noqa: F401
        checks["langchain"] = True
    except ImportError:
        checks["langchain"] = False
    try:
        import langgraph  # noqa: F401
        checks["langgraph"] = True
    except ImportError:
        checks["langgraph"] = False
    try:
        import langchain_openai  # noqa: F401
        checks["langchain_openai"] = True
    except ImportError:
        checks["langchain_openai"] = False

    ready = all(checks.values())
    reason = None
    if not ready:
        missing = [k for k, v in checks.items() if not v]
        reason = f"缺少依赖: {', '.join(missing)}"

    return {"ready": ready, "checks": checks, "reason": reason}


def _dispatch(message: str, mode: str, user_context: dict) -> dict:
    """
    根据模式分发到不同后端。

    - auto: 用多智能体工作流（Supervisor 自动路由）
    - qa:   直接走 RAG 问答
    - tools:直接走单 Agent 工具调用
    """
    from config.loader import get_config
    config_loader = get_config()

    if mode == "qa":
        return _run_qa(config_loader, message)
    if mode == "tools":
        return _run_tools(config_loader, message, user_context)
    # auto: 用多智能体工作流
    return _run_workflow(config_loader, message, user_context)


def _run_workflow(config_loader, message: str, user_context: dict) -> dict:
    """多智能体工作流（auto 模式）。

    透传完整的结构化结果，供前端展示审核结论、抽取结果与协作过程：
    - review:     审核结论（decision/issues/suggestion），来自 review_agent
    - extraction: 抽取结果（doc_type/data/confidence），来自 extraction_agent
    """
    from backend.agent.graph.workflow import MultiAgentWorkflow

    wf = MultiAgentWorkflow.from_config(config_loader)
    state = wf.run(task_type="auto", message=message, user_context=user_context)
    qa = state.get("qa_context") or {}
    review = state.get("review_result")
    extraction = state.get("extraction_result")

    # 走“抽取+审核”分支时 qa_context 通常为空，给前端一个友好默认回答
    answer = qa.get("answer")
    if not answer and (review or extraction):
        answer = "已完成材料抽取与智能审核，详见下方结果卡片。"

    return {
        "answer": answer or "(工作流未产生回答，请查看步骤)",
        "sources": qa.get("sources", []),
        "steps": state.get("steps", []),
        "mode_used": "multi_agent",
        "review": review,
        "extraction": extraction,
    }


def _run_qa(config_loader, message: str) -> dict:
    """RAG 问答（qa 模式）。"""
    from backend.agent.llm_adapter import build_chat_model
    from backend.rag.embeddings import build_embeddings
    from backend.rag.vectorstore import build_vectorstore
    from backend.agent.qa_agent import answer_question

    llm = build_chat_model(config_loader)
    emb = build_embeddings(config_loader)
    vs = build_vectorstore(config_loader, emb)
    result = answer_question(config_loader, vs, llm, message)
    return {
        "answer": result["answer"],
        "sources": result["sources"],
        "steps": [{"agent": "qa", "status": "done"}],
        "mode_used": "rag_qa",
    }


def _run_tools(config_loader, message: str, user_context: dict) -> dict:
    """单 Agent 工具调用（tools 模式）。"""
    from backend.agent.service import AgentService

    service = AgentService.from_config(config_loader)
    result = service.chat(message, user_context=user_context)
    return {
        "answer": result["output"],
        "sources": [],
        "steps": result["intermediate_steps"],
        "mode_used": "single_agent",
    }
