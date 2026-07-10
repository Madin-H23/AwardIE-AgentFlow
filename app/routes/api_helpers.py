"""
API辅助函数
用于处理用户ID转换等通用逻辑
"""
from typing import Optional, Tuple


def get_user_db_id(user_info: dict, student_manager=None, teacher_manager=None) -> Optional[int]:
    """
    将user_info中的user_id（student_id或teacher_id字符串）转换为数据库ID（整数）
    
    Args:
        user_info: 用户信息字典，包含user_id和user_type
        student_manager: 学生管理器（可选）
        teacher_manager: 教师管理器（可选）
    
    Returns:
        数据库ID（整数），如果转换失败返回None
    """
    if not user_info:
        return None
    
    user_id_str = user_info.get('user_id')
    user_type = user_info.get('user_type')
    
    if not user_id_str or not user_type:
        return None
    
    if user_type == 'student' and student_manager:
        student = student_manager.get_student_by_student_id(user_id_str)
        return student.id if student else None
    elif user_type == 'teacher' and teacher_manager:
        teacher = teacher_manager.get_teacher_by_teacher_id(user_id_str)
        return teacher.id if teacher else None
    
    return None

