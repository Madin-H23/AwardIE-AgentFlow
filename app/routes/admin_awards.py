"""
管理员 - 奖状管理路由（列表/编辑/删除/图片/刷新/成果页 Tab API）
"""
import logging
import json
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for, current_app, session
from pathlib import Path
from app.auth import require_role, require_role_api, require_admin_or_lab_view_api
from app.utils import get_app_context_instance
from backend.services.laboratory_association_service import LaboratoryAssociationService

logger = logging.getLogger(__name__)
bp = Blueprint('admin_awards', __name__)


@bp.route('/awards')
@require_role('admin')
def awards_list():
    """奖状列表页（含异常 TAB、筛选、分页）"""
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    competition_id = request.args.get('competition_id', type=int)
    track = request.args.get('track', '').strip()
    year = request.args.get('year', type=int)
    competition_level = request.args.get('competition_level', '').strip()
    award_level = request.args.get('award_level', '').strip()
    supervisor_name = request.args.get('supervisor_name', '').strip()
    winner_name = request.args.get('winner_name', '').strip()
    laboratory_id = request.args.get('laboratory_id')
    certificate_type = request.args.get('certificate_type', 'student').strip()  # 默认为学生
    tab = request.args.get('tab', 'management')
    is_abnormal_raw = request.args.get('is_abnormal', '').strip()
    
    try:
        # 获取AppContext和管理器
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        
        # 构建查询参数
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        query_params = {
            'with_associations': True,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
            'limit': per_page,
            'offset': (page - 1) * per_page
        }
        
        # 如果是异常奖状TAB，只查询异常奖状
        # 注意：这里设置is_abnormal=True是为了在正常查询流程中使用，但异常奖状TAB会使用数据库直接查询的方式
        if tab == 'abnormal':
            query_params['is_abnormal'] = True
        elif tab == 'management':
            # 奖状管理 Tab 的异常状态筛选
            if is_abnormal_raw == '1':
                query_params['is_abnormal'] = True
            elif is_abnormal_raw == '0':
                query_params['is_abnormal'] = False
        
        # 添加筛选条件
        if competition_id:
            query_params['competition_id'] = competition_id
        if track:
            query_params['track'] = track
        if year:
            query_params['year'] = year
        if competition_level:
            query_params['competition_level'] = competition_level
        if award_level:
            query_params['award_level'] = award_level
        if supervisor_name:
            query_params['supervisor_name'] = supervisor_name
        if winner_name:
            query_params['winner_name'] = winner_name
        if laboratory_id:
            if laboratory_id == 'none':
                # 筛选无实验室的奖状
                query_params['laboratory_id'] = None
                query_params['filter_no_laboratory'] = True
            else:
                try:
                    query_params['laboratory_id'] = int(laboratory_id)
                except (ValueError, TypeError):
                    pass  # 忽略无效的 laboratory_id 值
        
        # 根据证书类型筛选
        if certificate_type == 'student':
            # 只显示学生证书
            query_params['granted_role'] = '学生'
            query_params['exclude_teacher_certificates'] = True
        elif certificate_type == 'teacher':
            # 只显示教师证书
            query_params['granted_role'] = '教师'
        # certificate_type == 'all' 时不添加任何筛选条件，显示全部
        
        # 如果是异常奖状TAB，从内存缓存中查询异常奖状
        if tab == 'abnormal':
            # 使用is_abnormal参数从内存缓存中查询异常奖状
            query_params['is_abnormal'] = True
            awards = award_manager.query_awards(**query_params)
            
            # 计算总数（从内存缓存中统计所有异常奖状）
            all_abnormal_awards = award_manager.query_awards(is_abnormal=True)
            total_count = len(all_abnormal_awards)
            
        else:
            # 正常查询流程
            awards = award_manager.query_awards(**query_params)

            # 获取总数（用于分页）- 不加载关联数据以提升性能
            count_params = {k: v for k, v in query_params.items() if k not in ['limit', 'offset', 'with_associations']}
            count_params['with_associations'] = False  # 计算总数时不需要加载关联数据
            total_awards = award_manager.query_awards(**count_params)
            total_count = len(total_awards) if total_awards else 0
        
        # 获取竞赛（用于筛选下拉框）
        # 从所有有奖状的竞赛中提取 unique 列表
        # 这样下拉框只显示实际有奖状的竞赛，避免显示上百个空竞赛

        # 查询所有奖状（只获取 competition_id，不加载关联数据以提升性能）
        # 应用除 competition_id 外的所有筛选条件
        filter_params = {
            'with_associations': False,
            'limit': None,
            'offset': None
        }

        # 复制其他筛选条件（不含 competition_id、track，以便下拉选项来自当前结果集）
        if year:
            filter_params['year'] = year
        if competition_level:
            filter_params['competition_level'] = competition_level
        if award_level:
            filter_params['award_level'] = award_level
        if supervisor_name:
            filter_params['supervisor_name'] = supervisor_name
        if winner_name:
            filter_params['winner_name'] = winner_name
        if laboratory_id:
            filter_params['laboratory_id'] = laboratory_id
        
        # 根据证书类型筛选
        if certificate_type == 'student':
            filter_params['granted_role'] = '学生'
            filter_params['exclude_teacher_certificates'] = True
        elif certificate_type == 'teacher':
            filter_params['granted_role'] = '教师'
        # certificate_type == 'all' 时不添加任何筛选条件
        
        if tab == 'abnormal':
            filter_params['is_abnormal'] = True
        elif tab == 'management' and is_abnormal_raw:
            if is_abnormal_raw == '1':
                filter_params['is_abnormal'] = True
            elif is_abnormal_raw == '0':
                filter_params['is_abnormal'] = False

        # 查询所有满足条件的奖状（不分页）
        all_awards_for_filter = award_manager.query_awards(**filter_params)

        # 提取 unique 的 competition_id
        used_competition_ids = set()
        if all_awards_for_filter:
            for award in all_awards_for_filter:
                if award.competition_id:
                    used_competition_ids.add(award.competition_id)

        # 获取竞赛对象（只获取实际使用的竞赛）；缺失时从 DB 加载，避免新建竞赛显示「未知竞赛」
        all_competitions_map = {}
        if hasattr(competition_manager, 'competitions'):
            for comp in competition_manager.competitions:
                all_competitions_map[comp.id] = comp

        for comp_id in used_competition_ids:
            if comp_id not in all_competitions_map and hasattr(competition_manager, 'get_competition_by_id_from_db'):
                comp = competition_manager.get_competition_by_id_from_db(comp_id)
                if comp:
                    all_competitions_map[comp_id] = comp

        all_competitions = []
        for comp_id in used_competition_ids:
            if comp_id in all_competitions_map:
                all_competitions.append(all_competitions_map[comp_id])

        # 按名称排序，方便用户查找
        if all_competitions:
            all_competitions = sorted(all_competitions, key=lambda x: x.name)

        # 从当前结果集中提取赛道列表：若已选竞赛则只显示该竞赛下的赛道，否则显示全部
        awards_for_tracks = (all_awards_for_filter or [])
        if competition_id:
            awards_for_tracks = [a for a in awards_for_tracks if a.competition_id == competition_id]
        track_options = sorted(
            {a.track.strip() for a in awards_for_tracks
             if getattr(a, 'track', None) and str(a.track).strip()}
        )
        
        # 从全局配置加载竞赛等级列表（用于下拉框，只显示标准化的等级）
        from app.utils import get_competition_levels_for_ui
        competition_levels = get_competition_levels_for_ui()
        
        # 计算分页信息
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        # 获取异常奖状总数（用于显示在TAB上）
        # 从内存缓存中查询，保持与数据查询逻辑一致
        abnormal_count = 0
        if tab != 'abnormal':
            try:
                abnormal_awards = award_manager.query_awards(is_abnormal=True, with_associations=False)
                abnormal_count = len(abnormal_awards) if abnormal_awards else 0
            except Exception as e:
                current_app.logger.error(f"查询异常奖状总数失败: {e}")
        
        # 导入工具函数供模板使用
        from app.utils import get_competition_level_badge_class

        # 获取实验室列表（用于筛选下拉框和构建 laboratory_map）
        laboratory_manager = app_context.get_laboratory_manager()
        all_laboratories = []
        if hasattr(laboratory_manager, 'get_all_laboratories'):
            all_laboratories = laboratory_manager.get_all_laboratories()
        elif hasattr(laboratory_manager, 'laboratories'):
            all_laboratories = laboratory_manager.laboratories

        # 构建 laboratory_map (ID -> name)
        laboratory_map = {lab.id: lab.name for lab in all_laboratories}

        # 构建 award_laboratory_map (award_id -> lab_name) - 用于显示
        award_laboratory_map = {}
        if awards:
            for award in awards:
                if award.laboratory_id and award.laboratory_id in laboratory_map:
                    award_laboratory_map[award.id] = laboratory_map[award.laboratory_id]

        return render_template('admin/awards/main.html',
                             awards=awards or [],
                             competitions=all_competitions,
                             competition_levels=competition_levels,
                             laboratories=all_laboratories,
                             get_competition_level_badge_class=get_competition_level_badge_class,
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages,
                             competition_id=competition_id,
                             year=year,
                             competition_level=competition_level,
                             award_level=award_level,
                             supervisor_name=supervisor_name,
                             winner_name=winner_name,
                             laboratory_id=laboratory_id,
                             certificate_type=certificate_type,
                             is_abnormal_filter=is_abnormal_raw,
                             track=track,
                             track_options=track_options,
                             abnormal_count=abnormal_count,
                             laboratory_map=laboratory_map,
                             award_laboratory_map=award_laboratory_map)
    except Exception as e:
        flash(f'加载奖状列表失败: {str(e)}', 'error')
        # 加载竞赛等级配置（禁止硬编码，必须从配置文件读取）
        # 从全局配置加载竞赛等级列表（用于下拉框，只显示标准化的等级）
        from app.utils import get_competition_levels_for_ui
        competition_levels = get_competition_levels_for_ui()
        
        return render_template('admin/awards/main.html',
                             awards=[],
                             competitions=[],
                             competition_levels=competition_levels,
                             page=1,
                             per_page=20,
                             total_count=0,
                             total_pages=1,
                             competition_level='',
                             track='',
                             track_options=[],
                             supervisor_name='',
                             winner_name='',
                             certificate_type='student',
                             is_abnormal_filter='')

