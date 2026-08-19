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
            if session.get('needs_password_change'):
                return redirect(url_for(f'{user_type}.profile', tab='password'))
            return render_template(f'{user_type}/dashboard_ref.html')
    
    if 'activities' not in skip_routes:
        @blueprint.route('/activities')
        @require_user_type(user_type)
        def activities():
            """用户活动页面（参考网站风格，假数据）"""
            # 检查是否需要强制修改密码
            if session.get('needs_password_change'):
                return redirect(url_for(f'{user_type}.profile', tab='password'))
            return render_template(f'{user_type}/activities_ref.html')
    
    if 'achievements' not in skip_routes:
        @blueprint.route('/achievements')
        @require_user_type(user_type)
        def achievements():
            """用户成果页面（参考网站风格，假数据）"""
            # 检查是否需要强制修改密码
            if session.get('needs_password_change'):
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
                    manager.update_student(user.id, password_hash=new_password_hash, needs_password_change=0)
                else:
                    manager.update_teacher(user.id, password_hash=new_password_hash, needs_password_change=0)
                # M1 后半①：users 写真源（旧表 Manager 更新保留为视图化前镜像）
                from backend.orm.repositories import UserRepository
                UserRepository.update_password(str(user_id), new_password_hash, needs_password_change=0)
                
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


