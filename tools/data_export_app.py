"""
数据导出应用
提供奖状数据的筛选、查看和导出功能
"""
import streamlit as st
import sys
import os
import json
import logging
from pathlib import Path
from datetime import datetime
import pandas as pd
import io

# 添加项目根目录到 path
project_root = Path(__file__).parents[1]
sys.path.append(str(project_root))

from backend.models.award import AwardManager
from backend.models.competition import CompetitionManager
from backend.models.student import StudentManager
from backend.models.teacher import TeacherManager

# 初始化日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DataExportApp")


# 加载配置
@st.cache_data
def load_config():
    config_path = project_root / "app/config.json"
    if not config_path.exists():
        logging.error(f"Config file not found: {config_path}")
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


# 初始化 Managers (缓存)
@st.cache_resource
def get_competition_manager():
    db_path = project_root / "database/competitions.db"
    return CompetitionManager(str(db_path))


@st.cache_resource
def get_user_managers():
    db_path = project_root / "database/competitions.db"
    return StudentManager(str(db_path)), TeacherManager(str(db_path))


@st.cache_resource
def get_award_manager():
    db_path = project_root / "database/competitions.db"
    return AwardManager(str(db_path))


def filter_awards_by_competition_level(awards, competition_level):
    """根据比赛等级筛选奖状"""
    if not competition_level or competition_level == "全部":
        return awards
    
    filtered = []
    for award in awards:
        if award.competition_level == competition_level:
            filtered.append(award)
    return filtered


def filter_awards_by_certificate_type(awards, certificate_type):
    """根据证书类型筛选奖状"""
    if not certificate_type or certificate_type == "全部":
        return awards
    
    filtered = []
    for award in awards:
        granted_role = award.granted_role or ""
        if certificate_type == "学生" and "学生" in granted_role:
            filtered.append(award)
        elif certificate_type == "教师" and "教师" in granted_role:
            filtered.append(award)
    return filtered


def build_export_dataframe(awards):
    """构建导出用的 DataFrame"""
    table_data = []
    for a in awards:
        # 获取标准竞赛名称
        comp_name = "未知竞赛"
        if a.competition_obj:
            comp_name = a.competition_obj.name
        elif a.competition_name_in_file:
            comp_name = a.competition_name_in_file
        
        # 构建关联学生/教师信息
        student_winners_str = ", ".join([f"{s.name}({s.student_id})" for s in a.student_winners]) if a.student_winners else ""
        teacher_winners_str = ", ".join([f"{t.name}({t.teacher_id})" for t in a.teacher_winners]) if a.teacher_winners else ""
        supervisors_str = ", ".join([f"{t.name}({t.teacher_id})" for t in a.supervisors]) if a.supervisors else ""
        
        row = {
            "ID": str(a.id) if a.id else "",
            "标准竞赛名称": comp_name,
            "原始竞赛名称": a.competition_name_in_file or "",
            "年份": str(a.year) if a.year else "",
            "奖项等级": a.award_level or "",
            "比赛等级": a.competition_level or "",
            "获奖者": a.winner_name or "",
            "获奖者类型": a.granted_role or "",
            "指导教师": a.supervisor_name or "",
            "作品名称": a.project_title or "",
            "赛道": a.track or "",
            "组别": a.group_name or "",
            "届数": str(a.edition) if a.edition else "",
            "省份": a.province or "",
            "颁发机构": a.issuer or "",
            "颁发日期": a.date or "",
            "证书编号": str(a.certificate_id) if a.certificate_id is not None else "",
            "相关学生": a.related_student_name or "",
            "匹配状态": "✅ 完全匹配" if a.match_status else "⚠️ 部分匹配",
            "关联竞赛": "是" if a.competition_obj else "否",
            "关联获奖学生": student_winners_str,
            "关联获奖教师": teacher_winners_str,
            "关联指导教师": supervisors_str
        }
        table_data.append(row)
    
    return pd.DataFrame(table_data)