@bp.route('/awards/<int:award_id>', methods=['DELETE'])
@require_role('admin')
def award_delete(award_id):
    """删除奖状"""
    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()

        # 防重复删除：仅当成果真实存在时删除并留痕；已删除/不存在 → 明确提示且不再写留痕
        from backend.utils.db_connection import get_connection
        from config.loader import get_config
        conn = get_connection(get_config().get_path('database', 'competitions_db'))
        try:
            exists = conn.execute("SELECT COUNT(*) FROM awards WHERE id=?", (award_id,)).fetchone()[0]
        finally:
            conn.close()
        if not exists:
            return jsonify({'success': False, 'message': '成果不存在或已删除'}), 404

        # 删除奖状（删除前留痕：动作12=成果删除，可追溯/防留痕悬空）
        from backend.utils.audit_logger import audit_log
        audit_log(12, award_id, 'award', remark='成果删除')
        award_manager.delete_award(award_id)

        return jsonify({'success': True, 'message': '删除成功'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'删除失败: {str(e)}'}), 500

@bp.route('/awards/batch-delete', methods=['POST'])
@require_role('admin')
def awards_batch_delete():
    """批量删除奖状"""
    try:
        data = request.get_json()
        award_ids = data.get('award_ids', [])
        
        if not award_ids:
            return jsonify({'success': False, 'message': '请选择要删除的奖状'}), 400
        
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors = []
        
        # 防重复删除：仅真实存在的成果才删除并留痕；已不存在则跳过（不计成功、不再写留痕）
        from backend.utils.audit_logger import audit_log
        from backend.utils.db_connection import get_connection
        from config.loader import get_config
        conn = get_connection(get_config().get_path('database', 'competitions_db'))
        try:
            existing = {r[0] for r in conn.execute(
                f"SELECT id FROM awards WHERE id IN ({','.join('?' * len(award_ids))})",
                award_ids)}
        finally:
            conn.close()
        for award_id in award_ids:
            try:
                if award_id not in existing:
                    skipped_count += 1
                    continue
                audit_log(12, award_id, 'award', remark='成果删除')
                award_manager.delete_award(award_id)
                success_count += 1
            except Exception as e:
                failed_count += 1
                errors.append(f'ID {award_id}: {str(e)}')
        
        if failed_count == 0:
            return jsonify({
                'success': True, 
                'message': f'成功删除 {success_count} 条奖状'
                + (f'（{skipped_count} 条已不存在，跳过）' if skipped_count else '')
            })
        else:
            return jsonify({
                'success': True,
                'message': f'成功删除 {success_count} 条，失败 {failed_count} 条',
                'errors': errors[:5]  # 只返回前5个错误
            })
    except Exception as e:
        return jsonify({'success': False, 'message': f'批量删除失败: {str(e)}'}), 500

