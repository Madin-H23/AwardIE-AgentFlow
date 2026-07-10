"""
竞赛匹配器模块

提供竞赛名称和别名的匹配功能，从数据库 CompetitionManager 获取竞赛数据。
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, TYPE_CHECKING

from .utils import clean_text

if TYPE_CHECKING:
    from backend.models.competition import CompetitionManager

logger = logging.getLogger(__name__)


@dataclass
class Competition:
    """竞赛数据类"""
    id: int
    name: str
    aliases: List[str]

    def match(self, text: str) -> bool:
        """
        检查文本是否包含此竞赛的名称或别名

        Args:
            text: 待检查的文本

        Returns:
            是否匹配
        """
        clean_t = clean_text(text)
        # 检查正式名称
        if clean_text(self.name) in clean_t:
            return True
        # 检查别名
        for alias in self.aliases:
            if clean_text(alias) in clean_t:
                return True
        return False


class CompetitionMatcher:
    """
    竞赛匹配器类

    从数据库 CompetitionManager 加载竞赛数据，提供查询和匹配功能。
    使用单例模式确保全局只有一个实例。
    """

    _instance: Optional['CompetitionMatcher'] = None
    _competitions: List[Competition] = []
    _name_to_id: Dict[str, int] = {}
    _alias_to_name: Dict[str, str] = {}
    _is_loaded: bool = False
    _competition_manager: Optional['CompetitionManager'] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @classmethod
    def ensure_loaded(cls, db_path: Optional[str] = None, competition_manager: Optional['CompetitionManager'] = None) -> None:
        """
        确保竞赛配置已加载

        Args:
            db_path: 数据库文件路径（如果未提供 competition_manager）
            competition_manager: CompetitionManager 实例（优先使用）
        """
        if not cls._is_loaded:
            cls.load_from_database(db_path=db_path, competition_manager=competition_manager)

    @classmethod
    def load_from_database(cls, db_path: Optional[str] = None, competition_manager: Optional['CompetitionManager'] = None) -> None:
        """
        从数据库加载竞赛数据

        Args:
            db_path: 数据库文件路径（如果未提供 competition_manager）
            competition_manager: CompetitionManager 实例（优先使用）
        """
        try:
            # 优先使用传入的 CompetitionManager
            if competition_manager is None:
                if db_path is None:
                    logger.warning("未提供数据库路径或 CompetitionManager，无法加载竞赛数据")
                    return

                # 延迟导入，避免循环依赖
                from backend.models.competition import CompetitionManager
                competition_manager = CompetitionManager(db_path)

            cls._competition_manager = competition_manager

            # 清空现有数据
            cls._competitions = []
            cls._name_to_id = {}
            cls._alias_to_name = {}

            # 从 CompetitionManager 获取所有竞赛
            for comp in competition_manager.competitions:
                # 转换为 CompetitionMatcher 使用的 Competition 格式
                comp_wrapper = Competition(
                    id=comp.id,
                    name=comp.name,
                    aliases=comp.aliases
                )
                cls._competitions.append(comp_wrapper)
                cls._name_to_id[comp.name] = comp.id

                # 建立别名到名称的映射
                for alias in comp.aliases:
                    cls._alias_to_name[alias] = comp.name

            logger.info(f"从数据库加载了 {len(cls._competitions)} 个竞赛")
            cls._is_loaded = True

        except Exception as e:
            logger.error(f"从数据库加载竞赛数据失败: {e}", exc_info=True)
            cls._competitions = []
            cls._name_to_id = {}
            cls._alias_to_name = {}
            cls._is_loaded = False

    @classmethod
    def match(cls, text: str) -> Optional[str]:
        """
        从文本中匹配竞赛名称

        Args:
            text: OCR 识别的文本

        Returns:
            匹配到的竞赛名称，未匹配返回 None
        """
        if not text or not cls._competitions:
            return None

        # 按优先级匹配：正式名称 > 别名
        for comp in cls._competitions:
            if comp.match(text):
                logger.debug(f"匹配到竞赛: {comp.name}")
                return comp.name

        return None

    @classmethod
    def match_by_name(cls, name: str) -> Optional[Competition]:
        """
        根据竞赛名称获取竞赛对象

        Args:
            name: 竞赛名称

        Returns:
            竞赛对象，未找到返回 None
        """
        comp_id = cls._name_to_id.get(name)
        if comp_id is not None:
            for comp in cls._competitions:
                if comp.id == comp_id:
                    return comp
        return None

    @classmethod
    def get_all_competitions(cls) -> List[Competition]:
        """获取所有竞赛"""
        return cls._competitions.copy()

    @classmethod
    def get_competition_count(cls) -> int:
        """获取竞赛数量"""
        return len(cls._competitions)
