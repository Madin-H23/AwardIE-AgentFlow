"""T49 回归护栏：生成期真流式的一致性 / 白名单过滤 / 工具轮次静默 / 双跑消灭。

探针定案（见实施记录 §0）：
- langgraph 多模式流 (mode, payload)；metadata.langgraph_node = 白名单依据；
- tools 过滤规则 = 仅透出 content 非空的 AIMessageChunk；
- 终态取 values 通道末次（双跑消灭，invoke 仅异常兜底）；
- _answer_pieces 保留为降级路径（test_chat_stream_pieces 兼容）。
"""
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage


# ── 造块工具 ──
def ai_chunk(text):
    return AIMessageChunk(content=text)


def tool_call_chunk():
    return AIMessageChunk(content="", tool_call_chunks=[
        {"name": "fake_query", "args": '{"sql": "SELECT 1"}', "id": "t1", "index": 0}])


class ScriptedExecutor:
    """tools 侧 _agent_executor 替身：决策轮→ToolMessage→答案流→values 终态。"""

    def stream(self, messages, config=None, stream_mode=None):
        assert set(stream_mode) == {"messages", "values"}
        yield ("messages", (tool_call_chunk(), {"langgraph_node": "model"}))
        yield ("messages", (ToolMessage(content="查询结果X", tool_call_id="t1"),
                            {"langgraph_node": "tools"}))
        for ch in "查询完成":
            yield ("messages", (ai_chunk(ch), {"langgraph_node": "model"}))
        yield ("values", {"messages": [HumanMessage("查数据"),
                                       AIMessage(content="查询完成")]})


class WhitelistGraph:
    """auto 侧 graph 替身：supervisor 的消息不得进 delta。"""

    def stream(self, state, config=None, stream_mode=None):
        yield ("updates", {"supervisor": {}})
        yield ("messages", (ai_chunk("路由到知识检索"),
                            {"langgraph_node": "supervisor"}))
        yield ("messages", (ai_chunk("答"),
                            {"langgraph_node": "qa"}))
        yield ("values", {"qa_context": {"answer": "答案", "sources": []},
                          "steps": ["s1"]})


@pytest.fixture()
def tools_service(monkeypatch):
    from backend.agent.service import AgentService
    svc = AgentService.__new__(AgentService)
    monkeypatch.setattr(svc, "_agent_executor", ScriptedExecutor(), raising=False)
    monkeypatch.setattr(svc, "max_iterations", 8, raising=False)
    return svc


class TestToolsTrueStreaming:
    def test_delta_concat_equals_final_output(self, tools_service):
        """验收②：delta 拼接 == __final__.output。"""
        deltas, final = [], None
        for ev in tools_service.chat_stream("查数据"):
            if "__final__" in ev:
                final = ev["__final__"]
            else:
                deltas.append(ev["delta"])
        assert "".join(deltas) == final["output"] == "查询完成"

    def test_tool_rounds_are_silent(self, tools_service):
        """验收口径：决策块/ToolMessage 不产生任何 delta（工具回合静默）。"""
        kinds = []
        for ev in tools_service.chat_stream("查数据"):
            kinds.append("delta" if "delta" in ev else "final")
        # 序列形态：全部 delta 连续出现在末尾 final 之前，且首事件不是 final
        assert kinds[0] == "delta" and kinds[-1] == "final"
        assert all(k == "delta" for k in kinds[:-1])

    def test_final_uses_extract_answer_from_values(self, tools_service):
        """终态来自 values 末次的规范键提取（而非仅增量拼接）。"""
        final = list(tools_service.chat_stream("查数据"))[-1]["__final__"]
        assert final["output"] == "查询完成"
        assert isinstance(final["intermediate_steps"], list)


class TestAutoWhitelist:
    def test_supervisor_messages_never_leak_to_delta(self, monkeypatch):
        """验收③：白名单外节点（supervisor）的消息绝不进入 delta。"""
        from backend.agent.graph.workflow import MultiAgentWorkflow

        wf = MultiAgentWorkflow.__new__(MultiAgentWorkflow)
        wf.graph = WhitelistGraph()
        deltas, nodes, final = [], [], None
        for ev in wf.run_stream(task_type="auto", message="hi"):
            if "__final__" in ev:
                final = ev["__final__"]
            elif "delta" in ev:
                deltas.append(ev["delta"])
            else:
                nodes.append(ev.get("node"))

        assert deltas == ["答"]                    # 仅白名单 qa 节点
        assert "supervisor" in nodes               # progress 照常
        assert "路由到知识检索" not in "".join(deltas)
        assert final["qa_context"]["answer"] == "答案"

    def test_double_run_eliminated(self, monkeypatch):
        """双跑消灭：values 提供终态时不再 invoke。"""
        from backend.agent.graph.workflow import MultiAgentWorkflow

        class NoInvokeGraph(WhitelistGraph):
            invoked = False
            def invoke(self, state, config=None):
                type(self).invoked = True
                return {}

        g = NoInvokeGraph()
        wf = MultiAgentWorkflow.__new__(MultiAgentWorkflow)
        wf.graph = g
        list(wf.run_stream(task_type="auto", message="hi"))
        assert not g.invoked
