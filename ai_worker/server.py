"""AI Worker:gRPC server 包 v1 LangGraph 编排(N1:算法 1:1 保留,仅接口层)。

接口面(v1 既有服务类,零重写):
- Extract            → ToolContext().extract_framework.extract(file_path, ...)
- ExtractAndReview   → MultiAgentWorkflow.run_stream(task_type="extract_and_review", ...)
- Ask                → MultiAgentWorkflow.run_stream(task_type="qa", message=...)
- run_stream yield 契约:{"node": name} / {"delta": text} / {"__final__": state}

启动(D:\venvs\awardie,与 v1 Flask 同一环境):
    python ai_worker/server.py [port]     # 默认 50060
"""
import logging
import os
import sys
import threading
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

# 出站直连(v1 run.py 同款:剥离代理,防死代理吞 LLM/OCR 请求)
for _var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_var, None)
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"

import grpc  # noqa: E402
from concurrent import futures  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent / "protos"))
import ai_service_pb2 as pb  # noqa: E402
import ai_service_pb2_grpc as pb_grpc  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s [ai-worker] %(message)s")
log = logging.getLogger("ai_worker")

DISCLAIMER = "AI 建议仅辅助参考,以管理员白名单与人工审核为准(BR-2)"
WORKER_VERSION = "0.1.0"

_workflow = None
_workflow_lock = threading.Lock()


def _get_workflow():
    """进程级单例(v1 双检锁单例同语义):构建成本高,启动后复用。"""
    global _workflow
    if _workflow is None:
        with _workflow_lock:
            if _workflow is None:
                from config.loader import get_config_loader
                from backend.agent.graph.workflow import MultiAgentWorkflow
                _workflow = MultiAgentWorkflow.from_config(get_config_loader())
                log.info("MultiAgentWorkflow 构建完成")
    return _workflow


def _get_framework():
    from config.loader import get_config_loader
    from backend.agent.tools.context import get_tool_context
    return get_tool_context(get_config_loader()).extract_framework


