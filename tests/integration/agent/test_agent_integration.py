"""
Agent integration 测试

验证单 Agent 工具调用与多智能体工作流（需真实 API）。
固化了联调中验证的成果：工具调用、Supervisor 路由、抽取审核链路。

运行：RUN_AGENT_INTEGRATION=1 python -m pytest tests/integration/agent/test_agent_integration.py -v
"""
import pytest
from pathlib import Path
from tests.integration.agent.conftest import skip_if_no_integration

pytestmark = [skip_if_no_integration]

# 真实测试奖状图片
AWARD_IMAGE = str(Path(__file__).resolve().parents[2] / "test_images" / "award" / "chinese" / "2024数据安全-李杰-省赛-二等奖.jpg")


class TestSingleAgent:
    """单 Agent 工具调用"""

    def test_agent_stats_query(self, config_loader):
        """Agent 应自主选择统计工具回答竞赛排行"""
        from backend.agent.service import AgentService
        service = AgentService.from_config(config_loader)
        result = service.chat("哪些竞赛贡献的奖状最多？列前2名。", user_context={"role": "admin"})
        assert result["output"], "Agent 应有回答"
        # 应调用了工具（get_competition_contribution 或 list_competitions）
        tool_names = [s.get("tool", "") for s in result["intermediate_steps"]]
        assert any("competition" in t or "list" in t for t in tool_names), f"未调用统计工具: {tool_names}"

    def test_agent_whitelist_query(self, config_loader):
        """Agent 应调用白名单判断工具"""
        from backend.agent.service import AgentService
        service = AgentService.from_config(config_loader)
        result = service.chat("蓝桥杯是不是白名单赛事？", user_context={"role": "admin"})
        assert "蓝桥杯" in result["output"] or "白名单" in result["output"]


class TestMultiAgentWorkflow:
    """多智能体工作流"""

    def test_tools_routing(self, config_loader, vectorstore):
        """tools 任务：Supervisor 应路由到 tools 节点并完成"""
        from backend.agent.graph.workflow import MultiAgentWorkflow
        wf = MultiAgentWorkflow.from_config(config_loader, vectorstore=vectorstore)
        result = wf.run(task_type="tools", message="蓝桥杯是不是白名单？", user_context={"role": "admin"})
        agents = [s.get("agent") for s in result.get("steps", [])]
        assert "supervisor" in agents
        assert "tools" in agents  # 路由到了 tools 节点
        # 最终应 FINISH
        assert any(s.get("decision") == "FINISH" for s in result.get("steps", []) if s.get("agent") == "supervisor")

    def test_extract_review_pipeline(self, config_loader, vectorstore):
        """核心链路：抽取→审核 应完整执行"""
        from backend.agent.graph.workflow import MultiAgentWorkflow
        wf = MultiAgentWorkflow.from_config(config_loader, vectorstore=vectorstore)
        result = wf.run(task_type="extract_and_review", file_path=AWARD_IMAGE, user_context={"role": "admin"})

        # 1. 抽取应成功
        ex = result.get("extraction_result") or {}
        assert ex.get("doc_type") == "award", f"应识别为 award: {ex.get('doc_type')}"
        assert ex.get("data", {}).get("winner_name"), "应抽取到获奖人"

        # 2. 审核应执行
        rv = result.get("review_result") or {}
        assert rv.get("decision") in ("pass", "need_manual", "reject"), f"审核决策异常: {rv.get('decision')}"
        assert "suggestion" in rv, "应有审核建议"

        # 3. 流程应结束
        assert result.get("steps"), "应有执行轨迹"
