"""
工具上下文（依赖注入容器）

统一构造并缓存各 Manager / Framework 实例，供 Tool 共享。

为什么需要它？
- AwardManager / CompetitionManager 构造时会全量加载数据库到内存，开销大，必须单例
- 各 Tool 需要访问 db_path / config_loader / ExtractFramework，集中管理避免散落
- 类似 backend/services/context.py 的 ServiceContext 模式，保持架构一致

惰性构造：只有首次访问某属性时才实例化，避免启动时全量初始化（测试/轻量场景友好）。
"""
from __future__ import annotations

import logging
from functools import cached_property
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ToolContext:
    """
    工具上下文：缓存 Manager / Framework 单例。

    通过 config_loader 驱动一切路径与配置（遵守"配置驱动"规范）。

    用法：
        ctx = ToolContext(config_loader)
        ctx.award_manager.query_awards(...)
        ctx.extract_framework.extract(file_path)
    """

    def __init__(self, config_loader):
        self.config_loader = config_loader

    # ==================== 路径 ====================

    @property
    def db_path(self) -> str:
        """主业务数据库路径（绝对路径）。"""
        return self.config_loader.get_path_str("database", "competitions_db")

    # ==================== 惰性构造的 Manager ====================

    @cached_property
    def award_manager(self):
        """AwardManager 单例（构造时全量加载，开销大，必须缓存）。"""
        from backend.models.award import AwardManager
        images_dir = self.config_loader.get_path("files")
        logger.info("初始化 AwardManager (db=%s)", self.db_path)
        return AwardManager(self.db_path, images_dir=images_dir)

    @cached_property
    def competition_manager(self):
        """CompetitionManager 单例。"""
        from backend.models.competition import CompetitionManager
        logger.info("初始化 CompetitionManager (db=%s)", self.db_path)
        return CompetitionManager(self.db_path)

    @cached_property
    def data_analysis_manager(self):
        """DataAnalysisManager 单例。"""
        from backend.managers.data_analysis_manager import DataAnalysisManager
        logger.info("初始化 DataAnalysisManager (db=%s)", self.db_path)
        return DataAnalysisManager(self.db_path)

    @cached_property
    def extract_framework(self):
        """
        ExtractFramework 单例（OCR + LLM 抽取流水线）。

        复用项目已有的 ServiceContext.extract_framework，它已正确注册了
        Innovation/Patent/Software/Award 四个业务抽取器（含 template_manager）。
        不在此处重新构造空框架，否则抽取器未注册会导致抽取功能失效。
        """
        from backend.services.context import get_context
        logger.info("获取 ExtractFramework（复用 ServiceContext，含已注册抽取器）")
        return get_context().extract_framework

    @cached_property
    def laboratory_manager(self):
        """LaboratoryManager 单例（导出报表时可能需要）。"""
        from backend.models.laboratory import LaboratoryManager
        logger.info("初始化 LaboratoryManager (db=%s)", self.db_path)
        return LaboratoryManager(self.db_path)


# 全局单例（按需创建）
_tool_context: Optional[ToolContext] = None


def get_tool_context(config_loader=None) -> ToolContext:
    """
    获取全局 ToolContext 单例。

    Args:
        config_loader: 首次创建时传入；后续调用可不传

    Returns:
        ToolContext 实例
    """
    global _tool_context
    if _tool_context is None:
        if config_loader is None:
            from config.loader import get_config
            config_loader = get_config()
        _tool_context = ToolContext(config_loader)
    return _tool_context


def reset_tool_context():
    """重置全局单例（测试用）。"""
    global _tool_context
    _tool_context = None


__all__ = ["ToolContext", "get_tool_context", "reset_tool_context"]
