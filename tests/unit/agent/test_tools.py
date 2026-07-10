"""
Stage 2 单元测试：工具与 AgentService

覆盖可独立验证的部分（不依赖 langchain 真实安装 / 不调真实 LLM）：
- ToolContext 的路径解析与惰性构造（mock 验证属性被缓存）
- query_tools._award_to_dict / _competition_to_dict 序列化
- service._format_user_context / _summarize_steps 辅助函数

依赖 langchain @tool / create_tool_calling_agent 的端到端测试放在 integration。
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path

from config.loader import ConfigLoader
from backend.agent.tools.context import ToolContext, get_tool_context, reset_tool_context


@pytest.fixture
def config_loader():
    return ConfigLoader()


# ==================== ToolContext ====================

class TestToolContext:
    """工具上下文：路径解析与惰性构造"""

    def test_db_path_is_absolute(self, config_loader):
        ctx = ToolContext(config_loader)
        assert Path(ctx.db_path).is_absolute()
        assert ctx.db_path.endswith("competitions.db")

    def test_lazy_caching_award_manager(self, config_loader):
        """award_manager 应被缓存（cached_property），两次访问同一实例"""
        ctx = ToolContext(config_loader)
        # mock AwardManager 避免真实加载大数据库
        with patch("backend.models.award.AwardManager") as MockAM:
            MockAM.return_value = MagicMock(name="am1")
            am1 = ctx.award_manager
            am2 = ctx.award_manager
            assert am1 is am2  # 同一实例（缓存生效）
            MockAM.assert_called_once()  # 只构造一次

    def test_lazy_caching_competition_manager(self, config_loader):
        ctx = ToolContext(config_loader)
        with patch("backend.models.competition.CompetitionManager") as MockCM:
            MockCM.return_value = MagicMock()
            cm1 = ctx.competition_manager
            cm2 = ctx.competition_manager
            assert cm1 is cm2
            MockCM.assert_called_once()


class TestGlobalSingleton:
    """全局单例管理"""

    def test_get_and_reset(self, config_loader):
        reset_tool_context()
        ctx1 = get_tool_context(config_loader)
        ctx2 = get_tool_context()  # 不传 config_loader，应返回同一单例
        assert ctx1 is ctx2
        reset_tool_context()


# ==================== 序列化辅助函数 ====================

class TestSerializationHelpers:
    """_award_to_dict / _competition_to_dict 序列化"""

    def test_award_to_dict(self):
        from backend.agent.tools.query_tools import _award_to_dict
        award = MagicMock()
        award.id = 1
        award.competition_id = 5
        award.year = 2024
        award.competition_level = "国赛"
        award.award_level = "一等奖"
        award.track = None
        award.certificate_id = "CERT-001"
        award.issuer = "教育部"
        award.title = "测试"
        award.competition_name = "挑战杯"
        award.get_first_winner_info.return_value = {"name": "张三"}
        award.get_first_supervisor_info.return_value = {"name": "李老师"}
        award.get_team_count.return_value = 3

        d = _award_to_dict(award)
        assert d["id"] == 1
        assert d["year"] == 2024
        assert d["competition_level"] == "国赛"
        assert d["first_winner"]["name"] == "张三"
        assert d["team_count"] == 3

    def test_competition_to_dict(self):
        from backend.agent.tools.query_tools import _competition_to_dict
        comp = MagicMock()
        comp.id = 1
        comp.name = "挑战杯"
        comp.grade_category = "A"
        comp.is_white_list = 1
        comp.is_watch_list = 0
        comp.time_range = "3月-5月"
        comp.start_month = 3
        comp.end_month = 5
        comp.organizer = "共青团中央"
        comp.description = "学术科技作品竞赛"
        comp.aliases = ["挑战"]

        d = _competition_to_dict(comp)
        assert d["name"] == "挑战杯"
        assert d["grade_category"] == "A"
        assert d["is_white_list"] == 1


# ==================== AgentService 辅助函数 ====================

class TestAgentServiceHelpers:
    """service 模块的辅助函数"""

    def test_format_user_context_empty(self):
        from backend.agent.service import _format_user_context
        assert "未提供" in _format_user_context({})

    def test_format_user_context_with_role(self):
        from backend.agent.service import _format_user_context
        result = _format_user_context({"role": "teacher", "name": "张老师"})
        assert "teacher" in result
        assert "张老师" in result

    def test_extract_tool_steps(self):
        """从消息轨迹提取工具调用步骤（langchain 1.x 格式）"""
        from backend.agent.service import _extract_tool_steps
        from langchain_core.messages import AIMessage, ToolMessage

        messages = [
            AIMessage(content="", tool_calls=[{
                "id": "call_1", "name": "query_awards", "args": {"year": 2024}
            }]),
            ToolMessage(content='[{"id":1}]', tool_call_id="call_1"),
        ]
        steps = _extract_tool_steps(messages)
        assert len(steps) == 1
        assert steps[0]["tool"] == "query_awards"
        assert steps[0]["input"] == {"year": 2024}

    def test_extract_final_answer(self):
        """提取最终文本回答"""
        from backend.agent.service import _extract_final_answer
        from langchain_core.messages import AIMessage

        messages = [AIMessage(content="共3条奖状")]
        assert _extract_final_answer(messages) == "共3条奖状"
