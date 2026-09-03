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

    def ExtractTemplate(self, request, context):
        """模板样本图抽取(架构票;v1 extract-for-create 语义:强制 award 抽取器+默认 prompt)。"""
        log.info("ExtractTemplate: %s (%d bytes, trace_id=%s)",
                 request.filename or "-", len(request.image), request.trace_id or "-")
        import json
        import os
        import tempfile
        if not request.image:
            return pb.ExtractTemplateResponse(code=4004, message="请上传样本图片", trace_id=request.trace_id)
        suffix = os.path.splitext(request.filename or "")[1] or ".jpg"
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                tmp.write(request.image)
                temp_path = tmp.name
            framework = _get_framework()
            award_extractor = framework.get_extractor("award")
            if award_extractor is None:
                return pb.ExtractTemplateResponse(code=5000, message="奖状抽取器未注册", trace_id=request.trace_id)
            from backend.extract.extractors.base import ExtractContext
            ctx = ExtractContext(
                file_path=temp_path,
                use_ocr_cache=request.use_ocr_cache,
                use_llm_cache=request.use_llm_cache,
                use_default_prompt_only=True,
                force_type=True,
                ocr_engine=framework.ocr_engine,
                llm_engine=framework.llm_engine,
            )
            result = award_extractor.extract(ctx)
            from backend.extract.types import ExtractStatus
            if result.status != ExtractStatus.SUCCESS:
                return pb.ExtractTemplateResponse(
                    code=4004, message=result.error_message or "抽取失败", trace_id=request.trace_id)
            data = result.data if result.data else {}
            # v1 语义:note-only 数据=图不可抽取(非奖状图等),收敛为 4004
            if isinstance(data, dict) and list(data.keys()) == ["note"] and "note" in data:
                return pb.ExtractTemplateResponse(
                    code=4004, message=data.get("note") or result.error_message or "抽取失败",
                    trace_id=request.trace_id)
            ocr_text = getattr(result, "ocr_text", None)
            return pb.ExtractTemplateResponse(
                code=0,
                message="ok",
                data_json=json.dumps(data, ensure_ascii=False, default=str),
                ocr_text=ocr_text if isinstance(ocr_text, str) else str(ocr_text or ""),
                trace_id=request.trace_id,
            )
        except Exception as e:  # noqa: BLE001 —— Worker 边界:异常收敛为 4003/5000,不泄漏堆栈
            log.exception("ExtractTemplate 失败")
            code = 4003 if _is_ai_dependency_error(e) else 5000
            return pb.ExtractTemplateResponse(code=code, message=str(e)[:200], trace_id=request.trace_id)
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass

    def GeneratePrompt(self, request, context):
        """模板 prompt 生成(架构票;v1 generate-prompt-for-create 语义:临时 Template+base_fields)。"""
        log.info("GeneratePrompt: rule=%d bytes (trace_id=%s)",
                 len(request.template_rule_json), request.trace_id or "-")
        import json
        try:
            rule = json.loads(request.template_rule_json) if request.template_rule_json.strip() else {}
        except json.JSONDecodeError as e:
            return pb.GeneratePromptResponse(code=4000, message=f"模板规则 JSON 非法: {e}", trace_id=request.trace_id)
        try:
            from backend.extract.template.template import Template
            from backend.extract.types import TemplateType
            from backend.services.context import get_context

            # 与 extract_framework 同源的单例 ServiceContext,公开 template_manager property
            base_fields = get_context().template_manager.get_base_fields("award")
            keywords = [str(k).strip() for k in (rule.get("keywords") or []) if str(k).strip()]
            sample_text = (request.sample_text or "").strip() or "示例OCR文本"
            sample_extracted = rule.get("sample_extracted")
            if isinstance(sample_extracted, dict):
                sample_extracted = json.dumps(sample_extracted, ensure_ascii=False)
            try:
                min_length = int(rule.get("min_length") or 0)
                max_length = int(rule.get("max_length") or 0)
            except (TypeError, ValueError):
                # 架构票实施批 Low 挂账:数值字段非法收敛 4000 友好码,不落 5000
                return pb.GeneratePromptResponse(
                    code=4000, message="模板规则数值非法:min_length/max_length 必须为整数",
                    disclaimer=DISCLAIMER, trace_id=request.trace_id)
            temp_template = Template(
                template_type=TemplateType.AWARD,
                keywords=keywords,
                sample_text=sample_text,
                sample_extracted=(sample_extracted or "{}").strip() or "{}",
                default_fields=rule.get("default_fields") or {},
                llm_fields=rule.get("llm_fields") or {},
                min_length=min_length,
                max_length=max_length,
                language=(rule.get("language") or "zh").strip() or "zh",
                need_translate=bool(rule.get("need_translate")),
            )
            prompt = temp_template.generate_prompt(sample_text, base_fields)
            return pb.GeneratePromptResponse(
                code=0, message="ok", prompt=prompt, disclaimer=DISCLAIMER, trace_id=request.trace_id)
        except Exception as e:  # noqa: BLE001 —— Worker 边界:异常收敛为 4003/5000,不泄漏堆栈
            log.exception("GeneratePrompt 失败")
            code = 4003 if _is_ai_dependency_error(e) else 5000
            return pb.GeneratePromptResponse(code=code, message=str(e)[:200], disclaimer=DISCLAIMER,
                                             trace_id=request.trace_id)

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
