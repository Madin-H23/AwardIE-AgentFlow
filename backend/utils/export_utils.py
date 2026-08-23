"""
数据导出工具函数
提供可复用的数据生成、Excel渲染、HTML渲染功能
"""
import io
import json
import logging
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# 竞赛级别映射
LEVEL_MAPPING = {
    "省赛": "省级",
    "国赛": "国家级",
    "校赛": "校级"
}


def format_date_to_month(date_str: Optional[str]) -> str:
    """
    将日期字符串格式化为只显示年月
    
    Args:
        date_str: 日期字符串，可能包含完整日期
        
    Returns:
        格式化的年月字符串，如 "2024-03"，如果无法解析则返回原字符串
    """
    if not date_str or not date_str.strip():
        return ""
    
    date_str = date_str.strip()
    
    # 尝试提取年月
    # 支持格式：2024-03-15, 2024/03/15, 2024年3月15日等
    patterns = [
        r'(\d{4})[-/](\d{1,2})',  # 2024-03 或 2024/03
        r'(\d{4})年(\d{1,2})月',   # 2024年3月
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str)
        if match:
            year = match.group(1)
            month = match.group(2).zfill(2)  # 补零
            return f"{year}-{month}"
    
    # 如果无法解析，返回原字符串
    return date_str


def format_competition_level(level: Optional[str]) -> str:
    """
    格式化竞赛级别
    
    Args:
        level: 竞赛级别字符串
        
    Returns:
        格式化后的级别，如 "省级"、"国家级"、"校级"
    """
    if not level:
        return ""
    
    level = level.strip()
    # 检查是否包含关键词
    for key, value in LEVEL_MAPPING.items():
        if key in level:
            return value
    
    # 如果没有匹配，返回原值
    return level


def format_project_full_name(award: Any) -> str:
    """
    格式化获奖项目全称
    
    格式：{year}年第{edition}届{competition_name}{province}{track}
    如果没有届数，"第{届数}届"不显示
    如果获奖的是省赛，就显示省份，否则不显示
    
    Args:
        award: 奖状对象
        
    Returns:
        格式化的项目全称
    """
    parts = []
    
    # 年份
    if award.year:
        parts.append(f"{award.year}年")
    
    # 届数
    if award.edition:
        parts.append(f"第{award.edition}届")
    
    # 竞赛名称
    if award.competition_obj and award.competition_obj.name:
        parts.append(award.competition_obj.name)
    elif award.competition_name_in_file:
        parts.append(award.competition_name_in_file)
    
    # 省份（如果是省赛才显示）
    if award.competition_level and "省" in award.competition_level:
        if award.province:
            parts.append(award.province)
    
    # 赛道
    if award.track:
        parts.append(award.track)
    
    return "".join(parts)


def replace_comma_with_separator(text: Optional[str], separator: str = "、") -> str:
    """
    将逗号替换为指定分隔符
    
    Args:
        text: 原始文本
        separator: 替换后的分隔符，默认为"、"
        
    Returns:
        替换后的文本
    """
    if not text:
        return ""
    
    # 替换中英文逗号
    return text.replace(",", separator).replace("，", separator)


def get_laboratory_for_award(
    award: Any,
    laboratory_manager: Any
) -> str:
    """
    获取奖状所属的实验室名称

    关联路径：
    奖状 -> 指导教师（supervisors）-> 实验室

    每个奖状只考虑第一个导师，因此一个奖状只属于一个实验室

    Args:
        award: 奖状对象
        laboratory_manager: 实验室管理器

    Returns:
        实验室名称，如果未找到则返回空字符串
    """
    if not award or not award.id:
        return ""

    try:
        # 通过奖状的指导教师（supervisors）获取实验室
        if award.supervisors and len(award.supervisors) > 0:
            first_supervisor = award.supervisors[0]
            if first_supervisor and first_supervisor.id:
                lab = laboratory_manager.get_laboratory_by_teacher_id(first_supervisor.id)
                if lab:
                    return lab.name

        return ""
    except Exception as e:
        logger.warning(f"获取奖状 {award.id} 的实验室失败: {e}")
        return ""


def get_laboratories_for_awards_batch(
    awards: List[Any],
    laboratory_manager: Any
) -> Dict[int, str]:
    """
    批量获取奖状的实验室信息（性能优化版本）

    每个奖状只考虑第一个导师，因此一个奖状只属于一个实验室

    Args:
        awards: 奖状对象列表
        laboratory_manager: 实验室管理器

    Returns:
        字典，key为奖状ID，value为实验室名称
    """
    result = {}
    if not awards:
        return result

    try:
        # 创建奖状ID到奖状对象的映射（用于后续通过supervisors查询）
        award_map = {a.id: a for a in awards if a and a.id}

        # 对于每个奖状，优先使用直接关联的 laboratory_id
        for award in awards:
            if not award or not award.id:
                continue

            # 优先使用奖状直接关联的 laboratory_id
            if hasattr(award, 'laboratory_id') and award.laboratory_id:
                lab = laboratory_manager.get_laboratory_by_id(award.laboratory_id)
                if lab:
                    result[award.id] = lab.name
                    continue

            # 如果奖状没有直接关联实验室，通过第一个指导教师查找
            if award.supervisors and len(award.supervisors) > 0:
                first_supervisor = award.supervisors[0]
                if first_supervisor and first_supervisor.id:
                    lab = laboratory_manager.get_laboratory_by_teacher_id(first_supervisor.id)
                    if lab:
                        result[award.id] = lab.name

        return result

    except Exception as e:
        logger.warning(f"批量获取实验室信息失败: {e}")
        return result


