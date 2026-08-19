"""
认证路由：登录、登出
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_file, current_app
from pathlib import Path
from app.auth import verify_user, login_user, logout_user, is_logged_in, require_login
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
        
        # P2-25 登录失败锁定：先查锁定态（统一提示，不区分账号是否存在，防枚举）
        config = get_config()
        client_ip = request.remote_addr or ''
        from backend.utils.login_guard import check_login_allowed, record_login_failure, record_login_success
        allowed, retry_after = check_login_allowed(str(config.DATABASE_PATH), username, client_ip)
        if not allowed:
            flash(f'尝试过于频繁，请 {retry_after} 秒后再试', 'error')
            return render_template('auth/login.html')
        
        # 验证用户
        user_info = verify_user(username, password, str(config.DATABASE_PATH))
        
        if user_info:
            record_login_success(str(config.DATABASE_PATH), username, client_ip)
            login_user(user_info)
            
            # 首登强制改密（P1-2 全角色）：管理员重置密码时置 needs_password_change 标记，
            # 登录即拦截至改密页（取代旧"学生+默认密码"判定——默认密码已移除）
            if user_info.get('needs_password_change'):
                session['needs_password_change'] = True
                flash('为了您的账号安全，请先修改初始密码', 'warning')
                profile_route = {
                    'student': 'student.profile', 'teacher': 'teacher.profile',
                    'admin': 'admin.profile',
                }.get(user_info['user_type'], 'student.profile')
                return redirect(url_for(profile_route, tab='password'))

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
            record_login_failure(str(config.DATABASE_PATH), username, client_ip)
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
@require_login
def laboratory_file_access(relative_path):
    """提供实验室文件访问（P0-10/D1 整改：登录可见 + 强制下载 + mimetype 白名单，杜绝 inline 渲染 XSS）"""
    try:
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()

        # 构建完整的相对路径
        full_relative_path = f"laboratories/{relative_path}"

        # 使用统一文件管理器查找文件
        file_path = file_manager.find_file_by_path(full_relative_path)

        # P0-10：mimetype 白名单 + 强制 attachment（任何用户上传文件禁止 inline 渲染）
        from pathlib import PurePath
        SAFE_MIMETYPES = {
            '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
            '.pdf': 'application/pdf', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            '.zip': 'application/zip', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        }
        ext = PurePath(str(file_path)).suffix.lower()
        mimetype = SAFE_MIMETYPES.get(ext)
        if mimetype is None:
            from flask import abort
            abort(415)
        download_name = PurePath(relative_path).name
        return send_file(str(file_path), mimetype=mimetype, as_attachment=True, download_name=download_name)

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
@require_login
def laboratory_static_access(relative_path):
    """提供实验室静态文件访问（兼容旧的/static路径）"""
    return laboratory_file_access(relative_path)


@bp.route('/files/achievements/<int:pending_id>')
@require_login
def achievement_file_access(pending_id):
    """成果文件安全访问（P1-4/设计 API §6：按 ID 查库防路径猜解 + 归属校验 + 强制下载）。

    归属规则：提交人本人 或 管理员 可访问（教师经既有 teacher 审核路由访问，该路由自带
    get_pending_for_teacher 过滤）。旧路径式接口（/student|teacher/achievement-submit/file/<path>）
    已标记废弃，本端点运行一个迭代后由前端统一切换并移除旧路由。
    """
    from flask import abort, session, send_file as _send
    from werkzeug.exceptions import HTTPException
    try:
        from app.utils import get_app_context_instance
        pm = get_app_context_instance().get_pending_achievement_manager()
        pending = pm.get_pending_by_id(pending_id)
        if not pending or not pending.file_path:
            abort(404)

        utype, uid = session.get('user_type'), str(session.get('user_id', ''))
        is_owner = (utype == pending.submitter_type and uid == str(pending.submitter_id))
        if not (is_owner or utype == 'admin'):
            abort(403)   # IDOR：他人成果文件一律拒绝

        from pathlib import Path, PurePath
        from backend.services.unified_file_manager import get_unified_file_manager
        root = Path(get_unified_file_manager().files_root).resolve()
        fp = Path(pending.file_path)
        fp = fp.resolve() if fp.is_absolute() else (root / pending.file_path).resolve()
        if root not in fp.parents:   # 路径穿越兜底（历史绝对路径数据也受约束）
            abort(404)

        SAFE = {'.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png',
                '.pdf': 'application/pdf', '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                '.zip': 'application/zip', '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        ext = fp.suffix.lower()
        mimetype = SAFE.get(ext)
        if mimetype is None:
            abort(415)
        return _send(str(fp), mimetype=mimetype, as_attachment=True, download_name=fp.name)
    except HTTPException:
        raise                      # 403/404/415 等业务拒绝码原样抛出，不被兜底吞掉
    except Exception:
        abort(404)

