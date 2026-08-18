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

# CR-6 SSE 连接计数（进程级近似；多 worker 精确计数待 Redis 限流 T2）
_ACTIVE_SSE: dict = {}

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


@bp.route('/assistant/chat/stream')
@require_user_type('admin', 'teacher', 'student')
def chat_stream():
    """SSE 流式对话（P2-4/设计 API §5；FR-CHAT-05/FR-UI-04）。

    请求：GET /assistant/chat/stream?message=...&mode=auto
    事件：open{trace_id} → source{引用} → delta{text} → done{完整结果}
        | error{code, retry_after}
    连接限制：每用户同时 ≤2（计费 GET，防滥用占满 SSE worker，CR-6）。
    诚实边界：delta 当前先发完整结果，逐 token 增量依赖 workflow 流式化（TODO T23）。
    """
    from flask import Response, stream_with_context
    message = (request.args.get("message") or "").strip()
    mode = request.args.get("mode", "auto")
    if not message:
        return jsonify({"error": "消息不能为空"}), 400

    user_key = f"{session.get('user_type')}:{session.get('user_id')}"
    if _ACTIVE_SSE.get(user_key, 0) >= 2:
        return jsonify({"error": "同时进行的对话过多，请稍后再试"}), 429
    _ACTIVE_SSE[user_key] = _ACTIVE_SSE.get(user_key, 0) + 1

    import uuid
    trace_id = uuid.uuid4().hex[:12]

    def gen():
        import json as _json

        def sse(event, data):
            yield f"event: {event}\ndata: {_json.dumps(data, ensure_ascii=False)}\n\n"

        try:
            yield from sse("open", {"trace_id": trace_id})
            from backend.utils.circuit_breaker import CircuitBreaker
            breaker = CircuitBreaker.get("llm")
            if breaker.state == "open":
                yield from sse("error", {"code": 4003, "retry_after": breaker.remaining()})
                return
            user_context = {
                "role": session.get("role"), "name": session.get("user_name"),
                "user_id": session.get("user_id"), "user_type": session.get("user_type"),
            }
            # T23：qa 模式真流式（逐 token delta）；auto/tools 仍整段（workflow 流式化另行）
            if mode == "qa":
                try:
                    from config.loader import get_config
                    from backend.agent.llm_adapter import build_chat_model
                    from backend.rag.embeddings import build_embeddings
                    from backend.rag.vectorstore import build_vectorstore
                    from backend.agent.qa_agent import stream_answer
                    cl = get_config()
                    llm = build_chat_model(cl, streaming=True)
                    vs = build_vectorstore(cl, build_embeddings(cl))
                    if vs is None:
                        yield from sse("delta", {"text": "知识库未初始化，无法回答竞赛规则问题"})
                        yield from sse("done", {"answer": "知识库未初始化", "sources": [],
                                                "steps": [], "mode_used": "rag_qa"})
                        return
                    answer_parts = []
                    sources = []
                    for chunk in stream_answer(cl, vs, llm, message):
                        if isinstance(chunk, str):
                            answer_parts.append(chunk)
                            yield from sse("delta", {"text": chunk})
                        else:
                            sources = chunk.get("__sources__", [])
                    if sources:
                        yield from sse("source", {"docs": sources})
                    yield from sse("done", {"answer": "".join(answer_parts), "sources": sources,
                                            "steps": [{"agent": "qa", "status": "done"}],
                                            "mode_used": "rag_qa"})
                    return
                except ImportError as e:
                    yield from sse("error", {"code": 503, "message": f"依赖未安装: {e}"})
                    return
            # T23 auto 模式：节点级 progress 流（AI 正在抽取/审核…）+ 最终整段结果
            if mode == "auto":
                try:
                    from backend.agent.graph.workflow import MultiAgentWorkflow
                    from config.loader import get_config
                    wf = MultiAgentWorkflow.get_default(get_config())
                    NODE_LABELS = {"supervisor": "路由决策", "extraction": "AI 抽取中",
                                   "review": "AI 审核中", "qa": "知识检索中", "tools": "数据操作中"}
                    final = None
                    for ev in wf.run_stream(task_type="auto", message=message,
                                            user_context=user_context):
                        if "__final__" in ev:
                            final = ev["__final__"]
                        else:
                            yield from sse("progress", {"node": ev.get("node", ""),
                                                        "label": NODE_LABELS.get(ev.get("node", ""), ev.get("node", ""))})
                    if final is not None:
                        qa = final.get("qa_context") or {}
                        review = final.get("review_result")
                        extraction = final.get("extraction_result")
                        answer = qa.get("answer")
                        if not answer and (review or extraction):
                            answer = "已完成材料抽取与智能审核，详见下方结果卡片。"
                        result = {"answer": answer or "(工作流未产生回答)",
                                  "sources": qa.get("sources", []),
                                  "steps": final.get("steps", []),
                                  "mode_used": "multi_agent",
                                  "review": review, "extraction": extraction}
                        if result.get("sources"):
                            yield from sse("source", {"docs": result["sources"]})
                        yield from sse("delta", {"text": result["answer"]})
                        yield from sse("done", result)
                        return
                except ImportError:
                    pass   # 回退 _dispatch
                except Exception:
                    logger.exception("auto 流式执行异常，回退 _dispatch")
            result = _dispatch(message, mode, user_context)     # tools / auto 回退路径
            if result.get("sources"):
                yield from sse("source", {"docs": result["sources"]})
            yield from sse("delta", {"text": result.get("answer", "")})
            yield from sse("done", result)
        except ImportError as e:
            yield from sse("error", {"code": 503, "message": f"AI 助手依赖未安装: {e}"})
        except Exception:
            logger.exception("SSE 对话失败")
            yield from sse("error", {"code": 500, "message": "处理失败"})
        finally:
            _ACTIVE_SSE[user_key] = max(0, _ACTIVE_SSE.get(user_key, 1) - 1)

    resp = Response(stream_with_context(gen()), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    resp.headers["X-Trace-Id"] = trace_id
    return resp


@bp.route('/assistant/health')
def health():
    """健康检查：依赖安装 + 数据层可达 + 熔断状态（P2 假绿修复）。"""
    result = _check_capability()
    # 数据层：主库可读
    try:
        from config.loader import get_config
        from backend.utils.db_connection import get_connection
        conn = get_connection(get_config().get_path('database', 'competitions_db'))
        conn.execute("SELECT 1").fetchone()
        conn.close()
        result["db"] = True
    except Exception:
        result["db"] = False
    # 熔断状态（不主动拨测外部服务，避免产生费用——以熔断器状态为准）
    try:
        from backend.utils.circuit_breaker import CircuitBreaker
        result["breaker"] = {
            "llm": CircuitBreaker.get("llm").state,
            "ocr": CircuitBreaker.get("ocr").state,
        }
    except Exception:
        result["breaker"] = {"llm": "unknown", "ocr": "unknown"}
    result["status"] = "down" if not result.get("db") else "ok"
    return jsonify(result)


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
        wf = MultiAgentWorkflow.get_default(config_loader)
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

    wf = MultiAgentWorkflow.get_default(config_loader)
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