def generate_department_summary_data(
    awards: List[Any],
    competition_manager: Any,
    laboratory_manager: Optional[Any] = None
) -> pd.DataFrame:
    """
    生成系年度总结报表数据

    Args:
        awards: 奖状对象列表（需要已加载关联数据）
        competition_manager: 竞赛管理器
        laboratory_manager: 实验室管理器（可选，用于获取实验室信息）

    Returns:
        DataFrame，包含14列数据（新增"所属实验室"列）
    """
    result = []

    # 批量获取实验室信息（性能优化）
    laboratory_map = {}
    if laboratory_manager:
        laboratory_map = get_laboratories_for_awards_batch(
            awards, laboratory_manager
        )

    for award in awards:
        # 确保竞赛对象已加载
        if not award.competition_obj and award.competition_id:
            award.competition_obj = competition_manager.get_competition_by_id(award.competition_id)
        
        # 获取第一个学生负责人信息
        first_winner_info = award.get_first_winner_info()
        first_student = first_winner_info.get('obj') if first_winner_info.get('obj_type') == 'student' else None
        
        # 1. 竞赛名称
        competition_name = ""
        if award.competition_obj:
            competition_name = award.competition_obj.name
        elif award.competition_name_in_file:
            competition_name = award.competition_name_in_file
        
        # 2. 竞赛是否榜单类别
        is_whitelist = "非榜单"
        if award.competition_obj and award.competition_obj.is_white_list:
            is_whitelist = "榜单"
        
        # 3. 获奖项目全称
        project_full_name = format_project_full_name(award)
        
        # 4. 获奖日期（只显示到月份）
        award_date = format_date_to_month(award.date)
        
        # 5. 奖项级别
        award_level_type = format_competition_level(award.competition_level)
        
        # 6. 奖项等级
        award_level = award.award_level or ""
        
        # 7. 主办单位
        issuer = replace_comma_with_separator(award.issuer)
        
        # 8. 参赛队伍
        team_members = award.get_team_members_desc()
        
        # 9. 队伍人数
        team_count = award.get_team_count()
        
        # 10. 学生负责人
        leader_name = ""
        if first_student:
            leader_name = first_student.get_brief_desc()
        elif first_winner_info.get('name'):
            leader_name = first_winner_info.get('name')
        
        # 11. 学生负责人学号
        leader_student_id = ""
        if first_student:
            leader_student_id = first_student.student_id or ""
        
        # 12. 学生负责人手机
        leader_phone = ""
        if first_student:
            leader_phone = first_student.phone or ""
        
        # 13. 指导教师
        supervisor = replace_comma_with_separator(award.supervisor_name)
        
        # 14. 所属实验室
        laboratory_name = ""
        if award.id in laboratory_map:
            laboratory_name = laboratory_map[award.id]
        elif laboratory_manager:
            # 如果批量查询失败，回退到单个查询
            laboratory_name = get_laboratory_for_award(award, laboratory_manager)
        
        result.append({
            "id": award.id,
            "竞赛名称": competition_name,
            "竞赛是否榜单类别": is_whitelist,
            "获奖项目全称": project_full_name,
            "获奖日期": award_date,
            "奖项级别": award_level_type,
            "奖项等级": award_level,
            "主办单位": issuer,
            "参赛队伍": team_members,
            "队伍人数": team_count,
            "学生负责人": leader_name,
            "学生负责人学号": leader_student_id,
            "学生负责人手机": leader_phone,
            "指导教师": supervisor,
            "所属实验室": laboratory_name
        })
    
    # 转换为DataFrame
    df = pd.DataFrame(result)
    return df


def render_excel_report(
    df: pd.DataFrame,
    columns: List[str],
    title: str = "报表"
) -> bytes:
    """
    渲染Excel报表
    
    Args:
        df: DataFrame数据
        columns: 列名列表
        title: 报表标题
        
    Returns:
        Excel文件的bytes数据
    """
    try:
        # 确保列顺序
        if columns:
            # 只保留存在的列
            existing_columns = [col for col in columns if col in df.columns]
            df = df[existing_columns]
        
        # 生成Excel
        excel_buffer = io.BytesIO()
        
        # 尝试使用 openpyxl
        try:
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=title)
        except Exception:
            # 如果失败，尝试使用 xlsxwriter
            try:
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name=title)
            except Exception as e:
                logger.error(f"生成Excel失败: {e}")
                raise
        
        excel_buffer.seek(0)
        return excel_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"渲染Excel报表失败: {e}")
        raise


