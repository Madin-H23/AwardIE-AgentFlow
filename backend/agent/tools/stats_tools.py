"""
统计类工具：竞赛贡献度排名、获奖趋势、热力图等。

封装 DataAnalysisManager 的统计方法为 LangChain @tool。只读。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def make_list_competitions_tool(ctx):
    """构造"列出有奖状的竞赛"工具。"""
    from langchain_core.tools import tool

    @tool
    def list_competitions_with_awards() -> List[Dict[str, Any]]:
        """
        列出所有有奖状记录的竞赛，含每个竞赛的奖状数量、举办月份等。

        用于概览系统中有哪些竞赛及其活跃度。无参数。

        Returns:
            竞赛列表，每项含 id/name/award_count/start_month/end_month
        """
        try:
            return ctx.data_analysis_manager.get_competitions_with_awards()
        except Exception as e:
            logger.exception("list_competitions_with_awards 失败: %s", e)
            return [{"error": str(e)}]

    return list_competitions_with_awards


def make_contribution_ranking_tool(ctx):
    """构造"竞赛贡献度排名"工具。"""
    from langchain_core.tools import tool

    @tool
    def get_competition_contribution(
        year: Optional[int] = None,
        white_list_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        按奖状数量对竞赛做贡献度排名（哪些竞赛贡献的奖状最多）。

        Args:
            year: 限定年份，None 则全部年份
            white_list_only: 是否只统计白名单赛事（默认 False）

        Returns:
            排名列表，每项含 competition_id/name/award_count
        """
        try:
            years = [year] if year else None
            return ctx.data_analysis_manager.get_competition_contribution(
                years=years,
                white_list_only=white_list_only,
            )
        except Exception as e:
            logger.exception("get_competition_contribution 失败: %s", e)
            return [{"error": str(e)}]

    return get_competition_contribution


def make_competition_trend_tool(ctx):
    """构造"竞赛获奖趋势"工具。"""
    from langchain_core.tools import tool

    @tool
    def get_competition_trend(competition_id: int) -> Dict[str, Any]:
        """
        查询某竞赛历年的获奖数量趋势。

        Args:
            competition_id: 竞赛 ID

        Returns:
            {"years": [2022,2023,...], "counts": [N,...]}
        """
        try:
            return ctx.data_analysis_manager.get_competition_trend(competition_id)
        except Exception as e:
            logger.exception("get_competition_trend 失败: %s", e)
            return {"error": str(e)}

    return get_competition_trend


def make_heatmap_tool(ctx):
    """构造"竞赛热力图"工具。"""
    from langchain_core.tools import tool

    @tool
    def get_competition_heatmap(competition_id: int) -> Dict[str, Any]:
        """
        获取某竞赛奖状的年×月热力图数据，用于分析获奖的时间分布规律。

        Args:
            competition_id: 竞赛 ID

        Returns:
            {"years": [...], "months": [1..12], "data": 二维矩阵}
        """
        try:
            return ctx.data_analysis_manager.get_competition_heatmap(competition_id)
        except Exception as e:
            logger.exception("get_competition_heatmap 失败: %s", e)
            return {"error": str(e)}

    return get_competition_heatmap


__all__ = [
    "make_list_competitions_tool",
    "make_contribution_ranking_tool",
    "make_competition_trend_tool",
    "make_heatmap_tool",
]
