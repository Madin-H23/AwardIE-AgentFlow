"""
用户路由辅助函数
提供统一的路由URL生成，避免硬编码
"""
from flask import url_for, session

# 路由名映射表：某些用户类型的路由名需要特殊映射
ROUTE_NAME_MAPPING = {
    'admin': {
        'activities': 'activities_list',  # 管理员的活动列表路由名是 activities_list
        'achievements': 'awards_list',    # 管理员的成果页面路由名是 awards_list（奖状列表）
        'profile': 'dashboard',           # 管理员没有单独的 profile 路由，映射到 dashboard
    },
    'teacher': {
        'activities': 'dashboard',        # 教师的活动页面模板已删除，映射到仪表板
        'submissions': 'achievement_submit',  # 教师的成果提交页面
    },
    'student': {
        'submissions': 'achievement_submit',  # 学生的成果提交页面
    }
}

def get_user_route_name(route_name: str, user_type: str = None) -> str:
    """
    根据用户类型获取正确的路由名称
    
    Args:
        route_name: 路由名称（如 'dashboard', 'activities', 'profile'）
        user_type: 用户类型，如果为None则从session获取
    
    Returns:
        完整的路由名称，如 'student.dashboard' 或 'teacher.dashboard'
    """
    if user_type is None:
        user_type = session.get('user_type', 'student')
    
    # 检查是否有特殊映射
    if user_type in ROUTE_NAME_MAPPING:
        mapped_route_name = ROUTE_NAME_MAPPING[user_type].get(route_name)
        if mapped_route_name:
            route_name = mapped_route_name
    
    return f"{user_type}.{route_name}"

def get_user_route_url(route_name: str, user_type: str = None, **kwargs):
    """
    根据用户类型生成正确的路由URL
    
    Args:
        route_name: 路由名称（如 'dashboard', 'activities', 'profile'）
        user_type: 用户类型，如果为None则从session获取
        **kwargs: 传递给url_for的额外参数
    
    Returns:
        路由URL
    """
    full_route_name = get_user_route_name(route_name, user_type)
    return url_for(full_route_name, **kwargs)