def generate_heatmap_data(
    awards: List[Any],
    competition_manager: Any,
    laboratory_manager: Any
) -> Dict[str, Any]:
    """
    生成竞赛×实验室热力图数据

    Args:
        awards: 奖状对象列表
        competition_manager: 竞赛管理器
        laboratory_manager: 实验室管理器

    Returns:
        包含热力图数据的字典，格式：{competitions: [...], laboratories: [...], data: [[...]]}
    """
    try:
        from backend.services.heatmap_service import get_heatmap_service, HeatmapFilters
        from config.loader import get_config_loader

        config = get_config_loader()
        db_path = str(config.get_path("database", "competitions_db"))

        # 获取热力图服务（管理员视图）
        service = get_heatmap_service(db_path, laboratory_id=None)

        # 构建筛选条件（默认显示所有数据）
        filters = HeatmapFilters(
            years=None,
            white_list_only=False,
            include_teacher_certificates=False
        )

        # 获取热力图数据
        heatmap_data = service.get_lab_competition_heatmap(filters)

        return {
            "competitions": heatmap_data.competitions,
            "laboratories": heatmap_data.laboratories,
            "data": heatmap_data.data
        }
    except Exception as e:
        logger.warning(f"生成热力图数据失败: {e}")
        return {"competitions": [], "laboratories": [], "data": []}


