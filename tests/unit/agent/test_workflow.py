"""
Stage 3 单元测试：多智能体工作流

覆盖纯逻辑部分（不依赖 langgraph 真实安装）：
- supervisor._decide_next: 路由决策逻辑
- extraction_agent._estimate_confidence: 置信度估计
- review_agent: 规则校验逻辑（必填字段/级别/角色/建议生成）

依赖 langgraph StateGraph 的端到端测试放在 integration。
"""
import pytest
from unittest.mock import MagicMock

from backend.agent.graph.supervisor import (
    _decide_next,
    ROUTE_EXTRACTION,
    ROUTE_REVIEW,
    ROUTE_QA,
    ROUTE_TOOLS,
    ROUTE_FINISH,
)


# ==================== Supervisor 路由决策 ====================

class TestSupervisorRouting:
    """Supervisor 的路由决策逻辑"""

    def test_extract_and_review_starts_with_extraction(self):
        """extract_and_review 任务：无抽取结果时路由到 extraction"""
        state = {"task_type": "extract_and_review", "file_path": "/a.jpg"}
        assert _decide_next(state, "extract_and_review", None) == ROUTE_EXTRACTION

    def test_extract_and_review_after_extraction_goes_review(self):
        """已有抽取结果，路由到 review"""
        state = {
            "task_type": "extract_and_review",
            "extraction_result": {"doc_type": "award", "data": {"x": 1}},
        }
        assert _decide_next(state, "extract_and_review", None) == ROUTE_REVIEW

    def test_extract_and_review_after_review_finishes(self):
        """已有审核结果，结束"""
        state = {
            "task_type": "extract_and_review",
            "extraction_result": {"data": {}},
            "review_result": {"decision": "pass"},
        }
        assert _decide_next(state, "extract_and_review", None) == ROUTE_FINISH

    def test_qa_task_routes_to_qa(self):
        state = {"task_type": "qa"}
        assert _decide_next(state, "qa", None) == ROUTE_QA

    def test_stats_task_routes_to_tools(self):
        state = {"task_type": "stats"}
        assert _decide_next(state, "stats", None) == ROUTE_TOOLS

    def test_export_task_routes_to_tools(self):
        state = {"task_type": "export"}
        assert _decide_next(state, "export", None) == ROUTE_TOOLS

    def test_query_task_routes_to_tools(self):
        state = {"task_type": "query"}
        assert _decide_next(state, "query", None) == ROUTE_TOOLS

    def test_tools_task_routes_to_tools(self):
        """显式 tools 任务类型路由到 tools 节点"""
        state = {"task_type": "tools"}
        assert _decide_next(state, "tools", None) == ROUTE_TOOLS

    def test_no_task_type_no_llm_finishes(self):
        """无 task_type 且无 LLM，兜底 FINISH"""
        state = {"task_type": None}
        assert _decide_next(state, None, None) == ROUTE_FINISH


# ==================== 抽取置信度估计 ====================

class TestExtractionConfidence:
    """_estimate_confidence 置信度估计"""

    def test_empty_data_zero(self):
        from backend.agent.graph.extraction_agent import _estimate_confidence
        result = MagicMock()
        result.data = {}
        assert _estimate_confidence(result) == 0.0

    def test_partial_data(self):
        from backend.agent.graph.extraction_agent import _estimate_confidence
        result = MagicMock()
        result.data = {"competition_name": "挑战杯", "winner": "张三", "year": ""}
        # 2 个有效字段 / 8 = 0.25
        assert _estimate_confidence(result) == 0.25

    def test_full_data_capped_at_1(self):
        from backend.agent.graph.extraction_agent import _estimate_confidence
        result = MagicMock()
        result.data = {f"f{i}": f"v{i}" for i in range(10)}
        assert _estimate_confidence(result) == 1.0  # 上限 1.0


# ==================== 审核规则校验 ====================

class TestReviewRules:
    """review_agent 的规则校验逻辑"""

    def test_check_required_fields_missing(self):
        from backend.agent.graph.review_agent import _check_required_fields
        # 完全空数据
        issues = _check_required_fields({})
        assert len(issues) == 3  # 三个必填字段都缺
        assert all(i["severity"] == "high" for i in issues)

    def test_check_required_fields_present(self):
        from backend.agent.graph.review_agent import _check_required_fields
        data = {"competition_name": "挑战杯", "winner": "张三", "award_level": "一等奖"}
        issues = _check_required_fields(data)
        assert len(issues) == 0

    def test_check_required_fields_winner_name_alias(self):
        """抽取器输出 winner_name 时应兼容（不报缺失）"""
        from backend.agent.graph.review_agent import _check_required_fields
        data = {"competition_name": "挑战杯", "winner_name": "张三", "award_level": "一等奖"}
        issues = _check_required_fields(data)
        assert len(issues) == 0

    def test_get_field_alias(self):
        """_get_field 支持候选字段名"""
        from backend.agent.graph.review_agent import _get_field
        assert _get_field({"winner_name": "张三"}, ["winner", "winner_name"]) == "张三"
        assert _get_field({"winner": "李四"}, ["winner", "winner_name"]) == "李四"
        assert _get_field({}, ["winner", "winner_name"]) is None

    def test_check_award_level_invalid(self):
        from backend.agent.graph.review_agent import _check_award_level
        valid = {"一等奖", "二等奖", "三等奖"}
        issues = _check_award_level({"award_level": "特优奖"}, valid)
        assert len(issues) == 1
        assert issues[0]["severity"] == "medium"

    def test_check_award_level_valid(self):
        from backend.agent.graph.review_agent import _check_award_level
        valid = {"一等奖", "二等奖"}
        issues = _check_award_level({"award_level": "一等奖"}, valid)
        assert len(issues) == 0

    def test_check_roles_invalid(self):
        from backend.agent.graph.review_agent import _check_roles
        issues = _check_roles({"winner_role": "助教", "supervisor_role": "学生"})
        # "助教" 不合法，"学生" 合法
        assert len(issues) == 1
        assert issues[0]["field"] == "winner_role"


class TestReviewSuggestion:
    """审核建议生成"""

    def test_pass_suggestion(self):
        from backend.agent.graph.review_agent import _build_suggestion
        s = _build_suggestion("pass", [])
        assert "通过" in s

    def test_reject_suggestion(self):
        from backend.agent.graph.review_agent import _build_suggestion
        issues = [{"field": "winner", "issue": "缺少获奖人", "severity": "high"}]
        s = _build_suggestion("reject", issues)
        assert "未通过" in s
        assert "缺少获奖人" in s

    def test_need_manual_suggestion(self):
        from backend.agent.graph.review_agent import _build_suggestion
        issues = [{"field": "level", "issue": "级别可疑", "severity": "medium"}]
        s = _build_suggestion("need_manual", issues)
        assert "人工" in s


# ==================== QA 节点：消息提取 ====================

class TestQAExtractQuestion:
    """qa_agent_node 的消息提取"""

    def test_extract_from_dict_messages(self):
        from backend.agent.graph.qa_agent_node import _extract_user_question
        msgs = [
            {"role": "user", "content": "挑战杯是什么级别"},
            {"role": "assistant", "content": "..."},
            {"role": "user", "content": "白名单吗"},
        ]
        assert _extract_user_question(msgs) == "白名单吗"

    def test_extract_empty(self):
        from backend.agent.graph.qa_agent_node import _extract_user_question
        assert _extract_user_question([]) == ""
