"""
用户共同路由模块
将学生和教师的共同功能抽取到这里
"""
from flask import Blueprint, session, jsonify, request, render_template, flash, redirect, url_for
from app.auth import require_user_type
from app.utils import get_app_context_instance
from werkzeug.security import generate_password_hash, check_password_hash
import json
import logging

logger = logging.getLogger(__name__)


def register_common_routes(blueprint: Blueprint, user_type: str, skip_routes: list = None):
    """
    为指定的蓝图注册共同的路由
    
    Args:
        blueprint: Flask蓝图对象
        user_type: 用户类型 ('student' 或 'teacher')
        skip_routes: 要跳过的路由列表，如 ['personal', 'profile']
    """
    if skip_routes is None:
        skip_routes = []
    
    if 'dashboard' not in skip_routes:
        @blueprint.route('/')
        @blueprint.route('/dashboard')
        @require_user_type(user_type)
        def dashboard():
            """用户首页（参考网站风格）"""
            # 检查是否需要强制修改密码
            if session.get('needs_password_change') and user_type == 'student':
                return redirect(url_for(f'{user_type}.profile', tab='password'))
            return render_template(f'{user_type}/dashboard_ref.html')
    
    if 'activities' not in skip_routes:
        @blueprint.route('/activities')
        @require_user_type(user_type)
        def activities():
            """用户活动页面（参考网站风格，假数据）"""
            # 检查是否需要强制修改密码
            if session.get('needs_password_change') and user_type == 'student':
                return redirect(url_for(f'{user_type}.profile', tab='password'))
            return render_template(f'{user_type}/activities_ref.html')
    
    if 'achievements' not in skip_routes:
        @blueprint.route('/achievements')
        @require_user_type(user_type)
        def achievements():
            """用户成果页面（参考网站风格，假数据）"""
            # 检查是否需要强制修改密码
            if session.get('needs_password_change') and user_type == 'student':
                return redirect(url_for(f'{user_type}.profile', tab='password'))
            return render_template(f'{user_type}/achievements_ref.html')
    
    # 个人主页已合并到仪表板，不再需要单独路由
    
    if 'profile' not in skip_routes:
        @blueprint.route('/profile')
        @require_user_type(user_type)
        def profile():
            """用户个人设置页面"""
            return render_template(f'{user_type}/profile.html')

    if 'change_password' not in skip_routes:
        @blueprint.route('/change_password', methods=['POST'])
        @require_user_type(user_type)
        def change_password():
            """修改密码路由"""
            try:
                data = request.get_json()
                old_password = data.get('old_password')
                new_password = data.get('new_password')
                
                if not old_password or not new_password:
                    return jsonify({'success': False, 'message': '请填写所有必填项'}), 400
                
                user_id = session.get('user_id')
                app_context = get_app_context_instance()
                
                if user_type == 'student':
                    manager = app_context.get_student_manager()
                    user = manager.get_student_by_student_id(user_id)
                else:
                    manager = app_context.get_teacher_manager()
                    user = manager.get_teacher_by_teacher_id(user_id)
                    
                if not user:
                    return jsonify({'success': False, 'message': '用户信息不存在'}), 404
                
                # 验证旧密码
                if not check_password_hash(user.password_hash, old_password):
                    return jsonify({'success': False, 'message': '旧密码错误'}), 400

                # P2-28 密码策略校验（长度/四类三种/键盘连续）+ 常识项（不得同旧密码、不得含登录号）
                from app.password_policy import validate_password_strength
                ok, msg = validate_password_strength(new_password)
                if not ok:
                    return jsonify({'success': False, 'message': msg}), 400
                if new_password == old_password:
                    return jsonify({'success': False, 'message': '新密码不能与旧密码相同'}), 400
                if user_id and user_id.lower() in new_password.lower():
                    return jsonify({'success': False, 'message': '密码不能包含学号/工号'}), 400

                # 更新新密码
                new_password_hash = generate_password_hash(new_password)
                
                if user_type == 'student':
                    manager.update_student(user.id, password_hash=new_password_hash)
                else:
                    manager.update_teacher(user.id, password_hash=new_password_hash)
                
                # 如果有强制修改密码标记，清除它
                if session.get('needs_password_change'):
                    session.pop('needs_password_change', None)
                
                logger.info(f"User {user_id} ({user_type}) changed password successfully")
                return jsonify({'success': True, 'message': '密码修改成功'})
            except Exception as e:
                logger.error(f"Error changing password for {user_type} {session.get('user_id')}: {str(e)}")
                return jsonify({'success': False, 'message': f'修改失败: {str(e)}'}), 500


def get_profile_data_common(user_type: str):
    """
    获取用户个人信息的共同逻辑
    
    Args:
        user_type: 用户类型 ('student' 或 'teacher')
    
    Returns:
        JSON响应
    """
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'message': '用户未登录'}), 401
            
        app_context = get_app_context_instance()
        
        # 根据用户类型获取不同的管理器
        if user_type == 'student':
            manager = app_context.get_student_manager()
            user = manager.get_student_by_student_id(user_id)
            if not user:
                return jsonify({'success': False, 'message': '学生信息不存在'}), 404
            
            return jsonify({
                'success': True,
                'data': {
                    'id': user.id,
                    'student_id': user.student_id,
                    'name': user.name,
                    'major': user.major or '',
                    'grade': user.grade or '',
                    'phone': user.phone or '',
                    'qq': user.qq or '',
                    'skills': _parse_skills(user.skills)
                }
            })
        else:  # teacher
            manager = app_context.get_teacher_manager()
            user = manager.get_teacher_by_teacher_id(user_id)
            if not user:
                return jsonify({'success': False, 'message': '教师信息不存在'}), 404
            
            return jsonify({
                'success': True,
                'data': {
                    'id': user.id,
                    'teacher_id': user.teacher_id,
                    'name': user.name,
                    'department': user.department or '',
                    'phone': user.phone or '',
                    'qq': user.qq or '',
                    'skills': _parse_skills(user.skills)
                }
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'获取信息失败: {str(e)}'}), 500


def _parse_skills(skills_str):
    """解析技能标签JSON"""
    if not skills_str:
        return []
    try:
        return json.loads(skills_str) if isinstance(skills_str, str) else skills_str
    except:
        return []