@bp.route('/awards/<int:award_id>/image')
def award_image(award_id):
    """获取奖状图片"""
    from flask import send_file, session
    try:
        from app.auth import is_logged_in, get_current_user

        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        teacher_manager = app_context.get_teacher_manager()

        # 查询奖状
        awards = award_manager.query_awards(id=award_id, with_associations=True,
                                           student_manager=app_context.get_student_manager(),
                                           teacher_manager=teacher_manager)
        if not awards:
            return "奖状不存在", 404

        award = awards[0]

        # 检查登录状态
        if not is_logged_in():
            return "请先登录", 401

        # 已登录用户，检查权限（与 award_edit 保持一致）
        user_role = session.get('role')
        if user_role == 'teacher':
            user_id = session.get('user_id')
            teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
            if not teacher:
                return "教师信息不存在", 403

            # 检查教师是否关联了该奖状（与 award_edit 逻辑一致）
            is_related = False
            # 1. 作为获奖者
            for teacher_winner in award.teacher_winners:
                if teacher_winner.id == teacher.id:
                    is_related = True
                    break
            # 2. 作为指导教师
            if not is_related:
                for supervisor in award.supervisors:
                    if supervisor.id == teacher.id:
                        is_related = True
                        break
            # 3. 未认领奖状：实验室指导教师可访问
            if not is_related and award.laboratory_id is None:
                laboratory_manager = app_context.get_laboratory_manager()
                if laboratory_manager and laboratory_manager.is_teacher_in_lab(teacher.id):
                    is_related = True
            # 4. 已关联实验室：若教师是该实验室指导教师，可访问
            if not is_related and award.laboratory_id:
                laboratory_manager = app_context.get_laboratory_manager()
                if laboratory_manager:
                    lab = laboratory_manager.get_laboratory_by_id(award.laboratory_id)
                    if lab and teacher in lab.instructors:
                        is_related = True

            if not is_related:
                return "您没有权限访问该奖状图片", 403
        # 管理员可以直接访问，不需要额外检查

        # 获取图片路径（使用AwardManager的images_dir），确保使用绝对路径
        images_dir = award_manager.images_dir
        if not images_dir:
            images_dir = current_app.config.get('AWARD_IMAGES_DIR')
            if isinstance(images_dir, str):
                images_dir = Path(images_dir)
            if images_dir:
                images_dir = Path(images_dir).resolve()

        # 设置图片目录到 Award 对象（get_image_path 方法需要 _images_dir 属性）
        if images_dir:
            award.set_images_dir(images_dir)
            image_path = award.get_image_path()
        else:
            image_path = None
            logger.warning(
                "奖状 %s 的图片目录未配置，请检查 config/settings.json 的 files 配置及 unified_file_manager 初始化",
                award_id
            )
            return "图片目录未配置", 404

        if not image_path:
            logger.warning(
                "奖状 %s (image_hash: %s) 在 images_dir=%s 下未找到 .jpg/.jpeg/.png/.gif 文件",
                award_id, award.image_hash, images_dir
            )
            return "图片不存在", 404

        if not image_path.exists():
            logger.warning(
                "奖状 %s 的图片文件不存在: %s（images_dir=%s）",
                award_id, image_path, images_dir
            )
            return "图片不存在", 404

        ext = image_path.suffix.lower()
        # 检测实际为 PDF 的文件（含误存为 .jpg 等扩展名的历史数据）
        is_pdf_content = False
        if ext == '.pdf':
            is_pdf_content = True
        else:
            try:
                with open(image_path, 'rb') as f:
                    header = f.read(5)
                is_pdf_content = header == b'%PDF-'
            except Exception:
                pass

        # PDF 时返回第一页预览图，供 <img> 显示
        if is_pdf_content:
            preview_dir = image_path.parent / 'preview'
            preview_path = preview_dir / f"{image_path.stem}.png"
            if preview_path.exists():
                return send_file(str(preview_path), mimetype='image/png')
            try:
                from backend.utils.pdf_to_image import get_or_create_pdf_preview
                created = get_or_create_pdf_preview(str(image_path), preview_dir)
                if created and Path(created).exists():
                    return send_file(created, mimetype='image/png')
            except Exception as e:
                logger.warning("奖状 PDF 预览图生成失败 award_id=%s: %s", award_id, e)
            return send_file(str(image_path), mimetype='application/pdf')

        # 根据文件扩展名设置正确的MIME类型
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.pdf': 'application/pdf'
        }
        mimetype = mime_types.get(ext, 'image/jpeg')
        return send_file(str(image_path), mimetype=mimetype)
    except Exception as e:
        import traceback
        error_msg = str(e)
        if current_app.config.get('DEBUG'):
            error_msg += f"\n{traceback.format_exc()}"
        return f"加载图片失败: {error_msg}", 500


