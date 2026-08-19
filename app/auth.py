"""
认证相关功能：登录验证、权限检查装饰器
"""
from functools import wraps
from flask import session, redirect, url_for, request, flash, jsonify
from werkzeug.security import check_password_hash
import sqlite3
from pathlib import Path

def get_db_connection(db_path):
    """获取数据库连接"""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _self_heal_users_password(conn, login_code: str, password_hash: str) -> None:
    """过渡期自愈（8.5 渐进）：旧表登录成功时把密码同步进 users，防两表漂移。"""
    try:
        conn.execute("UPDATE users SET password_hash=?, updated_at=CURRENT_TIMESTAMP WHERE login_code=?",
                     (password_hash, login_code))
        conn.commit()
    except sqlite3.Error:
        pass   # 自愈失败不影响登录

def verify_user(username: str, password: str, db_path: str) -> dict | None:
    """
    验证用户登录（8.5 渐进第一批：users 单表优先，旧三表回退过渡）

    Args:
        username: 用户名（管理员用户名、学号或工号）
        password: 密码
        db_path: 数据库路径

    Returns:
        如果验证成功，返回用户信息字典；否则返回None
    """
    conn = get_db_connection(db_path)
    try:
        # ── users 单表优先（合并核心收益：一条 SQL 替代三表逐查）──
        try:
            from backend.orm.repositories import UserRepository
            u = UserRepository.get_by_login_code(username)
            if u and u.user_activated:
                if u.password_hash and check_password_hash(u.password_hash, password):
                    return {
                        'user_id': u.login_code, 'user_type': u.role,   # 业务号（存量路由兼容；写入时经映射转 users.id）
                        'name': u.name, 'role': u.role,
                        'needs_password_change': bool(u.needs_password_change),
                    }
                # users 密码不匹配 → 落入旧表路径：旧表验成功则自愈同步新密码进 users
                # （过渡期旧表是写路径真源，防漂移；自愈后下次登录走 users 快路径）
        except Exception:
            pass   # ORM 不可用/未迁移库——回退原生 users + 旧三表

        # ── 旧三表回退（过渡兼容，随引用重写下批移除）──
        # 先查管理员表（如果表存在）
        try:
            admin = conn.execute(
                'SELECT username, name, password_hash, user_activated, needs_password_change FROM admins WHERE username = ?',
                (username,)
            ).fetchone()

            if admin and admin['user_activated']:
                if admin['password_hash'] and check_password_hash(admin['password_hash'], password):
                    _self_heal_users_password(conn, admin['username'], admin['password_hash'])
                    return {
                        'user_id': admin['username'],
                        'user_type': 'admin',
                        'name': admin['name'] or '管理员',
                        'role': 'admin', 'needs_password_change': bool(admin['needs_password_change'])
                    }
        except sqlite3.OperationalError:
            # 如果admins表不存在，继续查询其他表
            pass
        
        # 再查学生表
        student = conn.execute(
            'SELECT student_id, name, password_hash, role, user_activated, needs_password_change FROM students WHERE student_id = ?',
            (username,)
        ).fetchone()
        
        if student and student['user_activated']:
            ph = student['password_hash']
            # P1-2：已移除默认密码兜底（原空 hash 可用明文 P@ss301 登录=批量弱凭证）。
            # 空 hash 一律拒绝登录；存量空 hash 已由迁移脚本生成随机初始密码（管理员线下分发）。
            pwd_ok = bool(ph) and check_password_hash(ph, password)
            if pwd_ok:
                _self_heal_users_password(conn, student['student_id'], ph)
                return {
                    'user_id': student['student_id'],
                    'user_type': 'student',
                    'name': student['name'],
                    'role': student['role'] or 'student',
                    'needs_password_change': bool(student['needs_password_change'])
                }
        
        # 最后查教师表
        teacher = conn.execute(
            'SELECT teacher_id, name, password_hash, role, user_activated, needs_password_change FROM teachers WHERE teacher_id = ?',
            (username,)
        ).fetchone()
        
        if teacher and teacher['user_activated']:
            ph = teacher['password_hash']
            # P1-2：同学生侧——默认密码兜底已移除，空 hash 拒绝登录
            pwd_ok = bool(ph) and check_password_hash(ph, password)
            if pwd_ok:
                _self_heal_users_password(conn, teacher['teacher_id'], ph)
                return {
                    'user_id': teacher['teacher_id'],
                    'user_type': 'teacher',
                    'name': teacher['name'],
                    'role': teacher['role'] or 'teacher',
                    'needs_password_change': bool(teacher['needs_password_change'])
                }
        
        return None
    finally:
        conn.close()

def login_user(user_info: dict):
    """
    登录用户，设置session
    
    Args:
        user_info: 用户信息字典，包含user_id, user_type, name, role
    """
    session['user_id'] = user_info['user_id']
    session['user_type'] = user_info['user_type']
    session['user_name'] = user_info['name']
    session['role'] = user_info['role']
    session.permanent = True