def generate_chart_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    生成图表数据（按实验室分组统计5个类别的获奖数量）

    Args:
        df: 包含"所属实验室"、"竞赛是否榜单类别"、"奖项级别"列的DataFrame

    Returns:
        包含图表配置的字典
    """
    # 确保有必要的列
    if "所属实验室" not in df.columns or "竞赛是否榜单类别" not in df.columns or "奖项级别" not in df.columns:
        return {
            "categories": [],
            "series": []
        }
    
    # 创建分类列：榜单国奖、榜单省奖、非榜单国奖、非榜单省奖、非榜单国际奖
    def get_category(row):
        is_whitelist = row["竞赛是否榜单类别"] == "榜单"
        level = str(row["奖项级别"]).strip()
        
        # 识别奖项级别：国赛/国家级、省赛/省级、国际赛
        is_national = "国" in level and "国际" not in level  # 国家级（排除国际）
        is_provincial = "省" in level
        is_international = "国际" in level
        
        if is_whitelist:
            if is_national:
                return "榜单国奖"
            elif is_provincial:
                return "榜单省奖"
        else:
            if is_national:
                return "非榜单国奖"
            elif is_provincial:
                return "非榜单省奖"
            elif is_international:
                return "非榜单国际奖"
        
        return None
    
    df_copy = df.copy()
    df_copy["类别"] = df_copy.apply(get_category, axis=1)
    
    # 过滤掉类别为None的行
    df_copy = df_copy[df_copy["类别"].notna()]
    
    # 处理空实验室名称
    df_copy["所属实验室"] = df_copy["所属实验室"].fillna("未分配")
    
    # 按实验室和类别分组统计
    chart_data = df_copy.groupby(["所属实验室", "类别"]).size().reset_index(name="数量")
    
    # 获取所有实验室和类别
    laboratories = sorted(df_copy["所属实验室"].unique().tolist())
    categories = ["榜单国奖", "榜单省奖", "非榜单国奖", "非榜单省奖", "非榜单国际奖"]
    
    # 构建系列数据
    series_data = {}
    for category in categories:
        series_data[category] = []
        for lab in laboratories:
            count = chart_data[
                (chart_data["所属实验室"] == lab) & 
                (chart_data["类别"] == category)
            ]["数量"].sum()
            series_data[category].append(int(count))
    
    return {
        "categories": laboratories,
        "series": [
            {"name": "榜单国奖", "data": series_data["榜单国奖"]},
            {"name": "榜单省奖", "data": series_data["榜单省奖"]},
            {"name": "非榜单国奖", "data": series_data["非榜单国奖"]},
            {"name": "非榜单省奖", "data": series_data["非榜单省奖"]},
            {"name": "非榜单国际奖", "data": series_data["非榜单国际奖"]}
        ]
    }


def generate_summary_chart_data(df: pd.DataFrame) -> Dict[str, Any]:
    """
    生成汇总图表数据（按榜单/非榜单分类，统计国奖、省奖、国际奖数量）
    
    Args:
        df: 包含"竞赛是否榜单类别"、"奖项级别"列的DataFrame
        
    Returns:
        包含汇总图表配置的字典
    """
    # 确保有必要的列
    if "竞赛是否榜单类别" not in df.columns or "奖项级别" not in df.columns:
        return {
            "categories": [],
            "series": []
        }
    
    df_copy = df.copy()
    
    # 识别奖项级别
    def get_level(row):
        level = str(row["奖项级别"]).strip()
        is_national = "国" in level and "国际" not in level
        is_provincial = "省" in level
        is_international = "国际" in level
        
        if is_national:
            return "国奖"
        elif is_provincial:
            return "省奖"
        elif is_international:
            return "国际奖"
        return None
    
    df_copy["奖项等级"] = df_copy.apply(get_level, axis=1)
    df_copy = df_copy[df_copy["奖项等级"].notna()]
    
    # 按榜单类别和奖项等级分组统计
    summary_data = df_copy.groupby(["竞赛是否榜单类别", "奖项等级"]).size().reset_index(name="数量")
    
    # 构建汇总数据
    categories = ["榜单赛事", "非榜单赛事"]
    level_types = ["国奖", "省奖", "国际奖"]
    
    # 初始化数据
    series_data = {}
    for level_type in level_types:
        series_data[level_type] = []
        for category in categories:
            # 匹配类别
            is_whitelist = category == "榜单赛事"
            whitelist_str = "榜单" if is_whitelist else "非榜单"
            
            count = summary_data[
                (summary_data["竞赛是否榜单类别"] == whitelist_str) & 
                (summary_data["奖项等级"] == level_type)
            ]["数量"].sum()
            series_data[level_type].append(int(count))
    
    # 计算小计行
    subtotal_row = []
    for level_type in level_types:
        subtotal = sum(series_data[level_type])
        subtotal_row.append(subtotal)
    
    # 计算小计列
    whitelist_total = sum([series_data[level_type][0] for level_type in level_types])
    non_whitelist_total = sum([series_data[level_type][1] for level_type in level_types])
    grand_total = whitelist_total + non_whitelist_total
    
    return {
        "categories": categories,
        "series": [
            {"name": "国奖项数", "data": series_data["国奖"]},
            {"name": "省奖项数", "data": series_data["省奖"]},
            {"name": "国际奖项数", "data": series_data["国际奖"]}
        ],
        "table_data": {
            "rows": [
                {
                    "name": "榜单赛事",
                    "national": series_data["国奖"][0],
                    "provincial": series_data["省奖"][0],
                    "international": series_data["国际奖"][0],
                    "subtotal": whitelist_total
                },
                {
                    "name": "非榜单赛事",
                    "national": series_data["国奖"][1],
                    "provincial": series_data["省奖"][1],
                    "international": series_data["国际奖"][1],
                    "subtotal": non_whitelist_total
                },
                {
                    "name": "小计",
                    "national": subtotal_row[0],
                    "provincial": subtotal_row[1],
                    "international": subtotal_row[2],
                    "subtotal": grand_total
                }
            ]
        }
    }


def render_html_report(
    df: pd.DataFrame,
    columns: List[str],
    title: str = "报表",
    show_chart: bool = False,
    chart_data: Optional[Dict[str, Any]] = None,
    awards: Optional[List[Any]] = None,
    competition_manager: Optional[Any] = None,
    laboratory_manager: Optional[Any] = None,
    raw_html_columns: Optional[List[str]] = None
) -> str:
    """
    渲染HTML报表

    Args:
        df: DataFrame数据
        columns: 列名列表
        title: 报表标题
        show_chart: 是否显示图表
        chart_data: 图表数据（如果show_chart=True且未提供，会自动生成）
        awards: 奖状对象列表（用于生成热力图）
        competition_manager: 竞赛管理器（用于生成热力图）
        laboratory_manager: 实验室管理器（用于生成热力图）

    Returns:
        HTML字符串
    """
    # 生成表格HTML
    table_rows = []
    
    # 表头
    header_row = "<tr>" + "".join([f'<th>{col}</th>' for col in columns if col in df.columns]) + "</tr>"
    table_rows.append(header_row)
    
    # 数据行
    raw_cols = set(raw_html_columns or [])
    for _, row in df.iterrows():
        cells = []
        for col in columns:
            if col not in df.columns:
                continue
            value = row[col]
            if pd.isna(value):
                value = ""
            else:
                value = str(value)
            # 非 raw 列转义 HTML 特殊字符
            if col not in raw_cols:
                value = value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")
            cells.append(f'<td>{value}</td>')
        table_rows.append("<tr>" + "".join(cells) + "</tr>")
    
    table_html = "<table class='report-table'>" + "".join(table_rows) + "</table>"
    
    # 生成图表HTML（如果需要）
    chart_html = ""
    if show_chart:
        import json

        # 生成热力图数据（竞赛×实验室）
        if awards and competition_manager and laboratory_manager:
            heatmap_data = generate_heatmap_data(awards, competition_manager, laboratory_manager)
        else:
            heatmap_data = {"competitions": [], "laboratories": [], "data": []}

        # 生成汇总图表数据
        summary_chart_data = generate_summary_chart_data(df)

        # 将数据转换为JSON字符串（用于ECharts）
        heatmap_json = json.dumps(heatmap_data, ensure_ascii=False)
        summary_chart_json = json.dumps(summary_chart_data, ensure_ascii=False)

        chart_html = f"""
        <div class="chart-wrapper">
            <h2 style="text-align: center; margin-bottom: 20px; color: #1a73e8;">竞赛×实验室 获奖数量热力图</h2>
            <div id="heatmap-container" style="width: 100%; height: 600px;"></div>
        </div>
        <div class="chart-wrapper" style="margin-top: 40px;">
            <h2 style="text-align: center; margin-bottom: 20px; color: #1a73e8;">汇总数据</h2>
            <div id="summary-chart-container" style="width: 100%; height: 400px;"></div>
            <div id="summary-table-container" style="margin-top: 30px;"></div>
        </div>
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
        <script>
            // 竞赛×实验室热力图
            var heatmapData = {heatmap_json};
            if (heatmapData.competitions && heatmapData.competitions.length > 0) {{
                var heatmapChart = echarts.init(document.getElementById('heatmap-container'));

                // 将数据转换为ECharts热力图格式 [yIndex, xIndex, value]
                var heatmapSeriesData = [];
                for (var i = 0; i < heatmapData.competitions.length; i++) {{
                    for (var j = 0; j < heatmapData.laboratories.length; j++) {{
                        heatmapSeriesData.push([j, i, heatmapData.data[i][j]]);
                    }}
                }}

                // 计算最大值
                var maxValue = Math.max(...heatmapSeriesData.map(d => d[2])) || 10;

                var heatmapOption = {{
                    title: {{
                        text: '竞赛×实验室 获奖数量',
                        left: 'center',
                        textStyle: {{ fontSize: 16, fontWeight: 600, color: '#333' }}
                    }},
                    tooltip: {{
                        formatter: function(params) {{
                            var comp = heatmapData.competitions[params.data[1]];
                            var lab = heatmapData.laboratories[params.data[0]];
                            return comp + '<br/>' + lab + ': ' + params.data[2] + ' 项';
                        }}
                    }},
                    grid: {{
                        top: '15%',
                        bottom: '15%',
                        left: '5%',
                        right: '5%',
                        containLabel: true
                    }},
                    xAxis: {{
                        type: 'category',
                        data: heatmapData.laboratories,
                        axisLabel: {{ rotate: 0 }}
                    }},
                    yAxis: {{
                        type: 'category',
                        data: heatmapData.competitions,
                        axisLabel: {{ width: 150, overflow: 'truncate' }}
                    }},
                    visualMap: {{
                        min: 0,
                        max: maxValue,
                        calculable: true,
                        orient: 'horizontal',
                        left: 'center',
                        bottom: '0%',
                        inRange: {{ color: ['#f7f7f7', '#1890ff', '#003a8c'] }}
                    }},
                    series: [{{
                        type: 'heatmap',
                        data: heatmapSeriesData,
                        label: {{ show: true }},
                        emphasis: {{
                            itemStyle: {{ shadowBlur: 10, shadowColor: 'rgba(0,0,0,0.5)' }}
                        }}
                    }}]
                }};
                heatmapChart.setOption(heatmapOption);
            }} else {{
                document.getElementById('heatmap-container').innerHTML = '<div style="text-align: center; padding: 50px; color: #999;">暂无热力图数据</div>';
            }}
            
            // 汇总图表
            var summaryChartData = {summary_chart_json};
            var summaryChart = echarts.init(document.getElementById('summary-chart-container'));
            var summaryOption = {{
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'shadow'
                    }}
                }},
                legend: {{
                    data: ['国奖项数', '省奖项数', '国际奖项数'],
                    top: 10
                }},
                grid: {{
                    left: '3%',
                    right: '4%',
                    bottom: '3%',
                    top: '15%',
                    containLabel: true
                }},
                xAxis: {{
                    type: 'category',
                    data: summaryChartData.categories
                }},
                yAxis: {{
                    type: 'value',
                    name: '获奖数量'
                }},
                series: summaryChartData.series.map(function(item) {{
                    return {{
                        name: item.name,
                        type: 'bar',
                        data: item.data
                    }};
                }})
            }};
            summaryChart.setOption(summaryOption);
            
            // 生成汇总表格
            var tableData = summaryChartData.table_data;
            var tableHtml = '<table class="summary-table" style="width: 100%; border-collapse: collapse; margin: 0 auto;">';
            tableHtml += '<thead><tr style="background-color: #90EE90;">';
            tableHtml += '<th style="padding: 12px; border: 1px solid #ddd; text-align: center;">年终汇报标准奖项等级</th>';
            tableHtml += '<th style="padding: 12px; border: 1px solid #ddd; text-align: center;">国奖项数</th>';
            tableHtml += '<th style="padding: 12px; border: 1px solid #ddd; text-align: center;">省奖项数</th>';
            tableHtml += '<th style="padding: 12px; border: 1px solid #ddd; text-align: center;">国际奖项数</th>';
            tableHtml += '<th style="padding: 12px; border: 1px solid #ddd; text-align: center;">小计</th>';
            tableHtml += '</tr></thead><tbody>';
            
            tableData.rows.forEach(function(row, index) {{
                var bgColor = index < 2 ? '#FFE4B5' : '#FFA500';
                tableHtml += '<tr style="background-color: ' + bgColor + ';">';
                tableHtml += '<td style="padding: 12px; border: 1px solid #ddd; text-align: center; font-weight: bold;">' + row.name + '</td>';
                tableHtml += '<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">' + row.national + '</td>';
                tableHtml += '<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">' + row.provincial + '</td>';
                tableHtml += '<td style="padding: 12px; border: 1px solid #ddd; text-align: center;">' + row.international + '</td>';
                tableHtml += '<td style="padding: 12px; border: 1px solid #ddd; text-align: center; font-weight: bold;">' + row.subtotal + '</td>';
                tableHtml += '</tr>';
            }});
            
            tableHtml += '</tbody></table>';
            document.getElementById('summary-table-container').innerHTML = tableHtml;
        </script>
        """
    
    # 生成完整HTML
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Helvetica Neue', Helvetica, Arial, sans-serif;
            background-color: #f8f9fa;
            padding: 20px;
            color: #202124;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 100%;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
            padding: 30px;
            overflow-x: auto;
        }}
        
        .header {{
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #e0e0e0;
        }}
        
        .header h1 {{
            font-size: 24px;
            font-weight: 600;
            color: #1a73e8;
            margin-bottom: 10px;
        }}
        
        .header .meta {{
            font-size: 14px;
            color: #5f6368;
        }}
        
        .chart-wrapper {{
            margin: 30px 0;
            padding: 20px;
            background: #ffffff;
            border-radius: 8px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.1);
        }}
        
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            margin: 20px auto;
        }}
        
        .summary-table th {{
            background-color: #90EE90;
            padding: 12px;
            border: 1px solid #ddd;
            text-align: center;
            font-weight: 600;
        }}
        
        .summary-table td {{
            padding: 12px;
            border: 1px solid #ddd;
            text-align: center;
        }}
        
        .summary-table tr:nth-child(1) td,
        .summary-table tr:nth-child(2) td {{
            background-color: #FFE4B5;
        }}
        
        .summary-table tr:nth-child(3) td {{
            background-color: #FFA500;
            font-weight: bold;
        }}
        
        .table-wrapper {{
            overflow-x: auto;
            width: 100%;
            margin-top: 30px;
        }}
        
        .report-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
            min-width: 1200px;
        }}
        
        .report-table th {{
            background-color: #1a73e8;
            color: #ffffff;
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            white-space: nowrap;
            position: sticky;
            top: 0;
            z-index: 10;
        }}
        
        .report-table td {{
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
            white-space: nowrap;
        }}
        
        .report-table tr:hover {{
            background-color: #f0f7ff;
        }}
        
        .report-table tr:nth-child(even) {{
            background-color: #f8f9fa;
        }}
        
        .report-table tr:nth-child(even):hover {{
            background-color: #f0f7ff;
        }}
        
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            text-align: center;
            font-size: 12px;
            color: #5f6368;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{title}</h1>
            <div class="meta">生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | 共 {len(df)} 条记录</div>
        </div>
        {chart_html}
        <div class="table-wrapper">
            {table_html}
        </div>
        <div class="footer">
            <p>数据导出系统 | AwardIE-AgentFlow</p>
        </div>
    </div>
</body>
</html>"""
    
    return html_template


