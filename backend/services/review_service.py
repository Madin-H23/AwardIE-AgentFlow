"""
成果审核服务模块

提供统一的审核业务逻辑，支持:
1. 单条/批量提交到主数据库
2. 单条/批量放弃（删除）
3. 字段修改与重新验证
4. 审核日志记录
5. 实验室关联

这个模块将 Web 端（admin.py）和测试程序（test_files_commit.py）
中的审核逻辑统一到一处，确保行为一致。
"""
import logging
import shutil
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from flask import copy_current_request_context
from config.loader import get_config

logger = logging.getLogger(__name__)


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class ReviewResult:
    """审核操作结果"""
    success: bool
    pending_id: int
    action: str  # 'approved', 'rejected', 'deleted', 'modified'
    
    # 成功时的结果信息
    target_table: Optional[str] = None  # 提交到的目标表名
    target_id: Optional[int] = None  # 目标表中的记录ID
    file_moved_to: Optional[str] = None  # 文件移动后的路径
    
    # 字段修改记录
    modifications: List[Dict] = field(default_factory=list)
    
    # 错误信息
    error: Optional[str] = None
    
    # 实验室关联
    laboratory_id: Optional[int] = None
    laboratory_name: Optional[str] = None

    # 大创等一对多场景：实际入库条数（默认 1）
    submitted_count: Optional[int] = None


@dataclass
class Reviewer:
    """审核人信息"""
    reviewer_type: str  # 'student', 'teacher', 'admin'
    reviewer_id: int


# ============================================================
# 常量定义
# ============================================================

# 成果类型映射
ACHIEVEMENT_TYPES = {
    'award': '奖状',
    'patent': '专利',
    'software': '软著',
    'innovation': '大创',
    'other': '其他'
}

# 图片文件扩展名
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.tif', '.jfif'}


# ============================================================
# ReviewService 主类
# ============================================================