def logout_user():
    """登出用户，清除session"""
    session.clear()

def is_logged_in() -> bool:
    """检查用户是否已登录"""
    return 'user_id' in session

def get_current_user() -> dict:
    """获取当前登录用户信息"""
    if not is_logged_in():
        return None
    return {
        'user_id': session.get('user_id'),
        'user_type': session.get('user_type'),
        'name': session.get('user_name'),
        'role': session.get('role')
    }

def require_login(f):
    """要求登录的装饰器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def require_role(*allowed_roles):
    """
    要求特定角色的装饰器
    
    Args:
        *allowed_roles: 允许的角色列表，如 'admin', 'teacher', 'student'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login', next=request.url))
            
            user_role = (session.get('role') or '').strip().lower()
            allowed_lower = {r.strip().lower() for r in allowed_roles}
            if user_role not in allowed_lower:
                flash('权限不足', 'error')
                return redirect(url_for('auth.login'))
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_user_type(*allowed_types):
    """
    要求特定用户类型的装饰器

    Args:
        *allowed_types: 允许的用户类型列表，如 'student', 'teacher'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                flash('请先登录', 'warning')
                return redirect(url_for('auth.login', next=request.url))

            user_type = session.get('user_type')
            role = session.get('role')

            # 检查权限：用户类型或角色匹配即可
            has_permission = False
            if user_type in allowed_types:
                has_permission = True
            elif role in allowed_types:
                has_permission = True

            if not has_permission:
                flash(f'权限不足，需要: {", ".join(allowed_types)}', 'error')
                return redirect(url_for('auth.login'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role_api(*allowed_roles):
    """
    要求特定角色的装饰器 - 用于API路由，返回JSON而不是重定向

    Args:
        *allowed_roles: 允许的角色列表，如 'admin', 'teacher', 'student'
    """
    from flask import jsonify
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_logged_in():
                return jsonify({'success': False, 'message': '请先登录'}), 401

            user_role = (session.get('role') or '').strip().lower()
            allowed_lower = {r.strip().lower() for r in allowed_roles}
            if user_role not in allowed_lower:
                return jsonify({'success': False, 'message': '权限不足'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_admin_or_lab_view_api(f):
    """
    用于成果 Tab API：管理员始终允许；非管理员仅当 GET 且带 laboratory_id 时允许（实验室成果展示只读视图）。
    """
    from flask import jsonify
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if is_logged_in() and session.get('role') == 'admin':
            return f(*args, **kwargs)
        if request.method == 'GET' and request.args.get('laboratory_id'):
            return f(*args, **kwargs)
        if not is_logged_in():
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return jsonify({'success': False, 'message': '权限不足'}), 403
    return decorated_function


def require_role_api_json(*allowed_roles):
    """
    要求特定角色的装饰器 - 用于API路由，自动检测请求类型并返回相应格式

    Args:
        *allowed_roles: 允许的角色列表，如 'admin', 'teacher', 'student'
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 检查是否是API请求（通过请求头或路径判断）
            is_api = request.path.startswith('/api/') or \
                    request.headers.get('Accept') == 'application/json' or \
                    request.headers.get('Content-Type') == 'application/json'

            if not is_logged_in():
                if is_api:
                    return jsonify({'success': False, 'message': '请先登录'}), 401
                else:
                    flash('请先登录', 'warning')
                    return redirect(url_for('auth.login', next=request.url))

            user_role = (session.get('role') or '').strip().lower()
            allowed_lower = {r.strip().lower() for r in allowed_roles}
            if user_role not in allowed_lower:
                if is_api:
                    return jsonify({'success': False, 'message': '权限不足'}), 403
                else:
                    flash('权限不足', 'error')
                    return redirect(url_for('auth.login'))

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def is_lab_instructor(user_info: dict, lab_id: int, laboratory_manager, teacher_manager) -> bool:
    """
    检查用户是否是实验室的指导教师
    
    Args:
        user_info: 用户信息字典（可能为None）
        lab_id: 实验室ID
        laboratory_manager: LaboratoryManager实例
        teacher_manager: TeacherManager实例
    
    Returns:
        bool: 如果是实验室指导教师则返回True
    """
    if not user_info:
        return False
    
    # 只有教师才可能是实验室指导教师（兼容 user_type 与 role）
    if user_info.get('user_type') != 'teacher' and user_info.get('role') != 'teacher':
        return False
    
    # 获取实验室
    lab = laboratory_manager.get_laboratory_by_id(lab_id)
    if not lab:
        return False
    
    # 获取教师对象
    teacher_id = user_info.get('user_id')  # 对于教师，user_id是teacher_id（工号）
    teacher = teacher_manager.get_teacher_by_teacher_id(teacher_id)
    if not teacher:
        return False
    
    # 检查教师是否在实验室的instructors列表中（按 id 比较，避免对象引用不一致）
    return any(getattr(t, 'id', None) == teacher.id for t in (lab.instructors or []))