def shared_achievement_submit_upload(user_obj, user_type, redirect_bp):
    """共享上传链路（M2：student/teacher 参数化去重，P3-2）。

    原 student.py/teacher.py 各 ~330 行克隆，差异仅 5 处（用户获取/检查、submitter、
    跳转蓝图、日志文案），本函数参数化统一；路由层保留薄壳。
    """
    import hashlib
    from pathlib import Path
    from datetime import datetime
    from backend.services.file_upload_service import FileUploadService
    from app.routes.admin_achievement import (
        _resolve_laboratory_by_first_supervisor,
        _resolve_laboratory_id_for_innovation_project,
    )
    import logging

    logger = logging.getLogger(__name__)

    """处理文件上传（学生版本，submitter_type为student）"""
    import hashlib
    from pathlib import Path
    from datetime import datetime
    from backend.services.file_upload_service import FileUploadService
    from app.routes.admin_achievement import (
        _resolve_laboratory_by_first_supervisor,
        _resolve_laboratory_id_for_innovation_project,
    )
    import logging

    logger = logging.getLogger(__name__)

    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        user_id = session.get('user_id')
        if not user_obj:
            return jsonify({'success': False, 'message': '用户信息不存在'}), 400

        # 获取上传的文件
        files = request.files.getlist('files')
        if not files:
            return jsonify({'success': False, 'message': '请选择要上传的文件'}), 400

        # 获取缓存选项
        use_ocr_cache = request.form.get('use_ocr_cache', '1') == '1'
        use_llm_cache = request.form.get('use_llm_cache', '1') == '1'

        # 获取实验室关联模式
        lab_association_mode = request.form.get('lab_association_mode', 'auto')
        laboratory_id = None
        if lab_association_mode and lab_association_mode != 'none':
            if lab_association_mode.startswith('specific:'):
                try:
                    laboratory_id = int(lab_association_mode.split(':', 1)[1])
                except (ValueError, IndexError):
                    pass

        # 从配置文件获取临时目录
        from config.loader import get_config
        config_loader = get_config()
        base_temp_dir = config_loader.get_path("temp_dir")

        # 导入会话ID：前端可传 task_id 以便轮询进度，否则服务端生成
        client_task_id = request.form.get('task_id', '').strip()
        if client_task_id:
            import_session_id = client_task_id
        else:
            import_session_id = hashlib.md5(str(datetime.now()).encode()).hexdigest()

        # 创建会话专用临时目录
        temp_dir = base_temp_dir / f"file_import_{import_session_id}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 FileUploadService
        upload_service = FileUploadService()

        # 统计结果
        results = {
            'award': {'valid': 0, 'invalid': 0},
            'patent': {'valid': 0, 'invalid': 0},
            'software': {'valid': 0, 'invalid': 0},
            'innovation': {'valid': 0, 'invalid': 0},
            'other': {'valid': 0, 'invalid': 0}
        }

        submitter_id = user_obj.id
        submitter_type = user_type

        from backend.services.unified_file_manager import get_unified_file_manager
        from backend.extract.types import ExtractStatus
        from app.utils import get_doc_rec_context
        file_manager = get_unified_file_manager()
        framework = get_doc_rec_context().extract_framework

        # 初始化进度（写入 import_progress_store，供进度接口轮询）
        valid_files = [f for f in files if f and f.filename]
        from app.import_progress_store import set_progress, update_progress
        initial_progress = {
            'total': len(valid_files),
            'current': 0,
            'current_file': '',
            'current_step': '正在处理文件...',
            'status': 'processing',
            'uploaded_count': len(valid_files),
            'stats': {
                'award': {'valid': 0, 'invalid': 0},
                'patent': {'valid': 0, 'invalid': 0},
                'software': {'valid': 0, 'invalid': 0},
                'innovation': {'valid': 0, 'invalid': 0},
                'other': {'valid': 0, 'invalid': 0}
            },
            'errors': []
        }
        set_progress(import_session_id, initial_progress)

        # 处理每个文件（与教师路由逻辑相同，但submitter_type不同）
        for idx, file in enumerate(valid_files):
            if not file or not file.filename:
                continue

            try:
                # 更新进度（供前端轮询）
                update_progress(import_session_id, current=idx + 1, current_file=file.filename,
                               current_step=f'正在识别: {file.filename}', stats=dict(results))

                # 1. 仅上传文件（FileUploadService 只接受 uploaded_file）
                upload_result = upload_service.upload_file(file)

                if not upload_result.success:
                    logger.error(f"文件上传失败: {file.filename}, 错误: {upload_result.error}")
                    results['other']['invalid'] += 1
                    continue

                full_path = file_manager.files_root / upload_result.relative_path
                if not full_path.exists():
                    logger.error(f"上传文件不存在: {full_path}")
                    results['other']['invalid'] += 1
                    continue

                # 2. 按路径自动识别类型并抽取，再创建 pending
                result = framework.extract(str(full_path), use_ocr_cache, use_llm_cache)

                if result.status != ExtractStatus.SUCCESS:
                    try:
                        data = {
                            'import_session_id': import_session_id,
                            'file_name': file.filename,
                            'file_path': upload_result.relative_path,
                            'file_type': Path(file.filename).suffix.lower()
                        }
                        note = (result.data or {}).get('note') or (getattr(result, 'error_message', None) or '识别失败，已转为其他类型处理。')
                        data['note'] = note
                        validation = {'is_valid': True, 'completeness_issues': []}
                        ext_info = {'import_session_id': import_session_id}
                        pending_manager.submit_for_review(
                            achievement_type='other',
                            achievement_data=data,
                            validation_result=validation,
                            submitter_type=submitter_type,
                            submitter_id=submitter_id,
                            file_path=upload_result.relative_path,
                            status='pending',
                            file_hash=upload_result.file_hash,
                            ext_info=ext_info
                        )
                        results['other']['valid'] += 1
                    except Exception as e:
                        logger.error(f"创建其他文件记录失败: {e}", exc_info=True)
                        results['other']['invalid'] += 1
                    continue

                result.metadata = result.metadata or {}
                result.metadata['session_id'] = import_session_id
                pending = pending_manager.create_from_extract_result(
                    result,
                    submitter_type=submitter_type,
                    submitter_id=submitter_id,
                    file_path=upload_result.relative_path,
                    file_hash=upload_result.file_hash,
                    status='pending',
                    laboratory_id=laboratory_id
                )
                if not pending:
                    logger.error("create_from_extract_result 未返回 pending")
                    results['other']['invalid'] += 1
                    continue

                # 获取验证结果
                validation_result = pending.get_validation_result()
                is_valid = validation_result.get('is_valid', False) if validation_result else False
                
                if not isinstance(is_valid, bool):
                    is_valid = False
                
                if is_valid:
                    content_issues = validation_result.get('content_issues', []) if validation_result else []
                    completeness_issues = validation_result.get('completeness_issues', []) if validation_result else []
                    if content_issues or completeness_issues:
                        is_valid = False

                status = 'pending'

                # 更新 achievement_data
                achievement_data = pending.get_achievement_data()
                if not isinstance(achievement_data, dict):
                    achievement_data = {}
                
                achievement_data['import_session_id'] = import_session_id
                achievement_data['file_name'] = file.filename
                achievement_data['file_path'] = upload_result.relative_path
                achievement_data['file_type'] = Path(file.filename).suffix.lower()

                # PDF 时生成第一页预览图，供 results 页显示
                preview_image_path = None
                if upload_result.relative_path and upload_result.relative_path.lower().endswith('.pdf'):
                    try:
                        from backend.utils.pdf_to_image import get_or_create_pdf_preview
                        preview_dir = full_path.parent / 'preview'
                        preview_dir.mkdir(parents=True, exist_ok=True)
                        preview_path = get_or_create_pdf_preview(str(full_path), preview_dir)
                        if preview_path:
                            preview_path_obj = Path(preview_path)
                            try:
                                preview_relative = preview_path_obj.relative_to(file_manager.files_root)
                                preview_image_path = str(preview_relative).replace('\\', '/')
                            except ValueError:
                                logger.warning("[学生上传PDF预览] 预览图不在 files_root 下: %s", preview_path)
                    except Exception as e:
                        logger.warning("[学生上传PDF预览] 生成失败: %s", e, exc_info=True)
                if preview_image_path:
                    achievement_data['preview_image_path'] = preview_image_path

                if laboratory_id is not None:
                    achievement_data['laboratory_id'] = laboratory_id

                if pending.ocr_text:
                    achievement_data['ocr_result'] = pending.ocr_text
                if pending.llm_response:
                    achievement_data['llm_response'] = pending.llm_response
                
                ext_info = pending.get_ext_info() if hasattr(pending, 'get_ext_info') else {}
                if isinstance(ext_info, dict):
                    template_id = ext_info.get('template_id')
                    template_name = ext_info.get('template_name')
                    
                    if template_id:
                        achievement_data['template_id'] = template_id
                    
                    if template_name:
                        achievement_data['matched_template_name'] = template_name
                    elif template_id:
                        try:
                            from app.utils import get_doc_rec_context
                            doc_rec_context = get_doc_rec_context()
                            template_manager = doc_rec_context.template_manager
                            template = template_manager.get_template(template_id)
                            if template:
                                achievement_data['matched_template_name'] = template.get_display_name()
                        except Exception as e:
                            logger.warning(f"获取模板名称失败: {e}")

                # 更新 pending 记录
                pending_manager.update(
                    pending_item=pending,
                    status=status,
                    achievement_data=achievement_data
                )

                # 未指定实验室时，根据第一导师自动关联
                ach_type = pending.achievement_type or 'other'
                if ach_type == 'innovation' and achievement_data.get('projects') and laboratory_manager:
                    for p in achievement_data['projects']:
                        if not isinstance(p, dict):
                            continue
                        lab_id = _resolve_laboratory_id_for_innovation_project(
                            p, teacher_manager, laboratory_manager
                        )
                        if lab_id is not None:
                            p['laboratory_id'] = lab_id
                    pending_manager.update(
                        pending_item=pending,
                        achievement_data=achievement_data,
                        status=status
                    )
                elif laboratory_id is None and laboratory_manager:
                    lab_id, reason = _resolve_laboratory_by_first_supervisor(
                        achievement_data, ach_type, teacher_manager, laboratory_manager
                    )
                    if lab_id and reason:
                        achievement_data['laboratory_id'] = lab_id
                        pending_manager.update(
                            pending_item=pending,
                            achievement_data=achievement_data,
                            status=status
                        )

                # 统计结果
                achievement_type = ach_type
                
                if achievement_type == 'innovation':
                    achievement_data_check = pending.get_achievement_data()
                    if isinstance(achievement_data_check, dict) and 'projects' in achievement_data_check:
                        if is_valid:
                            results['innovation']['valid'] += 1
                        else:
                            results['innovation']['invalid'] += 1
                    else:
                        if is_valid:
                            results['innovation']['valid'] += 1
                        else:
                            results['innovation']['invalid'] += 1
                elif achievement_type in results:
                    if is_valid:
                        results[achievement_type]['valid'] += 1
                    else:
                        results[achievement_type]['invalid'] += 1
                else:
                    if is_valid:
                        results['other']['valid'] += 1
                    else:
                        results['other']['invalid'] += 1

            except Exception as e:
                logger.error(f"处理文件失败 {file.filename}: {e}", exc_info=True)
                results['other']['invalid'] += 1

        # 更新最终进度状态（供前端轮询）
        update_progress(import_session_id, status='completed', current_step='处理完成', stats=dict(results))

        # 跳转到文件导入结果页面（按角色）
        redirect_url = url_for(f'{redirect_bp}.achievement_submit_results', session_id=import_session_id)

        return jsonify({
            'success': True,
            'uploaded_count': len([f for f in files if f and f.filename]),
            'import_session_id': import_session_id,
            'redirect_url': redirect_url
        })

    except Exception as e:
        logger.error(f"文件上传失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'上传失败: {str(e)}'}), 500


