"""
实验室关联服务模块

提供批量自动关联成果到实验室的功能：
- 根据第一指导教师自动关联奖状到实验室
- 根据第一导师自动关联大创项目到实验室
"""
import logging
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


class LaboratoryAssociationService:
    """实验室关联服务
    
    封装「根据第一导师自动关联实验室」的业务逻辑，供路由层和测试复用。
    """
    
    def __init__(
        self,
        award_manager,
        innovation_manager,
        laboratory_manager,
        teacher_manager
    ):
        """
        初始化服务
        
        Args:
            award_manager: AwardManager 实例
            innovation_manager: InnovationProjectManager 实例
            laboratory_manager: LaboratoryManager 实例
            teacher_manager: TeacherManager 实例
        """
        self.award_manager = award_manager
        self.innovation_manager = innovation_manager
        self.laboratory_manager = laboratory_manager
        self.teacher_manager = teacher_manager
    
    def auto_link_laboratory_for_awards(
        self,
        awards: Optional[List] = None
    ) -> Dict[str, int]:
        """
        自动关联奖状到实验室

        筛选条件：
        - laboratory_id 为空
        - supervisor_name 非空（学生证书）或 winner_name 非空且 granted_role 包含"教师"（教师证书）

        处理流程：
        1. 学生证书：通过第一指导教师关联实验室
        2. 教师证书：通过获奖者（教师本人）关联实验室

        Args:
            awards: 奖状列表（可选）。如果不提供，则自动查询符合条件的奖状

        Returns:
            dict: {
                'total': int,           # 符合条件的奖状总数
                'success_count': int,   # 成功关联数
                'skipped_count': int,   # 跳过数（无指导教师或未关联教师对象或教师无实验室）
                'failed_count': int     # 失败数
            }
        """
        # 如果没有提供奖状列表，自动查询符合条件的奖状
        if awards is None:
            # 查询所有无实验室的奖状（不预加载关联，后续按姓名查教师）
            awards = self.award_manager.query_awards(filter_no_laboratory=True)

            # 筛选条件：
            # 1. 有 supervisor_name（学生证书）
            # 2. 或者有 winner_name 且 granted_role 包含"教师"（教师证书）
            awards = [a for a in awards
                     if a.supervisor_name or (a.winner_name and a.granted_role and "教师" in a.granted_role)]

        success_count = 0
        skipped_count = 0
        failed_count = 0

        for award in awards:
            try:
                teacher = None
                link_type = None  # 用于日志记录关联类型

                # 判断是学生证书还是教师证书
                if award.supervisor_name:
                    # 学生证书：通过指导教师关联
                    link_type = "指导教师"
                    supervisor_info = award.get_first_supervisor_info()
                    first_name = supervisor_info.get('name')
                    if not first_name:
                        logger.debug(f"奖状 {award.id} 无第一指导教师姓名，跳过")
                        skipped_count += 1
                        continue

                    teacher = supervisor_info.get('obj')
                    if not teacher:
                        # 未关联到教师对象：按姓名精确查找
                        found = self.teacher_manager.find_teachers_by_name(first_name.strip())
                        for t in found:
                            if t.name.strip() == first_name.strip():
                                teacher = t
                                break
                    if not teacher:
                        logger.debug(f"奖状 {award.id} 的第一指导教师「{first_name}」未找到教师对象，跳过")
                        skipped_count += 1
                        continue

                elif award.winner_name and award.granted_role and "教师" in award.granted_role:
                    # 教师证书：通过获奖者（教师本人）关联
                    link_type = "获奖者"
                    winner_name = award.winner_name.strip()

                    # 按姓名精确查找教师
                    found = self.teacher_manager.find_teachers_by_name(winner_name)
                    for t in found:
                        if t.name.strip() == winner_name:
                            teacher = t
                            break

                    if not teacher:
                        logger.debug(f"教师证书 {award.id} 的获奖者「{winner_name}」未找到教师对象，跳过")
                        skipped_count += 1
                        continue
                else:
                    logger.debug(f"奖状 {award.id} 无指导教师且不是教师证书，跳过")
                    skipped_count += 1
                    continue

                # 查找教师所属实验室
                lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)

                if not lab:
                    # 教师未关联实验室，跳过
                    logger.debug(f"奖状 {award.id} 的{link_type} {teacher.name} (ID: {teacher.id}) 未关联实验室，跳过")
                    skipped_count += 1
                    continue

                # 设置实验室ID并保存
                award.laboratory_id = lab.id
                self.award_manager._save_award(award)
                logger.info(f"奖状 {award.id} （{link_type}：{teacher.name}）已关联到实验室: {lab.name} (ID: {lab.id})")
                success_count += 1

            except Exception as e:
                logger.error(f"自动关联奖状 {award.id} 失败: {e}", exc_info=True)
                failed_count += 1

        return {
            'total': len(awards),
            'success_count': success_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count
        }
    
    def auto_link_laboratory_for_innovation(
        self,
        projects: Optional[List] = None
    ) -> Dict[str, int]:
        """
        自动关联大创项目到实验室
        
        筛选条件：
        - laboratory_id 为空
        - supervisors 非空
        
        处理流程：
        1. 解析第一个导师姓名
        2. 查找教师（精确匹配）
        3. 查找教师所属实验室
        4. 更新项目的 laboratory_id
        
        Args:
            projects: 大创项目列表（可选）。如果不提供，则自动查询符合条件的项目
        
        Returns:
            dict: {
                'total': int,
                'success_count': int,
                'skipped_count': int,
                'failed_count': int
            }
        """
        # 如果没有提供项目列表，自动查询符合条件的项目
        if projects is None:
            from backend.models.innovation_project import InnovationProjectFilter
            
            # 查询所有无实验室但有导师的项目
            filter_obj = InnovationProjectFilter(
                laboratory_id=None,
                limit=None
            )
            projects = self.innovation_manager.query_projects(filter_obj=filter_obj)
            
            # 进一步筛选：必须有 supervisors
            projects = [p for p in projects if p.supervisors]
        
        success_count = 0
        skipped_count = 0
        failed_count = 0
        
        for project in projects:
            try:
                # 解析第一个导师姓名
                supervisors = project.get_supervisors_list()
                if not supervisors:
                    logger.debug(f"大创项目 {project.id} 没有导师信息，跳过")
                    skipped_count += 1
                    continue
                
                first_supervisor_name = supervisors[0].strip()
                
                # 查找教师（精确匹配）
                found_teachers = self.teacher_manager.find_teachers_by_name(first_supervisor_name)
                teacher = None
                for t in found_teachers:
                    if t.name == first_supervisor_name:
                        teacher = t
                        break
                
                if not teacher:
                    logger.debug(f"大创项目 {project.id} 的第一导师 {first_supervisor_name} 未找到教师对象，跳过")
                    skipped_count += 1
                    continue
                
                # 查找实验室
                lab = self.laboratory_manager.get_laboratory_by_teacher_id(teacher.id)
                
                if not lab:
                    logger.debug(f"大创项目 {project.id} 的第一导师 {teacher.name} (ID: {teacher.id}) 未关联实验室，跳过")
                    skipped_count += 1
                    continue
                
                # 更新项目
                self.innovation_manager.update_project(project.id, {'laboratory_id': lab.id})
                logger.info(f"大创项目 {project.id} 已关联到实验室: {lab.name} (ID: {lab.id})")
                success_count += 1
                
            except Exception as e:
                logger.error(f"自动关联大创项目 {project.id} 失败: {e}", exc_info=True)
                failed_count += 1
        
        return {
            'total': len(projects),
            'success_count': success_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count
        }
