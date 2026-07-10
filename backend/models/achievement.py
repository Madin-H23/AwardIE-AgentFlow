"""
成果抽象基类
支持多种成果类型：获奖（奖状）、立项通知、软件著作权、论文
"""
from abc import ABC, abstractmethod
from typing import List, Optional, TYPE_CHECKING
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field

if TYPE_CHECKING:
    from backend.models.student import Student
    from backend.models.teacher import Teacher

logger = __import__('logging').getLogger(__name__)


class AchievementType(str, Enum):
    """成果类型枚举"""
    AWARD = "award"                      # 获奖（奖状）
    PROJECT_APPROVAL = "project_approval"  # 立项通知
    COPYRIGHT = "copyright"              # 软件著作权
    PAPER = "paper"                      # 论文


@dataclass
class Achievement(ABC):
    """
    成果抽象基类
    
    所有成果类型的共同属性：
    - 基本信息：id, title, description, date
    - 成果类型：achievement_type
    - 关联的活动：activity_ids（多对多关系）
    - 参与者：participants（students, teachers）
    - 佐证材料：evidence_file_path
    """
    # 基本信息
    id: Optional[int] = None
    title: str = ""  # 成果标题
    description: Optional[str] = None  # 成果描述
    date: Optional[str] = None  # 日期（YYYY-MM-DD）
    
    # 成果类型
    achievement_type: AchievementType = AchievementType.AWARD
    
    # 关联的活动ID列表（多对多关系）
    activity_ids: List[int] = field(default_factory=list, init=False, repr=False)
    
    # 参与者（对象引用，不存储在基类中）
    participants_students: List['Student'] = field(default_factory=list, init=False, repr=False)
    participants_teachers: List['Teacher'] = field(default_factory=list, init=False, repr=False)
    
    # 佐证材料路径
    evidence_file_path: Optional[str] = None
    
    # 创建和更新时间
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @abstractmethod
    def get_display_name(self) -> str:
        """获取成果的显示名称"""
        pass
    
    @abstractmethod
    def validate(self) -> bool:
        """验证成果数据的有效性"""
        pass
    
    def add_activity(self, activity_id: int):
        """添加关联的活动ID"""
        if activity_id not in self.activity_ids:
            self.activity_ids.append(activity_id)
    
    def remove_activity(self, activity_id: int):
        """移除关联的活动ID"""
        if activity_id in self.activity_ids:
            self.activity_ids.remove(activity_id)
    
    def is_associated_with_activity(self, activity_id: int) -> bool:
        """检查是否与指定活动关联"""
        return activity_id in self.activity_ids
    
    def __str__(self) -> str:
        """转换为字符串表示"""
        parts = [
            f"成果类型: {self.achievement_type.value}",
            f"标题: {self.title}"
        ]
        if self.date:
            parts.append(f"日期: {self.date}")
        if self.description:
            parts.append(f"描述: {self.description}")
        return "\n".join(parts)


@dataclass
class AwardAchievement(Achievement):
    """获奖成果（奖状）"""
    award_id: Optional[int] = None  # 关联的奖状ID
    
    def __post_init__(self):
        self.achievement_type = AchievementType.AWARD
    
    def get_display_name(self) -> str:
        """获取成果的显示名称"""
        return f"获奖：{self.title}" if self.title else "获奖"
    
    def validate(self) -> bool:
        """验证成果数据的有效性"""
        return self.award_id is not None


@dataclass
class ProjectApprovalAchievement(Achievement):
    """立项通知成果（大创）"""
    project_number: Optional[str] = None  # 立项编号
    start_date: Optional[str] = None  # 起始日期（YYYY-MM-DD）
    end_date: Optional[str] = None    # 结束日期（YYYY-MM-DD）
    
    def __post_init__(self):
        self.achievement_type = AchievementType.PROJECT_APPROVAL
    
    def get_display_name(self) -> str:
        """获取成果的显示名称"""
        if self.project_number:
            return f"立项通知：{self.title}（编号：{self.project_number}）"
        return f"立项通知：{self.title}" if self.title else "立项通知"
    
    def validate(self) -> bool:
        """验证成果数据的有效性"""
        return bool(self.title and self.project_number)


@dataclass
class CopyrightAchievement(Achievement):
    """软件著作权成果"""
    copyright_name: Optional[str] = None  # 著作权名称
    registration_date: Optional[str] = None  # 登记日期（YYYY-MM-DD）
    
    def __post_init__(self):
        self.achievement_type = AchievementType.COPYRIGHT
        if not self.title and self.copyright_name:
            self.title = self.copyright_name
    
    def get_display_name(self) -> str:
        """获取成果的显示名称"""
        if self.copyright_name:
            return f"软件著作权：{self.copyright_name}"
        return f"软件著作权：{self.title}" if self.title else "软件著作权"
    
    def validate(self) -> bool:
        """验证成果数据的有效性"""
        return bool(self.copyright_name or self.title)


@dataclass
class PaperAchievement(Achievement):
    """论文成果"""
    paper_name: Optional[str] = None  # 论文名称
    publication_name: Optional[str] = None  # 发表刊物
    publication_date: Optional[str] = None  # 发表日期（YYYY-MM-DD）
    
    def __post_init__(self):
        self.achievement_type = AchievementType.PAPER
        if not self.title and self.paper_name:
            self.title = self.paper_name
        if not self.date and self.publication_date:
            self.date = self.publication_date
    
    def get_display_name(self) -> str:
        """获取成果的显示名称"""
        if self.paper_name:
            return f"论文：{self.paper_name}"
        return f"论文：{self.title}" if self.title else "论文"
    
    def validate(self) -> bool:
        """验证成果数据的有效性"""
        return bool(self.paper_name or self.title)

