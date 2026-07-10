"""
成果管理器
管理活动的各种成果：获奖、立项通知、软件著作权、论文
"""
import sqlite3
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from backend.models.achievement import (
    Achievement, AchievementType,
    AwardAchievement, ProjectApprovalAchievement,
    CopyrightAchievement, PaperAchievement
)
from backend.models.award import Award, AwardManager
from backend.models.student import StudentManager
from backend.models.teacher import TeacherManager

logger = logging.getLogger(__name__)


class AchievementManager:
    """成果管理器"""
    
    def __init__(
        self,
        db_path: str,
        award_manager: Optional[AwardManager] = None,
        student_manager: Optional[StudentManager] = None,
        teacher_manager: Optional[TeacherManager] = None
    ):
        """
        初始化成果管理器
        
        Args:
            db_path: 数据库路径
            award_manager: 奖状管理器（可选）
            student_manager: 学生管理器（可选）
            teacher_manager: 教师管理器（可选）
        """
        self.db_path = db_path
        self.award_manager = award_manager
        self.student_manager = student_manager
        self.teacher_manager = teacher_manager
        
        # 内存缓存
        self.achievements: List[Achievement] = []
        self._achievements_by_id: Dict[int, Achievement] = {}
        self._achievements_by_activity: Dict[int, List[Achievement]] = {}
        
        # 初始化数据库表（已在迁移脚本中创建）
        # 这里不需要再创建表，只需要加载数据
        self._load_all_from_db()
    
    def _get_db_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def _load_all_from_db(self):
        """从数据库加载所有成果"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 加载主表数据
            cursor.execute("SELECT * FROM activity_achievements")
            rows = cursor.fetchall()
            
            self.achievements = []
            self._achievements_by_id = {}
            
            for row in rows:
                achievement = self._row_to_achievement(row, cursor)
                if achievement:
                    self.achievements.append(achievement)
                    if achievement.id:
                        self._achievements_by_id[achievement.id] = achievement
            
            conn.close()
            logger.info(f"从数据库加载了 {len(self.achievements)} 个成果")
        except Exception as e:
            logger.error(f"从数据库加载成果失败: {e}")
            self.achievements = []
    
    def _row_to_achievement(self, row: sqlite3.Row, cursor: sqlite3.Cursor) -> Optional[Achievement]:
        """将数据库行转换为Achievement对象"""
        try:
            achievement_type = AchievementType(row['achievement_type'])
            achievement_id = row['id']
            
            if achievement_type == AchievementType.AWARD:
                # 加载奖状成果
                cursor.execute("""
                    SELECT award_id FROM activity_achievement_awards
                    WHERE achievement_id = ?
                """, (achievement_id,))
                award_row = cursor.fetchone()
                if not award_row:
                    return None
                
                award_id = award_row['award_id']
                if self.award_manager:
                    award = self.award_manager.get_award_by_id(award_id)
                    if not award:
                        return None
                    
                    achievement = AwardAchievement(
                        id=achievement_id,
                        title=award.competition_name_in_file or "获奖",
                        description=None,
                        date=award.date,
                        award_id=award_id,
                        evidence_file_path=str(award.get_image_path()) if award.get_image_path() else None,
                        created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    )
                    return achievement
            
            elif achievement_type == AchievementType.PROJECT_APPROVAL:
                # 加载立项通知成果
                cursor.execute("""
                    SELECT * FROM activity_achievement_projects
                    WHERE achievement_id = ?
                """, (achievement_id,))
                project_row = cursor.fetchone()
                if not project_row:
                    return None
                
                achievement = ProjectApprovalAchievement(
                    id=achievement_id,
                    title=row['title'],
                    description=row['description'],
                    date=row['date'],
                    project_number=project_row['project_number'],
                    start_date=project_row['start_date'],
                    end_date=project_row['end_date'],
                    evidence_file_path=project_row['evidence_file_path'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                return achievement
            
            elif achievement_type == AchievementType.COPYRIGHT:
                # 加载软件著作权成果
                cursor.execute("""
                    SELECT * FROM activity_achievement_copyrights
                    WHERE achievement_id = ?
                """, (achievement_id,))
                copyright_row = cursor.fetchone()
                if not copyright_row:
                    return None
                
                achievement = CopyrightAchievement(
                    id=achievement_id,
                    title=row['title'],
                    description=row['description'],
                    date=copyright_row['registration_date'],
                    copyright_name=copyright_row['copyright_name'],
                    evidence_file_path=copyright_row['evidence_file_path'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                return achievement
            
            elif achievement_type == AchievementType.PAPER:
                # 加载论文成果
                cursor.execute("""
                    SELECT * FROM activity_achievement_papers
                    WHERE achievement_id = ?
                """, (achievement_id,))
                paper_row = cursor.fetchone()
                if not paper_row:
                    return None
                
                achievement = PaperAchievement(
                    id=achievement_id,
                    title=row['title'],
                    description=row['description'],
                    date=paper_row['publication_date'],
                    paper_name=paper_row['paper_name'],
                    publication_name=paper_row['publication_name'],
                    publication_date=paper_row['publication_date'],
                    evidence_file_path=paper_row['evidence_file_path'],
                    created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
                    updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                )
                return achievement
            
            return None
        except Exception as e:
            logger.error(f"转换成果数据失败: {e}")
            return None
    
    def get_achievement_by_id(self, achievement_id: int) -> Optional[Achievement]:
        """根据ID获取成果"""
        return self._achievements_by_id.get(achievement_id)
    
    def get_achievements_by_activity(self, activity_id: int) -> List[Achievement]:
        """获取指定活动的所有成果"""
        if activity_id in self._achievements_by_activity:
            return self._achievements_by_activity[activity_id]
        
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 查询活动关联的成果
            cursor.execute("""
                SELECT achievement_id FROM activity_achievements
                WHERE activity_id = ?
            """, (activity_id,))
            rows = cursor.fetchall()
            
            achievements = []
            for row in rows:
                achievement_id = row['achievement_id']
                achievement = self.get_achievement_by_id(achievement_id)
                if achievement:
                    achievements.append(achievement)
                    achievement.add_activity(activity_id)
            
            self._achievements_by_activity[activity_id] = achievements
            conn.close()
            return achievements
        except Exception as e:
            logger.error(f"获取活动成果失败: {e}")
            return []
    
    def add_achievement(self, achievement: Achievement, activity_id: int) -> bool:
        """添加成果并关联到活动"""
        try:
            if not achievement.validate():
                logger.warning(f"成果验证失败: {achievement}")
                return False
            
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 插入主表
            cursor.execute("""
                INSERT INTO activity_achievements (
                    activity_id, achievement_type, title, description, date
                ) VALUES (?, ?, ?, ?, ?)
            """, (
                activity_id,
                achievement.achievement_type.value,
                achievement.title,
                achievement.description,
                achievement.date
            ))
            achievement.id = cursor.lastrowid
            
            # 根据类型插入子表
            if isinstance(achievement, AwardAchievement):
                cursor.execute("""
                    INSERT INTO activity_achievement_awards (achievement_id, award_id)
                    VALUES (?, ?)
                """, (achievement.id, achievement.award_id))
            
            elif isinstance(achievement, ProjectApprovalAchievement):
                cursor.execute("""
                    INSERT INTO activity_achievement_projects (
                        achievement_id, project_number, start_date, end_date, evidence_file_path
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    achievement.id,
                    achievement.project_number,
                    achievement.start_date,
                    achievement.end_date,
                    achievement.evidence_file_path
                ))
            
            elif isinstance(achievement, CopyrightAchievement):
                cursor.execute("""
                    INSERT INTO activity_achievement_copyrights (
                        achievement_id, copyright_name, registration_date, evidence_file_path
                    ) VALUES (?, ?, ?, ?)
                """, (
                    achievement.id,
                    achievement.copyright_name,
                    achievement.registration_date or achievement.date,
                    achievement.evidence_file_path
                ))
            
            elif isinstance(achievement, PaperAchievement):
                cursor.execute("""
                    INSERT INTO activity_achievement_papers (
                        achievement_id, paper_name, publication_name, publication_date, evidence_file_path
                    ) VALUES (?, ?, ?, ?, ?)
                """, (
                    achievement.id,
                    achievement.paper_name,
                    achievement.publication_name,
                    achievement.publication_date or achievement.date,
                    achievement.evidence_file_path
                ))
            
            # 添加参与者关联
            if self.student_manager and self.teacher_manager:
                self._save_achievement_participants(cursor, achievement)
            
            conn.commit()
            conn.close()
            
            # 更新缓存
            self.achievements.append(achievement)
            if achievement.id:
                self._achievements_by_id[achievement.id] = achievement
                achievement.add_activity(activity_id)
                if activity_id not in self._achievements_by_activity:
                    self._achievements_by_activity[activity_id] = []
                self._achievements_by_activity[activity_id].append(achievement)
            
            logger.info(f"添加成果成功: {achievement.id}")
            return True
        except Exception as e:
            logger.error(f"添加成果失败: {e}")
            return False
    
    def _save_achievement_participants(self, cursor: sqlite3.Cursor, achievement: Achievement):
        """保存成果的参与者关联"""
        if not achievement.id:
            return
        
        # 删除旧关联
        cursor.execute("""
            DELETE FROM activity_achievement_participants WHERE achievement_id = ?
        """, (achievement.id,))
        
        # 添加学生参与者
        for student in achievement.participants_students:
            if student.id:
                cursor.execute("""
                    INSERT OR IGNORE INTO activity_achievement_participants
                    (achievement_id, participant_id, participant_type)
                    VALUES (?, ?, 'student')
                """, (achievement.id, student.id))
        
        # 添加教师参与者
        for teacher in achievement.participants_teachers:
            if teacher.id:
                cursor.execute("""
                    INSERT OR IGNORE INTO activity_achievement_participants
                    (achievement_id, participant_id, participant_type)
                    VALUES (?, ?, 'teacher')
                """, (achievement.id, teacher.id))
    
    def delete_achievement(self, achievement_id: int) -> bool:
        """删除成果"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            
            # 获取成果类型
            cursor.execute("""
                SELECT achievement_type FROM activity_achievements WHERE id = ?
            """, (achievement_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            achievement_type = row['achievement_type']
            
            # 删除子表数据
            if achievement_type == AchievementType.AWARD.value:
                cursor.execute("DELETE FROM activity_achievement_awards WHERE achievement_id = ?", (achievement_id,))
            elif achievement_type == AchievementType.PROJECT_APPROVAL.value:
                cursor.execute("DELETE FROM activity_achievement_projects WHERE achievement_id = ?", (achievement_id,))
            elif achievement_type == AchievementType.COPYRIGHT.value:
                cursor.execute("DELETE FROM activity_achievement_copyrights WHERE achievement_id = ?", (achievement_id,))
            elif achievement_type == AchievementType.PAPER.value:
                cursor.execute("DELETE FROM activity_achievement_papers WHERE achievement_id = ?", (achievement_id,))
            
            # 删除参与者关联
            cursor.execute("DELETE FROM activity_achievement_participants WHERE achievement_id = ?", (achievement_id,))
            
            # 删除主表数据
            cursor.execute("DELETE FROM activity_achievements WHERE id = ?", (achievement_id,))
            
            conn.commit()
            conn.close()
            
            # 更新缓存
            if achievement_id in self._achievements_by_id:
                achievement = self._achievements_by_id[achievement_id]
                if achievement in self.achievements:
                    self.achievements.remove(achievement)
                del self._achievements_by_id[achievement_id]
                
                # 从活动缓存中移除
                for activity_id, achievements in self._achievements_by_activity.items():
                    if achievement in achievements:
                        achievements.remove(achievement)
            
            logger.info(f"删除成果成功: {achievement_id}")
            return True
        except Exception as e:
            logger.error(f"删除成果失败: {e}")
            return False

