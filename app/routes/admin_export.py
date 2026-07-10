"""
管理员 - 数据导出路由
"""
import logging
from flask import Blueprint, render_template, request, jsonify, redirect, url_for, Response, session

from app.auth import require_role
from app.utils import get_app_context_instance

logger = logging.getLogger(__name__)
bp = Blueprint('admin_export', __name__)


@bp.route('/data_export')
@require_role('admin')
def data_export():
    """数据导出主页面（重定向到系年度总结）"""
    return redirect(url_for('admin_export.department_summary'))


@bp.route('/data_export/department_summary')
@require_role('admin')
def department_summary():
    """系年度总结页面"""
    from datetime import datetime
    from backend.utils.export_utils import generate_department_summary_data, format_date_to_month

    app_context = get_app_context_instance()
    award_manager = app_context.get_award_manager()
    competition_manager = app_context.get_competition_manager()
    student_manager = app_context.get_student_manager()
    teacher_manager = app_context.get_teacher_manager()
    laboratory_manager = app_context.get_laboratory_manager()

    # 获取筛选参数，如果没有则设置默认值
    from datetime import timedelta
    start_date = request.args.get('start_date', '').strip()
    end_date = request.args.get('end_date', '').strip()
    year = request.args.get('year', type=int)

    # 设置默认日期：开始日期=一年前，结束日期=当前月份
    if not end_date:
        now = datetime.now()
        end_date = now.strftime('%Y-%m')

    if not start_date:
        one_year_ago = datetime.now() - timedelta(days=365)
        start_date = one_year_ago.strftime('%Y-%m')

    # 查询所有学生奖状（排除教师证书）
    query_params = {
        'exclude_teacher_certificates': True,
        'with_associations': True,
        'student_manager': student_manager,
        'teacher_manager': teacher_manager,
        'comp_mgr': competition_manager
    }

    # 年份筛选
    if year:
        query_params['year'] = year

    # 查询奖状
    awards = award_manager.query_awards(**query_params)

    # 日期范围筛选（基于date字段）
    if start_date or end_date:
        filtered_awards = []
        for award in awards:
            if not award.date:
                continue

            # 提取年月
            award_date_month = format_date_to_month(award.date)
            if not award_date_month:
                continue

            # 比较日期范围
            if start_date and award_date_month < start_date:
                continue
            if end_date and award_date_month > end_date:
                continue

            filtered_awards.append(award)
        awards = filtered_awards

    # 生成报表数据
    report_data_df = generate_department_summary_data(
        awards,
        competition_manager,
        laboratory_manager=laboratory_manager
    )

    # 将 DataFrame 转换为字典列表，以便在模板中使用
    report_data = report_data_df.to_dict('records') if not report_data_df.empty else []

    # 列名
    columns = [
        "竞赛名称", "竞赛是否榜单类别", "获奖项目全称", "获奖日期", "奖项级别",
        "奖项等级", "主办单位", "参赛队伍", "队伍人数", "学生负责人",
        "学生负责人学号", "学生负责人手机", "指导教师", "所属实验室"
    ]

    # 检查是否是AJAX请求
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if is_ajax:
        # AJAX请求：只返回预览部分的HTML
        return render_template('admin/data_export/tabs/department_summary_preview.html',
                             report_data=report_data,
                             columns=columns,
                             total_count=len(awards))
    else:
        # 普通请求：返回完整页面
        return render_template('admin/data_export/main.html',
                             tab='department_summary',
                             awards=awards,
                             report_data=report_data,
                             columns=columns,
                             start_date=start_date,
                             end_date=end_date,
                             year=year,
                             total_count=len(awards))


