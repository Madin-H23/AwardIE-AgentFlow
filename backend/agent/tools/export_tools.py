"""
导出类工具：生成年度成果汇总报表。

封装 export_utils.generate_department_summary_reports 为 LangChain @tool。
导出函数返回 bytes，在 Tool 内落盘到 output 目录后返回文件路径给 LLM/前端。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _get_export_dir(ctx) -> Path:
    """获取/创建导出目录（output/agent_reports/）。"""
    export_dir = ctx.config_loader.project_root / "output" / "agent_reports"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def make_export_report_tool(ctx):
    """构造"导出年度报表"工具。"""
    from langchain_core.tools import tool

    @tool
    def export_annual_report(
        year: Optional[int] = None,
        teacher_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        生成系年度学科竞赛等学生成果汇总报表（Excel + HTML 双格式），
        并保存到本地，返回文件路径。

        适用场景：用户要求"导出2024年成果汇总""生成马老师的指导成果报表"等。

        Args:
            year: 年份筛选，None 则全部
            teacher_name: 指导教师姓名筛选，None 则全部教师

        Returns:
            {"excel_path": str, "html_path": str, "title": str, "count": int}
        """
        try:
            from backend.utils import export_utils

            # 1. 取该条件下的奖状
            awards = ctx.award_manager.query_awards(
                supervisor_name=teacher_name,
                year=year,
                limit=100000,
            )
            if not awards:
                return {"error": "未找到符合条件的奖状数据", "count": 0}

            # 2. 生成报表（返回 excel_bytes, html_str, excel_filename, html_filename, title）
            excel_bytes, html_str, excel_filename, html_filename, title = (
                export_utils.generate_department_summary_reports(
                    awards,
                    ctx.competition_manager,
                    laboratory_manager=ctx.laboratory_manager,
                    year=year,
                    teacher_name=teacher_name,
                )
            )

            # 3. 落盘
            export_dir = _get_export_dir(ctx)
            excel_path = export_dir / excel_filename
            html_path = export_dir / html_filename
            excel_path.write_bytes(excel_bytes)
            html_path.write_text(html_str, encoding="utf-8")

            logger.info("导出报表完成: %s（%d 条奖状）", excel_filename, len(awards))
            return {
                "excel_path": str(excel_path),
                "html_path": str(html_path),
                "title": title,
                "count": len(awards),
            }
        except Exception as e:
            logger.exception("export_annual_report 失败: %s", e)
            return {"error": f"导出失败: {e}"}

    return export_annual_report


__all__ = ["make_export_report_tool"]
