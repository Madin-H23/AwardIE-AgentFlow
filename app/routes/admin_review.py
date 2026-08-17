"""
Achievement Review Routes (管理员 - 成果审核)
Handles the review workflow for student/teacher submitted achievements.

注意：审核业务逻辑统一由 ReviewService 处理，此模块仅负责 HTTP 请求处理和页面渲染。

重要：成果审核页面与文件导入审核页面共用同一模板 (results.html)，
通过 review_helpers 模块提供统一的渲染逻辑。
"""
import logging
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, session
from pathlib import Path
from app.auth import require_role, require_role_api
from backend.utils.idempotency import idempotent
from app.utils import get_app_context_instance
from app.routes.review_helpers import (
    render_review_page,
    query_pending_items,
    get_type_names,
    normalize_laboratory_id,
    normalize_related_student_from_ids,
)
from backend.models.pending_achievement import PendingAchievementManager, PendingAchievement, PendingAchievementFilter
from backend.services.review_service import ReviewService, Reviewer
from config.loader import get_config

logger = logging.getLogger(__name__)
bp = Blueprint('admin_review', __name__)


def _get_review_service(app_context) -> ReviewService:
    """
    获取 ReviewService 实例

    Args:
        app_context: 应用上下文

    Returns:
        ReviewService 实例
    """
    from backend.services.unified_file_manager import get_unified_file_manager

    file_manager = get_unified_file_manager()
    files_dir = file_manager.files_root

    # 使用单例 AutoArchiveConfigManager，不重复创建实例
    auto_archive_config_manager = app_context.get_auto_archive_config_manager()

    return ReviewService(
        pending_manager=app_context.get_pending_achievement_manager(),
        review_log_manager=app_context.get_review_log_manager(),
        laboratory_manager=app_context.get_laboratory_manager(),
        student_manager=app_context.get_student_manager(),
        teacher_manager=app_context.get_teacher_manager(),
        award_manager=app_context.get_award_manager(),
        patent_manager=app_context.get_patent_manager() if hasattr(app_context, 'get_patent_manager') else None,
        software_manager=app_context.get_software_copyright_manager() if hasattr(app_context, 'get_software_copyright_manager') else None,
        innovation_manager=app_context.get_innovation_project_manager() if hasattr(app_context, 'get_innovation_project_manager') else None,
        other_file_manager=app_context.get_other_file_manager() if hasattr(app_context, 'get_other_file_manager') else None,
        competition_manager=app_context.get_competition_manager(),
        auto_archive_config_manager=auto_archive_config_manager,
        files_dir=files_dir
    )


@bp.route('/achievement-review')
@require_role('admin')
def review_list():
    """待审核成果列表 - 重定向到单页式审核界面"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        
        # 成果审核页只显示 status='submit' 的记录，重定向时只用 submit 的统计，避免跳到空列表
        stats = pending_manager.get_stats_by_type_and_validation_for_review()
        if not isinstance(stats, dict):
            logger.error(f"get_stats_by_type_and_validation_for_review returned non-dict: {type(stats)}")
            stats = {}

        first_type = 'award'
        for type_key in ['award', 'patent', 'software', 'innovation', 'other']:
            type_stats = stats.get(type_key)
            if isinstance(type_stats, dict) and type_stats.get('total', 0) > 0:
                first_type = type_key
                break

        return redirect(url_for('admin_review.review_single_global',
                               type=first_type, sub_tab='valid', index=0))
    
    except Exception as e:
        logger.error(f"Error loading review list: {e}", exc_info=True)
        flash(f'加载待审核列表失败: {e}', 'error')
        return redirect(url_for('admin_achievement.achievements'))


@bp.route('/achievement-review/<type>/<sub_tab>/<int:index>')
@require_role('admin')
def review_single_global(type, sub_tab, index):
    """
    单页式审核页面 - 成果审核（显示所有pending_achievements）
    
    与文件导入审核页面共用同一模板 (results.html)，区别在于：
    - 文件导入审核：只显示本次导入的内容（需要 session_id）
    - 成果审核：显示所有待审核内容（session_id=None）
    """
    try:
        app_context = get_app_context_instance()
        
        # 使用统一的渲染函数，session_id=None 表示全局审核
        return render_review_page(
            session_id=None,  # 全局审核，无session_id
            tab_type=type,
            status=sub_tab,
            index=index,
            app_context=app_context,
            title_prefix='成果审核',
            route_prefix='admin_review'
        )
    
    except Exception as e:
        logger.error(f"加载成果审核页面失败: {e}", exc_info=True)
        flash(f'加载审核页面失败: {str(e)}', 'error')
        return redirect(url_for('admin_achievement.achievements'))


@bp.route('/achievement-review/<int:pending_id>')
@require_role('admin')
def review_view(pending_id):
    """查看待审核成果详情"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        pending = pending_manager.get_pending_by_id(pending_id)

        if not pending:
            flash('待审核记录不存在', 'error')
            return redirect(url_for('admin_review.review_list'))

        # Parse achievement data and validation result
        achievement_data = pending.get_achievement_data()
        validation_result = pending.get_validation_result()

        # Get submitter info
        submitter = None
        if pending.submitter_type == 'student':
            student_manager = app_context.get_student_manager()
            submitter = student_manager.get_student_by_id(pending.submitter_id)
        elif pending.submitter_type == 'teacher':
            teacher_manager = app_context.get_teacher_manager()
            submitter = teacher_manager.get_teacher_by_id(pending.submitter_id)

        return render_template('admin/review/view.html',
                             pending=pending,
                             achievement_data=achievement_data,
                             validation_result=validation_result,
                             submitter=submitter)

    except Exception as e:
        logger.error(f"Error viewing pending {pending_id}: {e}")
        flash(f'加载待审核详情失败: {e}', 'error')
        return redirect(url_for('admin_review.review_list'))


