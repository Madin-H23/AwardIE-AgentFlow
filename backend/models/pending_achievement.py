"""
Pending Achievement Management Module

Handles pending achievements awaiting review (待审核成果).
Supports the review workflow for student/teacher submissions.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from backend.extract.types import ExtractResult
    from backend.models.laboratory import LaboratoryManager
import sqlite3
import logging
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class PendingAchievement:
    """Pending Achievement data model"""
    # Achievement type and data (required, no defaults)
    achievement_type: str  # award, patent, software, innovation, other
    achievement_data: str  # JSON string of the achievement data
    submitter_type: str  # student, teacher, admin

    # Optional fields with defaults
    validation_result: Optional[str] = None
    submitter_id: int = 0
    submit_time: Optional[str] = None
    # Status values (新流程):
    # - pending: 等待提交人审核（可修改/提交/删除）
    # - submit: 已提交，等待审核人审核（审核人可操作）
    status: str = "pending"
    reviewer_id: Optional[int] = None
    review_time: Optional[str] = None
    review_comment: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[str] = None
    file_path: Optional[str] = None  # 相对路径（如 temp_upload/session_id/file.ext，便于跨服务器部署）或历史绝对路径

    # 新增字段：审核流程相关
    assigned_reviewer_type: Optional[str] = None  # 预分配审核人类型 ('teacher' | 'admin')
    reviewer_type: Optional[str] = None  # 实际审核人类型 ('teacher' | 'admin')
    file_hash: str = ""  # 文件hash（用于去重）

    # 新增字段：AI调试信息
    ocr_text: Optional[str] = None  # OCR识别的原始文本
    llm_prompt: Optional[str] = None  # LLM提示词
    llm_response: Optional[str] = None  # LLM响应
    ext_info: Optional[str] = None  # 扩展信息JSON: {ocr_cache_hit, llm_cache_hit, match_score, template_id}
    
    # 统一文件管理器会话字段
    session_id: Optional[str] = None  # 文件管理会话ID

    # 实验室关联字段
    laboratory_id: Optional[int] = None  # 关联的实验室ID

    # 乐观锁版本号（迁移§1.5 加列；P1-15 服务层条件更新的前置字段）
    version: int = 1

    def get_achievement_data(self) -> Dict[str, Any]:
        """
        解析 achievement_data JSON
        
        约定：achievement_data 在数据库中存储为 JSON 字符串，此方法返回字典
        """
        if not self.achievement_data:
            return {}
        
        if isinstance(self.achievement_data, dict):
            return self.achievement_data
        
        if isinstance(self.achievement_data, str):
            try:
                return json.loads(self.achievement_data)
            except json.JSONDecodeError as e:
                logger.error(f"解析 achievement_data JSON 失败: {e}, 数据: {self.achievement_data[:200]}")
                return {}
        
        logger.warning(f"achievement_data 类型不正确: {type(self.achievement_data)}")
        return {}

    def get_validation_result(self) -> Dict[str, Any]:
        """Parse validation_result JSON"""
        try:
            return json.loads(self.validation_result) if self.validation_result else {}
        except:
            return {}

    def is_valid(self) -> bool:
        """Check if validation passed"""
        validation = self.get_validation_result()
        return validation.get('is_valid', False)

    def has_content_issues(self) -> List[str]:
        """Get content validation issues"""
        validation = self.get_validation_result()
        return validation.get('content_issues', [])

    def has_completeness_issues(self) -> List[str]:
        """Get completeness validation issues"""
        validation = self.get_validation_result()
        return validation.get('completeness_issues', [])

    # 旧状态判断方法已移除，统一使用新流程状态

    def get_file_path(self) -> Optional[str]:
        """获取文件路径（优先从file_path字段，其次从achievement_data）"""
        if self.file_path:
            return self.file_path
        data = self.get_achievement_data()
        return data.get('file_path') if isinstance(data, dict) else None

    def get_preview_image_path(self) -> Optional[str]:
        """获取预览图片路径（用于PDF第一页转换的图片）"""
        data = self.get_achievement_data()
        return data.get('preview_image_path') if isinstance(data, dict) else None

    def get_ext_info(self) -> Dict[str, Any]:
        """
        解析 ext_info JSON

        Returns:
            Dict like: {
                'ocr_cache_hit': bool,
                'llm_cache_hit': bool,
                'match_score': float,
                'template_id': int or None
            }
        """
        if not self.ext_info:
            return {}
        try:
            return json.loads(self.ext_info)
        except json.JSONDecodeError as e:
            logger.error(f"解析 ext_info JSON 失败: {e}, 数据: {self.ext_info[:200]}")
            return {}

    # 新流程状态判断方法
    def is_pending(self) -> bool:
        """是否为 pending 状态（等待提交人审核）"""
        return self.status == 'pending'

    def is_submitted(self) -> bool:
        """是否为 submit 状态（等待审核人审核）"""
        return self.status == 'submit'

    def can_be_modified_by_submitter(self) -> bool:
        """提交人是否可以修改（pending状态可以修改）"""
        return self.status == 'pending'

    def can_be_reviewed(self) -> bool:
        """是否可以被审核人审核（submit状态）"""
        return self.status == 'submit'


@dataclass
class PendingAchievementFilter:
    """Pending Achievement query filter"""
    id: Optional[int] = None
    achievement_type: Optional[str] = None
    status: Optional[str] = None  # pending, submit (新流程状态)
    submitter_type: Optional[str] = None
    submitter_id: Optional[int] = None
    reviewer_id: Optional[int] = None
    import_session_id: Optional[str] = None  # 导入会话ID，用于文件导入功能
    session_id: Optional[str] = None  # 统一文件管理器会话ID
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.achievement_type is None,
            self.status is None,
            self.submitter_type is None,
            self.submitter_id is None,
            self.reviewer_id is None,
            self.import_session_id is None,
            self.session_id is None,
        ])


class PendingAchievementManager:
    """Manages pending achievement data operations"""

    def __init__(self, db_path: str):
        """
        Initialize PendingAchievementManager

        Args:
            db_path: Database file path
        """
        self.db_path = db_path
        logger.info(f"PendingAchievementManager initialized with db_path: {self.db_path}")
        self.pending: List[PendingAchievement] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection（统一工厂：外键/WAL/busy_timeout 强制契约，P0-4/5/7）"""
        from backend.utils.db_connection import get_connection
        return get_connection(self.db_path)

    def _load_all_from_db(self):
        """从数据库加载全部 pending 记录。遇错即抛，不姑息。"""
        conn = None
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM pending_achievements ORDER BY submit_time DESC")
            rows = cursor.fetchall()
            self.pending = [self._row_to_pending(row) for row in rows]
        except Exception as e:
            logger.error(f"数据库路径: {self.db_path}")
            logger.error("Failed to load pending achievements: %s", e)
            raise
        finally:
            if conn is not None:
                conn.close()

    def _row_to_pending(self, row: sqlite3.Row) -> PendingAchievement:
        """Convert database row to PendingAchievement object"""
        data = dict(row)
        # 保留created_at用于显示
        created_at = data.pop('created_at', None)
        pending = PendingAchievement(**data)
        pending.created_at = created_at
        return pending

    def get_pending_by_id(self, pending_id: int) -> Optional[PendingAchievement]:
        """Get pending achievement by ID"""
        for pending in self.pending:
            if pending.id == pending_id:
                return pending
        return None

    def submit_for_review(self, achievement_type: str, achievement_data: Dict[str, Any],
                          validation_result: Optional[Dict[str, Any]] = None,
                          submitter_type: str = "student",
                          submitter_id: int = 0,
                          file_path: Optional[str] = None,
                          status: Optional[str] = None,
                          # 新增参数：与 create_from_extract_result 保持一致
                          file_hash: Optional[str] = None,
                          ocr_text: Optional[str] = None,
                          llm_prompt: Optional[str] = None,
                          llm_response: Optional[str] = None,
                          ext_info: Optional[Dict[str, Any]] = None,
                          assigned_reviewer_type: Optional[str] = None,
                          laboratory_id: Optional[int] = None) -> PendingAchievement:
        """
        Submit an achievement for review

        Args:
            achievement_type: Type of achievement (award, patent, software, innovation, other)
            achievement_data: Achievement data dictionary
            validation_result: Optional validation result from validation module
            submitter_type: Type of submitter (student, teacher, admin)
            submitter_id: ID of submitter
            file_path: Optional file path of the uploaded file
            status: Optional initial status (defaults to 'pending')
            file_hash: Optional file hash for deduplication
            ocr_text: Optional OCR recognition text
            llm_prompt: Optional LLM prompt used
            llm_response: Optional LLM response text
            ext_info: Optional extended info (cache hit status, match score, etc.)
            assigned_reviewer_type: Optional pre-assigned reviewer type
            laboratory_id: Optional laboratory ID for the achievement

        Returns:
            Created PendingAchievement object
        """
        # 移动文件到 review 目录（使用统一文件管理器）
        # 注意：只有在状态为'submit'时才移动文件，'pending'状态时文件应保持在temp_upload目录
        initial_status = status or 'pending'
        if initial_status == 'submit' and file_path and ext_info and isinstance(ext_info, dict):
            session_id = ext_info.get('session_id')
            if session_id:
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager
                    file_manager = get_unified_file_manager()
                    # 将文件从 temp_upload 移动到 review
                    file_path = file_manager.move_to_review(session_id, file_path)
                    logger.info(f"文件已移动到review目录: {file_path}")
                except Exception as e:
                    logger.warning(f"移动文件到review目录失败，使用原路径: {e}")
                    # 如果移动失败，继续使用原路径（向后兼容）

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # 调试：打印即将保存的 laboratory_id
            logger.info(f"[submit_for_review] 准备插入 pending_achievements | laboratory_id={laboratory_id} | achievement_type={achievement_type}")

            # Prepare fields
            validation_json = json.dumps(validation_result, ensure_ascii=False) if validation_result else None
            data_json = json.dumps(achievement_data, ensure_ascii=False)
            ext_info_json = json.dumps(ext_info, ensure_ascii=False) if ext_info else None
            initial_status = status or 'pending'

            cursor.execute("""
                INSERT INTO pending_achievements
                (achievement_type, achievement_data, validation_result, submitter_type, submitter_id,
                 file_path, status, file_hash, ocr_text, llm_prompt, llm_response, ext_info, assigned_reviewer_type, session_id, laboratory_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (achievement_type, data_json, validation_json, submitter_type, submitter_id,
                  file_path, initial_status, file_hash, ocr_text, llm_prompt, llm_response, ext_info_json, assigned_reviewer_type,
                  ext_info.get('session_id') if isinstance(ext_info, dict) else None, laboratory_id))

            pending_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_pending_by_id(pending_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to submit achievement for review: {e}")
            raise

    def approve(self, pending_id: int, reviewer_id: int,
                comment: Optional[str] = None) -> bool:
        """
        Approve a pending achievement

        Args:
            pending_id: Pending achievement ID
            reviewer_id: ID of admin reviewer
            comment: Optional review comment

        Returns:
            True if successful
        """
        return self._update_status(pending_id, "approved", reviewer_id, comment)

    def reject(self, pending_id: int, reviewer_id: int,
               comment: Optional[str] = None) -> bool:
        """
        审核拒绝（已废弃）
        
        注意：此方法已废弃。新流程中应使用 reject_pending() 记录审核人信息，
        然后删除 pending 记录。
        
        Args:
            pending_id: Pending achievement ID
            reviewer_id: ID of admin reviewer
            comment: Optional review comment (required for rejection)

        Returns:
            True if successful
        """
        logger.warning("reject() 方法已废弃，请使用 reject_pending() + 删除记录")
        if not comment:
            logger.warning("Rejection requires a comment")
            return False
        return self._update_status(pending_id, "rejected", reviewer_id, comment)

    def _update_status(self, pending_id: int, status: str,
                       reviewer_id: int, comment: Optional[str]) -> bool:
        """Update status of pending achievement"""
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            return False

        if pending.status != "pending":
            logger.warning(f"Pending achievement {pending_id} is not in pending status")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE pending_achievements
                SET status = ?, reviewer_id = ?, review_time = CURRENT_TIMESTAMP, review_comment = ?
                WHERE id = ?
            """, (status, reviewer_id, comment, pending_id))

            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update pending achievement status: {e}")
            return False

    def delete_pending(self, pending_id: int) -> bool:
        """Delete pending achievement (e.g., after approval and data moved to main table)"""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM pending_achievements WHERE id = ?", (pending_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                self.pending = [p for p in self.pending if p.id != pending_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete pending achievement {pending_id}: {e}")
            return False

    def query_pending(self, filter_obj: Optional[PendingAchievementFilter] = None) -> List[PendingAchievement]:
        """
        Query pending achievements with optional filter

        Args:
            filter_obj: PendingAchievementFilter object

        Returns:
            List of matching pending achievements
        """
        results = list(self.pending)

        if not filter_obj or filter_obj.is_empty():
            return results

        # Apply filters
        if filter_obj.id is not None:
            results = [p for p in results if p.id == filter_obj.id]

        if filter_obj.achievement_type:
            results = [p for p in results if p.achievement_type == filter_obj.achievement_type]

        if filter_obj.status:
            results = [p for p in results if p.status == filter_obj.status]

        if filter_obj.submitter_type:
            results = [p for p in results if p.submitter_type == filter_obj.submitter_type]

        if filter_obj.submitter_id is not None:
            results = [p for p in results if p.submitter_id == filter_obj.submitter_id]

        if filter_obj.reviewer_id is not None:
            results = [p for p in results if p.reviewer_id == filter_obj.reviewer_id]

        if filter_obj.import_session_id is not None:
            # 从 achievement_data 中提取 import_session_id 进行过滤
            filtered_results = []
            for p in results:
                try:
                    data = p.get_achievement_data()
                    item_session_id = data.get('import_session_id') if isinstance(data, dict) else None
                    if isinstance(data, dict) and data.get('import_session_id') == filter_obj.import_session_id:
                        filtered_results.append(p)
                except Exception as e:
                    continue
            results = filtered_results

        if filter_obj.session_id is not None:
            results = [p for p in results if p.session_id == filter_obj.session_id]

        # Pagination
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def get_pending_count_by_status(self) -> Dict[str, int]:
        """Get count of pending achievements grouped by status (新流程)"""
        counts = {
            "pending": 0,  # 等待提交人审核
            "submit": 0    # 已提交，等待审核人审核
        }
        for pending in self.pending:
            if pending.status in counts:
                counts[pending.status] += 1
            else:
                # 未知状态或旧状态，计入pending（兼容旧数据）
                logger.warning(f"发现未知状态: {pending.status}, pending_id={pending.id}")
                counts["pending"] += 1
        return counts

    def get_pending_for_review(self) -> List[PendingAchievement]:
        """获取所有待审核的成果（用于成果审核页面）- 新流程"""
        # 只包含新流程状态：submit 状态表示已提交等待审核
        return [p for p in self.pending if p.status == 'submit']

    def get_stats_by_type_and_validation(self, session_id: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        获取按类型和验证状态分组的统计信息
        
        Args:
            session_id: 可选的session_id，用于筛选特定导入会话的数据
            
        Returns:
            Dict like {'award': {'valid': 5, 'invalid': 2, 'total': 7}, ...}
        """
        stats = {}
        
        try:
            for pending in self.pending:
                try:
                    # 如果指定了session_id，只统计该session的数据
                    if session_id:
                        data = pending.get_achievement_data()
                        # 确保 data 是字典类型
                        if not isinstance(data, dict):
                            logger.warning(f"get_achievement_data returned non-dict for pending {pending.id}: {type(data)}")
                            continue
                        if data.get('import_session_id') != session_id:
                            continue
                    
                    achievement_type = pending.achievement_type or 'other'
                    # 确保 achievement_type 是字符串
                    if not isinstance(achievement_type, str):
                        logger.warning(f"achievement_type is not string for pending {pending.id}: {type(achievement_type)}")
                        achievement_type = 'other'
                    
                    if achievement_type not in stats:
                        stats[achievement_type] = {'valid': 0, 'invalid': 0, 'total': 0}
                    
                    stats[achievement_type]['total'] += 1
                    if pending.is_valid():
                        stats[achievement_type]['valid'] += 1
                    else:
                        stats[achievement_type]['invalid'] += 1
                except Exception as e:
                    logger.error(f"Error processing pending achievement {pending.id if pending else 'unknown'}: {e}", exc_info=True)
                    continue
        except Exception as e:
            logger.error(f"Error in get_stats_by_type_and_validation: {e}", exc_info=True)
            # 返回空字典而不是抛出异常
            return {}
        
        return stats

    def get_stats_by_type_and_validation_for_review(self, session_id: Optional[str] = None) -> Dict[str, Dict[str, int]]:
        """
        获取按类型和验证状态分组的统计信息，仅统计 status='submit' 的记录。
        用于成果审核入口重定向，避免因存在大量 pending 而跳到“有统计但列表为空”的页。
        """
        stats = {}
        try:
            for pending in self.pending:
                if pending.status != 'submit':
                    continue
                try:
                    if session_id:
                        data = pending.get_achievement_data()
                        if not isinstance(data, dict) or data.get('import_session_id') != session_id:
                            continue
                    achievement_type = pending.achievement_type or 'other'
                    if not isinstance(achievement_type, str):
                        achievement_type = 'other'
                    if achievement_type not in stats:
                        stats[achievement_type] = {'valid': 0, 'invalid': 0, 'total': 0}
                    stats[achievement_type]['total'] += 1
                    if pending.is_valid():
                        stats[achievement_type]['valid'] += 1
                    else:
                        stats[achievement_type]['invalid'] += 1
                except Exception as e:
                    logger.error(f"Error processing pending achievement {pending.id}: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Error in get_stats_by_type_and_validation_for_review: {e}", exc_info=True)
            return {}
        return stats

    def get_pending_by_submitter(self, submitter_type: str,
                                  submitter_id: int,
                                  status: Optional[str] = None,
                                  exclude_archived: bool = True) -> List[PendingAchievement]:
        """按提交人查询 pending_achievements 表。

        Args:
            status: 指定状态；None 时不过滤
            exclude_archived: True（默认）排除 archived——软归档(8.6.4)后已入库记录不再出现在
                提交人 submissions 页；显式查历史时传 False。
        """
        filter_obj = PendingAchievementFilter(
            submitter_type=submitter_type,
            submitter_id=submitter_id,
            status=status
        )
        result = self.query_pending(filter_obj)
        if exclude_archived:
            result = [p for p in result if p.status != 'archived']
        return result

    def archive(self, pending_id: int) -> bool:
        """approve 软归档（8.6.4）：submit -> archived，保留行/文件/AI 结论。

        条件更新（乐观锁语义）：仅 status='submit' 时成功，防撤回/并发竞态（P1-15）。
        Returns:
            是否归档成功（False=状态已变或不存在）。
        """
        conn = self._get_db_connection()
        try:
            cur = conn.execute(
                "UPDATE pending_achievements SET status='archived', version=version+1, "
                "review_time=CURRENT_TIMESTAMP WHERE id=? AND status='submit'",
                (pending_id,),
            )
            conn.commit()
            ok = cur.rowcount > 0
            if ok:
                self._load_all_from_db()
            return ok
        finally:
            conn.close()

    def unarchive(self, pending_id: int) -> bool:
        """入库失败补偿（P1-8）：archived -> submit 回滚，供修复后重审。

        条件更新：仅 archived 态可回滚。
        Returns:
            是否回滚成功。
        """
        conn = self._get_db_connection()
        try:
            cur = conn.execute(
                "UPDATE pending_achievements SET status='submit', version=version+1 "
                "WHERE id=? AND status='archived'",
                (pending_id,),
            )
            conn.commit()
            ok = cur.rowcount > 0
            if ok:
                self._load_all_from_db()
            return ok
        finally:
            conn.close()

    def reject(self, pending_id: int, reviewer_type: str, reviewer_id: int, reason: str) -> bool:
        """驳回打回（FR-APPROVE-07）：submit -> rejected，留驳回原因供提交人修改后重交。

        条件更新：仅 status='submit' 时成功（防重复驳回/并发）。
        Returns:
            是否驳回成功。
        """
        conn = self._get_db_connection()
        try:
            cur = conn.execute(
                "UPDATE pending_achievements SET status='rejected', version=version+1, "
                "reviewer_type=?, reviewer_id=?, review_comment=?, review_time=CURRENT_TIMESTAMP "
                "WHERE id=? AND status='submit'",
                (reviewer_type, reviewer_id, reason, pending_id),
            )
            conn.commit()
            ok = cur.rowcount > 0
            if ok:
                self._load_all_from_db()
            return ok
        finally:
            conn.close()

    def get_by_id(self, pending_id: int) -> Optional[PendingAchievement]:
        """Alias for get_pending_by_id for compatibility"""
        return self.get_pending_by_id(pending_id)

    def update(self, pending_item: PendingAchievement,
               achievement_type: Optional[str] = None,
               achievement_data: Optional[Any] = None,  # 支持字典或 JSON 字符串
               validation_result: Optional[Any] = None,  # 支持字典或 JSON 字符串
               status: Optional[str] = None,
               reviewer_id: Optional[int] = None,
               review_comment: Optional[str] = None,
               file_path: Optional[str] = None,
               submitter_type: Optional[str] = None,
               submitter_id: Optional[int] = None,
               assigned_reviewer_type: Optional[str] = None,
               ext_info: Optional[Any] = None) -> bool:
        """
        Update a pending achievement

        约定：
        - achievement_data 和 validation_result 可以传入字典或 JSON 字符串
        - 如果是字典，会自动转换为 JSON 字符串存储
        - 如果是字符串，直接存储（假设已经是 JSON 格式）

        Args:
            pending_item: PendingAchievement object to update
            achievement_type: New achievement type
            achievement_data: New achievement data (dict or JSON string)
            validation_result: New validation result (dict or JSON string)
            status: New status
            reviewer_id: Reviewer ID
            review_comment: Review comment
            file_path: New file path
            submitter_type: New submitter type (student, teacher, admin)
            submitter_id: New submitter ID
            assigned_reviewer_type: New assigned reviewer type
            ext_info: New extended info (dict or JSON string；常用于存 AI 审核结论 agent_review)

        Returns:
            True if successful
        """
        if not pending_item or not pending_item.id:
            logger.warning("Invalid pending achievement for update")
            return False

        # 如果状态从pending变为submit，需要移动文件从temp_upload到review
        old_status = pending_item.status
        new_file_path = pending_item.file_path
        if status is not None and status == 'submit' and old_status == 'pending':
            # 状态从pending变为submit，需要移动文件；session_id 存于表列 session_id（create_from_extract_result 写入），不在 ext_info JSON 中
            session_id = getattr(pending_item, 'session_id', None)
            if not session_id:
                ext_info = pending_item.get_ext_info()
                session_id = ext_info.get('session_id') if isinstance(ext_info, dict) else None
            if session_id and new_file_path:
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager
                    file_manager = get_unified_file_manager()
                    # 将文件从 temp_upload 移动到 review
                    new_file_path = file_manager.move_to_review(session_id, new_file_path)
                    # 更新file_path参数，确保数据库中的路径也被更新
                    file_path = new_file_path
                except Exception as e:
                    logger.warning(f"移动文件到review目录失败，使用原路径: {e}")
                    # 如果移动失败，继续使用原路径

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Build update query dynamically based on provided fields
            update_fields = []
            params = []

            if achievement_type is not None:
                update_fields.append("achievement_type = ?")
                params.append(achievement_type)

            if achievement_data is not None:
                update_fields.append("achievement_data = ?")
                # 统一约定：如果是字典，转换为 JSON 字符串；如果是字符串，直接使用
                if isinstance(achievement_data, dict):
                    params.append(json.dumps(achievement_data, ensure_ascii=False))
                elif isinstance(achievement_data, str):
                    params.append(achievement_data)
                else:
                    logger.warning(f"achievement_data 类型不正确: {type(achievement_data)}，跳过更新")
                    achievement_data = None

            if validation_result is not None:
                # 统一约定：如果是字典，转换为 JSON 字符串；如果是字符串，直接使用
                # 如果是 ValidationResult 对象，调用其 to_dict() 方法
                if isinstance(validation_result, dict):
                    update_fields.append("validation_result = ?")
                    params.append(json.dumps(validation_result, ensure_ascii=False))
                elif isinstance(validation_result, str):
                    update_fields.append("validation_result = ?")
                    params.append(validation_result)
                elif hasattr(validation_result, 'to_dict'):
                    # ValidationResult 对象，调用 to_dict() 转换
                    update_fields.append("validation_result = ?")
                    params.append(json.dumps(validation_result.to_dict(), ensure_ascii=False))
                else:
                    logger.warning(f"validation_result 类型不支持: {type(validation_result)}，跳过更新")

            if status is not None:
                update_fields.append("status = ?")
                params.append(status)
                if status == 'submit':
                    data_summary = None
                    if hasattr(pending_item, 'get_achievement_data') and callable(pending_item.get_achievement_data):
                        try:
                            ad = pending_item.get_achievement_data()
                            if isinstance(ad, dict):
                                data_summary = {
                                    'competition_name': ad.get('competition_name'),
                                    'achievement_type': getattr(pending_item, 'achievement_type', None),
                                    'keys': list(ad.keys())[:20],
                                }
                        except Exception:
                            data_summary = 'get_achievement_data_error'
                   

            if ext_info is not None:
                update_fields.append("ext_info = ?")
                if isinstance(ext_info, dict):
                    params.append(json.dumps(ext_info, ensure_ascii=False))
                elif isinstance(ext_info, str):
                    params.append(ext_info)
                else:
                    logger.warning(f"ext_info 类型不支持: {type(ext_info)}，跳过更新")

            if reviewer_id is not None:
                update_fields.append("reviewer_id = ?")
                params.append(reviewer_id)

            if review_comment is not None:
                update_fields.append("review_comment = ?")
                params.append(review_comment)

            if file_path is not None:
                update_fields.append("file_path = ?")
                params.append(file_path)

            if submitter_type is not None:
                update_fields.append("submitter_type = ?")
                params.append(submitter_type)

            if submitter_id is not None:
                update_fields.append("submitter_id = ?")
                params.append(submitter_id)

            if assigned_reviewer_type is not None:
                update_fields.append("assigned_reviewer_type = ?")
                params.append(assigned_reviewer_type)

            # 从 achievement_data 中同步 laboratory_id 到表列，保证文件导入选择的实验室在成果审核页可见
            lab_id_to_write: Optional[int] = None
            if achievement_data is not None and isinstance(achievement_data, dict):
                raw = achievement_data.get('laboratory_id')
                if raw is not None and raw != '':
                    try:
                        lab_id_to_write = int(raw) if int(raw) > 0 else None
                    except (TypeError, ValueError):
                        lab_id_to_write = None
                else:
                    lab_id_to_write = None
                update_fields.append("laboratory_id = ?")
                params.append(lab_id_to_write)

            if not update_fields:
                return True  # Nothing to update

            update_fields.append("review_time = CURRENT_TIMESTAMP")
            params.append(pending_item.id)

            query = f"UPDATE pending_achievements SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)

            conn.commit()
            conn.close()

            # 同步更新内存对象的属性（这样测试中的引用也能看到更新）
            if achievement_type is not None:
                pending_item.achievement_type = achievement_type
            if achievement_data is not None and isinstance(achievement_data, dict):
                pending_item.achievement_data = json.dumps(achievement_data, ensure_ascii=False)
            if achievement_data is not None and isinstance(achievement_data, dict):
                pending_item.laboratory_id = lab_id_to_write
            if status is not None:
                pending_item.status = status
            if reviewer_id is not None:
                pending_item.reviewer_id = reviewer_id
            if review_comment is not None:
                pending_item.review_comment = review_comment
            if file_path is not None:
                pending_item.file_path = file_path
            if submitter_type is not None:
                pending_item.submitter_type = submitter_type
            if submitter_id is not None:
                pending_item.submitter_id = submitter_id
            if assigned_reviewer_type is not None:
                pending_item.assigned_reviewer_type = assigned_reviewer_type

            # 重新加载数据以保持一致性
            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update pending achievement: {e}")
            return False

    def update_laboratory_id(self, pending_id: int, laboratory_id: Optional[int]) -> bool:
        """
        更新 pending 记录的实验室ID

        Args:
            pending_id: PendingAchievement ID
            laboratory_id: 新的实验室ID（如果为None则清空关联）

        Returns:
            True if successful
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE pending_achievements
                SET laboratory_id = ?
                WHERE id = ?
            """, (laboratory_id, pending_id))

            conn.commit()
            conn.close()

            # 同步更新内存对象
            for pending in self.pending:
                if pending.id == pending_id:
                    pending.laboratory_id = laboratory_id
                    break

            self._load_all_from_db()
            logger.info(f"更新 pending {pending_id} 的 laboratory_id 为 {laboratory_id}")
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update laboratory_id for pending {pending_id}: {e}")
            return False

    # ============================================================
    # 新增方法：文件去重相关
    # ============================================================

    def find_by_file_hash(self, file_hash: str) -> Optional[PendingAchievement]:
        """
        根据文件hash查找已存在的记录

        Args:
            file_hash: 文件hash值

        Returns:
            PendingAchievement对象，如果未找到则返回None
        """
        for pending in self.pending:
            if pending.file_hash == file_hash:
                return pending
        return None

    def create_from_extract_result(
        self,
        extract_result: ExtractResult,  # 避免循环导入，使用字符串引用
        submitter_type: str,
        submitter_id: int,
        file_path: str,
        file_hash: str,
        status: str = 'pending',
        assigned_reviewer_type: Optional[str] = None,
        laboratory_id: Optional[int] = None
    ) -> PendingAchievement:
        """
        从 ExtractResult 创建 pending 记录

        Args:
            extract_result: 文档抽取结果对象
            submitter_type: 提交人类型
            submitter_id: 提交人ID
            file_path: 文件路径
            file_hash: 文件hash
            status: 初始状态
            assigned_reviewer_type: 预分配审核人类型
            laboratory_id: 关联的实验室ID

        Returns:
            创建的 PendingAchievement 对象
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # 准备数据：有 data 用 data；无 data 但有 error_message（如 OCR/LLM 失败）则写入 note 供界面展示
            if extract_result.data:
                achievement_data_json = json.dumps(extract_result.data, ensure_ascii=False)
            elif getattr(extract_result, "error_message", None):
                achievement_data_json = json.dumps({"note": extract_result.error_message}, ensure_ascii=False)
            else:
                achievement_data_json = "{}"
            validation_result_json = extract_result.validation_result.to_json() if hasattr(extract_result, 'validation_result') and extract_result.validation_result else None

            # 从 metadata 或 extract_result 顶层属性获取 template_id、template_name、llm_prompt、llm_response
            metadata = extract_result.metadata if hasattr(extract_result, 'metadata') and extract_result.metadata else {}
            template_id = metadata.get('template_id') if metadata else None
            template_name = metadata.get('template_name') if metadata else None
            llm_prompt = (metadata.get('llm_prompt') if metadata else None) or getattr(extract_result, 'llm_prompt', None)
            llm_response = (metadata.get('llm_response') if metadata else None) or getattr(extract_result, 'llm_response', None)

 
            ext_info_json = json.dumps({
                'ocr_cache_hit': getattr(extract_result, 'ocr_cache_hit', False),
                'llm_cache_hit': getattr(extract_result, 'llm_cache_hit', False),
                'match_score': getattr(extract_result, 'match_score', 0.0),
                'template_id': template_id,
                'template_name': template_name
            }, ensure_ascii=False)


            cursor.execute("""
                INSERT INTO pending_achievements
                (achievement_type, achievement_data, validation_result, submitter_type, submitter_id,
                 file_path, file_hash, status, assigned_reviewer_type,
                 ocr_text, llm_prompt, llm_response, ext_info, session_id, laboratory_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                extract_result.template_type or 'other',
                achievement_data_json,
                validation_result_json,
                submitter_type,
                submitter_id,
                file_path,
                file_hash,
                status,
                assigned_reviewer_type,
                getattr(extract_result, 'ocr_text', None),
                llm_prompt,
                llm_response,
                ext_info_json,
                metadata.get('session_id') if isinstance(metadata, dict) else None,
                laboratory_id
            ))

            pending_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # 重新加载并返回
            self._load_all_from_db()
            return self.get_pending_by_id(pending_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"创建 pending 记录失败: {e}")
            raise

    def update_from_extract_result(
        self,
        pending_id: int,
        extract_result: ExtractResult,
        file_path: str,
        file_hash: str,
        submitter_type: Optional[str] = None,
        submitter_id: Optional[int] = None,
        assigned_reviewer_type: Optional[str] = None
    ) -> bool:
        """
        更新已存在的记录（文件覆盖时使用）

        Args:
            pending_id: pending 记录ID
            extract_result: 新的抽取结果
            file_path: 新的文件路径
            file_hash: 文件hash
            submitter_type: 新的提交人类型（覆盖上传时更新）
            submitter_id: 新的提交人ID（覆盖上传时更新）
            assigned_reviewer_type: 新的审核人类型（覆盖上传时更新）

        Returns:
            是否成功
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        # 从 metadata 中获取 template_id 和 template_name（如果存在）
        metadata = extract_result.metadata if hasattr(extract_result, 'metadata') and extract_result.metadata else {}
        template_id = metadata.get('template_id') if metadata else None
        template_name = metadata.get('template_name') if metadata else None
        
        # 构建 ext_info
        ext_info_json = json.dumps({
            'ocr_cache_hit': getattr(extract_result, 'ocr_cache_hit', False),
            'llm_cache_hit': getattr(extract_result, 'llm_cache_hit', False),
            'match_score': getattr(extract_result, 'match_score', 0.0),
            'template_id': template_id,
            'template_name': template_name
        }, ensure_ascii=False)

        # 更新记录（包括 ext_info、ocr_text、llm_prompt、llm_response）
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                UPDATE pending_achievements
                SET achievement_type = ?,
                    achievement_data = ?,
                    validation_result = ?,
                    file_path = ?,
                    file_hash = ?,
                    status = ?,
                    submitter_type = ?,
                    submitter_id = ?,
                    assigned_reviewer_type = ?,
                    ocr_text = ?,
                    llm_prompt = ?,
                    llm_response = ?,
                    ext_info = ?,
                    session_id = ?
                WHERE id = ?
            """, (
                extract_result.template_type or 'other',
                json.dumps(extract_result.data, ensure_ascii=False) if extract_result.data
                else (json.dumps({"note": extract_result.error_message}, ensure_ascii=False) if getattr(extract_result, "error_message", None) else '{}'),
                extract_result.validation_result.to_json() if hasattr(extract_result, 'validation_result') and extract_result.validation_result else None,
                file_path,
                file_hash,
                'pending',
                submitter_type if submitter_type is not None else pending.submitter_type,
                submitter_id if submitter_id is not None else pending.submitter_id,
                assigned_reviewer_type if assigned_reviewer_type is not None else pending.assigned_reviewer_type,
                getattr(extract_result, 'ocr_text', None),
                getattr(extract_result, 'llm_prompt', None),
                getattr(extract_result, 'llm_response', None),
                ext_info_json,
                (json.loads(ext_info_json).get('session_id') if isinstance(ext_info_json, str) else None),
                pending_id
            ))
            
            conn.commit()
            conn.close()
            
            # 重新加载数据以保持一致性
            self._load_all_from_db()
            return True
            
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"更新 pending 记录失败: {e}")
            return False

    # ============================================================
    # 新增方法：审核人相关
    # ============================================================

    def determine_assigned_reviewer(
        self,
        submitter_type: str,
        submitter_id: int,
        laboratory_manager: Optional[LaboratoryManager] = None
    ) -> str:
        """
        确定审核人类型

        Args:
            submitter_type: 提交人类型
            submitter_id: 提交人ID
            laboratory_manager: LaboratoryManager实例（用于查询实验室归属）

        Returns:
            'teacher' 或 'admin'
        """
        # 教师/管理员提交 → 由管理员审核
        if submitter_type in ('teacher', 'admin'):
            return 'admin'

        # 学生提交 → 查询实验室归属
        if submitter_type == 'student' and laboratory_manager:
            # 查询学生所属的实验室（从数据库直接查询）
            conn = self._get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    SELECT laboratory_id FROM laboratory_students WHERE student_id = ?
                """, (submitter_id,))
                result = cursor.fetchone()
                conn.close()

                if result:
                    # 学生属于实验室 → 由教师审核
                    return 'teacher'
                else:
                    # 学生不属于实验室 → 由管理员审核
                    return 'admin'
            except Exception as e:
                conn.close()
                logger.error(f"查询学生实验室归属失败: {e}")
                return 'admin'  # 默认由管理员审核

        # 默认由管理员审核
        return 'admin'

    def get_pending_for_teacher(
        self, 
        teacher_id: int, 
        teacher_manager: Optional[Any] = None,
        teacher_name: Optional[str] = None
    ) -> List[PendingAchievement]:
        """
        获取教师可以审核的记录，包括：
        1. 本实验室学生提交的成果（状态为 submit）
        2. 教师作为指导教师或获奖者的成果（状态为 submit）

        Args:
            teacher_id: 教师ID
            teacher_manager: TeacherManager实例（可选，用于通过姓名匹配）
            teacher_name: 教师姓名（可选，如果提供则直接使用，否则从teacher_manager获取）

        Returns:
            可审核的记录列表
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()
        
        result_ids = set()  # 使用set避免重复
        result_pendings = []  # 最终结果列表

        try:
            # 1. 查询实验室相关的成果（本实验室学生提交的）
            cursor.execute("""
                SELECT pa.id FROM pending_achievements pa
                INNER JOIN laboratory_students ls ON pa.submitter_id = ls.student_id
                INNER JOIN laboratory_instructors li ON ls.laboratory_id = li.laboratory_id
                WHERE li.teacher_id = ?
                  AND pa.submitter_type = 'student'
                  AND pa.status = 'submit'
                  AND (pa.assigned_reviewer_type = 'teacher' OR pa.assigned_reviewer_type IS NULL)
            """, (teacher_id,))

            lab_rows = cursor.fetchall()
            for row in lab_rows:
                result_ids.add(row['id'])

            # 1b. 所有学生提交且待审核的记录：教师均可查看（避免因未配置实验室导致教师审核页为空）
            cursor.execute("""
                SELECT pa.id FROM pending_achievements pa
                WHERE pa.submitter_type = 'student'
                  AND pa.status = 'submit'
            """)
            for row in cursor.fetchall():
                result_ids.add(row['id'])

            # 2. 查询教师作为指导教师或获奖者的成果
            # 需要从 achievement_data JSON 中匹配
            if teacher_manager or teacher_name:
                # 获取教师姓名
                if not teacher_name:
                    try:
                        if teacher_manager:
                            teacher = teacher_manager.get_teacher_by_id(teacher_id)
                            if teacher:
                                teacher_name = teacher.name
                    except Exception as e:
                        logger.warning(f"获取教师姓名失败: {e}")

                if teacher_name:
                    # 查询所有 submit 状态的记录
                    cursor.execute("""
                        SELECT pa.* FROM pending_achievements pa
                        WHERE pa.status = 'submit'
                    """)

                    all_rows = cursor.fetchall()
                    
                    # 在Python层面过滤
                    for row in all_rows:
                        pending = self._row_to_pending(row)
                        if pending.id in result_ids:
                            continue  # 已包含在实验室成果中
                        
                        # 解析 achievement_data JSON
                        achievement_data = pending.get_achievement_data()
                        if not isinstance(achievement_data, dict):
                            continue
                        
                        # 检查指导教师
                        supervisor_name = achievement_data.get('supervisor_name', '')
                        supervisors = achievement_data.get('supervisors', '')
                        
                        # 检查获奖者（教师获奖者）
                        winner_name = achievement_data.get('winner_name', '')
                        winners = achievement_data.get('winners', '')
                        
                        # 检查 granted_role 是否为教师
                        granted_role = achievement_data.get('granted_role', '')
                        is_teacher_role = granted_role and '教师' in str(granted_role)
                        
                        # 匹配逻辑
                        def name_matches(name_str: str, target_name: str) -> bool:
                            """检查姓名字符串中是否包含目标姓名"""
                            if not name_str or not target_name:
                                return False
                            # 支持逗号分隔的多个姓名
                            names = [n.strip() for n in str(name_str).split(',') if n.strip()]
                            target_name = target_name.strip()
                            return any(n == target_name or n.startswith(target_name) or target_name in n for n in names)
                        
                        # 检查是否是指导教师
                        if supervisor_name and name_matches(supervisor_name, teacher_name):
                            result_ids.add(pending.id)
                            continue
                        
                        if supervisors and name_matches(supervisors, teacher_name):
                            result_ids.add(pending.id)
                            continue
                        
                        # 检查是否是获奖者（且是教师角色）
                        if is_teacher_role:
                            if winner_name and name_matches(winner_name, teacher_name):
                                result_ids.add(pending.id)
                                continue
                            
                            if winners and name_matches(winners, teacher_name):
                                result_ids.add(pending.id)
                                continue
                        
                        # 检查提交人是否是教师本人
                        if pending.submitter_type == 'teacher' and pending.submitter_id == teacher_id:
                            result_ids.add(pending.id)
                            continue

            # 3. 获取所有匹配的记录
            if result_ids:
                placeholders = ','.join(['?'] * len(result_ids))
                cursor.execute(f"""
                    SELECT pa.* FROM pending_achievements pa
                    WHERE pa.id IN ({placeholders})
                    ORDER BY pa.submit_time DESC
                """, list(result_ids))
                
                final_rows = cursor.fetchall()
                result_pendings = [self._row_to_pending(row) for row in final_rows]

            conn.close()
            return result_pendings

        except Exception as e:
            conn.close()
            logger.error(f"查询教师可审核记录失败: {e}", exc_info=True)
            return []

    def get_pending_for_admin(self) -> List[PendingAchievement]:
        """
        获取管理员可以审核的记录

        Returns:
            可审核的记录列表
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT pa.* FROM pending_achievements pa
                WHERE pa.status = 'submit'
                  AND (
                      pa.submitter_type IN ('admin', 'teacher')
                      OR pa.assigned_reviewer_type = 'admin'
                      OR pa.submitter_id NOT IN (
                          SELECT DISTINCT student_id FROM laboratory_students
                      )
                  )
                ORDER BY pa.submit_time DESC
            """)

            rows = cursor.fetchall()
            conn.close()

            return [self._row_to_pending(row) for row in rows]

        except Exception as e:
            conn.close()
            logger.error(f"查询管理员可审核记录失败: {e}")
            return []

    def can_teacher_review(
        self,
        teacher_id: int,
        pending_id: int,
        laboratory_manager: Optional[LaboratoryManager] = None
    ) -> bool:
        """
        验证教师是否可以审核指定记录

        Args:
            teacher_id: 教师ID
            pending_id: pending记录ID
            laboratory_manager: LaboratoryManager实例（可选）

        Returns:
            是否可以审核
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            return False

        # 只能审核学生提交的记录
        if pending.submitter_type != 'student':
            return False

        # 从数据库直接验证（避免依赖 laboratory_manager）
        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT COUNT(*) FROM laboratory_students ls
                INNER JOIN laboratory_instructors li ON ls.laboratory_id = li.laboratory_id
                WHERE li.teacher_id = ? AND ls.student_id = ?
            """, (teacher_id, pending.submitter_id))

            count = cursor.fetchone()[0]
            conn.close()

            return count > 0

        except Exception as e:
            conn.close()
            logger.error(f"验证教师审核权限失败: {e}")
            return False

    # ============================================================
    # 新增方法：状态操作
    # ============================================================

    def submit_for_review_status(self, pending_id: int) -> bool:
        """
        提交审核（状态从 pending 变为 submit）

        Args:
            pending_id: pending 记录ID

        Returns:
            是否成功
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        return self.update(pending_item=pending, status='submit')

    def revert_to_pending(self, pending_id: int) -> bool:
        """
        回退到 pending 状态（提交人修改后）

        Args:
            pending_id: pending 记录ID

        Returns:
            是否成功
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        return self.update(pending_item=pending, status='pending')

    # ============================================================
    # 新增方法：审核操作（原子事务）
    # ============================================================

    def approve_pending(
        self,
        pending_id: int,
        reviewer_id: int,
        reviewer_type: str,
        review_comment: Optional[str] = None
    ) -> bool:
        """
        审核通过（原子事务）

        注意：此方法只处理 pending 记录的状态和审核人信息，
        创建成果记录和文件移动需要由调用方处理。

        Args:
            pending_id: pending 记录ID
            reviewer_id: 审核人ID
            reviewer_type: 审核人类型 ('teacher' | 'admin')
            review_comment: 审核意见

        Returns:
            是否成功
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        if pending.status != 'submit':
            logger.warning(f"记录状态不是 submit，无法审核: {pending_id}, status={pending.status}")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            conn.execute('BEGIN TRANSACTION')

            # 更新审核人信息
            cursor.execute("""
                UPDATE pending_achievements
                SET reviewer_type = ?, reviewer_id = ?, review_time = CURRENT_TIMESTAMP, review_comment = ?
                WHERE id = ?
            """, (reviewer_type, reviewer_id, review_comment, pending_id))

            conn.commit()
            conn.close()

            # 重新加载数据
            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"审核通过失败: {e}")
            return False

    def reject_pending(
        self,
        pending_id: int,
        reviewer_id: int,
        reviewer_type: str,
        review_comment: str
    ) -> bool:
        """
        审核拒绝（原子事务）

        注意：此方法只处理 pending 记录的状态和审核人信息，
        文件删除需要由调用方处理。

        Args:
            pending_id: pending 记录ID
            reviewer_id: 审核人ID
            reviewer_type: 审核人类型 ('teacher' | 'admin')
            review_comment: 拒绝原因（必填）

        Returns:
            是否成功
        """
        if not review_comment:
            logger.warning("拒绝审核必须填写原因")
            return False

        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        if pending.status != 'submit':
            logger.warning(f"记录状态不是 submit，无法审核: {pending_id}, status={pending.status}")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            conn.execute('BEGIN TRANSACTION')

            # 更新审核人信息
            cursor.execute("""
                UPDATE pending_achievements
                SET reviewer_type = ?, reviewer_id = ?, review_time = CURRENT_TIMESTAMP, review_comment = ?
                WHERE id = ?
            """, (reviewer_type, reviewer_id, review_comment, pending_id))

            conn.commit()
            conn.close()

            # 重新加载数据
            self._load_all_from_db()
            logger.info(f"审核拒绝: pending_id={pending_id}, reviewer={reviewer_type}/{reviewer_id}")
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"审核拒绝失败: {e}")
            return False

    def delete_pending_by_submitter(self, pending_id: int, submitter_id: int) -> bool:
        """
        提交人删除（原子事务）

        注意：此方法只删除 pending 记录，文件删除需要由调用方处理。

        Args:
            pending_id: pending 记录ID
            submitter_id: 提交人ID（用于权限验证）

        Returns:
            是否成功
        """
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"找不到 pending 记录: {pending_id}")
            return False

        # 验证权限
        if pending.submitter_id != submitter_id:
            logger.warning(f"无权删除他人的记录: pending_id={pending_id}, submitter_id={submitter_id}")
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            conn.execute('BEGIN TRANSACTION')

            # 删除记录
            cursor.execute("DELETE FROM pending_achievements WHERE id = ?", (pending_id,))

            conn.commit()
            conn.close()

            # 重新加载数据
            self._load_all_from_db()
            logger.info(f"提交人删除记录: pending_id={pending_id}")
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"删除记录失败: {e}")
            return False

    # ============================================================
    # 文件引用计数与安全删除（用于大创等一对多场景）
    # ============================================================

    def count_by_file_path(self, file_path: str) -> int:
        """
        统计引用指定文件路径的 pending 记录数量

        用于判断删除记录时是否可以同时删除关联文件。
        大创等场景下，多条记录可能引用同一个 Excel 文件。

        Args:
            file_path: 文件路径

        Returns:
            引用该文件的记录数量
        """
        if not file_path:
            return 0

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM pending_achievements WHERE file_path = ?",
                (file_path,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count

        except Exception as e:
            conn.close()
            logger.error(f"统计文件引用数量失败: {e}")
            return 0

    def count_by_file_hash(self, file_hash: str) -> int:
        """
        统计引用指定文件 hash 的 pending 记录数量

        Args:
            file_hash: 文件 hash

        Returns:
            引用该文件的记录数量
        """
        if not file_hash:
            return 0

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "SELECT COUNT(*) FROM pending_achievements WHERE file_hash = ?",
                (file_hash,)
            )
            count = cursor.fetchone()[0]
            conn.close()
            return count

        except Exception as e:
            conn.close()
            logger.error(f"统计文件 hash 引用数量失败: {e}")
            return 0

    def safe_delete_with_file(self, pending_id: int) -> Dict[str, Any]:
        """
        安全删除 pending 记录并处理关联文件

        删除逻辑：
        1. 获取记录的 file_path
        2. 删除数据库记录
        3. 检查是否还有其他记录引用该文件
        4. 如果没有其他引用，删除文件

        Args:
            pending_id: pending 记录 ID

        Returns:
            Dict 包含:
            - success: 是否成功删除记录
            - file_deleted: 是否删除了文件
            - file_path: 文件路径（用于调试）
            - remaining_refs: 剩余引用数（删除前）
            - message: 描述信息
        """
        result = {
            'success': False,
            'file_deleted': False,
            'file_path': None,
            'remaining_refs': 0,
            'message': ''
        }

        # 获取记录
        pending = self.get_pending_by_id(pending_id)
        if not pending:
            result['message'] = f'找不到 pending 记录: {pending_id}'
            logger.warning(result['message'])
            return result

        file_path = pending.file_path
        result['file_path'] = file_path

        # 删除数据库记录
        if not self.delete_pending(pending_id):
            result['message'] = f'删除数据库记录失败: {pending_id}'
            return result

        result['success'] = True

        # 检查文件引用
        if file_path:
            # 删除记录后，重新统计引用数量
            remaining_refs = self.count_by_file_path(file_path)
            result['remaining_refs'] = remaining_refs

            if remaining_refs == 0:
                # 没有其他记录引用该文件，可以安全删除（file_path 可能为相对路径）
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager
                    ufm = get_unified_file_manager()
                    path = ufm.resolve_path(file_path)
                    if path.exists():
                        path.unlink()
                        result['file_deleted'] = True
                        result['message'] = f'记录和文件均已删除'
                        logger.info(f"删除 pending 记录和关联文件: pending_id={pending_id}, file={file_path}")
                        # 清理该文件所在空目录（如 review/session_id）
                        ufm.cleanup_empty_parent_dirs_for_path(path, ['temp_upload', 'review'])
                    else:
                        result['message'] = f'记录已删除，文件不存在'
                        logger.debug(f"删除 pending 记录，文件已不存在: pending_id={pending_id}, file={file_path}")
                except Exception as e:
                    result['message'] = f'记录已删除，但删除文件失败: {e}'
                    logger.warning(f"删除文件失败: {file_path}, {e}")
            else:
                result['message'] = f'记录已删除，文件仍被 {remaining_refs} 条记录引用'
                logger.info(f"删除 pending 记录，文件仍有引用: pending_id={pending_id}, refs={remaining_refs}")
        else:
            result['message'] = '记录已删除（无关联文件）'

        return result