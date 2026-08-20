"""
Flask应用工厂
"""
from flask import Flask
from pathlib import Path
import os

def create_app(config_class=None):
    """
    创建Flask应用实例
    
    Args:
        config_class: 配置类，如果为None则从环境变量获取
    
    Returns:
        Flask应用实例
    """
    app = Flask(__name__, 
                template_folder='templates',
                static_folder='static',
                static_url_path='/static')
    
    # 加载配置
    if config_class is None:
        from config.flask import get_config
        config_class = get_config()
    app.config.from_object(config_class)

    # P1-1 CSRF 全局防护：所有写请求须携带 Token（前端经 csrf.js 统一注入：
    # fetch/XHR 自动加头 + POST 表单动态补 hidden；模板经 csrf_token() 输出 meta）
    from flask_wtf.csrf import CSRFProtect
    CSRFProtect(app)

    # T4 统一异常契约：业务异常 -> 统一包装（设计 API §1.4），业务侧不再自行 jsonify 错误
    from flask import jsonify
    from backend.utils.app_error import AppError, BreakerOpenError

    @app.errorhandler(AppError)
    def _handle_app_error(e: AppError):
        # 阶段六 L1：业务异常落系统事件（error 级；写入失败已吞）
        from backend.utils.system_event_logger import SystemEventLogger
        SystemEventLogger.from_exception(
            e, category="system", level="error",
            message=f"AppError {e.code}: {e.message}",
            trace_id=getattr(app, '_current_trace_id', None),
            source_module="app.errorhandler")
        payload = jsonify({"trace_id": getattr(app, '_current_trace_id', None),
                           "code": e.code, "message": e.message, "data": None})
        resp = app.make_response((payload, e.http_status))
        if isinstance(e, BreakerOpenError):
            resp.headers["Retry-After"] = str(e.retry_after)
        return resp

    @app.errorhandler(Exception)
    def _handle_unexpected_error(e: Exception):
        """阶段六 L1：未预期异常兜底 500 + 落系统事件（含堆栈）。

        HTTPException（403/404/400 等框架级响应）放行走默认处理——
        否则会把 CSRF 400/IDOR 403 误吞成 500（L1 实测教训）。
        """
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        from backend.utils.system_event_logger import SystemEventLogger
        SystemEventLogger.from_exception(
            e, category="system", level="critical",
            trace_id=getattr(app, '_current_trace_id', None),
            source_module="app.errorhandler")
        payload = jsonify({"trace_id": getattr(app, '_current_trace_id', None),
                           "code": 5000, "message": "服务器内部错误", "data": None})
        return app.make_response((payload, 500))

    # 确保必要的目录存在
    _ensure_directories(app)
    
    # 注册蓝图
    _register_blueprints(app)
    
    # 注册上下文处理器
    _register_context_processors(app)

    # 阶段六 L1：应用启动落系统事件（system info；写入失败已吞）
    from backend.utils.system_event_logger import SystemEventLogger
    SystemEventLogger.log("system", "info", f"应用启动（env={app.config.get('ENV', 'default')}）",
                          source_module="app.create_app")

    return app

def _ensure_directories(app):
    """确保必要的目录存在（统一文件管理器会自动处理文件目录创建）"""
    # 统一文件管理器会在初始化时创建所需的目录，这里不再需要手动创建
    pass

def _register_blueprints(app):
    """注册蓝图"""
    from app.routes import auth, admin, teacher, student, api
    from app.routes import admin_achievement, admin_awards, admin_export, admin_laboratory, admin_templates
    from app.routes import admin_patents, admin_software, admin_innovation, admin_review, admin_other_files
    from app.routes import admin_data_analysis
    from app.routes import chat

    # Main role blueprints
    app.register_blueprint(auth.bp, url_prefix='')
    app.register_blueprint(admin.bp, url_prefix='/admin')
    app.register_blueprint(teacher.bp, url_prefix='/teacher')
    app.register_blueprint(student.bp, url_prefix='/student')
    app.register_blueprint(api.bp, url_prefix='/api')
    # AI 智能助手（对话系统）
    app.register_blueprint(chat.bp, url_prefix='')

    # Admin sub-blueprints (achievement, export, laboratory, templates)
    app.register_blueprint(admin_achievement.bp, url_prefix='/admin')
    app.register_blueprint(admin_awards.bp, url_prefix='/admin')
    app.register_blueprint(admin_export.bp, url_prefix='/admin')
    app.register_blueprint(admin_laboratory.bp, url_prefix='/admin')
    app.register_blueprint(admin_templates.bp, url_prefix='/admin')
    # Admin sub-blueprints for new achievement types
    app.register_blueprint(admin_patents.bp, url_prefix='/admin')
    app.register_blueprint(admin_software.bp, url_prefix='/admin')
    app.register_blueprint(admin_innovation.bp, url_prefix='/admin')
    app.register_blueprint(admin_review.bp, url_prefix='/admin')
    app.register_blueprint(admin_other_files.bp, url_prefix='/admin')
    # Admin data analysis blueprint
    app.register_blueprint(admin_data_analysis.bp, url_prefix='/admin')

def _register_context_processors(app):
    """注册上下文处理器"""
    @app.context_processor
    def inject_user():
        """注入当前用户信息到模板"""
        from flask import session
        from app.auth import is_logged_in
        from app.utils.user_routes import get_user_route_url, get_user_route_name
        from app.utils import get_competition_level_badge_class
        
        result = {
            # 添加工具函数供模板使用
            'get_competition_level_badge_class': get_competition_level_badge_class,
        }
        
        if is_logged_in():
            result.update({
                'current_user': {
                    'id': session.get('user_id'),
                    'user_id': session.get('user_id'),  # 为了兼容性也添加这个
                    'type': session.get('user_type'),
                    'user_type': session.get('user_type'),  # 为了兼容性也添加这个
                    'role': session.get('role'),
                    'name': session.get('user_name'),
                    'user_name': session.get('user_name')  # 为了兼容性也添加这个
                },
                # 添加路由辅助函数
                'user_route': get_user_route_url,
                'user_route_name': get_user_route_name
            })
        else:
            result.update({
                'current_user': None,
                'user_route': lambda route_name, **kwargs: '#',
                'user_route_name': lambda route_name: ''
            })
        
        return result