def get_award_image_relative_path(award: Any, base_path: str = "images") -> Optional[str]:
    """
    计算奖状在导出 zip 中对应的佐证图片相对路径（与 add_award_images_to_zip 规则一致）。
    若该奖状无图片或找不到文件，返回 None。
    """
    if not getattr(award, "image_hash", None):
        return None
    try:
        from backend.services.unified_file_manager import get_unified_file_manager
        file_manager = get_unified_file_manager()
        ext = None
        for possible_ext in [".jpg", ".jpeg", ".png", ".gif"]:
            try:
                file_manager.find_file_by_path(f"awards/{award.image_hash}{possible_ext}")
                ext = possible_ext
                break
            except FileNotFoundError:
                continue
        if ext is None:
            return None
    except Exception:
        return None

    competition_name = (
        getattr(award, "competition_name_in_file", "")
        or (getattr(award.competition_obj, "name", "") if getattr(award, "competition_obj", None) else "")
        or "未知竞赛"
    )
    competition_name = competition_name.replace("/", "_").replace("\\", "_").replace(":", "").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")

    winner_name = getattr(award, "winner_name", "") or ""
    first_winner = (winner_name.replace("、", ",").replace("，", ",").split(",")[0] or "未知").strip()
    first_winner = first_winner.replace("\\", "_").replace("/", "_")
    track = getattr(award, "track", "") or ""
    competition_level = getattr(award, "competition_level", "") or "未知级别"
    award_level = getattr(award, "award_level", "") or "未知奖项"

    if track:
        img_filename = f"{track}_{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
    else:
        img_filename = f"{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
    img_filename = img_filename.replace("/", "_").replace("\\", "_").replace(":", "").replace("*", "").replace("?", "").replace('"', "").replace("<", "").replace(">", "").replace("|", "")

    return f"{base_path}/{competition_name}/{img_filename}"


