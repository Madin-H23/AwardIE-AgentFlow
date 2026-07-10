"""
抽取类工具：触发文档智能抽取。

封装 ExtractFramework.extract 为 LangChain @tool。
这是项目核心 AI 能力（OCR + LLM 结构化抽取）的 Agent 化封装。

注意：此工具有真实副作用（消耗 OCR/LLM 调用额度、写缓存），但不变更业务库，
适合作为 Agent 工具（参数明确、返回结构化 ExtractResult）。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _extract_result_to_dict(result) -> Dict[str, Any]:
    """把 ExtractResult 序列化为可 JSON 化的 dict（剥离 OCR 原文等大字段）。"""
    return {
        "status": getattr(result.status, "value", str(result.status)),
        "doc_type": getattr(result, "template_type", None).value if getattr(result, "template_type", None) else None,
        "extractor": getattr(result, "extractor_name", None),
        "data": getattr(result, "data", None),
        "error": getattr(result, "error_message", None),
        "ocr_cache_hit": getattr(result, "ocr_cache_hit", None),
        "llm_cache_hit": getattr(result, "llm_cache_hit", None),
    }


def make_extract_tool(ctx):
    """
    构造"智能抽取"工具。

    通过闭包注入 ToolContext 的 extract_framework。
    注意：extract_framework 默认未注册业务抽取器，需在 AgentService 中
    完成注册后再传入（见 AgentService.build）。
    """
    from langchain_core.tools import tool

    @tool
    def extract_document(file_path: str, use_cache: bool = True) -> Dict[str, Any]:
        """
        对一个文件（奖状/专利/软著/大创的图片或PDF）进行智能抽取，自动 OCR 识别并用大模型提取结构化信息。

        适用场景：用户上传或指定一个证书文件路径，需要提取其中的获奖人、竞赛、级别等信息。

        Args:
            file_path: 文件的绝对路径（支持 jpg/png/pdf 等）
            use_cache: 是否使用 OCR/LLM 缓存（默认 True，避免重复调用额度）

        Returns:
            抽取结果，含 status / doc_type / data（结构化字段）/ error
        """
        try:
            result = ctx.extract_framework.extract(
                file_path,
                use_ocr_cache=use_cache,
                use_llm_cache=use_cache,
            )
            return _extract_result_to_dict(result)
        except Exception as e:
            logger.exception("extract_document 失败: %s", e)
            return {"status": "error", "error": f"抽取失败: {e}"}

    return extract_document


__all__ = ["make_extract_tool"]