@bp.route('/awards/refresh-associations', methods=['POST'])
@require_role('admin')
def awards_refresh_associations():
    """刷新所有奖状的人名关联关系"""
    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 执行刷新
        result = award_manager.refresh_all_associations(
            student_manager=student_manager,
            teacher_manager=teacher_manager
        )
        
        return jsonify({
            'success': True,
            'message': f'刷新完成！共处理 {result["total"]} 条奖状，'
                      f'成功匹配 {result["matched"]} 个人名，'
                      f'重名 {result["ambiguous"]} 个，'
                      f'未找到 {result["not_found"]} 个',
            'result': result
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        if current_app.config.get('DEBUG'):
            error_msg += f"\n{traceback.format_exc()}"
        return jsonify({'success': False, 'message': f'刷新失败: {error_msg}'}), 500

@bp.route('/awards/refresh-supervisors', methods=['POST'])
@require_role('admin')
def awards_refresh_supervisors():
    """从教师奖状补充学生奖状的指导教师信息"""
    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        
        # 执行刷新
        result = award_manager.refresh_association_for_student_award(
            comp_mgr=competition_manager,
            stu_mgr=student_manager,
            tea_mgr=teacher_manager
        )
        
        return jsonify({
            'success': True,
            'message': f'刷新完成！共找到 {result["total_student_awards"]} 个学生奖状，'
                      f'{result["total_teacher_awards"]} 个教师奖状，'
                      f'成功补充 {result["updated"]} 个学生奖状的指导教师信息',
            'result': result
        })
    except Exception as e:
        import traceback
        error_msg = str(e)
        if current_app.config.get('DEBUG'):
            error_msg += f"\n{traceback.format_exc()}"
        return jsonify({'success': False, 'message': f'刷新失败: {error_msg}'}), 500

@bp.route('/awards/<int:award_id>/edit', methods=['GET', 'POST'])
@require_role('admin', 'teacher')
def award_edit(award_id):
    """奖状编辑页面"""
    try:
        from flask import session
        from app.auth import is_logged_in
        
        if not is_logged_in():
            flash('请先登录', 'warning')
            return redirect(url_for('auth.login', next=request.url))
        
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        
        # 查询奖状
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        awards = award_manager.query_awards(
            id=award_id, 
            with_associations=True,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=competition_manager
        )
        if not awards:
            flash('奖状不存在', 'error')
            # 根据用户类型重定向
            if session.get('role') == 'admin':
                return redirect(url_for('admin_awards.awards_list'))
            else:
                return redirect(url_for('teacher.dashboard'))

        award = awards[0]

        # 如果是教师，检查是否有权限访问该奖状
        user_role = session.get('role')
        if user_role == 'teacher':
            user_id = session.get('user_id')
            teacher = teacher_manager.get_teacher_by_teacher_id(user_id)
            if not teacher:
                flash('教师信息不存在', 'error')
                return redirect(url_for('teacher.dashboard'))
            
            # 检查教师是否关联了该奖状（作为获奖者或指导教师）
            is_related = False
            # 检查是否作为获奖者
            for teacher_winner in award.teacher_winners:
                if teacher_winner.id == teacher.id:
                    is_related = True
                    break
            # 检查是否作为指导教师
            if not is_related:
                for supervisor in award.supervisors:
                    if supervisor.id == teacher.id:
                        is_related = True
                        break

            # 未认领奖状：实验室指导教师可编辑（用于成果认领）
            if not is_related and award.laboratory_id is None:
                laboratory_manager = app_context.get_laboratory_manager()
                if laboratory_manager and laboratory_manager.is_teacher_in_lab(teacher.id):
                    is_related = True

            # 已关联实验室：若教师是该实验室指导教师，可编辑
            if not is_related and award.laboratory_id:
                laboratory_manager = app_context.get_laboratory_manager()
                if laboratory_manager:
                    lab = laboratory_manager.get_laboratory_by_id(award.laboratory_id)
                    if lab and teacher in lab.instructors:
                        is_related = True
            
            if not is_related:
                flash('您没有权限访问该奖状', 'error')
                return redirect(url_for('teacher.dashboard'))
        
        # 确保 Award 对象设置了图片目录
        images_dir = award_manager.images_dir
        if images_dir:
            award.set_images_dir(images_dir)

        # 编辑页加载时，对异常奖状重新验证，若已通过则清除异常标记
        if request.method == 'GET' and award.is_abnormal:
            try:
                from backend.extract.validation import AwardValidator
                validator = AwardValidator()
                validation_result = validator.validate_for_db_object(award)
                if validation_result.is_valid:
                    award_manager.update_validation_status(
                        award.id, is_abnormal=False, validation_result=None
                    )
            except Exception as e:
                logger.warning(f"奖状 {award.id} 重新检测失败: {e}")
        
        # 获取所有竞赛（用于下拉框）
        all_competitions = []
        if hasattr(competition_manager, 'competitions'):
            all_competitions = competition_manager.competitions
        elif hasattr(competition_manager, '_competitions'):
            all_competitions = competition_manager._competitions
        
        # 获取所有教师和学生（用于下拉框）
        all_teachers = []
        if hasattr(teacher_manager, 'teachers'):
            all_teachers = teacher_manager.teachers
        elif hasattr(teacher_manager, '_teachers'):
            all_teachers = teacher_manager._teachers
        
        all_students = []
        if hasattr(student_manager, 'students'):
            all_students = student_manager.students
        elif hasattr(student_manager, '_students'):
            all_students = student_manager._students
        
        # 获取所有实验室（用于下拉框）
        laboratory_manager = app_context.get_laboratory_manager()
        all_laboratories = []
        if hasattr(laboratory_manager, 'laboratories'):
            all_laboratories = laboratory_manager.laboratories
        elif hasattr(laboratory_manager, 'get_all_laboratories'):
            all_laboratories = laboratory_manager.get_all_laboratories()
        
        # 确定默认选中的实验室
        default_laboratory_id = None
        logger.info(f"[award_edit GET/POST] award_id={award.id}, award.laboratory_id={award.laboratory_id}, type={type(award.laboratory_id)}")
        if award.laboratory_id is not None:
            # 如果奖状已有关联的实验室，使用它
            default_laboratory_id = award.laboratory_id
        elif award.supervisors and len(award.supervisors) > 0:
            # 如果奖状没有关联实验室，通过第一指导教师查找
            first_supervisor = award.supervisors[0]
            if first_supervisor and first_supervisor.id:
                try:
                    lab = laboratory_manager.get_laboratory_by_teacher_id(first_supervisor.id)
                    if lab:
                        default_laboratory_id = lab.id
                        logger.debug(f"奖状 {award.id} 未关联实验室，通过第一指导教师 {first_supervisor.name} (ID: {first_supervisor.id}) 找到实验室: {lab.name} (ID: {lab.id})")
                    else:
                        logger.debug(f"奖状 {award.id} 未关联实验室，第一指导教师 {first_supervisor.name} (ID: {first_supervisor.id}) 未关联任何实验室，默认选择'无'")
                except Exception as e:
                    logger.warning(f"查找指导教师所属实验室失败: {e}", exc_info=True)
            else:
                logger.debug(f"奖状 {award.id} 未关联实验室，第一指导教师不存在或没有ID，默认选择'无'")
        else:
            logger.debug(f"奖状 {award.id} 未关联实验室且没有指导教师，默认选择'无'")
        
        if request.method == 'POST':
            # 处理表单提交
            try:
                # 获取表单数据
                competition_id = request.form.get('competition_id')
                if competition_id:
                    competition_id = int(competition_id)
                else:
                    competition_id = None
                
                year = request.form.get('year')
                if year:
                    year = int(year)
                else:
                    year = None
                
                # 直接更新奖状对象的字段
                award.competition_id = competition_id
                award.award_level = request.form.get('award_level') or None
                award.competition_level = request.form.get('competition_level') or None
                award.year = year
                award.track = request.form.get('track') or None
                award.certificate_id = request.form.get('certificate_id') or None
                award.project_title = request.form.get('project_title') or None
                award.date = request.form.get('date') or None
                award.province = request.form.get('province') or None
                award.issuer = request.form.get('issuer') or None
                
                # 处理实验室关联
                laboratory_id = request.form.get('laboratory_id')

                logger.info(f"[award_edit] POST数据 laboratory_id原始值: {repr(laboratory_id)}, 类型: {type(laboratory_id)}")

                if laboratory_id and laboratory_id != '':
                    try:
                        award.laboratory_id = int(laboratory_id)
                    except (ValueError, TypeError):
                        award.laboratory_id = None
                else:
                    award.laboratory_id = None

                logger.info(f"[award_edit] 设置 laboratory_id = {award.laboratory_id}")

                # 处理证书类型
                certificate_type = request.form.get('certificate_type', 'student')
                if certificate_type == 'teacher':
                    award.granted_role = '教师'
                else:
                    award.granted_role = '学生'
                
                # 处理关联信息更新
                # 获取表单中的关联信息
                # 优先使用从卡片 DOM 读取的导师顺序（supervisor_ids_from_dom）
                supervisor_ids = request.form.getlist('supervisor_ids_from_dom[]')
                if not supervisor_ids:
                    # 如果没有，则回退到 Select2 的值（supervisor_ids）
                    supervisor_ids = request.form.getlist('supervisor_ids[]')

                logger.info(f"[award_edit POST] award_id={award.id}, 接收到的 supervisor_ids: {supervisor_ids}")

                teacher_winner_ids = request.form.getlist('teacher_winner_ids[]')
                student_winner_ids = request.form.getlist('student_winner_ids[]')
                related_student_ids = request.form.getlist('related_student_ids[]')

                # 转换为对象列表
                award.supervisors = []
                supervisor_names_in_order = []
                for teacher_id in supervisor_ids:
                    if teacher_id:
                        try:
                            teacher = teacher_manager.get_teacher_by_id(int(teacher_id))
                            if teacher:
                                award.supervisors.append(teacher)
                                supervisor_names_in_order.append(teacher.name)
                        except (ValueError, TypeError):
                            pass

                logger.info(f"[award_edit POST] 转换后导师对象顺序: {[f'{s.id}:{s.name}' for s in award.supervisors]}")

                # 重要：更新 supervisor_name 字段以匹配新的导师顺序
                # 因为页面加载时是按照 supervisor_name 的顺序来匹配导师的
                if award.supervisors:
                    award.supervisor_name = ', '.join([s.name for s in award.supervisors])
                else:
                    award.supervisor_name = None

                logger.info(f"[award_edit POST] 更新后的 supervisor_name: {award.supervisor_name}")
                
                award.teacher_winners = []
                for teacher_id in teacher_winner_ids:
                    if teacher_id:
                        try:
                            teacher = teacher_manager.get_teacher_by_id(int(teacher_id))
                            if teacher:
                                award.teacher_winners.append(teacher)
                        except (ValueError, TypeError):
                            pass
                
                # 处理学生获奖者（从新的输入方式）
                import re
                award.student_winners = []
                student_winner_names = request.form.get('student_winner_names', '').strip()
                
                if student_winner_names:
                    # 解析姓名列表（支持逗号分隔）
                    names = [n.strip() for n in student_winner_names.split(',') if n.strip()]
                    for name in names:
                        # 尝试在数据库中查找
                        matched_students = student_manager.find_students_by_name(name)
                        exact_matches = [s for s in matched_students if s.name.strip() == name.strip()]
                        if exact_matches:
                            # 如果找到，添加到student_winners（避免重复）
                            for match in exact_matches:
                                if match not in award.student_winners:
                                    award.student_winners.append(match)
                
                # 更新winner_name字段（包含所有学生姓名，包括不在数据库中的）
                if student_winner_names:
                    award.winner_name = student_winner_names
                elif award.student_winners:
                    award.winner_name = ', '.join([w.name for w in award.student_winners])
                
                # 处理关联学生（仅教师证书）
                award.related_students = []
                if certificate_type == 'teacher':
                    for student_id in related_student_ids:
                        if student_id:
                            try:
                                student = student_manager.get_student_by_id(int(student_id))
                                if student:
                                    award.related_students.append(student)
                            except (ValueError, TypeError):
                                pass
                else:
                    # 学生证书时清空关联学生
                    award.related_students = []
                
                # 刷新关联（如果需要）
                try:
                    award.refresh_associations(
                        comp_manager=competition_manager,
                        student_manager=app_context.get_student_manager(),
                        teacher_manager=app_context.get_teacher_manager()
                    )
                except Exception as e:
                    # 如果refresh_associations失败，继续保存其他字段
                    logger.warning(f"刷新关联失败: {e}")

                # 获取保存前的异常状态（用于后续判断是否显示"异常已修复"）
                was_abnormal_before = award.is_abnormal if hasattr(award, 'is_abnormal') else False

                # 使用 AwardManager 的 _save_award 方法保存（包含主表、关联表、内存缓存更新）
                # 注意：_save_award 会自动处理所有字段和关联，不需要手动 SQL
                award_manager._save_award(award)
                logger.info(f"[award_edit POST] 已保存奖状 award_id={award.id}, laboratory_id={award.laboratory_id}")
                logger.info(f"[award_edit POST] 保存后 award.supervisor_name: {award.supervisor_name}")
                logger.info(f"[award_edit POST] 保存后 award.supervisors: {[f'{s.id}:{s.name}' for s in award.supervisors]}")

                # 验证：从内存缓存重新读取确认
                cached_award = award_manager.get_award_by_id(award.id)
                if cached_award:
                    logger.info(f"[award_edit POST] 内存缓存中的 laboratory_id: {cached_award.laboratory_id}")
                    logger.info(f"[award_edit POST] 内存缓存中的 supervisor_name: {cached_award.supervisor_name}")
                    logger.info(f"[award_edit POST] 内存缓存中的 supervisors: {[f'{s.id}:{s.name}' for s in cached_award.supervisors]}")

                # 实时检测奖状（添加错误处理，确保检测失败不影响保存）
                try:
                    from backend.extract.validation import AwardValidator
                    validator = AwardValidator()
                    validation_result = validator.validate_for_db_object(award)

                    # 更新 is_abnormal 和 validation_result 字段
                    # 使用 AwardManager 的 update_validation_status 方法
                    award_manager.update_validation_status(
                        award.id,
                        is_abnormal=not validation_result.is_valid,
                        validation_result=validation_result.to_json() if not validation_result.is_valid else None
                    )
                    logger.info(f"[award_edit POST] 已更新奖状验证状态 award_id={award.id}, is_valid={validation_result.is_valid}")
                except Exception as validation_error:
                    # 检测失败不影响保存，只记录日志
                    logger.warning(f"奖状 {award.id} 检测失败: {validation_error}")

                flash('奖状更新成功', 'success')
                
                # 如果有return_url参数，返回到原页面，否则返回编辑页面
                return_url = request.args.get('return_url', '')
                if return_url:
                    return redirect(return_url)
                else:
                    return redirect(url_for('admin_awards.award_edit', award_id=award_id))
            except Exception as e:
                import traceback
                flash(f'更新失败: {str(e)}', 'error')
                # 开发环境显示详细错误
                if current_app.config.get('DEBUG'):
                    flash(f'错误详情: {traceback.format_exc()}', 'error')
        
        # 获取竞赛信息
        competition = None
        if award.competition_id:
            competition = competition_manager.get_competition_by_id(award.competition_id)
        
        # 处理获奖者和指导教师的匹配状态，用于显示标记
        # 归一化：按纯姓名去重，避免 "林俊杰(23计科),林俊杰(23软工)" 显示两个标签
        def _base_name_aw(seg: str) -> str:
            s = seg.strip()
            if "(" in s:
                return s.split("(")[0].strip()
            return s
        winner_status_list = []
        if award.winner_name:
            raw_winner_names = award._parse_names(award.winner_name)
            seen_base_aw = {}
            for n in raw_winner_names:
                b = _base_name_aw(n)
                if b not in seen_base_aw:
                    seen_base_aw[b] = b
            winner_names = list(seen_base_aw.values())
            is_teacher_role = award.granted_role and "教师" in award.granted_role

            for name in winner_names:
                name = name.strip()
                if not name:
                    continue
                
                status = {'name': name, 'matched': False, 'ambiguous': False, 'not_found': False, 'obj': None}
                
                if is_teacher_role:
                    # 教师证书：在teacher_winners中查找
                    found_teachers = teacher_manager.find_teachers_by_name(name)
                    matched_teacher = None
                    # 先检查是否已经在teacher_winners中
                    for teacher in award.teacher_winners:
                        if teacher.name == name:
                            matched_teacher = teacher
                            break
                    
                    if matched_teacher:
                        status['matched'] = True
                        status['obj'] = matched_teacher
                    elif len(found_teachers) > 1:
                        # 重名：找到多个匹配
                        status['ambiguous'] = True
                    elif len(found_teachers) == 1:
                        # 找到唯一匹配，但可能因为其他原因没有添加到teacher_winners
                        # 这种情况也标记为matched，使用找到的教师对象
                        status['matched'] = True
                        status['obj'] = found_teachers[0]
                    else:
                        # 未找到
                        status['not_found'] = True
                else:
                    # 学生证书：在student_winners中查找
                    found_students = student_manager.find_students_by_name(name)
                    matched_student = None
                    # 先检查是否已经在student_winners中
                    for student in award.student_winners:
                        if student.name == name:
                            matched_student = student
                            break
                    
                    if matched_student:
                        status['matched'] = True
                        status['obj'] = matched_student
                    elif len(found_students) > 1:
                        # 重名：找到多个匹配
                        status['ambiguous'] = True
                    elif len(found_students) == 1:
                        # 找到唯一匹配，但可能因为其他原因没有添加到student_winners
                        # 这种情况也标记为matched，使用找到的学生对象
                        status['matched'] = True
                        status['obj'] = found_students[0]
                    else:
                        # 未找到
                        status['not_found'] = True
                
                winner_status_list.append(status)

        # 教师证书：已在 winner_status_list 中展示的教师 id，模板用其避免「教师获奖者」与 award.teacher_winners 重复显示
        matched_teacher_ids = set()
        if award.granted_role and "教师" in award.granted_role:
            for status in winner_status_list:
                if status.get("obj") and hasattr(status["obj"], "id"):
                    matched_teacher_ids.add(status["obj"].id)

        # 处理指导教师的匹配状态
        supervisor_status_list = []
        if award.supervisor_name:
            supervisor_names = award._parse_names(award.supervisor_name)
            for name in supervisor_names:
                name = name.strip()
                if not name:
                    continue
                status = {'name': name, 'matched': False, 'ambiguous': False, 'not_found': False, 'obj': None}
                found_teachers = teacher_manager.find_teachers_by_name(name)
                matched_supervisor = None
                for sup in award.supervisors:
                    if sup.name == name:
                        matched_supervisor = sup
                        break
                if matched_supervisor:
                    status['matched'] = True
                    status['obj'] = matched_supervisor
                elif len(found_teachers) > 1:
                    status['ambiguous'] = True
                elif len(found_teachers) == 1:
                    status['matched'] = True
                    status['obj'] = found_teachers[0]
                else:
                    status['not_found'] = True
                supervisor_status_list.append(status)
        elif award.supervisors:
            # 仅有 award_supervisors 关联、无 supervisor_name 时，用关联的教师列表生成展示项
            for sup in award.supervisors:
                if sup and sup.name:
                    supervisor_status_list.append({
                        'name': sup.name,
                        'matched': True,
                        'ambiguous': False,
                        'not_found': False,
                        'obj': sup,
                    })

        # 关联学生（教师证书）的匹配状态
        related_student_status_list = []
        if award.related_student_name:
            related_names = award._parse_names(award.related_student_name)
            for name in related_names:
                name = name.strip()
                if not name:
                    continue
                status = {'name': name, 'matched': False, 'ambiguous': False, 'not_found': False, 'obj': None}
                matched_related = None
                for r in (award.related_students or []):
                    if r and r.name == name:
                        matched_related = r
                        break
                if matched_related:
                    status['matched'] = True
                    status['obj'] = matched_related
                else:
                    found = student_manager.find_students_by_name(name)
                    exact = [s for s in found if s.name.strip() == name.strip()]
                    if len(exact) == 1:
                        status['matched'] = True
                        status['obj'] = exact[0]
                    elif len(exact) > 1:
                        status['ambiguous'] = True
                    else:
                        status['not_found'] = True
                related_student_status_list.append(status)
        elif award.related_students:
            for r in award.related_students:
                if r and r.name:
                    related_student_status_list.append({
                        'name': r.name, 'matched': True, 'ambiguous': False, 'not_found': False, 'obj': r,
                    })

        # 获取实验室和竞赛列表供下拉框使用
        # 注意：使用前面已经获取的 all_laboratories，而不是重新获取
        # 确保 default_laboratory_id 是基于相同的实验室列表计算的
        # laboratory_manager = app_context.get_laboratory_manager()
        # laboratories = laboratory_manager.get_all() if hasattr(laboratory_manager, 'get_all') else []
        competitions = competition_manager.competitions if hasattr(competition_manager, 'competitions') else []
        return_url = request.args.get('return_url', '')
        if not return_url:
            # award_edit 由 admin/teacher 共用，返回列表按角色回到各自的列表页
            role = (session.get('role') or '').strip().lower()
            return_url = url_for('admin_awards.awards_list') if role == 'admin' else url_for('teacher.achievements')

        return render_template('admin/awards/edit.html',
                               award=award,
                               competitions=competitions,
                               all_teachers=all_teachers,
                               all_students=all_students,
                               all_laboratories=all_laboratories,
                               default_laboratory_id=default_laboratory_id,  # 传递默认实验室ID
                               winner_status_list=winner_status_list,
                               matched_teacher_ids=matched_teacher_ids,
                               supervisor_status_list=supervisor_status_list,
                               related_student_status_list=related_student_status_list,
                               return_url=return_url)
    except Exception as e:
        import traceback
        logger.exception("奖状编辑页加载失败")
        flash(f'加载失败: {str(e)}', 'error')
        return redirect(url_for('admin_awards.awards_list'))

@bp.route('/api/achievements/awards')
@require_admin_or_lab_view_api
def api_achievements_awards():
    """API: 获取奖状管理内容。仅当 lab_view=1（实验室成果页）时隐藏学生实验室筛选；成果页按实验室筛选时保留该组件。"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        competition_id = request.args.get('competition_id', type=int)
        track = request.args.get('track', '').strip()
        year = request.args.get('year', type=int)
        competition_level = request.args.get('competition_level', '').strip()
        award_level = request.args.get('award_level', '').strip()
        supervisor_name = request.args.get('supervisor_name', '').strip()
        winner_name = request.args.get('winner_name', '').strip()
        laboratory_id_raw = request.args.get('laboratory_id')
        lab_view = request.args.get('lab_view') in ('1', 1)
        is_abnormal_raw = request.args.get('is_abnormal', '').strip()
        certificate_type = request.args.get('certificate_type', 'student').strip()  # 默认为学生
        tab = 'management'

        # laboratory_id：支持 'none'（无实验室）或数字；供查询与模板回显
        laboratory_id = None
        laboratory_id_int = None
        filter_no_laboratory = False
        if laboratory_id_raw is not None and str(laboratory_id_raw).strip() != '':
            if str(laboratory_id_raw).strip().lower() == 'none':
                filter_no_laboratory = True
                laboratory_id = 'none'
            else:
                try:
                    laboratory_id_int = int(laboratory_id_raw)
                    laboratory_id = laboratory_id_int
                except (ValueError, TypeError):
                    pass

        app_context = get_app_context_instance()
        laboratory_manager = app_context.get_laboratory_manager()
        teacher_manager = app_context.get_teacher_manager()
        from app.auth import get_current_user, can_edit_laboratory
        hide_laboratory_filter = bool(lab_view)
        is_readonly = False
        if lab_view and laboratory_id_int is not None:
            user_info = get_current_user()
            can_edit = can_edit_laboratory(user_info, laboratory_id_int, laboratory_manager, teacher_manager) if user_info else False
            is_readonly = not can_edit
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()

        # 首次进入奖状管理时，对异常奖状重新验证并清除已修复的异常标记
        if page == 1:
            award_manager.refresh_abnormal_awards_status(
                student_manager=student_manager,
                teacher_manager=teacher_manager,
                comp_mgr=competition_manager
            )

        query_params = {
            'with_associations': True,
            'student_manager': student_manager,
            'teacher_manager': teacher_manager,
            'comp_mgr': competition_manager,
            'limit': per_page,
            'offset': (page - 1) * per_page
        }

        if competition_id:
            query_params['competition_id'] = competition_id
        if track:
            query_params['track'] = track
        if year:
            query_params['year'] = year
        if competition_level:
            query_params['competition_level'] = competition_level
        if award_level:
            query_params['award_level'] = award_level
        if supervisor_name:
            query_params['supervisor_name'] = supervisor_name
        if winner_name:
            query_params['winner_name'] = winner_name
        if filter_no_laboratory:
            query_params['laboratory_id'] = None
            query_params['filter_no_laboratory'] = True
        elif laboratory_id_int is not None:
            query_params['laboratory_id'] = laboratory_id_int
        if is_abnormal_raw == '1':
            query_params['is_abnormal'] = True
        elif is_abnormal_raw == '0':
            query_params['is_abnormal'] = False
        
        # 根据证书类型筛选
        if certificate_type == 'student':
            query_params['granted_role'] = '学生'
            query_params['exclude_teacher_certificates'] = True
        elif certificate_type == 'teacher':
            query_params['granted_role'] = '教师'
        # certificate_type == 'all' 时不添加任何筛选条件

        awards = award_manager.query_awards(**query_params)

        count_params = {k: v for k, v in query_params.items() if k not in ['limit', 'offset', 'with_associations']}
        count_params['with_associations'] = False
        total_awards = award_manager.query_awards(**count_params)
        total_count = len(total_awards) if total_awards else 0

        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1

        # 获取竞赛列表
        # 从所有有奖状的竞赛中提取 unique 列表
        # 查询所有奖状（应用除 competition_id 外的所有筛选条件）
        filter_params = {
            'with_associations': False,
            'limit': None,
            'offset': None
        }

        # 复制其他筛选条件（不包括 competition_id、track）
        if year:
            filter_params['year'] = year
        if competition_level:
            filter_params['competition_level'] = competition_level
        if award_level:
            filter_params['award_level'] = award_level
        if supervisor_name:
            filter_params['supervisor_name'] = supervisor_name
        if winner_name:
            filter_params['winner_name'] = winner_name
        if filter_no_laboratory:
            filter_params['laboratory_id'] = None
            filter_params['filter_no_laboratory'] = True
        elif laboratory_id_int is not None:
            filter_params['laboratory_id'] = laboratory_id_int
        if is_abnormal_raw == '1':
            filter_params['is_abnormal'] = True
        elif is_abnormal_raw == '0':
            filter_params['is_abnormal'] = False
        
        # 根据证书类型筛选
        if certificate_type == 'student':
            filter_params['granted_role'] = '学生'
            filter_params['exclude_teacher_certificates'] = True
        elif certificate_type == 'teacher':
            filter_params['granted_role'] = '教师'
        # certificate_type == 'all' 时不添加任何筛选条件

        # 查询所有满足条件的奖状（不分页）
        all_awards_for_filter = award_manager.query_awards(**filter_params)

        # 提取 unique 的 competition_id
        used_competition_ids = set()
        if all_awards_for_filter:
            for award in all_awards_for_filter:
                if award.competition_id:
                    used_competition_ids.add(award.competition_id)

        # 获取竞赛对象（只获取实际使用的竞赛）；缺失时从 DB 加载，避免新建竞赛显示「未知竞赛」
        all_competitions_map = {}
        if hasattr(competition_manager, 'competitions'):
            for comp in competition_manager.competitions:
                all_competitions_map[comp.id] = comp

        for comp_id in used_competition_ids:
            if comp_id not in all_competitions_map and hasattr(competition_manager, 'get_competition_by_id_from_db'):
                comp = competition_manager.get_competition_by_id_from_db(comp_id)
                if comp:
                    all_competitions_map[comp_id] = comp

        all_competitions = []
        for comp_id in used_competition_ids:
            if comp_id in all_competitions_map:
                all_competitions.append(all_competitions_map[comp_id])

        # 按名称排序
        if all_competitions:
            all_competitions = sorted(all_competitions, key=lambda x: x.name)

        # 从当前结果集中提取赛道列表：若已选竞赛则只显示该竞赛下的赛道，否则显示全部
        awards_for_tracks = (all_awards_for_filter or [])
        if competition_id:
            awards_for_tracks = [a for a in awards_for_tracks if a.competition_id == competition_id]
        track_options = sorted(
            {a.track.strip() for a in awards_for_tracks
             if getattr(a, 'track', None) and str(a.track).strip()}
        )

        from app.utils import get_competition_levels_for_ui
        competition_levels = get_competition_levels_for_ui()

        # 获取异常奖状总数
        abnormal_count = 0
        try:
            abnormal_awards = award_manager.query_awards(is_abnormal=True, with_associations=False)
            abnormal_count = len(abnormal_awards) if abnormal_awards else 0
        except Exception:
            pass

        from app.utils import get_competition_level_badge_class

        # 获取实验室列表（用于构建 laboratory_map）
        laboratory_manager = app_context.get_laboratory_manager()
        all_laboratories = []
        if hasattr(laboratory_manager, 'get_all_laboratories'):
            all_laboratories = laboratory_manager.get_all_laboratories()
        elif hasattr(laboratory_manager, 'laboratories'):
            all_laboratories = laboratory_manager.laboratories

        # 构建 laboratory_map (ID -> name)
        laboratory_map = {lab.id: lab.name for lab in all_laboratories}

        # 构建 award_laboratory_map (award_id -> lab_name) - 用于显示
        award_laboratory_map = {}
        for award in awards:
            if award.laboratory_id and award.laboratory_id in laboratory_map:
                award_laboratory_map[award.id] = laboratory_map[award.laboratory_id]

        laboratory_name = None
        if isinstance(laboratory_id, int) and all_laboratories:
            laboratory_name = next((lab.name for lab in all_laboratories if lab.id == laboratory_id), None)

        is_abnormal_filter = is_abnormal_raw

        html = render_template('admin/awards/tabs/management.html',
                             awards=awards,
                             competitions=all_competitions,
                             competition_levels=competition_levels,
                             get_competition_level_badge_class=get_competition_level_badge_class,
                             page=page,
                             per_page=per_page,
                             total_count=total_count,
                             total_pages=total_pages,
                             competition_id=competition_id,
                             track=track,
                             track_options=track_options,
                             year=year,
                             competition_level=competition_level,
                             award_level=award_level,
                             supervisor_name=supervisor_name,
                             winner_name=winner_name,
                             laboratory_id=laboratory_id,
                             laboratory_name=laboratory_name,
                             certificate_type=certificate_type,
                             abnormal_count=abnormal_count,
                             is_abnormal_filter=is_abnormal_filter,
                             laboratories=all_laboratories,
                             laboratory_map=laboratory_map,
                             award_laboratory_map=award_laboratory_map,
                             is_readonly=is_readonly,
                             hide_laboratory_filter=hide_laboratory_filter)

        return jsonify({'success': True, 'html': html, 'total_count': total_count})
    except Exception as e:
        logger.error(f"Error loading awards tab: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/awards/auto-link-laboratory', methods=['POST'])
@require_role_api('admin')
def api_awards_auto_link_laboratory():
    """API: 自动关联实验室 - 将有指导教师但未关联实验室的奖状关联到第一指导教师所属实验室"""
    try:
        app_context = get_app_context_instance()
        service = LaboratoryAssociationService(
            award_manager=app_context.get_award_manager(),
            innovation_manager=app_context.get_innovation_project_manager(),
            laboratory_manager=app_context.get_laboratory_manager(),
            teacher_manager=app_context.get_teacher_manager(),
        )
        stats = service.auto_link_laboratory_for_awards()
        return jsonify({
            'success': True,
            'total': stats['total'],
            'success_count': stats['success_count'],
            'skipped_count': stats['skipped_count'],
            'failed_count': stats['failed_count'],
        })
    except Exception as e:
        logger.error(f"自动关联实验室失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/api/awards/link-teacher-student', methods=['POST'])
@require_role_api('admin')
def api_awards_link_teacher_student():
    """API: 关联师生奖状 - 从教师奖状中补充学生奖状的导师信息"""
    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        teacher_manager = app_context.get_teacher_manager()
        student_manager = app_context.get_student_manager()
        competition_manager = app_context.get_competition_manager()

        # 获取请求参数
        data = request.get_json() or {}
        dry_run = data.get('dry_run', True)  # 默认为试运行模式

        # 1. 获取所有教师奖状（包含关联学生信息）
        teacher_awards = award_manager.query_awards(
            granted_role='教师',
            with_associations=True,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=competition_manager
        )

        # 2. 筛选出有关联学生信息的教师奖状
        teacher_awards_with_related = []
        for award in teacher_awards:
            if award.related_student_name and award.related_students and award.teacher_winners:
                teacher_awards_with_related.append(award)

        if not teacher_awards_with_related:
            return jsonify({
                'success': True,
                'message': '没有找到包含关联学生信息的教师奖状',
                'matched': 0,
                'updated': 0
            })

        # 3. 获取所有缺少导师的学生奖状
        student_awards = award_manager.query_awards(
            granted_role='学生',
            with_associations=True,
            student_manager=student_manager,
            teacher_manager=teacher_manager,
            comp_mgr=competition_manager
        )

        # 筛选出缺少导师的学生奖状
        student_awards_need_supervisor = []
        for award in student_awards:
            if not award.supervisor_name or not award.supervisors:
                student_awards_need_supervisor.append(award)

        if not student_awards_need_supervisor:
            return jsonify({
                'success': True,
                'message': '没有找到缺少导师的学生奖状',
                'matched': 0,
                'updated': 0
            })

        # 4. 匹配逻辑：找出所有可能的匹配对
        matches = []

        for teacher_award in teacher_awards_with_related:
            if not teacher_award.related_students:
                continue

            # 获取教师奖状的关联学生
            related_student_ids = set(s.id for s in teacher_award.related_students if s.id)

            # 获取教师奖状的教师获奖者（作为学生奖状的指导教师）
            if not teacher_award.teacher_winners:
                continue

            supervisor_ids = [t.id for t in teacher_award.teacher_winners if t.id]
            if not supervisor_ids:
                continue

            for student_award in student_awards_need_supervisor:
                # 必须同一竞赛、同一年份、同一获奖等级（避免跨竞赛误匹配及重复计数）
                if teacher_award.competition_id != student_award.competition_id:
                    continue
                if (teacher_award.year or 0) != (student_award.year or 0):
                    continue
                if (teacher_award.award_level or '').strip() != (student_award.award_level or '').strip():
                    continue
                if (teacher_award.track or '').strip() != (student_award.track or '').strip():
                    continue

                # 检查学生奖状的获奖者是否在教师奖状的关联学生中
                student_winner_ids = set()
                if student_award.student_winners:
                    student_winner_ids = set(s.id for s in student_award.student_winners if s.id)

                # 如果有交集，则匹配成功
                intersection = related_student_ids & student_winner_ids
                if intersection:
                    matches.append({
                        'teacher_award': teacher_award,
                        'student_award': student_award,
                        'teacher_award_id': teacher_award.id,
                        'student_award_id': student_award.id,
                        'supervisor_ids': supervisor_ids,
                        'matched_students': list(intersection)
                    })

        if not matches:
            return jsonify({
                'success': True,
                'message': '没有找到匹配的师生奖状对',
                'matched': 0,
                'updated': 0,
                'details': []
            })

        # 5. 更新学生奖状（如果不是试运行模式）
        updated_count = 0
        details = []

        for match in matches:
            student_award = match['student_award']
            teacher_award = match['teacher_award']
            supervisor_ids = match['supervisor_ids']
            matched_students = match['matched_students']

            # 获取教师奖状的教师获奖者名称（将作为学生奖状的指导教师）
            supervisor_names = ', '.join([t.name for t in teacher_award.teacher_winners if t.id in supervisor_ids])

            # 获取匹配的学生名称
            matched_student_names = []
            for s in student_award.student_winners:
                if s.id in matched_students:
                    matched_student_names.append(s.name)
            matched_student_names_str = ', '.join(matched_student_names)

            detail = {
                'student_award_id': student_award.id,
                'teacher_award_id': teacher_award.id,
                'student_names': matched_student_names_str,
                'supervisor_names': supervisor_names,
                'success': False
            }

            if not dry_run:
                try:
                    # 更新学生奖状的导师信息（内存对象）
                    student_award.supervisor_name = supervisor_names
                    student_award.supervisors = []
                    for teacher_id in supervisor_ids:
                        teacher = teacher_manager.get_teacher_by_id(teacher_id)
                        if teacher:
                            student_award.supervisors.append(teacher)

                    # 保存到数据库
                    award_manager._save_award(student_award)

                    # 重新检测并更新异常状态（修复后需清除 is_abnormal 标记）
                    try:
                        from backend.extract.validation import AwardValidator
                        validator = AwardValidator()
                        validation_result = validator.validate_for_db_object(student_award)
                        award_manager.update_validation_status(
                            student_award.id,
                            is_abnormal=not validation_result.is_valid,
                            validation_result=validation_result.to_json() if not validation_result.is_valid else None
                        )
                    except Exception as validation_error:
                        logger.warning(f"奖状 {student_award.id} 重新检测失败: {validation_error}")

                    updated_count += 1
                    detail['success'] = True
                    logger.info(f"成功更新学生奖状 {student_award.id}，添加导师: {supervisor_names}")

                except Exception as e:
                    logger.error(f"更新学生奖状 {student_award.id} 时发生错误: {e}", exc_info=True)
            else:
                # 试运行模式，只记录但不更新
                detail['success'] = True  # 假设会成功

            details.append(detail)

        result_message = f"匹配到 {len(matches)} 对师生奖状"
        if not dry_run:
            result_message += f"，成功更新 {updated_count} 个学生奖状的导师信息"
        else:
            result_message += "（试运行模式，未实际更新）"

        return jsonify({
            'success': True,
            'message': result_message,
            'matched': len(matches),
            'updated': updated_count,
            'details': details
        })

    except Exception as e:
        logger.error(f"关联师生奖状失败: {e}", exc_info=True)
        return jsonify({'success': False, 'message': f'操作失败: {str(e)}'}), 500

# ==================== 通用数据导入功能 ====================