def add_award_images_to_zip(
    zip_file: zipfile.ZipFile,
    awards: List[Any],
    base_path: str = "awards"
) -> int:
    """
    将奖状图片添加到ZIP文件中

    Args:
        zip_file: 已打开的ZipFile对象
        awards: 奖状对象列表
        base_path: 图片在ZIP中的基础路径，默认为"awards"
        
    Returns:
        成功添加的图片数量
    """
    added_count = 0
    
    for award in awards:
        try:
            # 使用统一文件管理器查找奖状图片
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            
            image_path = None
            image_bytes = None
            ext = '.jpg'
            
            # 尝试通过image_hash查找图片文件
            if hasattr(award, 'image_hash') and award.image_hash:
                # 在awards目录中查找对应的图片文件
                for possible_ext in ['.jpg', '.jpeg', '.png', '.gif']:
                    try:
                        relative_path = f"awards/{award.image_hash}{possible_ext}"
                        image_path = file_manager.find_file_by_path(relative_path)
                        ext = possible_ext
                        break
                    except FileNotFoundError:
                        continue
            
            # 如果找不到文件，跳过
            if not image_path:
                continue
            
            # 创建新的图片路径结构
            competition_name = getattr(award, 'competition_name_in_file', '') or \
                             (getattr(award.competition_obj, 'name', '') if hasattr(award, 'competition_obj') and award.competition_obj else '') or \
                             "未知竞赛"
            
            # 清理竞赛名称，避免路径问题
            competition_name = competition_name.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
            
            # 获取第一个获奖者名字
            winner_name = getattr(award, 'winner_name', '').replace('、', ',').replace('，', ',')
            first_winner = winner_name.split(',')[0] if winner_name else "未知"
            
            # 获取赛道
            track = getattr(award, 'track', '') or ""
            
            # 获取竞赛等级和获奖等级
            competition_level = getattr(award, 'competition_level', '') or "未知级别"
            award_level = getattr(award, 'award_level', '') or "未知奖项"
            
            # 构建图片文件名
            if track:
                img_filename = f"{track}_{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
            else:
                img_filename = f"{first_winner}_{competition_level}{award_level}_{award.id}{ext}"
            
            # 清理文件名
            img_filename = img_filename.replace('/', '_').replace('\\', '_').replace(':', '').replace('*', '').replace('?', '').replace('"', '').replace('<', '').replace('>', '').replace('|', '')
            
            # 构建完整路径
            full_img_path = f"{base_path}/{competition_name}/{img_filename}"
            
            # 添加到ZIP
            if image_path:
                # 从文件系统读取
                zip_file.write(str(image_path), full_img_path)
            elif image_bytes:
                # 从内存字节数据写入
                zip_file.writestr(full_img_path, image_bytes)
            else:
                continue
            
            added_count += 1
            logger.debug(f"已添加图片到压缩包: {full_img_path}")
            
        except Exception as e:
            logger.warning(f"无法添加奖状 {award.id} 的图片: {e}")
            continue
    
    return added_count


