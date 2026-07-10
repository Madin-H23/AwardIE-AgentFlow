"""
PDF文本提取测试工具 (Streamlit)
用于测试PDF引擎的文本提取功能
"""
import streamlit as st
import sys
from pathlib import Path
from PIL import Image
import io

# 添加项目根目录到 path
project_root = Path(__file__).parent.parent
sys.path.append(str(project_root))

from backend.utils.pdf_engine import PDFEngine

# 配置页面
st.set_page_config(
    page_title="PDF文本提取测试工具",
    page_icon="📄",
    layout="wide"
)

# 基础路径
BASE_PATH = Path(r"D:\code\教学工具\信息管理rebuild\images\奖状")


def scan_pdf_files(base_path: Path) -> list:
    """
    扫描指定路径下的所有PDF文件
    
    Args:
        base_path: 基础路径
        
    Returns:
        PDF文件路径列表
    """
    pdf_files = []
    if base_path.exists() and base_path.is_dir():
        # 递归搜索所有PDF文件
        pdf_files = sorted(list(base_path.rglob("*.pdf")))
    return pdf_files


def display_pdf_preview(pdf_path: Path, max_pages: int = 5):
    """
    显示PDF预览（将PDF页面转换为图片显示）
    
    Args:
        pdf_path: PDF文件路径
        max_pages: 最多显示的页数
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        
        st.info(f"📄 PDF文件共有 {total_pages} 页，显示前 {min(max_pages, total_pages)} 页预览")
        
        # 显示前几页的预览
        for page_num in range(min(max_pages, total_pages)):
            page = doc[page_num]
            
            # 将PDF页面转换为图片
            # 设置缩放比例以获得清晰的图片
            zoom = 2.0  # 放大2倍
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 显示图片
            st.image(img, caption=f"第 {page_num + 1} 页", use_container_width=True)
        
        doc.close()
        
        if total_pages > max_pages:
            st.warning(f"⚠️ 还有 {total_pages - max_pages} 页未显示")
            
    except ImportError:
        st.error("❌ PyMuPDF未安装，无法显示PDF预览")
    except Exception as e:
        st.error(f"❌ 显示PDF预览失败: {e}")


def main():
    """主函数"""
    st.title("📄 PDF文本提取测试工具")
    st.markdown("---")
    
    # 侧边栏：配置
    st.sidebar.header("⚙️ 配置")
    
    # 允许用户自定义基础路径
    custom_path = st.sidebar.text_input(
        "基础路径（可选）",
        value=str(BASE_PATH),
        help="留空则使用默认路径"
    )
    
    base_path = Path(custom_path) if custom_path else BASE_PATH
    
    # 显示当前路径
    st.sidebar.info(f"📁 当前路径:\n`{base_path}`")
    
    # 扫描PDF文件
    with st.spinner("正在扫描PDF文件..."):
        pdf_files = scan_pdf_files(base_path)
    
    if not pdf_files:
        st.warning(f"⚠️ 在路径 `{base_path}` 下未找到PDF文件")
        st.info("💡 提示：请确保路径正确，且该路径下存在PDF文件")
        return
    
    st.success(f"✅ 找到 {len(pdf_files)} 个PDF文件")
    
    # 创建下拉框选择PDF文件
    pdf_options = {f.name: f for f in pdf_files}
    selected_pdf_name = st.selectbox(
        "📋 选择PDF文件",
        options=list(pdf_options.keys()),
        help="从下拉列表中选择要测试的PDF文件"
    )
    
    if selected_pdf_name:
        selected_pdf_path = pdf_options[selected_pdf_name]
        
        st.markdown("---")
        
        # 显示文件信息
        col_info1, col_info2, col_info3 = st.columns(3)
        with col_info1:
            st.metric("文件名", selected_pdf_name)
        with col_info2:
            file_size = selected_pdf_path.stat().st_size / 1024  # KB
            st.metric("文件大小", f"{file_size:.2f} KB")
        with col_info3:
            st.metric("完整路径", str(selected_pdf_path))
        
        st.markdown("---")
        
        # 创建两列布局：左侧显示PDF预览，右侧显示提取的文本
        col_left, col_right = st.columns([1, 1])
        
        with col_left:
            st.subheader("📄 PDF预览")
            
            # 显示PDF预览选项
            show_preview = st.checkbox("显示PDF预览", value=True)
            if show_preview:
                max_pages = st.slider("最多显示页数", 1, 10, 3, help="选择要预览的页数")
                display_pdf_preview(selected_pdf_path, max_pages=max_pages)
            else:
                st.info("PDF预览已关闭")
        
        with col_right:
            st.subheader("📝 提取的文本内容")
            
            # 初始化PDF引擎
            try:
                pdf_engine = PDFEngine(debug=False)
                
                # 提取文本按钮
                if st.button("🔄 提取文本", type="primary", use_container_width=True):
                    with st.spinner("正在提取PDF文本..."):
                        try:
                            extracted_text = pdf_engine.get_text(str(selected_pdf_path))
                            
                            # 保存到session state
                            st.session_state['extracted_text'] = extracted_text
                            st.session_state['pdf_name'] = selected_pdf_name
                            
                            st.success("✅ 文本提取成功！")
                            
                        except Exception as e:
                            st.error(f"❌ 文本提取失败: {e}")
                            st.session_state['extracted_text'] = None
                
                # 显示提取的文本
                if 'extracted_text' in st.session_state and st.session_state['extracted_text']:
                    if st.session_state.get('pdf_name') == selected_pdf_name:
                        text = st.session_state['extracted_text']
                        
                        # 显示文本统计信息
                        col_stat1, col_stat2 = st.columns(2)
                        with col_stat1:
                            st.metric("文本长度", f"{len(text)} 字符")
                        with col_stat2:
                            line_count = len(text.split('\n'))
                            st.metric("行数", f"{line_count} 行")
                        
                        # 显示文本内容
                        st.text_area(
                            "文本内容",
                            value=text,
                            height=600,
                            help="提取的PDF文本内容",
                            key=f"text_area_{selected_pdf_name}"
                        )
                        
                        # 下载按钮
                        st.download_button(
                            label="💾 下载文本",
                            data=text,
                            file_name=f"{selected_pdf_path.stem}_extracted.txt",
                            mime="text/plain",
                            use_container_width=True
                        )
                    else:
                        st.info("ℹ️ 请点击'提取文本'按钮获取当前PDF的文本内容")
                else:
                    st.info("ℹ️ 请点击'提取文本'按钮开始提取")
                    
            except ImportError as e:
                st.error(f"❌ PyMuPDF未安装: {e}")
                st.code("pip install PyMuPDF", language="bash")
            except Exception as e:
                st.error(f"❌ 初始化PDF引擎失败: {e}")
        
        st.markdown("---")
        
        # 底部信息
        st.caption(f"📄 当前文件: {selected_pdf_name} | 📁 路径: {selected_pdf_path.parent}")


if __name__ == "__main__":
    main()














