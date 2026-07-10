"""
认证路由：登录、登出
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from pathlib import Path
from app.auth import verify_user, login_user, logout_user, is_logged_in
from config.flask import get_config

bp = Blueprint('auth', __name__)

@bp.route('/login', methods=['GET', 'POST'])
def login():
    """登录页面"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('请输入用户名和密码', 'error')
            return render_template('auth/login.html')
        
        # 验证用户
        config = get_config()
        user_info = verify_user(username, password, str(config.DATABASE_PATH))
        
        if user_info:
            login_user(user_info)
            
            # 检查是否需要强制修改密码（学生且使用初始密码）
            from app.utils import get_default_password
            try:
                default_password = get_default_password()
                if user_info['user_type'] == 'student' and password == default_password:
                    session['needs_password_change'] = True
                    flash('为了您的账号安全，请先修改初始密码', 'warning')
                    return redirect(url_for('student.profile', tab='password'))
            except Exception as e:
                # 如果无法获取默认密码配置，记录错误但不影响登录流程
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f'无法获取默认密码配置: {e}')
            
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            # 根据角色跳转到不同页面
            role = user_info['role']
            user_type = user_info.get('user_type')
            
            if role == 'admin' or user_type == 'admin':
                return redirect(url_for('admin_achievement.achievements'))
            elif role == 'teacher' or user_type == 'teacher':
                return redirect(url_for('teacher.dashboard'))
            else:
                return redirect(url_for('student.dashboard'))
        else:
            flash('用户名或密码错误', 'error')
    
    # GET请求或登录失败，显示登录页面
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    """登出"""
    logout_user()
    flash('已成功登出', 'info')
    return redirect(url_for('auth.login'))

@bp.route('/')
def index():
    """首页：展示所有实验室"""
    from app.utils import get_app_context_instance

    try:
        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取所有实验室
        all_labs = laboratory_manager.get_all_laboratories()

        # 为每个实验室计算统计信息
        labs_data = []
        for lab in all_labs:
            # 获取指导教师姓名列表
            instructor_names = [teacher.name for teacher in lab.instructors]

            labs_data.append({
                'lab': lab,
                'instructor_count': len(lab.instructors),
                'instructor_names': instructor_names,
                'student_count': len(lab.students),
                'assistant_count': len(lab.assistants)
            })

        return render_template('index.html', labs_data=labs_data, is_logged_in=is_logged_in())
    except Exception as e:
        import traceback
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'加载首页失败: {str(e)}\n{traceback.format_exc()}')
        return render_template('index.html', labs_data=[], is_logged_in=is_logged_in(), error=str(e))

@bp.route('/files/laboratories/<path:relative_path>')
def laboratory_file_access(relative_path):
    """提供实验室文件访问（公开访问，无需登录）"""
    try:
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()

        # 构建完整的相对路径
        full_relative_path = f"laboratories/{relative_path}"

        # 使用统一文件管理器查找文件
        file_path = file_manager.find_file_by_path(full_relative_path)

        return send_file(str(file_path))

    except FileNotFoundError:
        from flask import abort
        abort(404)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Laboratory file access failed: {e}")
        from flask import abort
        abort(404)

@bp.route('/static/laboratories/<path:relative_path>')
def laboratory_static_access(relative_path):
    """提供实验室静态文件访问（兼容旧的/static路径）"""
    return laboratory_file_access(relative_path)