def create_zip_with_report_and_images(
    report_data: Union[bytes, str],
    report_filename: str,
    awards: List[Any],
    images_base_path: str = "awards"
) -> bytes:
    """
    创建包含报表和图片的ZIP文件
    
    Args:
        report_data: 报表文件的字节数据（Excel或HTML）
        report_filename: 报表文件名（在ZIP中的名称）
        awards: 奖状对象列表（用于提取图片）
        images_base_path: 图片在ZIP中的基础路径，默认为"images"
        
    Returns:
        ZIP文件的字节数据
    """
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加报表文件（如果是字符串需要编码为bytes）
            if isinstance(report_data, str):
                report_bytes = report_data.encode('utf-8')
            else:
                report_bytes = report_data
            zf.writestr(report_filename, report_bytes)
            
            # 添加图片
            images_count = add_award_images_to_zip(zf, awards, images_base_path)
            logger.info(f"已创建ZIP文件，包含报表和 {images_count} 张图片")
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        raise


def create_zip_with_multiple_reports_and_images(
    report_files: List[Dict[str, Union[bytes, str]]],
    awards: List[Any],
    images_base_path: str = "awards"
) -> bytes:
    """
    创建包含多个报表文件和图片的ZIP文件
    
    Args:
        report_files: 报表文件列表，每个元素为字典，包含 'data' 和 'filename' 键
            - data: 报表文件的字节数据或字符串（Excel或HTML）
            - filename: 报表文件名（在ZIP中的名称）
        awards: 奖状对象列表（用于提取图片）
        images_base_path: 图片在ZIP中的基础路径，默认为"images"
        
    Returns:
        ZIP文件的字节数据
    """
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            # 添加所有报表文件
            for report_file in report_files:
                report_data = report_file['data']
                report_filename = report_file['filename']
                
                # 如果是字符串需要编码为bytes
                if isinstance(report_data, str):
                    report_bytes = report_data.encode('utf-8')
                else:
                    report_bytes = report_data
                
                zf.writestr(report_filename, report_bytes)
            
            # 添加图片
            images_count = add_award_images_to_zip(zf, awards, images_base_path)
            logger.info(f"已创建ZIP文件，包含 {len(report_files)} 个报表文件和 {images_count} 张图片")
        
        zip_buffer.seek(0)
        return zip_buffer.getvalue()
        
    except Exception as e:
        logger.error(f"创建ZIP文件失败: {e}")
        raise


