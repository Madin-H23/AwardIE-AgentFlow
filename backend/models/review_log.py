"""
Review Log Management Module

Handles audit logs for the review workflow (审核日志管理).
Records all review actions: approved, rejected, deleted.
"""
import sqlite3
import logging
import json
from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class ReviewLog:
    """Review Log data model"""
    id: Optional[int] = None

    # 关联的pending记录信息（已删除）
    pending_id: int = 0
    achievement_type: str = ""
    file_hash: Optional[str] = None
    file_path: Optional[str] = None

    # 提交人信息
    submitter_type: str = ""
    submitter_id: int = 0

    # 审核人信息
    reviewer_type: str = ""
    reviewer_id: int = 0

    # 操作信息
    action_type: str = ""  # 'approved', 'rejected', 'deleted'
    result_type: Optional[str] = None  # approved时的成果类型
    result_id: Optional[int] = None  # approved时的成果ID
    result_file_path: Optional[str] = None  # approved时文件移动后的路径

    # 备注
    review_comment: Optional[str] = None
    operation_note: Optional[str] = None

    # 时间戳
    created_at: Optional[str] = None

    def is_approved(self) -> bool:
        """是否为审核通过"""
        return self.action_type == 'approved'

    def is_rejected(self) -> bool:
        """是否为审核拒绝"""
        return self.action_type == 'rejected'

    def is_deleted(self) -> bool:
        """是否为提交人删除"""
        return self.action_type == 'deleted'


class ReviewLogManager:
    """Manages review log data operations"""

    def __init__(self, db_path: str):
        """
        Initialize ReviewLogManager

        Args:
            db_path: Database file path
        """
        self.db_path = db_path
        self.logs: List[ReviewLog] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)

    def _load_all_from_db(self):
        """Load all review logs from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM review_logs ORDER BY created_at DESC")
            rows = cursor.fetchall()
            conn.close()

            self.logs = [self._row_to_log(row) for row in rows]
            logger.info(f"Loaded {len(self.logs)} review logs from database")
        except Exception as e:
            logger.error(f"Failed to load review logs: {e}")
            self.logs = []

    def _row_to_log(self, row: sqlite3.Row) -> ReviewLog:
        """Convert database row to ReviewLog object"""
        return ReviewLog(**dict(row))

    def get_log_by_id(self, log_id: int) -> Optional[ReviewLog]:
        """Get review log by ID"""
        for log in self.logs:
            if log.id == log_id:
                return log
        return None

    def create_log(
        self,
        pending_id: int,
        achievement_type: str,
        submitter_type: str,
        submitter_id: int,
        reviewer_type: str,
        reviewer_id: int,
        action_type: str,
        file_hash: Optional[str] = None,
        file_path: Optional[str] = None,
        result_type: Optional[str] = None,
        result_id: Optional[int] = None,
        result_file_path: Optional[str] = None,
        review_comment: Optional[str] = None,
        operation_note: Optional[str] = None
    ) -> ReviewLog:
        """
        创建审核日志记录

        Args:
            pending_id: pending记录ID
            achievement_type: 成果类型
            submitter_type: 提交人类型
            submitter_id: 提交人ID
            reviewer_type: 审核人类型
            reviewer_id: 审核人ID
            action_type: 操作类型 ('approved', 'rejected', 'deleted')
            file_hash: 文件hash（可选）
            file_path: 文件路径（可选）
            result_type: approved时的成果类型（可选）
            result_id: approved时的成果ID（可选）
            result_file_path: approved时文件移动后的路径（可选）
            review_comment: 审核意见（可选）
            operation_note: 操作说明（可选）

        Returns:
            创建的 ReviewLog 对象
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                INSERT INTO review_logs
                (pending_id, achievement_type, file_hash, file_path,
                 submitter_type, submitter_id,
                 reviewer_type, reviewer_id,
                 action_type, result_type, result_id, result_file_path,
                 review_comment, operation_note)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pending_id, achievement_type, file_hash, file_path,
                submitter_type, submitter_id,
                reviewer_type, reviewer_id,
                action_type, result_type, result_id, result_file_path,
                review_comment, operation_note
            ))

            log_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # 重新加载并返回
            self._load_all_from_db()
            return self.get_log_by_id(log_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"创建审核日志失败: {e}")
            raise

    def query_logs(
        self,
        action_type: Optional[str] = None,
        reviewer_type: Optional[str] = None,
        reviewer_id: Optional[int] = None,
        submitter_type: Optional[str] = None,
        submitter_id: Optional[int] = None,
        pending_id: Optional[int] = None,
        limit: Optional[int] = None
    ) -> List[ReviewLog]:
        """
        查询审核日志

        Args:
            action_type: 操作类型
            reviewer_type: 审核人类型
            reviewer_id: 审核人ID
            submitter_type: 提交人类型
            submitter_id: 提交人ID
            pending_id: pending记录ID
            limit: 返回数量限制

        Returns:
            匹配的日志列表
        """
        results = list(self.logs)

        # 应用过滤条件
        if action_type:
            results = [log for log in results if log.action_type == action_type]

        if reviewer_type:
            results = [log for log in results if log.reviewer_type == reviewer_type]

        if reviewer_id is not None:
            results = [log for log in results if log.reviewer_id == reviewer_id]

        if submitter_type:
            results = [log for log in results if log.submitter_type == submitter_type]

        if submitter_id is not None:
            results = [log for log in results if log.submitter_id == submitter_id]

        if pending_id is not None:
            results = [log for log in results if log.pending_id == pending_id]

        # 分页
        if limit:
            results = results[:limit]

        return results

    def get_stats_by_action_type(self) -> dict:
        """
        获取按操作类型分组的统计信息

        Returns:
            Dict like: {'approved': 10, 'rejected': 5, 'deleted': 2}
        """
        stats = {'approved': 0, 'rejected': 0, 'deleted': 0}
        for log in self.logs:
            if log.action_type in stats:
                stats[log.action_type] += 1
        return stats

    def get_recent_logs(self, limit: int = 50) -> List[ReviewLog]:
        """
        获取最近的审核日志

        Args:
            limit: 返回数量限制

        Returns:
            最近的日志列表
        """
        return self.logs[:limit]

    def delete_log(self, log_id: int) -> bool:
        """
        删除审核日志（一般不需要调用，仅用于清理旧数据）

        Args:
            log_id: 日志ID

        Returns:
            是否成功
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM review_logs WHERE id = ?", (log_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                self.logs = [log for log in self.logs if log.id != log_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"删除审核日志失败: {e}")
            return False

    def cleanup_old_logs(self, days: int = 90) -> int:
        """
        清理旧日志（定期任务）

        Args:
            days: 保留天数，删除超过此天数的日志

        Returns:
            删除的日志数量
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                DELETE FROM review_logs
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            # 重新加载
            self._load_all_from_db()
            logger.info(f"清理了 {deleted_count} 条旧审核日志（超过 {days} 天）")
            return deleted_count

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"清理旧日志失败: {e}")
            return 0