@bp.route('/achievement-review/<int:pending_id>/approve', methods=['POST'])
@require_role('admin')
def review_approve(pending_id):
    """审核通过 - 将待审核成果移入正式表（使用 ReviewService 统一逻辑）"""
    try:
        app_context = get_app_context_instance()
        review_service = _get_review_service(app_context)
        
        # 获取审核备注
        comment = request.form.get('comment', '').strip() or None
        reviewer_id = session.get('user_id')
        reviewer = Reviewer(reviewer_type='admin', reviewer_id=reviewer_id)
        
        # 使用 ReviewService 执行审核（force=True 跳过验证检查）
        result = review_service.approve_single(pending_id, reviewer, force=True)
        
        if result.success:
            flash('审核通过，成果已入库', 'success')
            return redirect(url_for('admin_review.review_list'))
        else:
            flash(f'审核失败: {result.error}', 'error')
            return redirect(url_for('admin_review.review_view', pending_id=pending_id))

    except Exception as e:
        logger.error(f"Error approving pending {pending_id}: {e}")
        flash(f'审核失败: {e}', 'error')
        return redirect(url_for('admin_review.review_view', pending_id=pending_id))


@bp.route('/api/achievement-review/<int:pending_id>/reject', methods=['POST'])
@require_role_api('admin')
def api_reject(pending_id):
    """驳回打回（FR-APPROVE-07，原废弃路由重开）：submit→rejected + 留痕。

    管理员对全量待审记录有权限（get_pending_for_admin 校验）。
    """
    try:
        data = request.get_json(silent=True) or {}
        reason = (data.get('reason') or '').strip()
        if not reason:
            return jsonify({'success': False, 'message': '请填写驳回原因'}), 400

        from app.utils import get_app_context_instance
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()

        if pending_id not in [p.id for p in pending_manager.get_pending_for_admin()]:
            return jsonify({'success': False, 'message': '无权操作该记录'}), 403

        from flask import session
        reviewer_id = session.get('user_id')
        if pending_manager.reject(pending_id, 'admin', reviewer_id, reason):
            from backend.utils.audit_logger import audit_log
            audit_log(7, pending_id, None,
                      operator={"id": reviewer_id, "code": str(reviewer_id), "user_type": "admin"},
                      action_result=2, remark=reason[:200])
            return jsonify({'success': True, 'message': '已驳回，提交人可查看原因并修改后重新提交'})
        return jsonify({'success': False, 'message': '驳回失败：记录不存在或状态已变化'}), 409
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/achievement-review/<int:pending_id>/approve-with-data', methods=['POST'])
@require_role_api('admin')
def api_approve_with_data(pending_id):
    """
    审核通过单条记录（JSON API），支持前端提交的表单数据更新。
    用于成果审核页面「提交」按钮：先更新 pending 的 achievement_data（如有编辑），
    再审核通过并入库、删除 pending。仅用于全局审核模式（submit 状态记录）。
    """
    try:
        payload = request.get_json() or {}
        modified_data = payload.get('data') or {}

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        pending = pending_manager.get_pending_by_id(pending_id)

        if not pending:
            return jsonify({'success': False, 'message': '记录不存在'}), 404

        if modified_data:
            # 奖状：将 related_student_ids 转为 related_student/related_student_name
            if pending.achievement_type == 'award':
                normalize_related_student_from_ids(modified_data, app_context.get_student_manager())
            current = pending.get_achievement_data()
            if isinstance(current, dict):
                current = dict(current)
                current.update(modified_data)
                current['laboratory_id'] = normalize_laboratory_id(current.get('laboratory_id'))
                # 未选具体竞赛时用解析出的竞赛名，后端将自动创建竞赛
                if not (current.get('competition_name') or '').strip() and (current.get('original_competition_name') or '').strip():
                    current['competition_name'] = (current.get('original_competition_name') or '').strip()

                # 重新计算验证结果
                achievement_type = pending.achievement_type or 'award'
                from app.routes.admin_achievement import _get_full_validation_result
                import json
                new_validation_result = _get_full_validation_result(achievement_type, current, app_context)
                new_validation_json = json.dumps(new_validation_result, ensure_ascii=False)

                # 同时更新 achievement_data 和 validation_result
                pending_manager.update(
                    pending_item=pending,
                    achievement_data=current,
                    validation_result=new_validation_json,
                    status=pending.status
                )
                pending = pending_manager.get_pending_by_id(pending_id)

        # 优先使用修改后的laboratory_id，其次使用pending记录本身的laboratory_id，最后使用achievement_data中的laboratory_id
        lab_id = None
        if isinstance(modified_data, dict) and modified_data.get('laboratory_id') is not None:
            lab_id = normalize_laboratory_id(modified_data['laboratory_id'])
        elif pending.laboratory_id is not None:
            lab_id = pending.laboratory_id

        review_service = _get_review_service(app_context)
        reviewer_id = session.get('user_id')
        reviewer = Reviewer(reviewer_type='admin', reviewer_id=reviewer_id)
        result = review_service.approve_single(
            pending_id, reviewer, lab_id=lab_id or None, force=True
        )

        if result.success:
            return jsonify({
                'success': True,
                'message': '审核通过，成果已入库',
                'target_id': result.target_id,
                'target_table': result.target_table,
            })
        return jsonify({
            'success': False,
            'message': result.error or '审核失败',
        }), 400

    except Exception as e:
        logger.error(f"api_approve_with_data 失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/achievement-review/<int:pending_id>/validation', methods=['GET'])
@require_role('admin')
def api_get_validation(pending_id):
    """获取验证结果（AJAX）"""
    try:
        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        pending = pending_manager.get_pending_by_id(pending_id)

        if not pending:
            return jsonify({'error': '记录不存在'}), 404

        validation_result = pending.get_validation_result()

        return jsonify({
            'is_valid': validation_result.get('is_valid', False),
            'content_issues': validation_result.get('content_issues', []),
            'completeness_issues': validation_result.get('completeness_issues', [])
        })

    except Exception as e:
        logger.error(f"Error getting validation: {e}")
        return jsonify({'error': str(e)}), 500


@bp.route('/api/achievement-review/<int:pending_id>/validate', methods=['POST'])
@require_role_api('admin', 'teacher')
def api_validate_with_data(pending_id):
    """
    用当前表单数据重新校验（不保存）。
    用于审核页用户修订日期等字段后，立即更新「识别存在以下问题」提示。
    """
    try:
        payload = request.get_json() or {}
        modified_data = payload.get('data') or {}

        app_context = get_app_context_instance()
        pending_manager = app_context.get_pending_achievement_manager()
        pending = pending_manager.get_pending_by_id(pending_id)

        if not pending:
            return jsonify({'error': '记录不存在'}), 404

        current = pending.get_achievement_data()
        if not isinstance(current, dict):
            current = {}
        else:
            current = dict(current)
        current.update(modified_data)
        current['laboratory_id'] = normalize_laboratory_id(current.get('laboratory_id'))

        achievement_type = pending.achievement_type or 'award'
        from app.routes.admin_achievement import _get_full_validation_result
        result = _get_full_validation_result(achievement_type, current, app_context)
        new_validation_json = json.dumps(result, ensure_ascii=False)

        # 同时更新 pending 的 achievement_data 和 validation_result，使失焦/重新校验后的修订和校验结果持久化
        pending_manager.update(
            pending_item=pending,
            achievement_data=current,
            validation_result=new_validation_json,
            status=pending.status
        )

        return jsonify({
            'is_valid': result.get('is_valid', True),
            'content_issues': result.get('content_issues', []),
            'completeness_issues': result.get('completeness_issues', []),
        })
    except Exception as e:
        logger.error(f"api_validate_with_data 失败: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/api/achievement-review/batch-approve', methods=['POST'])
@require_role('admin')
@idempotent(ttl=600)
def api_batch_approve():
    """批量审核通过（AJAX，幂等防双击）- 使用 ReviewService 统一逻辑"""
    try:
        data = request.get_json()
        pending_ids = data.get('pending_ids', [])
        comment = data.get('comment', '').strip() or None

        if not pending_ids:
            return jsonify({'success': False, 'error': '未选择任何记录'}), 400

        app_context = get_app_context_instance()
        review_service = _get_review_service(app_context)
        reviewer_id = session.get('user_id')
        reviewer = Reviewer(reviewer_type='admin', reviewer_id=reviewer_id)

        # 使用 ReviewService 批量审核（force=True 跳过验证检查）
        results = review_service.approve_batch(pending_ids, reviewer, force=True)

        # 统计结果：大创等一对多按 submitted_count，否则按 1
        approved_count = sum(
            (getattr(r, 'submitted_count', None) or 1) for r in results if r.success
        )
        failed_count = len(results) - sum(1 for r in results if r.success)
        failed_errors = [r.error or '未知错误' for r in results if not r.success]

        return jsonify({
            'success': True,
            'approved': approved_count,
            'failed': failed_count,
            'errors': failed_errors
        })

    except Exception as e:
        logger.error(f"Error in batch approve: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
