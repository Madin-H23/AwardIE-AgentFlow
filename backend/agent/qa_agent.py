"""
问答 Agent（RAG）

把向量检索与 LLM 生成串联，实现基于知识库的自然语言问答。

流程：
    用户提问
      ↓
    向量检索（MMR）── 竞赛规则知识库
      ↓
    拼 Prompt（system: 角色 + 检索上下文；user: 问题）
      ↓
    LLM 生成回答 + 引用来源
      ↓
    返回 {answer, sources}

应用场景：
- "挑战杯是 A 类还是 B 类？"
- "有哪些国家级的 A 类竞赛？"
- "数模竞赛属于什么级别？"

这是岗位 JD 第 1 条（RAG 知识库）和第 3 条（前沿技术迭代）的直接落地。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.rag.retriever import retrieve, format_context

logger = logging.getLogger(__name__)


# 系统提示词：定义 Agent 角色与回答规范
QA_SYSTEM_PROMPT = """你是一个竞赛规则知识助手，专门回答关于"福州大学至诚学院学生文化科技创新竞赛等级分类"的问题。

请严格基于下方【知识库】中的内容回答问题。如果知识库中没有相关信息，请明确说明"知识库中未找到相关竞赛信息"，不要编造。

回答要求：
1. 优先给出竞赛的"级别"和"类别（A/B/C类）"
2. 简洁明了，直接回答用户问题
3. 如果涉及多个竞赛，逐条列出
4. 回答末尾标注信息来源（如"信息来源：竞赛等级分类表"）

【知识库】
{context}
"""


def answer_question(
    config_loader,
    vectorstore,
    llm,
    question: str,
    *,
    filter: Optional[Dict[str, Any]] = None,
    top_k: Optional[int] = None,
) -> Dict[str, Any]:
    """
    基于 RAG 回答用户问题。

    Args:
        config_loader: ConfigLoader 实例
        vectorstore: Chroma 向量库
        llm: LangChain ChatModel（由 build_chat_model 构造）
        question: 用户问题
        filter: 元数据过滤（如 {"category": "A"}）
        top_k: 检索条数覆盖

    Returns:
        {
            "answer": str,           # LLM 生成的回答
            "question": str,         # 原始问题
            "sources": List[Dict],   # 引用来源（竞赛名/级别/类别）
        }
    """
    # 1. 检索相关知识
    docs = retrieve(config_loader, vectorstore, question, filter=filter, top_k=top_k)
    context = format_context(docs)
    sources = [
        {
            "name": d.metadata.get("name", ""),
            "level": d.metadata.get("level", ""),
            "category": d.metadata.get("category", ""),
        }
        for d in docs
    ]

    # 2. 构造消息并调用 LLM
    messages = [
        {"role": "system", "content": QA_SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question},
    ]
    logger.info("QA Agent 回答问题: %r（检索到 %d 条）", question, len(docs))
    response = llm.invoke(messages)
    answer = response.content if hasattr(response, "content") else str(response)

    return {
        "answer": answer,
        "question": question,
        "sources": sources,
    }


def stream_answer(config_loader, vectorstore, llm, question: str,
                  *, filter=None, top_k=None):
    """流式 RAG 问答（T23）：逐 token yield，结束后 yield {'__sources__': [...]} 收尾标记。

    用法:
        for chunk in stream_answer(...):
            if isinstance(chunk, str):      # 增量文本
            else:                           # {'__sources__': [...]} 引用来源
    """
    docs = retrieve(config_loader, vectorstore, question, filter=filter, top_k=top_k)
    context = format_context(docs)
    sources = [
        {"name": d.metadata.get("name", ""), "level": d.metadata.get("level", ""),
         "category": d.metadata.get("category", "")}
        for d in docs
    ]
    # M1 输入截断：防超长 prompt 失控成本
    question = question[:4000]
    messages = [
        {"role": "system", "content": QA_SYSTEM_PROMPT.format(context=context)},
        {"role": "user", "content": question},
    ]
    logger.info("QA Agent 流式回答: %r（检索 %d 条）", question, len(docs))
    try:
        for chunk in llm.stream(messages):
            text = chunk.content if hasattr(chunk, "content") else str(chunk)
            if text:
                yield text
    except Exception as e:
        logger.warning("流式输出异常，降级为完整调用: %s", e)
        response = llm.invoke(messages)
        answer = response.content if hasattr(response, "content") else str(response)
        yield answer
    yield {"__sources__": sources}


__all__ = ["answer_question", "stream_answer", "QA_SYSTEM_PROMPT"]