@bp.route('/data_export/department_summary/export', methods=['POST'])
@require_role('admin', 'teacher')
def department_summary_export():
    """导出系年度总结报表"""
    from datetime import datetime
    from backend.utils.export_utils import (
        format_date_to_month,
        create_zip_with_multiple_reports_and_images,
        generate_department_summary_reports
    )
    import sqlite3

    try:
        app_context = get_app_context_instance()
        award_manager = app_context.get_award_manager()
        competition_manager = app_context.get_competition_manager()
        student_manager = app_context.get_student_manager()
        teacher_manager = app_context.get_teacher_manager()
        laboratory_manager = app_context.get_laboratory_manager()

        # 获取参数
        data = request.get_json() or {}
        start_date = data.get('start_date', '').strip()
        end_date = data.get('end_date', '').strip()
        year = data.get('year')
        include_images = data.get('include_images', False)  # 是否包含图片
        teacher_id = data.get('teacher_id')  # 教师ID（用于教师导出）

        # 如果是教师导出，只查询该教师的奖状
        if teacher_id and session.get('user_type') == 'teacher':
            # 查询教师关联的奖状
            conn = sqlite3.connect(award_manager.db_path)
            cursor = conn.cursor()

            # 查询教师作为获奖者的奖状
            cursor.execute("""
                SELECT DISTINCT award_id 
                FROM award_teacher_winners 
                WHERE teacher_id = ?
            """, (teacher_id,))
            winner_award_ids = [row[0] for row in cursor.fetchall()]

            # 查询教师作为指导教师的奖状
            cursor.execute("""
                SELECT DISTINCT award_id 
                FROM award_supervisors 
                WHERE teacher_id = ?
            """, (teacher_id,))
            supervisor_award_ids = [row[0] for row in cursor.fetchall()]

            conn.close()

            # 合并奖状ID（去重）
            all_award_ids = list(set(winner_award_ids + supervisor_award_ids))

            # 获取奖状对象
            awards = []
            if all_award_ids:
                for award in award_manager.awards:
                    if award.id in all_award_ids:
                        award.refresh_associations(competition_manager, student_manager, teacher_manager)
                        awards.append(award)
        else:
            # 管理员导出：查询所有奖状（与department_summary相同的逻辑）
            query_params = {
                'exclude_teacher_certificates': True,
                'with_associations': True,
                'student_manager': student_manager,
                'teacher_manager': teacher_manager,
                'comp_mgr': competition_manager
            }

            if year:
                query_params['year'] = int(year)

            awards = award_manager.query_awards(**query_params)

        # 日期范围筛选
        if start_date or end_date:
            filtered_awards = []
            for award in awards:
                if not award.date:
                    continue
                award_date_month = format_date_to_month(award.date)
                if not award_date_month:
                    continue
                if start_date and award_date_month < start_date:
                    continue
                if end_date and award_date_month > end_date:
                    continue
                filtered_awards.append(award)
            awards = filtered_awards

        # 生成报表（使用封装函数）
        from urllib.parse import quote
        from backend.utils.export_utils import generate_department_summary_reports

        # 判断是否为教师导出
        is_teacher_export = teacher_id and session.get('user_type') == 'teacher'
        teacher_name_for_export = None
        if is_teacher_export:
            teacher = teacher_manager.get_teacher_by_id(teacher_id)
            teacher_name_for_export = teacher.name if teacher else f"teacher_{teacher_id}"

        # 调用封装函数生成报表
        excel_content, html_content, excel_filename_in_zip, html_filename_in_zip, report_title = generate_department_summary_reports(
            awards=awards,
            competition_manager=competition_manager,
            laboratory_manager=laboratory_manager,
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            year=year,
            teacher_id=teacher_id,
            teacher_name=teacher_name_for_export,
            is_teacher_export=is_teacher_export
        )

        # 生成显示名称（用于ZIP文件名）
        if is_teacher_export:
            display_name_parts = ["教师成果导出", teacher_name_for_export]
        else:
            display_name_parts = ["竞赛数据（系）"]

        if year:
            display_name_parts.append(str(year))
        if start_date:
            display_name_parts.append(f"从{start_date}")
        if end_date:
            display_name_parts.append(f"到{end_date}")
        display_name_parts.append(datetime.now().strftime("%Y%m%d"))
        display_name = "_".join(display_name_parts)

        # 提取文件名基础部分（用于ZIP文件名）
        filename_base_ascii = excel_filename_in_zip.replace(".xlsx", "")

        # 创建ZIP文件，包含两种格式的报表
        report_files = [
            {'data': excel_content, 'filename': excel_filename_in_zip},
            {'data': html_content, 'filename': html_filename_in_zip}
        ]

        # 如果包含图片，也添加到ZIP中
        awards_for_zip = awards if include_images else []

        zip_data = create_zip_with_multiple_reports_and_images(
            report_files=report_files,
            awards=awards_for_zip,
            images_base_path="images"
        )

        # ZIP文件名 - 确保ASCII安全
        zip_filename_ascii = f"{filename_base_ascii}.zip"
        zip_display_name = f"{display_name}.zip"

        # 使用RFC 2231编码处理中文文件名
        try:
            zip_encoded_filename = quote(zip_display_name, safe='')
            zip_content_disposition = f'attachment; filename="{zip_filename_ascii}"; filename*=UTF-8\'\'{zip_encoded_filename}'
            zip_content_disposition.encode('latin-1')
        except (UnicodeEncodeError, AttributeError, TypeError):
            zip_content_disposition = f'attachment; filename="{zip_filename_ascii}"'

        return Response(
            zip_data,
            mimetype='application/zip',
            headers={
                'Content-Disposition': zip_content_disposition
            }
        )

    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        logger.error(f"导出报表失败: {e}\n{error_trace}")

        error_response = jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}',
            'error_type': type(e).__name__
        })
        error_response.status_code = 500
        return error_response


@bp.route('/data_export/student_affairs')
@require_role('admin')
def student_affairs():
    """学工数据页面（预留）"""
    return render_template('admin/data_export/main.html')


@bp.route('/data_export/teacher_personal')
@require_role('admin')
def teacher_personal():
    """教师个人数据页面（预留）"""
    return render_template('admin/data_export/main.html')
