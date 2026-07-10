"""
模板管理模块

提供证书模板的创建、管理、匹配等功能。
支持奖状、专利、软著三种类型的证书模板。

主要类:
    Template: 证书模板类
    TemplateManager: 模板管理器
    TemplateMatcher: 模板匹配器
    TypeMatcher: 类型识别器
    CompetitionMatcher: 竞赛名称匹配器
    MatchResult: 匹配结果数据类

使用示例:
    >>> from backend.extract.template import TemplateManager
    >>>
    >>> # 初始化管理器（使用正确的验证数据库）
    >>> manager = TemplateManager(db_path="database/competitions.db")
    >>>
    >>> # 匹配模板
    >>> result = manager.match_full("蓝桥杯省赛获奖证书")
    >>> if result.template:
    >>>     print(f"匹配到模板: {result.template.get_display_name()}")
"""

from .template import Template
from .manager import TemplateManager
from .matcher import TemplateMatcher, TypeMatcher, MatchResult
from .competition import CompetitionMatcher, Competition

__all__ = [
    "Template",
    "TemplateManager",
    "TemplateMatcher",
    "TypeMatcher",
    "MatchResult",
    "CompetitionMatcher",
    "Competition",
]