def require_can_edit_laboratory(f):
    """
    实验室编辑权限装饰器：
    - 添加实验室（lab_id 为空）：仅管理员
    - 编辑实验室（lab_id 有值）：管理员或该实验室指导教师
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login', next=request.url))

        user_info = get_current_user()
        lab_id = kwargs.get('lab_id')

        # 添加新实验室：仅管理员
        if lab_id is None:
            if user_info.get('role') != 'admin':
                flash('权限不足', 'error')
                return redirect(url_for('auth.login'))
            return f(*args, **kwargs)

        # 编辑实验室：管理员或实验室指导教师
        from app.utils import get_app_context_instance
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()
        if can_edit_laboratory(user_info, lab_id, laboratory_manager, teacher_manager):
            return f(*args, **kwargs)

        flash('权限不足', 'error')
        return redirect(url_for('admin_laboratory.laboratory_detail', lab_id=lab_id))
    return decorated_function


def require_can_edit_laboratory_api(f):
    """
    实验室编辑权限装饰器（API 版，返回 JSON）：
    仅当 lab_id 有值且用户为管理员或该实验室指导教师时允许访问。
    """
    from flask import jsonify
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return jsonify({'success': False, 'message': '请先登录'}), 401

        lab_id = kwargs.get('lab_id')
        if lab_id is None:
            return jsonify({'success': False, 'message': '权限不足'}), 403

        user_info = get_current_user()
        from app.utils import get_app_context_instance
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()
        if can_edit_laboratory(user_info, lab_id, laboratory_manager, teacher_manager):
            return f(*args, **kwargs)
        return jsonify({'success': False, 'message': '权限不足'}), 403
    return decorated_function


def can_edit_laboratory(user_info: dict, lab_id: int, laboratory_manager, teacher_manager) -> bool:
    """
    检查用户是否可以编辑指定实验室
    
    Args:
        user_info: 用户信息字典（可能为None）
        lab_id: 实验室ID
        laboratory_manager: LaboratoryManager实例
        teacher_manager: TeacherManager实例
    
    Returns:
        bool: 如果可以编辑则返回True
    """
    if not user_info:
        return False
    
    # 管理员可以编辑所有实验室
    if user_info.get('role') == 'admin':
        return True
    
    # 检查是否是实验室指导教师
    return is_lab_instructor(user_info, lab_id, laboratory_manager, teacher_manager)

def can_edit_activity(user_info: dict, activity, laboratory_manager, teacher_manager) -> bool:
    """
    检查用户是否可以编辑指定活动
    
    Args:
        user_info: 用户信息字典（可能为None）
        activity: Competition_activity对象
        laboratory_manager: LaboratoryManager实例
        teacher_manager: TeacherManager实例
    
    Returns:
        bool: 如果可以编辑则返回True
    """
    if not user_info:
        return False
    
    # 管理员可以编辑所有活动
    if user_info.get('role') == 'admin':
        return True
    
    if not activity:
        return False
    
    user_id = user_info.get('user_id')
    if not user_id:
        return False
    
    # 检查是否是活动关联的教师
    # 先刷新活动的教师关联（如果还没有刷新）
    if hasattr(activity, 'teachers') and activity.teachers:
        # 检查当前用户是否是活动关联的教师之一
        for teacher in activity.teachers:
            if teacher and teacher.teacher_id == user_id:
                return True
    
    # 如果活动关联了实验室，检查是否是实验室的指导教师
    if activity.laboratory_id:
        return is_lab_instructor(user_info, activity.laboratory_id, laboratory_manager, teacher_manager)
    
    return False

def can_manage_activities(user_info: dict, lab_id: int = None, laboratory_manager = None, teacher_manager = None) -> bool:
    """
    检查用户是否可以管理活动（添加、删除、批量操作等）
    
    Args:
        user_info: 用户信息字典（可能为None）
        lab_id: 可选的实验室ID（如果提供，则检查是否是该实验室的指导教师）
        laboratory_manager: LaboratoryManager实例（当lab_id提供时需要）
        teacher_manager: TeacherManager实例（当lab_id提供时需要）
    
    Returns:
        bool: 如果可以管理活动则返回True
    """
    if not user_info:
        return False
    
    # 管理员可以管理所有活动
    if user_info.get('role') == 'admin':
        return True
    
    # 如果是教师，且提供了lab_id，检查是否是该实验室的指导教师
    if user_info.get('user_type') == 'teacher':
        if lab_id and laboratory_manager and teacher_manager:
            return is_lab_instructor(user_info, lab_id, laboratory_manager, teacher_manager)
        # 如果没有提供lab_id，则所有教师都可以管理活动（但只能编辑自己实验室的活动）
        return True
    
    return False