def generate_department_summary_reports(
    awards: List[Any],
    competition_manager: Any,
    laboratory_manager: Optional[Any] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    year: Optional[int] = None,
    teacher_id: Optional[int] = None,
    teacher_name: Optional[str] = None,
    is_teacher_export: bool = False
) -> Tuple[bytes, str, str, str, str]:
    """
    生成系年度总结报表（Excel和HTML）

    Args:
        awards: 奖状对象列表（需要已加载关联数据）
        competition_manager: 竞赛管理器
        laboratory_manager: 实验室管理器（可选）
        start_date: 开始日期（格式：YYYY-MM）
        end_date: 结束日期（格式：YYYY-MM）
        year: 年份（可选）
        teacher_id: 教师ID（用于教师导出）
        teacher_name: 教师姓名（用于教师导出）
        is_teacher_export: 是否为教师导出

    Returns:
        (excel_content, html_content, excel_filename, html_filename, report_title)
        excel_content: Excel文件的bytes数据
        html_content: HTML文件的字符串
        excel_filename: Excel文件名（在ZIP中的名称）
        html_filename: HTML文件名（在ZIP中的名称）
        report_title: 报表标题（用于HTML）
    """
    # 生成报表数据（DataFrame）
    df = generate_department_summary_data(
        awards,
        competition_manager,
        laboratory_manager=laboratory_manager
    )
    
    # 列名（id 为第一列，Excel 为数字，HTML 为指向佐证图片的超链）
    columns = [
        "id",
        "竞赛名称", "竞赛是否榜单类别", "获奖项目全称", "获奖日期", "奖项级别",
        "奖项等级", "主办单位", "参赛队伍", "队伍人数", "学生负责人",
        "学生负责人学号", "学生负责人手机", "指导教师", "所属实验室"
    ]
    
    # 生成文件名和标题
    if is_teacher_export and teacher_id:
        filename_parts = ["teacher_export", f"teacher_{teacher_id}"]
        display_name_parts = ["教师成果导出", teacher_name or f"teacher_{teacher_id}"]
        report_title = "教师成果导出"
    else:
        filename_parts = ["department_summary"]
        display_name_parts = ["竞赛数据（系）"]
        report_title = "系年度总结"
    
    if year:
        filename_parts.append(str(year))
        display_name_parts.append(str(year))
    if start_date:
        filename_parts.append(f"from_{start_date}")
        display_name_parts.append(f"从{start_date}")
    if end_date:
        filename_parts.append(f"to_{end_date}")
        display_name_parts.append(f"到{end_date}")
    filename_parts.append(datetime.now().strftime("%Y%m%d"))
    display_name_parts.append(datetime.now().strftime("%Y%m%d"))
    filename_base_ascii = "_".join(filename_parts)
    
    excel_filename = f"{filename_base_ascii}.xlsx"
    html_filename = f"{filename_base_ascii}.html"
    
    # 生成Excel
    excel_content = render_excel_report(df, columns, report_title)
    
    # 生成HTML标题（带日期范围）
    html_title = report_title
    if not is_teacher_export:
        # 计算机系学科竞赛数据报告（xx年xx月~xx年xx月）
        date_range_str = ""
        if start_date and end_date:
            # 将YYYY-MM格式转换为xx年xx月
            try:
                start_parts = start_date.split("-")
                end_parts = end_date.split("-")
                if len(start_parts) == 2 and len(end_parts) == 2:
                    start_year = start_parts[0]
                    start_month = str(int(start_parts[1]))  # 去掉前导零
                    end_year = end_parts[0]
                    end_month = str(int(end_parts[1]))  # 去掉前导零
                    date_range_str = f"（{start_year}年{start_month}月~{end_year}年{end_month}月）"
            except Exception:
                pass
        elif year:
            date_range_str = f"（{year}年）"
        
        html_title = f"计算机系学科竞赛数据报告{date_range_str}"
    
    # HTML 表格第一列 id 使用超链指向导出 zip 内的图片（相对路径）
    id_link_html = []
    for a in awards:
        path = get_award_image_relative_path(a, base_path="images")
        if path:
            id_link_html.append(f'<a href="{path}">{a.id}</a>')
        else:
            id_link_html.append(str(a.id))
    df_for_html = df.copy()
    df_for_html["id"] = id_link_html

    # 生成HTML（带图表）
    html_content = render_html_report(
        df_for_html,
        columns,
        title=html_title,
        show_chart=True,
        awards=awards,
        competition_manager=competition_manager,
        laboratory_manager=laboratory_manager,
        raw_html_columns=["id"]
    )

    return excel_content, html_content, excel_filename, html_filename, report_title
