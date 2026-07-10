"""
PDF转图片工具
将PDF文件转换为图片格式
"""
import io
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from PIL import Image

# 尝试导入 PyMuPDF
try:
    import fitz  # PyMuPDF
    FITZ_AVAILABLE = True
except ImportError:
    FITZ_AVAILABLE = False

logger = logging.getLogger(__name__)


def pdf_to_image(
    pdf_path: str, 
    output_dir: Optional[str] = None, 
    dpi: float = 200.0,
    first_page_only: bool = False
) -> Dict[str, Any]:
    """
    将PDF文件转换为图片
    
    :param pdf_path: PDF文件路径
    :param output_dir: 输出目录，如果为None则使用PDF文件所在目录下的pdf_images子目录
    :param dpi: 输出图片的DPI（每英寸点数），默认200，值越大图片越清晰但文件也越大
    :param first_page_only: 是否只转换第一页（用于奖状处理，默认False转换所有页面）
    :return: 包含处理结果的字典，格式如下：
        {
            "success": bool,  # 是否成功
            "images": List[str],  # 保存的图片文件路径列表
            "total_pages": int,  # PDF总页数
            "error": Optional[str],  # 错误信息（如果失败）
            "output_dir": str,  # 输出目录路径
            "first_page_path": Optional[str]  # 第一页图片路径（如果first_page_only=True或需要）
        }
    """
    result = {
        "success": False,
        "images": [],
        "total_pages": 0,
        "error": None,
        "output_dir": "",
        "first_page_path": None
    }
    
    # 检查 PyMuPDF 是否可用
    if not FITZ_AVAILABLE:
        error_msg = "PyMuPDF未安装，无法将PDF转换为图片。请运行: pip install PyMuPDF"
        logger.error(error_msg)
        result["error"] = error_msg
        return result
    
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        error_msg = f"PDF文件不存在: {pdf_path}"
        logger.error(error_msg)
        result["error"] = error_msg
        return result
    
    # 设置输出目录
    if output_dir is None:
        # 默认使用PDF文件所在目录下的pdf_images子目录
        output_dir = pdf_file.parent / "pdf_images"
    else:
        output_dir = Path(output_dir)
    
    # 创建输出目录
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        result["output_dir"] = str(output_dir)
    except Exception as e:
        error_msg = f"无法创建输出目录 {output_dir}: {e}"
        logger.error(error_msg)
        result["error"] = error_msg
        return result
    
    try:
        # 打开PDF文件
        doc = fitz.open(pdf_path)
        total_pages = len(doc)
        result["total_pages"] = total_pages
        
        saved_images = []
        
        # 计算缩放因子（DPI转换为缩放因子）
        # fitz.Matrix 使用缩放因子，200 DPI 约等于缩放因子 2.0
        zoom = dpi / 100.0
        mat = fitz.Matrix(zoom, zoom)
        
        # 确定要处理的页面范围
        if first_page_only:
            page_range = [0]  # 只处理第一页
        else:
            page_range = range(total_pages)  # 处理所有页面
        
        # 遍历每一页
        for page_num in page_range:
            page = doc[page_num]
            
            # 将PDF页面渲染为图片
            pix = page.get_pixmap(matrix=mat)
            
            # 转换为PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # 生成输出文件名
            pdf_name = pdf_file.stem  # 不含扩展名的文件名
            if first_page_only:
                # 如果只转换第一页，使用更简单的文件名
                output_filename = f"{pdf_name}.png"
            else:
                output_filename = f"{pdf_name}_page_{page_num + 1}.png"
            output_path = output_dir / output_filename
            
            # 保存图片
            img.save(output_path, "PNG")
            saved_images.append(str(output_path))
            
            # 记录第一页路径
            if page_num == 0:
                result["first_page_path"] = str(output_path)
        
        doc.close()
        
        result["success"] = True
        result["images"] = saved_images
        
        return result
        
    except Exception as e:
        error_msg = f"PDF转图片失败: {e}"
        logger.error(error_msg, exc_info=True)
        result["error"] = error_msg
        return result


def pdf_first_page_to_image(pdf_path: str, output_dir: Path, dpi: float = 150.0) -> Optional[str]:
    """
    将PDF第一页转换为图片，返回图片路径
    
    这是一个便捷函数，用于审核流程中的PDF预览功能
    
    :param pdf_path: PDF文件路径
    :param output_dir: 输出目录
    :param dpi: 输出图片的DPI，默认150（审核预览用，不需要太高）
    :return: 图片路径，如果失败则返回None
    """
    result = pdf_to_image(
        pdf_path=pdf_path,
        output_dir=str(output_dir),
        dpi=dpi,
        first_page_only=True
    )
    
    if result["success"] and result["first_page_path"]:
        return result["first_page_path"]
    else:
        logger.warning(f"PDF第一页转图片失败: {result.get('error', '未知错误')}")
        return None


def get_or_create_pdf_preview(pdf_path: str, preview_dir: Path) -> Optional[str]:
    """
    获取或创建PDF预览图
    
    如果预览图已存在则直接返回，否则创建新的预览图
    
    :param pdf_path: PDF文件路径
    :param preview_dir: 预览图保存目录
    :return: 预览图路径，如果失败则返回None
    """
    pdf_file = Path(pdf_path)
    if not pdf_file.exists():
        logger.warning(f"PDF文件不存在: {pdf_path}")
        return None
    
    # 检查预览图是否已存在
    preview_dir = Path(preview_dir)
    preview_path = preview_dir / f"{pdf_file.stem}.png"
    
    if preview_path.exists():
        return str(preview_path)
    
    # 创建预览图
    return pdf_first_page_to_image(pdf_path, preview_dir)