class ReviewService:
    """
    成果审核服务
    
    统一的审核业务逻辑入口，提供:
    - 实验室关联确定
    - 单条/批量审核通过
    - 单条/批量放弃
    - 字段修改与重新验证
    - 提交到主数据库
    - 审核日志记录
    """
    
    def __init__(
        self,
        pending_manager,
        review_log_manager,
        laboratory_manager,
        student_manager,
        teacher_manager,
        # 各类型成果 Manager
        award_manager=None,
        patent_manager=None,
        software_manager=None,
        innovation_manager=None,
        other_file_manager=None,
        competition_manager=None,
        # 配置管理
        auto_archive_config_manager=None,
        # 配置
        files_dir: Optional[Path] = None
    ):
        """
        初始化审核服务

        Args:
            pending_manager: PendingAchievementManager 实例
            review_log_manager: ReviewLogManager 实例
            laboratory_manager: LaboratoryManager 实例
            student_manager: StudentManager 实例
            teacher_manager: TeacherManager 实例
            award_manager: AwardManager 实例（可选）
            patent_manager: PatentManager 实例（可选）
            software_manager: SoftwareCopyrightManager 实例（可选）
            innovation_manager: InnovationProjectManager 实例（可选）
            other_file_manager: OtherFileManager 实例（可选）
            competition_manager: CompetitionManager 实例（可选，奖状需要）
            auto_archive_config_manager: AutoArchiveConfigManager 实例（可选）
            files_dir: 文件存储根目录
        """
        # 必需的 Manager
        self.pending_manager = pending_manager
        self.review_log_manager = review_log_manager
        self.laboratory_manager = laboratory_manager
        self.student_manager = student_manager
        self.teacher_manager = teacher_manager

        # 各类型成果 Manager（可选，按需提供）
        self.award_manager = award_manager
        self.patent_manager = patent_manager
        self.software_manager = software_manager
        self.innovation_manager = innovation_manager
        self.other_file_manager = other_file_manager
        self.competition_manager = competition_manager

        # 自动归档配置管理（可选）
        self.auto_archive_config_manager = auto_archive_config_manager

        # 配置
        self.files_dir = files_dir
    
    # ============================================================
    # 实验室关联逻辑
    # ============================================================
    
    def determine_laboratory(self, pending) -> Tuple[Optional[int], Optional[str]]:
        """
        确定成果关联的实验室

        规则优先级:
        1. 编辑页用户选定的 laboratory_id（用户在页面修改的最新选择）→ 最高优先级
        2. Pending 记录中的 laboratory_id（导入时用户选定的实验室）→ 次优先级
        3. 对于大创：从第一导师（指导教师/supervisors）所在实验室，与奖状逻辑一致
        4. 对于奖状类型：
           - 教师奖状：从获奖者（winner_name）中取排名第一的教师所在实验室
           - 学生奖状：从指导教师（supervisor_name）中取排名第一的教师所在实验室
        5. 对于其他类型：从指导教师中取排名第一的教师所在实验室
        6. 如果提交人是教师 → 提交人所在实验室
        7. 其他情况 → 不设置实验室关联

        注：
        - 用户在编辑页的修改应该覆盖导入时的设置
        - 不根据学生提交人所属实验室推定成果关联，因为学生可能属于多个实验室，
          且学生提交的成果不一定与其所属实验室相关。

        Args:
            pending: PendingAchievement 对象

        Returns:
            Tuple[实验室ID, 关联原因说明]，如果无法确定则返回 (None, None)
        """

        data = pending.get_achievement_data()

        # 1. 最高优先级：编辑页用户选定的 laboratory_id（用户在页面修改的最新选择）
        raw = data.get('laboratory_id')
       
        if raw is not None and raw != '':
            try:
                lab_id = int(raw)
                if lab_id > 0:
                    lab = self.laboratory_manager.get_laboratory_by_id(lab_id)
                    if lab:
                        reason = "编辑页用户选定的实验室"
       
                        return lab_id, reason
            except (TypeError, ValueError):
                pass

        # 2. 次优先级：Pending 记录中的 laboratory_id（导入时用户选定的实验室）
        if hasattr(pending, 'laboratory_id') and pending.laboratory_id is not None:
            lab = self.laboratory_manager.get_laboratory_by_id(pending.laboratory_id)
            if lab:
                reason = "导入时用户已选定的实验室"
                
                return pending.laboratory_id, reason
            

        # 3. 大创：按第一导师（指导教师）所在实验室，与奖状逻辑一致
        if pending.achievement_type == 'innovation':
            first_item = None
            projects_list = data.get('projects')
            if isinstance(projects_list, list) and len(projects_list) > 0:
                first_item = projects_list[0]
            else:
                first_item = data
            if first_item and isinstance(first_item, dict):
                teachers_raw = first_item.get('指导教师') or first_item.get('supervisors') or first_item.get('teachers') or []
                if isinstance(teachers_raw, str):
                    teachers_raw = [teachers_raw]
                if teachers_raw:
                    first_teacher_name = teachers_raw[0]
                    if isinstance(first_teacher_name, dict):
                        first_teacher_name = first_teacher_name.get('姓名', '') or first_teacher_name.get('name', '')
                    if first_teacher_name:
                        found_teachers = self.teacher_manager.find_teachers_by_name(first_teacher_name)
                        teacher = None
                        for t in found_teachers:
                            if (t.name or '').strip() == (first_teacher_name or '').strip():
                                teacher = t
                                break
                        if teacher:
                            lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                            if lab:
                                reason = f"大创：根据第一导师 {first_teacher_name} 所在实验室关联"
                                
                                return lab.id, reason

        # 4. 对于奖状类型，根据证书类型选择不同的教师来源
        if pending.achievement_type == 'award':
            granted_role = data.get('granted_role', '')
            is_teacher_certificate = granted_role and "教师" in granted_role
            
            if is_teacher_certificate:
                # 教师奖状：从获奖者（winner_name）中取排名第一的教师
                winner_name = data.get('winner_name', '')
                if winner_name:
                    # 解析获奖者姓名（可能是逗号分隔的多个姓名）
                    winner_names = [n.strip() for n in str(winner_name).split(',') if n.strip()]
                    if winner_names:
                        first_winner_name = winner_names[0]
                        # 通过教师姓名查找教师（精确匹配）
                        found_teachers = self.teacher_manager.find_teachers_by_name(first_winner_name)
                        teacher = None
                        for t in found_teachers:
                            if t.name.strip() == first_winner_name.strip():
                                teacher = t
                                break
                        
                        if teacher:
                            # 查找教师所属的实验室
                            lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                            if lab:
                                reason = f"教师奖状：根据第一教师获奖者 {first_winner_name} 关联"
                                
                                return lab.id, reason
            else:
                # 学生奖状：从指导教师（supervisor_name）中取排名第一的教师
                supervisor_name = data.get('supervisor_name', '')
                if supervisor_name:
                    # 解析指导教师姓名（可能是逗号分隔的多个姓名）
                    supervisor_names = [n.strip() for n in str(supervisor_name).split(',') if n.strip()]
                    if supervisor_names:
                        first_supervisor_name = supervisor_names[0]
                        # 通过教师姓名查找教师（精确匹配）
                        found_teachers = self.teacher_manager.find_teachers_by_name(first_supervisor_name)
                        teacher = None
                        for t in found_teachers:
                            if t.name.strip() == first_supervisor_name.strip():
                                teacher = t
                                break
                        
                        if teacher:
                            # 查找教师所属的实验室
                            lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                            if lab:
                                reason = f"学生奖状：根据第一指导教师 {first_supervisor_name} 关联"
                                
                                return lab.id, reason
        
        # 2. 对于其他类型，尝试从成果数据中获取教师信息（指导教师）
        teachers = data.get('指导教师') or data.get('teachers') or data.get('supervisor_name') or []
        if isinstance(teachers, str):
            teachers = [teachers]
        
        if teachers and len(teachers) > 0:
            first_teacher_name = teachers[0]
            if isinstance(first_teacher_name, dict):
                first_teacher_name = first_teacher_name.get('姓名', '')
            
            if first_teacher_name:
                # 通过教师姓名查找教师（精确匹配）
                found_teachers = self.teacher_manager.find_teachers_by_name(first_teacher_name)
                teacher = None
                for t in found_teachers:
                    if t.name == first_teacher_name:
                        teacher = t
                        break
                
                if teacher:
                    # 查找教师所属的实验室
                    lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                    if lab:
                        reason = f"根据指导教师 {first_teacher_name} 关联"
                        return lab.id, reason
        
        # 3. 如果提交人是教师，检查其所属实验室
        if pending.submitter_type == 'teacher':
            lab = self.laboratory_manager.get_laboratory_by_teacher_id(pending.submitter_id)
            if lab:
                reason = "根据提交人（教师）关联"
                return lab.id, reason
        
        # 4. 无法确定实验室（不根据学生提交人推定）
       
        return None, None
    
    def get_student_laboratories(self, student_id: int) -> List:
        """
        获取学生所属的所有实验室
        
        Args:
            student_id: 学生ID
        
        Returns:
            Laboratory 对象列表
        """
        labs = []
        for lab in self.laboratory_manager.laboratories:
            for student in lab.students:
                if student.id == student_id:
                    labs.append(lab)
                    break
        return labs
    
    # ============================================================
    # 文件类型判断
    # ============================================================
    
    def is_image_file(self, file_path: str) -> bool:
        """
        判断文件是否为图片
        
        Args:
            file_path: 文件路径
        
        Returns:
            是否为图片文件
        """
        if not file_path:
            return False
        ext = Path(file_path).suffix.lower()
        return ext in IMAGE_EXTENSIONS

    # ============================================================
    # 审核策略管理 (Policy Management)
    # ============================================================

    def submit_achievement(self, pending_id: int, submitter_type: str, submitter_id: int) -> ReviewResult:
        """
        提交成果（Status: pending -> submit）并触发审核策略

        Args:
            pending_id: PendingAchievement ID
            submitter_type: 提交人类型
            submitter_id: 提交人ID

        Returns:
            ReviewResult: 操作结果
        """
        logger.info(f"[submit_achievement] 开始: pending_id={pending_id}, submitter_type={submitter_type}, submitter_id={submitter_id}")

        pending = self.pending_manager.get_pending_by_id(pending_id)
        if not pending:
            logger.warning(f"[submit_achievement] 记录不存在: pending_id={pending_id}")
            return ReviewResult(success=False, pending_id=pending_id, action='submit', error="Record not found")

        logger.info(f"[submit_achievement] pending.submitter_type={pending.submitter_type}, pending.submitter_id={pending.submitter_id}")

        # 1. 验证权限（管理员可以代提交，跳过权限验证）
        if submitter_type != 'admin':
            if pending.submitter_type != submitter_type or pending.submitter_id != submitter_id:
                return ReviewResult(success=False, pending_id=pending_id, action='submit', error="Permission denied")
        else:
            logger.info(f"[submit_achievement] 管理员提交，跳过权限验证")

        # P1-13 留痕：动作1=提交（best-effort，失败不阻塞）
        try:
            from backend.utils.audit_logger import audit_log
            audit_log(1, pending_id, getattr(pending, 'achievement_type', None),
                      operator={"id": submitter_id, "code": str(submitter_id),
                                "user_type": submitter_type})
        except Exception:
            pass

        # 2. 更新状态为 submit
        old_status = pending.status
        if pending.status != 'submit':
            # 只有从 pending -> submit 才更新
            logger.info(
                "[submit_achievement] 即将写入数据库: pending_id=%s, submitter_type=%s, submitter_id=%s, old_status=%s, new_status=%s",
                pending_id, submitter_type, submitter_id, old_status, 'submit',
            )
            self.pending_manager.update(pending, status='submit')
            # 重新获取以确保最新
            pending = self.pending_manager.get_pending_by_id(pending_id)
            logger.info("[submit_achievement] 已写入数据库: pending_id=%s, status=%s", pending_id, pending.status if pending else None)
        else:
            logger.info("[submit_achievement] 记录已是 submit 状态，跳过更新: pending_id=%s", pending_id)

        logger.info(f"[submit_achievement] 调用 apply_review_policy: pending_id={pending_id}, status={pending.status}")

        # 3. 应用审核策略
        return self.apply_review_policy(pending)

    def apply_review_policy(self, pending_item) -> ReviewResult:
        """
        根据配置自动应用审核策略

        策略在用户提交时触发（status='submit'）。
        教师和管理员提交一律自动归档；学生提交由本页配置（奖状/专利/软著、大创/其他）决定是否自动归档。
        """
        logger.info(f"[apply_review_policy] 开始: pending_id={pending_item.id}, type={pending_item.achievement_type}, is_valid={pending_item.is_valid()}, submitter_type={getattr(pending_item, 'submitter_type', None)}, auto_archive_config_manager={self.auto_archive_config_manager is not None}")

        # 1. 教师/管理员提交一律自动归档，不查配置
        submitter_type = getattr(pending_item, 'submitter_type', None)
        force_archive = False  # 是否强制归档（跳过验证检查）
        if submitter_type in ('teacher', 'admin'):
            should_auto_archive = True
            use_async = False  # 改为同步归档，确保提交后立即完成
            force_archive = True  # 教师/管理员提交跳过验证检查
            logger.info(f"教师/管理员提交，强制自动归档（同步，跳过验证）: pending={pending_item.id}")
        else:
            # 2. 学生提交：由配置决定是否自动归档（优先使用数据库配置）
            should_auto_archive = False
            use_async = False

            if self.auto_archive_config_manager:
                should_auto_archive = self.auto_archive_config_manager.should_auto_archive(
                    achievement_type=pending_item.achievement_type,
                    is_valid=pending_item.is_valid()
                )
                use_async = True
                logger.info(f"数据库配置判断: pending={pending_item.id}, auto_archive={should_auto_archive}")
            else:
                # 回退到配置文件（向后兼容）
                config_loader = get_config()
                config = config_loader.reload()
                review_config = config.get("审核配置", {})
                mode = review_config.get("审核模式", "manual_review")
                manual_types = review_config.get("需人工审核类型", [])

                logger.info(f"配置文件模式: {mode}")

                if mode == "allow_all":
                    should_auto_archive = True
                elif mode == "allow_qualified":
                    should_auto_archive = pending_item.is_valid()
                elif mode == "manual_review":
                    if pending_item.achievement_type not in manual_types:
                        should_auto_archive = pending_item.is_valid()

                use_async = False  # 配置文件模式不使用异步

        # 3. Agent 智能把关：即将自动归档的成果先过 AI 复核（语义 + 知识库交叉校验）
        #    决策为 reject / need_manual → 转人工审核；pass 或 Agent 异常 → 保持自动归档
        agent_review = None
        if should_auto_archive:
            blocked, agent_review = self._run_agent_gate(pending_item)
            if blocked:
                logger.info(
                    f"[apply_review_policy] Agent 把关拦截，转人工审核: pending={pending_item.id}, "
                    f"decision={agent_review.get('decision') if agent_review else '?'}"
                )
                should_auto_archive = False
            if agent_review:
                self._save_agent_review(pending_item, agent_review)

        # 4. 构造系统审核人
        reviewer = Reviewer(reviewer_type='system', reviewer_id=0)

        # 5. 执行策略
        if should_auto_archive:
            # 应该自动归档
            if use_async:
                # 使用异步任务处理
                logger.info(f"[apply_review_policy] 触发异步自动归档: pending={pending_item.id}")
                self._trigger_async_auto_archive(pending_item.id)
                return ReviewResult(
                    success=True,
                    pending_id=pending_item.id,
                    action='auto_archive_started',
                    error="Async auto-archive task started"
                )
            else:
                # 同步执行（向后兼容）
                logger.info(f"[apply_review_policy] 同步自动归档开始: pending={pending_item.id}, reviewer={reviewer.reviewer_type}, force={force_archive}")
                result = self.approve_single(pending_item.id, reviewer, force=force_archive)
                logger.info(f"[apply_review_policy] 同步自动归档完成: pending={pending_item.id}, action={result.action}, success={result.success}")
                return result
        else:
            # 不自动归档，保持 submit 状态等待人工审核
            logger.info(f"等待人工审核: pending={pending_item.id}")
            return ReviewResult(
                success=True,
                pending_id=pending_item.id,
                action='pending_review',
                error=None
            )

    # ============================================================
    # Agent 智能把关（P1：决策层接入）
    # ============================================================

    def _run_agent_gate(self, pending_item):
        """对即将自动归档的成果跑 Agent 复核（规则 + RAG 知识库交叉校验）。

        Returns:
            (blocked, review_result)
            - blocked: decision in (reject, need_manual) 时为 True（拦截自动归档）
            - review_result: {decision, issues, suggestion, rag_reference}；失败为 None
        任何异常都降级为 (False, None)，绝不阻塞业务（可用性优先）。
        """
        try:
            from backend.agent.review_api import review_extraction
            from config.loader import get_config as _get_config
            from backend.rag.embeddings import build_embeddings
            from backend.rag.vectorstore import build_vectorstore

            config_loader = _get_config()
            data = pending_item.get_achievement_data() or {}

            # 向量库可选：构造失败则只做规则校验，跳过 RAG 交叉校验
            vectorstore = None
            try:
                emb = build_embeddings(config_loader)
                vectorstore = build_vectorstore(config_loader, emb)
            except Exception as e:
                logger.warning("Agent 把关：向量库不可用，跳过 RAG 交叉校验: %s", e)

            review = review_extraction(
                config_loader,
                {
                    "data": data,
                    "doc_type": getattr(pending_item, "achievement_type", None),
                },
                vectorstore,
            )
            blocked = review.get("decision") in ("reject", "need_manual")
            logger.info(f"[Agent把关] pending={pending_item.id}, decision={review.get('decision')}, blocked={blocked}")
            return blocked, review
        except Exception as e:
            logger.warning(f"Agent 把关失败，降级为原策略: {e}")
            return False, None

    def _save_agent_review(self, pending_item, agent_review: dict):
        """把 Agent 审核结论存入 pending.ext_info.agent_review（供审核页展示）。"""
        # P1-13 留痕：动作2=AI审核（operator=AI，决策快照入 change_detail，双保险防随 pending 删除丢失）
        try:
            from backend.utils.audit_logger import audit_log
            decision = agent_review.get("decision") if isinstance(agent_review, dict) else None
            audit_log(2, getattr(pending_item, 'id', None), getattr(pending_item, 'achievement_type', None),
                      operator="AI", action_result={"pass": 1, "need_manual": 0, "reject": 2}.get(decision, 0),
                      change_detail=agent_review)
        except Exception:
            pass
        try:
            ext_info = pending_item.get_ext_info() or {}
            ext_info["agent_review"] = agent_review
            self.pending_manager.update(pending_item, ext_info=ext_info)
        except Exception as e:
            logger.warning(f"保存 agent_review 失败: {e}")

    # ============================================================
    # 异步自动归档
    # ============================================================

    def _trigger_async_auto_archive(self, pending_id: int):
        """
        触发异步自动归档任务

        Args:
            pending_id: pending 记录 ID
        """
        @copy_current_request_context
        def _async_task():
            """异步任务函数"""
            try:
                self._auto_archive_pending_async(pending_id)
            except Exception as e:
                logger.error(f"异步自动归档失败: pending_id={pending_id}, error={e}", exc_info=True)

        thread = threading.Thread(target=_async_task, daemon=True)
        thread.start()
        logger.info(f"异步自动归档任务已启动: pending_id={pending_id}")

    def _auto_archive_pending_async(self, pending_id: int):
        """
        异步自动归档 pending 记录

        Args:
            pending_id: pending 记录 ID
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                logger.warning(f"异步自动归档找不到记录: {pending_id}")
                return

            # 构造系统审核人
            reviewer = Reviewer(reviewer_type='system', reviewer_id=0)

            # 执行审核通过（自动归档使用 force=True，因为用户已经确认提交）
            result = self.approve_single(pending_id, reviewer, force=True)

            if result.success:
                logger.info(f"异步自动归档成功: pending_id={pending_id}, target_id={result.target_id}")
            else:
                logger.error(f"异步自动归档失败: pending_id={pending_id}, error={result.error}")

        except Exception as e:
            logger.error(f"异步自动归档异常: pending_id={pending_id}, error={e}", exc_info=True)

    # ============================================================
    # 审核操作
    # ============================================================
    
    def approve_single(
        self,
        pending_id: int,
        reviewer: Reviewer,
        lab_id: Optional[int] = None,
        force: bool = False
    ) -> ReviewResult:
        """
        审核通过单条记录
        
        Args:
            pending_id: pending 记录 ID
            reviewer: 审核人信息
            lab_id: 指定的实验室ID（可选，如果不指定则自动确定）
            force: 是否强制通过（跳过验证检查）
        
        Returns:
            ReviewResult 操作结果
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                return ReviewResult(
                    success=False,
                    pending_id=pending_id,
                    action='approved',
                    error=f'找不到 pending 记录: {pending_id}'
                )
            
            # 检查验证状态（除非 force=True）
            if not force:
                validation_result = pending.get_validation_result()
                if validation_result and not validation_result.get('is_valid', True):
                    return ReviewResult(
                        success=False,
                        pending_id=pending_id,
                        action='approved',
                        error='验证未通过，请先修正数据或使用强制通过'
                    )
            
            # 确定实验室关联
            if lab_id is None:
                lab_id, reason = self.determine_laboratory(pending)
            
            lab_name = None
            if lab_id:
                lab = self.laboratory_manager.get_laboratory_by_id(lab_id)
                lab_name = lab.name if lab else None
            
            # 根据成果类型处理
            if pending.achievement_type == 'other':
                return self.handle_other_type(pending, lab_id, reviewer)
            else:
                # P1-8 防重闸先行：先软归档（条件更新 submit→archived，rowcount=0 说明已被并发处理）
                if not self.pending_manager.archive(pending_id):
                    logger.warning(f"[approve_single] 并发防重拦截：记录已不在 submit 态 pending_id={pending_id}")
                    return ReviewResult(
                        success=False, pending_id=pending_id, action='approved',
                        error="记录状态已变化，可能已被他人处理")
                # 提交到主数据库
                success, target_id, error, submitted_count = self.submit_to_main_db(pending, lab_id, reviewer)

                if success:
                    self._log_review_action(
                        pending=pending,
                        reviewer=reviewer,
                        action_type='approved',
                        result_type=pending.achievement_type,
                        result_id=target_id
                    )
                    # P1-13 留痕：动作6=审核通过 + 动作8=入库（同一原子动作，两条时间线记录）
                    try:
                        from backend.utils.audit_logger import audit_log
                        op = {"id": reviewer.reviewer_id, "code": str(reviewer.reviewer_id),
                              "user_type": reviewer.reviewer_type}
                        audit_log(6, pending_id, pending.achievement_type, operator=op,
                                  change_detail={"target_table": pending.achievement_type, "target_id": target_id})
                        audit_log(8, target_id, pending.achievement_type, operator=op, remark="入库")
                    except Exception:
                        pass
                    return ReviewResult(
                        success=True,
                        pending_id=pending_id,
                        action='approved',
                        target_table=pending.achievement_type,
                        target_id=target_id,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name,
                        submitted_count=submitted_count
                    )
                else:
                    # P1-8 入库失败补偿：回滚归档，恢复 submit 供修复后重审
                    if self.pending_manager.unarchive(pending_id):
                        logger.warning(f"[approve_single] 入库失败，已回滚归档: pending_id={pending_id}")
                    return ReviewResult(
                        success=False,
                        pending_id=pending_id,
                        action='approved',
                        error=error,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name
                    )
                    
        except Exception as e:
            logger.error(f"审核通过失败: {e}", exc_info=True)
            return ReviewResult(
                success=False,
                pending_id=pending_id,
                action='approved',
                error=str(e)
            )
    
    def approve_batch(
        self,
        pending_ids: List[int],
        reviewer: Reviewer,
        force: bool = False
    ) -> List[ReviewResult]:
        """
        批量审核通过
        
        Args:
            pending_ids: pending 记录 ID 列表
            reviewer: 审核人信息
            force: 是否强制通过（跳过验证检查）
        
        Returns:
            ReviewResult 列表
        """
        results = []
        for pending_id in pending_ids:
            result = self.approve_single(
                pending_id=pending_id,
                reviewer=reviewer,
                force=force
            )
            results.append(result)
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        logger.info(f"批量审核完成: 成功 {success_count}, 失败 {fail_count}")
        
        return results
    
    def discard_single(
        self,
        pending_id: int,
        reviewer: Reviewer,
        reason: Optional[str] = None
    ) -> ReviewResult:
        """
        放弃单条记录
        
        Args:
            pending_id: pending 记录 ID
            reviewer: 审核人信息
            reason: 放弃原因
        
        Returns:
            ReviewResult 操作结果
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                return ReviewResult(
                    success=False,
                    pending_id=pending_id,
                    action='deleted',
                    error=f'找不到 pending 记录: {pending_id}'
                )
            
            # 记录审核日志
            self._log_review_action(
                pending=pending,
                reviewer=reviewer,
                action_type='deleted',
                review_comment=reason
            )
            
            # 安全删除 pending 记录（包括文件）
            self.pending_manager.safe_delete_with_file(pending_id)
            
            logger.info(f"已放弃 pending 记录: {pending_id}")
            return ReviewResult(
                success=True,
                pending_id=pending_id,
                action='deleted'
            )
            
        except Exception as e:
            logger.error(f"放弃记录失败: {e}", exc_info=True)
            return ReviewResult(
                success=False,
                pending_id=pending_id,
                action='deleted',
                error=str(e)
            )
    
    def discard_batch(
        self,
        pending_ids: List[int],
        reviewer: Reviewer,
        reason: Optional[str] = None
    ) -> List[ReviewResult]:
        """
        批量放弃
        
        Args:
            pending_ids: pending 记录 ID 列表
            reviewer: 审核人信息
            reason: 放弃原因
        
        Returns:
            ReviewResult 列表
        """
        results = []
        for pending_id in pending_ids:
            result = self.discard_single(
                pending_id=pending_id,
                reviewer=reviewer,
                reason=reason
            )
            results.append(result)
        
        # 统计结果
        success_count = sum(1 for r in results if r.success)
        fail_count = len(results) - success_count
        logger.info(f"批量放弃完成: 成功 {success_count}, 失败 {fail_count}")
        
        return results
    
    def _log_review_action(
        self,
        pending,
        reviewer: Reviewer,
        action_type: str,
        result_type: Optional[str] = None,
        result_id: Optional[int] = None,
        result_file_path: Optional[str] = None,
        review_comment: Optional[str] = None,
        operation_note: Optional[str] = None
    ):
        """
        记录审核日志
        
        Args:
            pending: PendingAchievement 对象
            reviewer: 审核人信息
            action_type: 操作类型 ('approved', 'rejected', 'deleted')
            result_type: approved 时的成果类型
            result_id: approved 时的成果ID
            result_file_path: approved 时文件移动后的路径
            review_comment: 审核意见
            operation_note: 操作说明
        """
        if not self.review_log_manager:
            logger.warning("未配置 ReviewLogManager，跳过日志记录")
            return
        
        try:
            self.review_log_manager.create_log(
                pending_id=pending.id,
                achievement_type=pending.achievement_type,
                file_hash=pending.file_hash if hasattr(pending, 'file_hash') else None,
                file_path=pending.file_path if hasattr(pending, 'file_path') else None,
                submitter_type=pending.submitter_type,
                submitter_id=pending.submitter_id,
                reviewer_type=reviewer.reviewer_type,
                reviewer_id=reviewer.reviewer_id,
                action_type=action_type,
                result_type=result_type,
                result_id=result_id,
                result_file_path=result_file_path,
                review_comment=review_comment,
                operation_note=operation_note
            )
        except Exception as e:
            logger.error(f"记录审核日志失败: {e}", exc_info=True)
    
    # ============================================================
    # 字段修改
    # ============================================================
    
    def modify_field(
        self,
        pending_id: int,
        field_name: str,
        new_value: Any,
        modifier: Reviewer
    ) -> ReviewResult:
        """
        修改单个字段
        
        Args:
            pending_id: pending 记录 ID
            field_name: 字段名
            new_value: 新值
            modifier: 修改人信息
        
        Returns:
            ReviewResult 操作结果（包含修改记录）
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                return ReviewResult(
                    success=False,
                    pending_id=pending_id,
                    action='modified',
                    error=f'找不到 pending 记录: {pending_id}'
                )
            
            # 获取当前数据
            data = pending.get_achievement_data()
            old_value = data.get(field_name)
            
            # 更新字段
            data[field_name] = new_value
            
            # 保存更新后的数据
            self.pending_manager.update(
                pending_item=pending,
                achievement_data=data
            )
            
            # P1-13 留痕：动作9=修改字段（before/after diff 入 change_detail）
            try:
                from backend.utils.audit_logger import audit_log
                audit_log(9, pending.id, pending.achievement_type,
                          operator={"id": modifier.reviewer_id, "code": str(modifier.reviewer_id),
                                    "user_type": modifier.reviewer_type},
                          change_detail={"field": field_name, "old": old_value, "new": new_value})
            except Exception:
                pass
            # 记录修改
            modification = {
                'field': field_name,
                'old_value': old_value,
                'new_value': new_value,
                'modifier_type': modifier.reviewer_type,
                'modifier_id': modifier.reviewer_id,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"字段修改: pending_id={pending_id}, field={field_name}, old={old_value}, new={new_value}")
            
            return ReviewResult(
                success=True,
                pending_id=pending_id,
                action='modified',
                modifications=[modification]
            )
            
        except Exception as e:
            logger.error(f"修改字段失败: {e}", exc_info=True)
            return ReviewResult(
                success=False,
                pending_id=pending_id,
                action='modified',
                error=str(e)
            )
    
    def modify_multiple_fields(
        self,
        pending_id: int,
        field_updates: Dict[str, Any],
        modifier: Reviewer
    ) -> ReviewResult:
        """
        批量修改多个字段
        
        Args:
            pending_id: pending 记录 ID
            field_updates: 字段更新字典 {field_name: new_value}
            modifier: 修改人信息
        
        Returns:
            ReviewResult 操作结果（包含所有修改记录）
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                return ReviewResult(
                    success=False,
                    pending_id=pending_id,
                    action='modified',
                    error=f'找不到 pending 记录: {pending_id}'
                )
            
            # 获取当前数据
            data = pending.get_achievement_data()
            modifications = []
            
            # 更新所有字段
            for field_name, new_value in field_updates.items():
                old_value = data.get(field_name)
                data[field_name] = new_value
                
                modifications.append({
                    'field': field_name,
                    'old_value': old_value,
                    'new_value': new_value,
                    'modifier_type': modifier.reviewer_type,
                    'modifier_id': modifier.reviewer_id,
                    'timestamp': datetime.now().isoformat()
                })
            
            # 保存更新后的数据
            self.pending_manager.update(
                pending_item=pending,
                achievement_data=data
            )
            
            logger.info(f"批量字段修改: pending_id={pending_id}, fields={list(field_updates.keys())}")
            
            return ReviewResult(
                success=True,
                pending_id=pending_id,
                action='modified',
                modifications=modifications
            )
            
        except Exception as e:
            logger.error(f"批量修改字段失败: {e}", exc_info=True)
            return ReviewResult(
                success=False,
                pending_id=pending_id,
                action='modified',
                error=str(e)
            )
    
    def revalidate(self, pending_id: int) -> Dict[str, Any]:
        """
        重新验证
        
        Args:
            pending_id: pending 记录 ID
        
        Returns:
            验证结果字典，包含 is_valid 和 issues 等字段
        """
        try:
            # 获取 pending 记录
            pending = self.pending_manager.get_pending_by_id(pending_id)
            if not pending:
                return {
                    'is_valid': False,
                    'error': f'找不到 pending 记录: {pending_id}'
                }
            
            # 获取成果数据
            data = pending.get_achievement_data()
            achievement_type = pending.achievement_type
            
            # 使用基本验证
            return self._basic_validation(data, achievement_type)
            
        except Exception as e:
            logger.error(f"重新验证失败: {e}", exc_info=True)
            return {
                'is_valid': False,
                'error': str(e)
            }
    
    def _basic_validation(self, data: Dict[str, Any], achievement_type: str) -> Dict[str, Any]:
        """
        基本验证（验证引擎不可用时的后备方案）
        
        Args:
            data: 成果数据
            achievement_type: 成果类型
        
        Returns:
            验证结果字典
        """
        issues = []
        
        if achievement_type == 'award':
            if not data.get('competition_name'):
                issues.append('缺少竞赛名称')
            if not data.get('winner_name'):
                issues.append('缺少获奖人姓名')
        elif achievement_type == 'patent':
            if not data.get('patent_name'):
                issues.append('缺少专利名称')
        elif achievement_type == 'software':
            if not data.get('software_name'):
                issues.append('缺少软件名称')
        elif achievement_type == 'innovation':
            project_name = data.get('project_name') or data.get('项目名称')
            if not project_name:
                issues.append('缺少项目名称')
        elif achievement_type == 'other':
            if not data.get('title') and not data.get('file_name'):
                issues.append('缺少文件标题')
        
        return {
            'is_valid': len(issues) == 0,
            'issues': issues,
            'validation_type': 'basic'
        }
    
    def collect_validation_issues(self, validation_result: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        收集并格式化验证问题
        
        Args:
            validation_result: 验证结果字典
        
        Returns:
            格式化的问题列表，每个元素包含 field 和 message（已去重）
            如果 field 包含多个字段（逗号分隔），会拆分成多个独立问题
        """
        issues = []
        seen = set()  # 用于去重: (field, message)
        
        def add_issue(field: str, message: str):
            """添加问题（自动去重，支持拆分多字段）"""
            # 如果 field 包含逗号，拆分成多个字段
            if ',' in field:
                fields = [f.strip() for f in field.split(',') if f.strip()]
                for single_field in fields:
                    key = (single_field, message)
                    if key not in seen:
                        seen.add(key)
                        issues.append({'field': single_field, 'message': message})
            else:
                key = (field, message)
                if key not in seen:
                    seen.add(key)
                    issues.append({'field': field, 'message': message})
        
        def process_issue_item(item, default_field: str = 'unknown'):
            """处理单个问题项"""
            if isinstance(item, str):
                add_issue(default_field, item)
            elif isinstance(item, dict):
                field = item.get('field') or item.get('field_name') or default_field
                message = item.get('message') or item.get('error_message') or str(item)
                add_issue(field, message)
        
        # 处理 content_issues 字段（奖状内问题）
        content_issues = validation_result.get('content_issues', [])
        if isinstance(content_issues, list):
            for issue in content_issues:
                process_issue_item(issue, 'content')
        
        # 处理 completeness_issues 字段（完整性问题）
        completeness_issues = validation_result.get('completeness_issues', [])
        if isinstance(completeness_issues, list):
            for issue in completeness_issues:
                process_issue_item(issue, 'completeness')
        
        # 处理 errors 字段（向后兼容）
        errors = validation_result.get('errors', [])
        if isinstance(errors, list):
            for issue in errors:
                process_issue_item(issue, 'unknown')
        
        # 处理 issues 字段（旧格式兼容）
        raw_issues = validation_result.get('issues', [])
        if isinstance(raw_issues, list):
            for issue in raw_issues:
                process_issue_item(issue, 'unknown')
        
        # 处理 field_issues 字段（按字段分组的格式）
        field_issues = validation_result.get('field_issues', {})
        if isinstance(field_issues, dict):
            for field, field_msgs in field_issues.items():
                if isinstance(field_msgs, list):
                    for msg in field_msgs:
                        if isinstance(msg, str):
                            add_issue(field, msg)
                        elif isinstance(msg, dict):
                            message = msg.get('message') or msg.get('error_message') or str(msg)
                            add_issue(field, message)
                elif isinstance(field_msgs, str):
                    add_issue(field, field_msgs)
        
        return issues
    
    # ============================================================
    # 提交到主表
    # ============================================================
    
    def submit_to_main_db(
        self,
        pending,
        lab_id: Optional[int] = None,
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str], int]:
        """
        提交到主数据库

        Returns:
            Tuple[是否成功, 目标记录ID, 错误信息, 入库条数]。大创为项目数，其他为 1。
        """
        try:
            achievement_type = pending.achievement_type
            data = pending.get_achievement_data()

            if lab_id:
                data['laboratory_id'] = lab_id

            if achievement_type == 'award':
                ok, tid, err = self._submit_award(pending, data, reviewer)
                return (ok, tid, err, 1 if ok else 0)
            elif achievement_type == 'patent':
                ok, tid, err = self._submit_patent(pending, data, reviewer)
                return (ok, tid, err, 1 if ok else 0)
            elif achievement_type == 'software':
                ok, tid, err = self._submit_software(pending, data, reviewer)
                return (ok, tid, err, 1 if ok else 0)
            elif achievement_type == 'innovation':
                return self._submit_innovation(pending, data, reviewer)
            elif achievement_type == 'other':
                ok, tid, err = self._submit_other(pending, data, reviewer)
                return (ok, tid, err, 1 if ok else 0)
            else:
                return False, None, f'未知的成果类型: {achievement_type}', 0

        except Exception as e:
            logger.error(f"提交到主数据库失败: {e}", exc_info=True)
            return False, None, str(e), 0
    
    def _submit_award(
        self,
        pending,
        data: Dict[str, Any],
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        提交奖状到主数据库
        
        Args:
            pending: PendingAchievement 对象
            data: 成果数据
            reviewer: 审核人信息
        
        Returns:
            Tuple[是否成功, 奖状ID, 错误信息]
        """
        if not self.award_manager:
            return False, None, '未配置 AwardManager'
        if not self.competition_manager:
            return False, None, '未配置 CompetitionManager'
        
        try:
            file_path = pending.file_path if hasattr(pending, 'file_path') else data.get('file_path')
            image_hash = data.get('image_hash', '') or (pending.file_hash if hasattr(pending, 'file_hash') else '')

            if not file_path:
                return False, None, '缺少文件路径'

            # 如果文件在 review 目录，先移动到业务目录
            if file_path.startswith('review/'):
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager, FileType
                    file_manager = get_unified_file_manager()
                    file_path = file_manager.move_from_review_to_business(
                        file_path, FileType.AWARD, image_hash
                    )
                    logger.info(f"审核通过，文件已从review移动到业务目录: {file_path}")
                except Exception as e:
                    logger.error(f"移动文件从review到业务目录失败: {e}")
                    return False, None, f'文件移动失败: {e}'

            # 获取 OCR 结果：优先从 pending 对象获取，然后从 data 中获取
            ocr_text = ''
            if hasattr(pending, 'ocr_text') and pending.ocr_text:
                ocr_text = pending.ocr_text
            elif data.get('ocr_result'):
                ocr_text = data.get('ocr_result')
            elif data.get('ocr_text'):
                ocr_text = data.get('ocr_text')
            
            # 竞赛名称：优先用 data，若仅有 competition_id 则从竞赛表解析，避免入库时误用占位竞赛
            competition_name = data.get('competition_name')
            if not (competition_name and str(competition_name).strip()):
                raw_cid = data.get('competition_id')
                if raw_cid is not None and raw_cid != '':
                    try:
                        cid = int(raw_cid)
                        comp = self.competition_manager.get_competition_by_id(cid)
                        if not comp:
                            comp = self.competition_manager.get_competition_by_id_from_db(cid)
                        if comp and comp.name:
                            competition_name = comp.name
                    except (TypeError, ValueError):
                        pass
            if not competition_name and data.get('original_competition_name'):
                competition_name = (data.get('original_competition_name') or '').strip()

            # 构建抽取结果
            extract_result = {
                'competition_name': competition_name,
                'track': data.get('track'),
                'issuer': data.get('issuer'),
                'province': data.get('province'),
                'group_name': data.get('group_name'),
                'winner_name': data.get('winner_name'),
                'supervisor_name': data.get('supervisor_name'),
                'award_level': data.get('award_level'),
                'date': data.get('date'),
                'year': data.get('year'),
                # 补充遗漏的字段（与 Award.update_from_json 的 field_map 保持一致）
                'granted_role': data.get('granted_role'),
                'competition_level': data.get('competition_level'),
                'certificate_id': data.get('certificate_id'),
                'project_title': data.get('project_title'),
                'related_student': data.get('related_student') or data.get('related_student_name'),  # 兼容 related_student / related_student_name（表单可能写入后者）
                'edition': data.get('edition'),
            }

            # 获取元信息（来自 pending 对象）
            submitter_type = pending.submitter_type if hasattr(pending, 'submitter_type') else data.get('submitter_type')
            submitter_id = pending.submitter_id if hasattr(pending, 'submitter_id') else data.get('submitter_id')
            submit_time = pending.submit_time if hasattr(pending, 'submit_time') else data.get('submit_time')
            
            # 获取 LLM 调试信息
            llm_prompt = pending.llm_prompt if hasattr(pending, 'llm_prompt') else data.get('llm_prompt')
            llm_response = pending.llm_response if hasattr(pending, 'llm_response') else data.get('llm_response')
            
            # 确定是否异常（基于验证结果）
            is_abnormal = False
            if hasattr(pending, 'is_valid'):
                is_abnormal = not pending.is_valid()
            elif hasattr(pending, 'validation_result') and pending.validation_result:
                validation = pending.get_validation_result() if hasattr(pending, 'get_validation_result') else {}
                is_abnormal = not validation.get('is_valid', True)
            # 获取实验室ID（如果已设置）
            # 优先级：1. data中的laboratory_id（用户编辑时选择或自动匹配） 2. 通过determine_laboratory自动确定
            laboratory_id = None
            raw_lab_id = data.get('laboratory_id')
            if raw_lab_id is not None and raw_lab_id != '':
                try:
                    laboratory_id = int(raw_lab_id)
                except (ValueError, TypeError):
                    pass
            
            # 如果数据中没有laboratory_id，尝试自动确定
            if not laboratory_id:
                lab_id, lab_reason = self.determine_laboratory(pending)
                if lab_id:
                    laboratory_id = lab_id
                    logger.info(f"[审核通过] 自动确定实验室ID: {laboratory_id}, 原因: {lab_reason}")

            # 获取 validation_result（JSON格式）
            validation_result = None
            if hasattr(pending, 'validation_result') and pending.validation_result:
                validation_result = pending.validation_result

            award, is_new = self.award_manager.add_award(
                image_path=file_path,
                ocr_text=ocr_text,
                extract_result=extract_result,
                image_hash=image_hash,
                comp_mgr=self.competition_manager,
                stu_mgr=self.student_manager,
                tea_mgr=self.teacher_manager,
                # 传递元信息
                submitter_type=submitter_type,
                submitter_id=submitter_id,
                submit_time=submit_time,
                laboratory_id=laboratory_id,
                is_abnormal=is_abnormal,
                validation_result=validation_result,
                llm_prompt=llm_prompt,
                llm_response=llm_response
            )
            
            logger.info(f"奖状导入{'成功' if is_new else '（已存在）'}: ID={award.id}, submitter={submitter_type}:{submitter_id}")
            return True, award.id, None
            
        except Exception as e:
            logger.error(f"提交奖状失败: {e}", exc_info=True)
            return False, None, str(e)
    
    def _submit_patent(
        self,
        pending,
        data: Dict[str, Any],
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        提交专利到主数据库
        
        Args:
            pending: PendingAchievement 对象
            data: 成果数据
            reviewer: 审核人信息
        
        Returns:
            Tuple[是否成功, 专利ID, 错误信息]
        """
        if not self.patent_manager:
            return False, None, '未配置 PatentManager'
        
        try:
            file_path = pending.file_path if hasattr(pending, 'file_path') else data.get('file_path')
            if not file_path:
                return False, None, '缺少文件路径'

            # 如果文件在 review 目录，先移动到业务目录
            if file_path.startswith('review/'):
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager, FileType
                    file_manager = get_unified_file_manager()
                    file_path = file_manager.move_from_review_to_business(
                        file_path, FileType.PATENT, image_hash=None
                    )
                except Exception as e:
                    logger.error(f"专利文件从review移动到业务目录失败: {e}")
                    return False, None, f'文件移动失败: {e}'

            patent_data = {
                'patent_name': data.get('patent_name'),
                'patent_type': data.get('patent_type'),
                'application_number': data.get('application_number'),
                'publication_number': data.get('publication_number') or data.get('patent_number'),
                'inventor': data.get('inventor') or data.get('inventors'),
                'application_date': data.get('application_date'),
                'patentee': data.get('patentee'),
                'laboratory_id': data.get('laboratory_id'),
            }
            if reviewer:
                patent_data['submitter_type'] = reviewer.reviewer_type
                patent_data['submitter_id'] = reviewer.reviewer_id

            patent = self.patent_manager.add_patent(patent_data, file_path=file_path)

            logger.info(f"专利导入成功: ID={patent.id}")
            return True, patent.id, None
            
        except Exception as e:
            logger.error(f"提交专利失败: {e}", exc_info=True)
            return False, None, str(e)
    
    def _submit_software(
        self,
        pending,
        data: Dict[str, Any],
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        提交软著到主数据库
        
        Args:
            pending: PendingAchievement 对象
            data: 成果数据
            reviewer: 审核人信息
        
        Returns:
            Tuple[是否成功, 软著ID, 错误信息]
        """
        if not self.software_manager:
            return False, None, '未配置 SoftwareCopyrightManager'
        
        try:
            file_path = pending.file_path if hasattr(pending, 'file_path') else data.get('file_path')
            if not file_path:
                return False, None, '缺少文件路径'

            # 如果文件在 review 目录，先移动到业务目录
            if file_path.startswith('review/'):
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager, FileType
                    file_manager = get_unified_file_manager()
                    file_path = file_manager.move_from_review_to_business(
                        file_path, FileType.SOFTWARE, image_hash=None
                    )
                except Exception as e:
                    logger.error(f"软著文件从review移动到业务目录失败: {e}")
                    return False, None, f'文件移动失败: {e}'

            raw_lab = data.get('laboratory_id')
            lab_id_val = None
            if raw_lab is not None and raw_lab != '':
                try:
                    lab_id_val = int(raw_lab)
                    if lab_id_val <= 0:
                        lab_id_val = None
                except (TypeError, ValueError):
                    pass
            software_data = {
                'software_name': data.get('software_name'),
                'software_version': data.get('software_version'),
                'registration_number': data.get('registration_number'),
                'certificate_no': data.get('certificate_no'),
                'registration_date': data.get('registration_date'),
                'copyright_owner': data.get('copyright_owner'),
                'laboratory_id': lab_id_val,
            }
            if reviewer:
                software_data['submitter_type'] = reviewer.reviewer_type
                software_data['submitter_id'] = reviewer.reviewer_id

            software = self.software_manager.add_copyright(software_data, file_path=file_path)

            logger.info(f"软著导入成功: ID={software.id}")
            return True, software.id, None
            
        except Exception as e:
            logger.error(f"提交软著失败: {e}", exc_info=True)
            return False, None, str(e)
    
    def _submit_innovation(
        self,
        pending,
        data: Dict[str, Any],
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str], int]:
        """
        提交大创项目到主数据库。
        以每个项目为单位：若 data 含 projects 数组则逐条入库（每项目一行）；否则将 data 视为单条项目。
        Returns:
            (成功, 首条目标ID, 错误信息, 入库条数)
        """
        if not self.innovation_manager:
            return False, None, '未配置 InnovationProjectManager', 0

        try:
            # 大创不需要保留文件，审核通过时删除 review 中的临时文件
            file_path = pending.file_path if hasattr(pending, 'file_path') else data.get('file_path')
            if file_path and file_path.startswith('review/'):
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager
                    fm = get_unified_file_manager()
                    p = fm.files_root / file_path
                    if p.exists():
                        p.unlink()
                except Exception as e:
                    logger.warning("大创删除临时文件失败: %s", e)

            # 实验室关联：与奖状一致，由 approve_single 通过 determine_laboratory 确定并写入 data['laboratory_id']
            lab_id = data.get('laboratory_id')
            projects_list = data.get('projects')
            if isinstance(projects_list, list) and len(projects_list) > 0:
                # Excel 等多项目：按项目逐条入库，每个项目一行；每项继承顶层 laboratory_id
                first_id = None
                added = 0
                for idx, p in enumerate(projects_list):
                    if not isinstance(p, dict):
                        continue
                    if lab_id is not None and p.get('laboratory_id') is None:
                        p = {**p, 'laboratory_id': lab_id}
                    innovation_data = self._build_innovation_project_data(p, reviewer)
                    project = self.innovation_manager.add_project(
                        innovation_data, student_manager=self.student_manager
                    )
                    if first_id is None:
                        first_id = project.id
                    added += 1
                    logger.info(f"大创项目导入成功: 第{idx + 1}项 ID={project.id}")
                return True, first_id, None, added

            # 单条项目（无 projects 或空列表）：将 data 视为一条项目
            innovation_data = self._build_innovation_project_data(data, reviewer)
            project = self.innovation_manager.add_project(
                innovation_data, student_manager=self.student_manager
            )
            logger.info(f"大创项目导入成功: ID={project.id}")
            return True, project.id, None, 1

        except Exception as e:
            logger.error(f"提交大创项目失败: {e}", exc_info=True)
            return False, None, str(e), 0

    def _build_innovation_project_data(
        self, d: Dict[str, Any], reviewer: Optional[Reviewer] = None
    ) -> Dict[str, Any]:
        """从单条项目字典构建 innovation_projects 表一行所需数据。"""
        project_name = d.get('project_name') or d.get('项目名称') or d.get('file_name') or '未命名项目'
        project_no = d.get('project_number') or d.get('project_no') or d.get('项目编号')
        leader_name = d.get('leader_name') or d.get('student_leader_name') or self._get_leader_name(d) or '未知'
        leader_id = d.get('leader_student_id') or d.get('student_leader_id') or self._get_leader_id(d) or d.get('项目负责人学号')
        members_raw = d.get('members') or d.get('other_members') or d.get('其他成员') or d.get('项目其他成员信息') or []
        other_members = self._convert_members_format(members_raw)
        supervisors_raw = d.get('supervisors') or d.get('指导教师') or []
        supervisors = self._convert_supervisors_format(supervisors_raw)
        start_date = d.get('start_date') or d.get('项目开始时间')
        end_date = d.get('end_date') or d.get('项目结束时间')
        start_date = self._normalize_date_format(start_date)
        end_date = self._normalize_date_format(end_date)

        innovation_data = {
            'project_no': project_no,
            'project_name': project_name,
            'project_type': d.get('project_level') or d.get('project_type') or d.get('项目类型') or d.get('项目级别'),
            'start_date': start_date,
            'end_date': end_date,
            'student_leader_name': leader_name,
            'student_leader_id': leader_id,
            'other_members': other_members,
            'supervisors': supervisors,
            'funding_amount': d.get('funding_amount'),
            'laboratory_id': d.get('laboratory_id'),
        }
        # 状态判断逻辑：
        # 1. 如果用户明确设置了状态（进行中、已结题、终止），使用用户设置（允许手动覆盖）
        # 2. 否则默认为"进行中"
        # 3. 如果最终状态是"进行中"且截止时间早于当前时间，自动改为"已结束"
        level = d.get('level') or d.get('project_level') or d.get('项目级别')
        if level and level in ['进行中', '已结题', '终止', '已结束']:
            innovation_data['status'] = level
        elif level and level in ['国家级', '省级', '院级']:
            innovation_data['project_type'] = level
            innovation_data['status'] = '进行中'
        else:
            innovation_data['status'] = '进行中'

        # 如果状态是"进行中"且有截止时间，检查是否需要自动设为"已结束"
        if innovation_data['status'] == '进行中' and end_date:
            if self._is_project_expired(end_date):
                innovation_data['status'] = '已结束'
        if not start_date:
            year = d.get('year') or d.get('年份')
            if year:
                try:
                    innovation_data['start_date'] = f"{int(year)}-06"
                    if not end_date:
                        innovation_data['end_date'] = f"{int(year) + 1}-06"
                except (TypeError, ValueError):
                    pass
        if reviewer:
            innovation_data['submitter_type'] = reviewer.reviewer_type
            innovation_data['submitter_id'] = reviewer.reviewer_id
        return innovation_data
    
    def _convert_members_format(self, members_raw: Any) -> Optional[str]:
        """
        转换成员格式：从各种格式转换为JSON字符串
        输入可能是：
        - ["张三(2022001)", "李四(2022002)"]  # 抽取器格式
        - [{"姓名":"张三","学号":"2022001"}]  # JSON格式
        - "张三,李四"  # 逗号分隔
        """
        if not members_raw:
            return None
        
        import json
        import re
        
        # 如果是字符串，尝试解析JSON
        if isinstance(members_raw, str):
            # 尝试解析JSON
            try:
                parsed = json.loads(members_raw)
                if isinstance(parsed, list):
                    members_raw = parsed
                elif ',' in members_raw:
                    # 逗号分隔的字符串
                    return members_raw  # 保持原样，让后续处理
            except:
                # 不是JSON，可能是逗号分隔
                if ',' in members_raw:
                    return members_raw  # 保持原样
        
        # 如果是列表
        if isinstance(members_raw, list):
            result = []
            for item in members_raw:
                if isinstance(item, dict):
                    # 已经是字典格式
                    result.append(item)
                elif isinstance(item, str):
                    # 解析 "姓名(学号)" 格式
                    match = re.match(r'^(.+?)\((\d+)\)$', item)
                    if match:
                        result.append({"姓名": match.group(1), "学号": match.group(2)})
                    else:
                        # 只有姓名
                        result.append({"姓名": item, "学号": None})
            
            if result:
                return json.dumps(result, ensure_ascii=False)
        
        return None
    
    def _convert_supervisors_format(self, supervisors_raw: Any) -> Optional[str]:
        """
        转换指导教师格式：从列表或字符串转换为逗号分隔字符串
        """
        if not supervisors_raw:
            return None
        
        if isinstance(supervisors_raw, list):
            return ",".join([str(s).strip() for s in supervisors_raw if s])
        elif isinstance(supervisors_raw, str):
            # 尝试解析JSON列表
            try:
                import json
                parsed = json.loads(supervisors_raw)
                if isinstance(parsed, list):
                    return ",".join([str(s).strip() for s in parsed if s])
            except:
                pass
            # 已经是逗号分隔字符串
            return supervisors_raw
        
        return str(supervisors_raw)
    
    def _normalize_date_format(self, date_str: Any) -> Optional[str]:
        """
        标准化日期格式：将 YYYY.MM 转换为 YYYY-MM
        """
        if not date_str:
            return None
        
        date_str = str(date_str).strip()
        if not date_str:
            return None
        
        # 将 YYYY.MM 转换为 YYYY-MM
        if '.' in date_str and '-' not in date_str:
            date_str = date_str.replace('.', '-')
        
        return date_str

    def _is_project_expired(self, end_date_str: Optional[str]) -> bool:
        """
        判断项目是否已过期（截止时间早于当前时间）

        支持格式：YYYY-MM, YYYY-MM-DD

        Args:
            end_date_str: 截止时间字符串

        Returns:
            True 如果项目已过期，False 否则
        """
        from datetime import datetime

        if not end_date_str:
            return False

        try:
            end_date_str = str(end_date_str).strip()

            # 解析日期
            # 格式1: YYYY-MM
            if len(end_date_str) == 7 and end_date_str[4] == '-':
                year = int(end_date_str[:4])
                month = int(end_date_str[5:7])
                # 使用月末最后一天进行比较
                if month == 12:
                    end_date = datetime(year, 12, 31)
                else:
                    import calendar
                    last_day = calendar.monthrange(year, month)[1]
                    end_date = datetime(year, month, last_day)

            # 格式2: YYYY-MM-DD
            elif len(end_date_str) >= 10 and end_date_str[4] == '-':
                parts = end_date_str.split('-')
                if len(parts) >= 3:
                    year = int(parts[0])
                    month = int(parts[1])
                    day = int(parts[2][:2])  # 只取前两位，避免包含时间的情况
                    end_date = datetime(year, month, day)
                else:
                    return False
            else:
                # 无法识别的格式
                return False

            # 当前时间
            now = datetime.now()

            # 比较日期
            return end_date < now

        except (ValueError, TypeError, IndexError):
            logger.warning(f"无法解析截止时间: {end_date_str}")
            return False

    def _get_leader_name(self, data: Dict[str, Any]) -> Optional[str]:
        """从数据中提取负责人姓名"""
        # 尝试多种字段名
        leader = data.get('学生负责人') or data.get('leader_name') or data.get('student_leader_name')
        if isinstance(leader, dict):
            return leader.get('姓名')
        elif isinstance(leader, str):
            return leader
        return None
    
    def _get_leader_id(self, data: Dict[str, Any]) -> Optional[str]:
        """从数据中提取负责人学号"""
        # 尝试多种字段名
        leader = data.get('学生负责人')
        if isinstance(leader, dict):
            return leader.get('学号')
        
        leader_id = data.get('leader_student_id') or data.get('student_leader_id') or data.get('项目负责人学号')
        if leader_id:
            return str(leader_id).strip()
        return None
    
    def _submit_other(
        self,
        pending,
        data: Dict[str, Any],
        reviewer: Optional[Reviewer] = None
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """
        提交其他文件到主数据库
        
        Args:
            pending: PendingAchievement 对象
            data: 成果数据
            reviewer: 审核人信息
        
        Returns:
            Tuple[是否成功, 文件ID, 错误信息]
        """
        if not self.other_file_manager:
            return False, None, '未配置 OtherFileManager'
        
        try:
            file_path = pending.file_path if hasattr(pending, 'file_path') else data.get('file_path')
            if not file_path:
                return False, None, '缺少文件路径'

            # 如果文件在 review 目录，先移动到业务目录
            if file_path.startswith('review/'):
                try:
                    from backend.services.unified_file_manager import get_unified_file_manager, FileType
                    file_manager = get_unified_file_manager()
                    file_path = file_manager.move_from_review_to_business(
                        file_path, FileType.OTHER, image_hash=None
                    )
                except Exception as e:
                    logger.error(f"其他文件从review移动到业务目录失败: {e}")
                    return False, None, f'文件移动失败: {e}'

            file_data = {
                'title': data.get('title') or data.get('file_name'),
                'description': data.get('description'),
                'file_name': data.get('file_name') or Path(file_path).name,
                'laboratory_id': data.get('laboratory_id'),
            }
            if reviewer:
                file_data['submitter_type'] = reviewer.reviewer_type
                file_data['submitter_id'] = reviewer.reviewer_id

            other_file = self.other_file_manager.add_file_from_path(file_path, file_data)
            
            logger.info(f"其他文件导入成功: ID={other_file.id}")
            return True, other_file.id, None
            
        except Exception as e:
            logger.error(f"提交其他文件失败: {e}", exc_info=True)
            return False, None, str(e)
    
    # ============================================================
    # other 类型处理
    # ============================================================
    
    def handle_other_type(
        self,
        pending,
        lab_id: Optional[int],
        reviewer: Reviewer,
        target_type: Optional[str] = None,
        file_title: Optional[str] = None
    ) -> ReviewResult:
        """
        处理 other 类型成果
        
        规则:
        - 无实验室关联 → 丢弃成果 + 删除文件
        - 有实验室关联:
            - target_type='album' 或 (图片且无指定) → 放入实验室相册
            - target_type='downloads' 或 非图片 → 放入实验室下载专区
        
        Args:
            pending: PendingAchievement 对象
            lab_id: 实验室ID（可选）
            reviewer: 审核人信息
            target_type: 目标位置 ('album' | 'downloads')，可选
            file_title: 文件标题（用于下载专区显示）
        
        Returns:
            ReviewResult 操作结果
        """
        try:
            # 获取文件路径
            file_path = pending.file_path if hasattr(pending, 'file_path') else None
            
            if not file_path:
                return ReviewResult(
                    success=False,
                    pending_id=pending.id,
                    action='approved',
                    error='other 类型成果缺少文件路径'
                )
            
            lab_name = None
            if lab_id:
                lab = self.laboratory_manager.get_laboratory_by_id(lab_id)
                lab_name = lab.name if lab else None
            
            # 情况1：无实验室关联 → 丢弃
            if lab_id is None:
                logger.info(f"other 类型成果无实验室关联，将被丢弃: {pending.id}")
                
                # 记录审核日志
                self._log_review_action(
                    pending=pending,
                    reviewer=reviewer,
                    action_type='deleted',
                    review_comment='other 类型成果无实验室关联，自动丢弃'
                )
                
                # 删除记录和文件
                self.pending_manager.safe_delete_with_file(pending.id)
                
                return ReviewResult(
                    success=True,
                    pending_id=pending.id,
                    action='deleted',
                    error=None
                )
            
            # 情况2：有实验室关联
            if not self.files_dir:
                return ReviewResult(
                    success=False,
                    pending_id=pending.id,
                    action='approved',
                    error='未配置 files_dir，无法移动文件'
                )
            
            # 统一解析为可访问的完整路径（支持相对路径与历史绝对路径，便于跨服务器部署）
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            source_file_path = file_manager.resolve_path(file_path)
            
            if not source_file_path.exists():
                return ReviewResult(
                    success=False,
                    pending_id=pending.id,
                    action='approved',
                    error=f'源文件不存在: {source_file_path}'
                )
            
            data = pending.get_achievement_data()
            # 优先使用传入的 file_title，否则使用 achievement_data 中的值
            effective_file_title = file_title or data.get('title') or data.get('file_name')
            
            # 判断文件类型
            is_image = self.is_image_file(str(source_file_path))
            
            # 确定目标位置：
            # - 如果明确指定了 target_type，使用指定值
            # - 否则：图片默认放 album，非图片放 downloads
            if target_type:
                go_to_album = (target_type == 'album')
            else:
                go_to_album = is_image
            
            if go_to_album:
                # 放入实验室相册
                success, target_path, error = self.laboratory_manager.move_file_to_album(
                    lab_id=lab_id,
                    source_path=source_file_path,
                    files_base_dir=self.files_dir
                )
                
                if success:
                    # 记录审核日志
                    self._log_review_action(
                        pending=pending,
                        reviewer=reviewer,
                        action_type='approved',
                        result_type='laboratory_image',
                        result_file_path=target_path,
                        operation_note='图片已移动到实验室相册'
                    )
                    
                    # 删除 pending 记录（文件已移动，不需要删除）
                    self.pending_manager.delete_pending(pending.id)
                    
                    return ReviewResult(
                        success=True,
                        pending_id=pending.id,
                        action='approved',
                        target_table='laboratory_images',
                        file_moved_to=target_path,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name
                    )
                else:
                    return ReviewResult(
                        success=False,
                        pending_id=pending.id,
                        action='approved',
                        error=error,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name
                    )
            else:
                # 放入实验室下载专区
                success, target_path, error = self.laboratory_manager.move_file_to_downloads(
                    lab_id=lab_id,
                    source_path=source_file_path,
                    files_base_dir=self.files_dir,
                    file_title=effective_file_title,
                    submitter_type=pending.submitter_type,
                    submitter_id=pending.submitter_id
                )
                
                if success:
                    # 记录审核日志
                    self._log_review_action(
                        pending=pending,
                        reviewer=reviewer,
                        action_type='approved',
                        result_type='laboratory_download',
                        result_file_path=target_path,
                        operation_note='文件已移动到实验室下载区'
                    )
                    
                    # 删除 pending 记录（文件已移动，不需要删除）
                    self.pending_manager.delete_pending(pending.id)
                    
                    return ReviewResult(
                        success=True,
                        pending_id=pending.id,
                        action='approved',
                        target_table='laboratory_downloads',
                        file_moved_to=target_path,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name
                    )
                else:
                    return ReviewResult(
                        success=False,
                        pending_id=pending.id,
                        action='approved',
                        error=error,
                        laboratory_id=lab_id,
                        laboratory_name=lab_name
                    )
                    
        except Exception as e:
            logger.error(f"处理 other 类型失败: {e}", exc_info=True)
            return ReviewResult(
                success=False,
                pending_id=pending.id,
                action='approved',
                error=str(e)
            )