class AiService(pb_grpc.AiServiceServicer):

    def Health(self, request, context):
        try:
            import langgraph  # noqa: F401
            lg_ok = True
        except ImportError:
            lg_ok = False
        return pb.HealthResponse(ok=True, version=WORKER_VERSION, langgraph_available=lg_ok)

    def Extract(self, request, context):
        log.info("Extract: %s (trace_id=%s)", request.file_path, request.trace_id or "-")
        try:
            result = _get_framework().extract(
                request.file_path, use_ocr_cache=request.use_ocr_cache, use_llm_cache=request.use_llm_cache
            )
            return pb.ExtractResponse(
                code=0,
                message="ok",
                doc_type=result.template_type.value if hasattr(result.template_type, "value") else str(result.template_type or ""),
                data_json=__import__("json").dumps(result.data, ensure_ascii=False, default=str),
                confidence=float(getattr(result, "confidence", 0.0) or 0.0),
                ocr_text=(result.ocr_text or "")[:500],
                status=result.status.value if hasattr(result.status, "value") else str(result.status),
                error_message=result.error_message or "",
                trace_id=request.trace_id,
            )
        except Exception as e:  # noqa: BLE001 —— Worker 边界:异常收敛为 4003/5000,不泄漏堆栈
            log.exception("Extract 失败")
            code = 4003 if _is_ai_dependency_error(e) else 5000
            return pb.ExtractResponse(code=code, message=str(e)[:200], trace_id=request.trace_id)

    def ExtractAndReview(self, request, context):
        log.info("ExtractAndReview: %s (trace_id=%s)", request.file_path, request.trace_id or "-")
        try:
            wf = _get_workflow()
        except Exception as e:  # noqa: BLE001
            log.exception("workflow 构建失败")
            yield pb.WorkflowEvent(
                trace_id=request.trace_id,
                final=pb.ReviewFinal(code=4003, message=f"AI Worker 不可用: {e}", disclaimer=DISCLAIMER),
            )
            return

        final_state = None
        try:
            for evt in wf.run_stream(task_type="extract_and_review", file_path=request.file_path):
                if "node" in evt:
                    yield pb.WorkflowEvent(trace_id=request.trace_id, node=pb.NodeEvent(node=evt["node"]))
                elif "delta" in evt:
                    yield pb.WorkflowEvent(trace_id=request.trace_id, delta=pb.TextDelta(text=evt["delta"]))
                else:
                    final_state = evt.get("__final__")
        except Exception as e:  # noqa: BLE001
            log.exception("工作流流中断")
            yield pb.WorkflowEvent(
                trace_id=request.trace_id,
                final=pb.ReviewFinal(code=4003, message=f"工作流中断: {e}", disclaimer=DISCLAIMER),
            )
            return

        if final_state is None:
            yield pb.WorkflowEvent(
                trace_id=request.trace_id,
                final=pb.ReviewFinal(code=5000, message="工作流无终态", disclaimer=DISCLAIMER),
            )
            return

        extraction = final_state.get("extraction_result") or {}
        review = final_state.get("review_result") or {}
        import json
        yield pb.WorkflowEvent(
            trace_id=request.trace_id,
            final=pb.ReviewFinal(
                decision=review.get("decision", "need_manual"),
                issues_json=json.dumps(review.get("issues", []), ensure_ascii=False, default=str),
                suggestion=review.get("suggestion", ""),
                extraction_json=json.dumps(extraction, ensure_ascii=False, default=str),
                code=0,
                message="ok",
                disclaimer=DISCLAIMER,
            ),
        )

    def Ask(self, request, context):
        log.info("Ask: %s (trace_id=%s)", request.question[:50], request.trace_id or "-")
        try:
            wf = _get_workflow()
        except Exception as e:  # noqa: BLE001
            yield pb.AnswerEvent(
                trace_id=request.trace_id,
                final=pb.AnswerFinal(code=4003, message=f"AI Worker 不可用: {e}", disclaimer=DISCLAIMER),
            )
            return

        final_state = None
        try:
            for evt in wf.run_stream(task_type="qa", message=request.question):
                if "node" in evt:
                    yield pb.AnswerEvent(trace_id=request.trace_id, node=pb.NodeEvent(node=evt["node"]))
                elif "delta" in evt:
                    yield pb.AnswerEvent(trace_id=request.trace_id, delta=pb.TextDelta(text=evt["delta"]))
                else:
                    final_state = evt.get("__final__")
        except Exception as e:  # noqa: BLE001
            log.exception("问答流中断")
            yield pb.AnswerEvent(
                trace_id=request.trace_id,
                final=pb.AnswerFinal(code=4003, message=f"问答中断: {e}", disclaimer=DISCLAIMER),
            )
            return

        qa = (final_state or {}).get("qa_context") or {}
        import json
        yield pb.AnswerEvent(
            trace_id=request.trace_id,
            final=pb.AnswerFinal(
                answer=qa.get("answer", ""),
                sources_json=json.dumps(qa.get("sources", []), ensure_ascii=False, default=str),
                code=0,
                message="ok",
                disclaimer=DISCLAIMER,
            ),
        )


def _is_ai_dependency_error(e: Exception) -> bool:
    text = str(e).lower()
    return any(k in text for k in ("ocr", "llm", "api", "timeout", "connection", "key"))


def serve(port: int = 50060):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=8))
    pb_grpc.add_AiServiceServicer_to_server(AiService(), server)
    server.add_insecure_port(f"127.0.0.1:{port}")
    server.start()
    log.info("AI Worker gRPC server on 127.0.0.1:%d (version=%s)", port, WORKER_VERSION)
    server.wait_for_termination()


if __name__ == "__main__":
    serve(int(sys.argv[1]) if len(sys.argv) > 1 else 50060)