def main():
    st.set_page_config(page_title="数据导出", layout="wide")
    st.title("📊 奖状数据导出")
    
    # 初始化 Managers
    try:
        comp_manager = get_competition_manager()
        student_manager, teacher_manager = get_user_managers()
        award_manager = get_award_manager()
    except Exception as e:
        st.error(f"初始化失败: {e}")
        logger.error(f"初始化失败: {e}", exc_info=True)
        return
    
    # 左侧栏：筛选条件
    with st.sidebar:
        st.header("筛选条件")
        
        # 年份筛选
        all_years = sorted(list(set([a.year for a in award_manager.awards if a.year])), reverse=True)
        filter_year = st.selectbox(
            "年份",
            ["全部"] + [str(y) for y in all_years],
            key="export_year_filter"
        )
        
        # 比赛等级筛选（省赛/国赛）
        filter_competition_level = st.selectbox(
            "比赛等级",
            ["全部", "省赛", "国赛"],
            key="export_competition_level_filter"
        )
        
        # 证书类型筛选
        filter_certificate_type = st.selectbox(
            "证书类型",
            ["全部", "学生", "教师"],
            key="export_certificate_type_filter"
        )
        
        st.divider()
        
        # 统计信息
        st.subheader("数据统计")
        total_awards = len(award_manager.awards)
        st.metric("总奖状数", total_awards)
    
    # 主内容区
    st.markdown("### 数据查询与导出")
    
    # 查询数据
    query_kwargs = {
        "with_associations": True,
        "stu_mgr": student_manager,
        "tea_mgr": teacher_manager,
        "comp_mgr": comp_manager
    }
    
    if filter_year != "全部":
        query_kwargs["year"] = int(filter_year)
    
    with st.spinner("正在加载数据..."):
        all_awards = award_manager.query_awards(**query_kwargs)
        
        # 应用比赛等级筛选
        all_awards = filter_awards_by_competition_level(all_awards, filter_competition_level)
        
        # 应用证书类型筛选
        all_awards = filter_awards_by_certificate_type(all_awards, filter_certificate_type)
    
    # 显示统计信息
    st.info(f"共找到 {len(all_awards)} 条符合条件的数据")
    
    # 构建表格数据
    if all_awards:
        df = build_export_dataframe(all_awards)
        
        # 显示表格
        st.markdown("#### 数据预览")
        st.dataframe(df, use_container_width=True, height=600)
        
        # 导出功能
        st.markdown("#### 数据导出")
        
        # 生成文件名后缀
        filters = []
        if filter_year != "全部":
            filters.append(f"年份{filter_year}")
        if filter_competition_level != "全部":
            filters.append(filter_competition_level)
        if filter_certificate_type != "全部":
            filters.append(filter_certificate_type)
        
        file_suffix = "_".join(filters) if filters else "all"
        file_suffix += f"_{datetime.now().strftime('%Y%m%d')}"
        
        # 生成 Excel
        excel_buffer = io.BytesIO()
        try:
            with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='奖状数据')
        except Exception:
            try:
                with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
                    df.to_excel(writer, index=False, sheet_name='奖状数据')
            except Exception as e:
                st.error(f"无法生成 Excel 文件。请安装 openpyxl 或 xlsxwriter: `pip install openpyxl` 或 `pip install xlsxwriter`")
                excel_data = None
                return
        
        excel_data = excel_buffer.getvalue()
        
        # 下载按钮
        st.download_button(
            label="📥 下载 Excel 表格",
            data=excel_data,
            file_name=f"award_data_{file_suffix}_{datetime.now().strftime('%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
        
        # 显示数据统计
        with st.expander("📈 数据统计", expanded=False):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("总记录数", len(all_awards))
            
            with col2:
                # 按年份统计
                year_counts = df["年份"].value_counts()
                st.metric("年份数", len(year_counts))
            
            with col3:
                # 按比赛等级统计
                level_counts = df["比赛等级"].value_counts()
                st.metric("比赛等级数", len(level_counts))
            
            with col4:
                # 按证书类型统计
                role_counts = df["获奖者类型"].value_counts()
                st.metric("证书类型数", len(role_counts))
            
            # 详细统计表格
            st.markdown("##### 年份分布")
            st.bar_chart(year_counts)
            
            st.markdown("##### 比赛等级分布")
            st.bar_chart(level_counts)
            
            st.markdown("##### 证书类型分布")
            st.bar_chart(role_counts)
    else:
        st.warning("没有找到符合条件的数据")


if __name__ == "__main__":
    main()

