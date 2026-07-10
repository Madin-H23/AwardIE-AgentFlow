"""
查询类工具：奖状查询、竞赛查询。

封装 AwardManager / CompetitionManager 的查询方法为 LangChain @tool。
只读，无副作用。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _award_to_dict(award, competition_name: Optional[str] = None) -> Dict[str, Any]:
    """把 Award 对象序列化为可 JSON 化的 dict。"""
    return {
        "id": getattr(award, "id", None),
        "competition_id": getattr(award, "competition_id", None),
        "competition_name": competition_name or getattr(award, "competition_name", None),
        "year": getattr(award, "year", None),
        "competition_level": getattr(award, "competition_level", None),
        "award_level": getattr(award, "award_level", None),
        "track": getattr(award, "track", None),
        "certificate_id": getattr(award, "certificate_id", None),
        "issuer": getattr(award, "issuer", None),
        "title": getattr(award, "title", None),
        "first_winner": award.get_first_winner_info() if hasattr(award, "get_first_winner_info") else None,
        "first_supervisor": award.get_first_supervisor_info() if hasattr(award, "get_first_supervisor_info") else None,
        "team_count": award.get_team_count() if hasattr(award, "get_team_count") else None,
    }


def _competition_to_dict(comp) -> Dict[str, Any]:
    """把 Competition 对象序列化为可 JSON 化的 dict。"""
    return {
        "id": getattr(comp, "id", None),
        "name": getattr(comp, "name", None),
        "grade_category": getattr(comp, "grade_category", None),
        "is_white_list": getattr(comp, "is_white_list", None),
        "is_watch_list": getattr(comp, "is_watch_list", None),
        "time_range": getattr(comp, "time_range", None),
        "start_month": getattr(comp, "start_month", None),
        "end_month": getattr(comp, "end_month", None),
        "organizer": getattr(comp, "organizer", None),
        "description": getattr(comp, "description", None),
        "aliases": getattr(comp, "aliases", None),
    }


def make_query_awards_tool(ctx):
    """
    构造"查询奖状"工具。

    使用闭包注入 ToolContext（避免 LangChain @tool 难以传依赖的问题）。

    支持按 指导教师 / 获奖学生 / 年份 / 竞赛级别 / 奖项级别 等组合查询。
    """
    from langchain_core.tools import tool

    @tool
    def query_awards(
        supervisor_name: Optional[str] = None,
        winner_name: Optional[str] = None,
        year: Optional[int] = None,
        competition_level: Optional[str] = None,
        award_level: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        查询奖状记录。可按指导教师姓名、获奖学生姓名、年份、竞赛级别（国赛/省赛/校赛）、奖项级别（一等奖/二等奖等）组合筛选。

        示例：
        - 查某老师2024年指导的奖状：supervisor_name="张三", year=2024
        - 查所有国赛一等奖：competition_level="国赛", award_level="一等奖"

        Args:
            supervisor_name: 指导教师姓名（模糊）
            winner_name: 获奖学生姓名（模糊）
            year: 年份
            competition_level: 竞赛级别，如 国赛/省赛/校赛/国际赛
            award_level: 奖项级别，如 一等奖/二等奖/金奖
            limit: 最多返回条数（默认20）

        Returns:
            奖状信息列表
        """
        try:
            awards = ctx.award_manager.query_awards(
                supervisor_name=supervisor_name,
                winner_name=winner_name,
                year=year,
                competition_level=competition_level,
                award_level=award_level,
                limit=limit,
            )
            result = [_award_to_dict(a) for a in awards]
            logger.info("query_awards 命中 %d 条", len(result))
            return result
        except Exception as e:
            logger.exception("query_awards 失败: %s", e)
            return [{"error": f"查询失败: {e}"}]

    return query_awards


def make_match_competition_tool(ctx):
    """构造"竞赛匹配"工具：用自然语言/模糊名称匹配竞赛。"""
    from langchain_core.tools import tool

    @tool
    def match_competition(query_name: str) -> Optional[Dict[str, Any]]:
        """
        通过竞赛名称或别名模糊匹配一个竞赛，返回其等级、白名单状态等信息。

        当用户提到一个竞赛名（可能不精确）时使用此工具确认具体竞赛。

        Args:
            query_name: 竞赛名称（可以是别名或简称，如"挑战杯""数模"）

        Returns:
            匹配到的竞赛信息，未匹配返回 None
        """
        try:
            comp = ctx.competition_manager.match_competition(query_name)
            if comp is None:
                return None
            return _competition_to_dict(comp)
        except Exception as e:
            logger.exception("match_competition 失败: %s", e)
            return {"error": f"匹配失败: {e}"}

    return match_competition


def make_get_competition_tool(ctx):
    """构造"查竞赛详情"工具：按 ID 查竞赛。"""
    from langchain_core.tools import tool

    @tool
    def get_competition_by_id(competition_id: int) -> Optional[Dict[str, Any]]:
        """
        按竞赛 ID 查询竞赛详情（等级、白名单、举办时间等）。

        Args:
            competition_id: 竞赛 ID

        Returns:
            竞赛详情，不存在返回 None
        """
        try:
            comp = ctx.competition_manager.get_competition_by_id(competition_id)
            if comp is None:
                return None
            return _competition_to_dict(comp)
        except Exception as e:
            logger.exception("get_competition_by_id 失败: %s", e)
            return {"error": f"查询失败: {e}"}

    return get_competition_by_id


def make_check_whitelist_tool(ctx):
    """构造"白名单判断"工具：判断竞赛是否白名单。"""
    from langchain_core.tools import tool

    @tool
    def is_white_list_competition(competition_name: str) -> Dict[str, Any]:
        """
        判断一个竞赛是否属于白名单赛事（官方认可的高质量竞赛）。

        Args:
            competition_name: 竞赛名称

        Returns:
            {"competition_name": str, "is_white_list": bool, "matched": bool}
        """
        try:
            is_wl = ctx.competition_manager.is_white_list_competion(competition_name)
            return {
                "competition_name": competition_name,
                "is_white_list": bool(is_wl),
                "matched": is_wl is not None,
            }
        except Exception as e:
            logger.exception("is_white_list_competition 失败: %s", e)
            return {"competition_name": competition_name, "error": str(e)}

    return is_white_list_competition


__all__ = [
    "make_query_awards_tool",
    "make_match_competition_tool",
    "make_get_competition_tool",
    "make_check_whitelist_tool",
]
