"""
统一文件管理器

严格按照设计文档实现，零兼容性，无降级方案
"""
import hashlib
import logging
import shutil
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from datetime import datetime, timedelta
from enum import Enum

from .file_exceptions import (
    ConfigurationError, 
    FileNotFoundError, InvalidFileTypeError, OperationFailedError
)

logger = logging.getLogger(__name__)


class FileType(Enum):
    """文件类型枚举"""
    SESSION = "session"
    AWARD = "award" 
    PATENT = "patent"
    SOFTWARE = "software"
    OTHER = "other"
    
    @property
    def directory(self) -> str:
        """获取对应的目录路径"""
        directory_map = {
            self.AWARD: "awards",
            self.PATENT: "patents", 
            self.SOFTWARE: "software"
        }
        return directory_map.get(self, self.value)


class SessionStatus(Enum):
    """会话文件状态"""
    TEMP_UPLOAD = "temp_upload"
    REVIEW = "review"
    TEMP_IMAGES = "temp_images"  # 模板测试临时图片
    EXPORT = "export"  # 报告导出临时文件
    
    @property
    def directory(self) -> str:
        """获取对应的目录路径"""
        return self.value


class LabFileType(Enum):
    """实验室文件子类型"""
    COVER = "cover"
    DOWNLOADS = "downloads"  
    PHOTOS = "photos"
    
    @property
    def directory(self) -> str:
        """获取对应的目录路径"""
        # 返回相对于laboratories的子目录
        return self.value
    
    def get_full_directory(self, lab_id: int) -> str:
        """获取包含lab_id的完整目录路径"""
        return f"laboratories/{lab_id}/{self.value}"


class UnifiedFileManager:
    """统一文件管理器"""
    
    def __init__(self):
        """初始化 - 配置缺失时抛出异常"""
        self._load_config()
        self._ensure_directories()
    
    def _load_config(self) -> None:
        """加载配置 - 严格模式，缺失抛出异常"""
        try:
            from config.loader import get_config
            config_loader = get_config()
            # get_path 已返回 resolve() 后的绝对路径
            self.files_root = config_loader.get_path("files")
        except Exception as e:
            raise ConfigurationError(f"无法加载基础文件路径配置: {e}")
        
        try:
            config = config_loader.load_config()
            fm_config = config["unified_file_manager"]
            self.cleanup_config = fm_config["cleanup"]
        except KeyError as e:
            raise ConfigurationError(f"缺少必需的配置项: {e}")
        except Exception as e:
            raise ConfigurationError(f"配置文件格式错误: {e}")
    
    def _ensure_directories(self) -> None:
        """确保目录存在 - 创建失败抛出异常"""
        # 会话目录
        for status in SessionStatus:
            try:
                dir_path = self.files_root / status.directory
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise OperationFailedError(f"无法创建目录 {status.directory}: {e}")
        
        # 业务文件目录
        for file_type in [FileType.AWARD, FileType.PATENT, FileType.SOFTWARE, FileType.OTHER]:
            try:
                dir_path = self.files_root / file_type.directory
                dir_path.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                raise OperationFailedError(f"无法创建目录 {file_type.directory}: {e}")
        
        # 实验室基础目录（具体lab_id目录在save_lab_file时按需创建）
        try:
            laboratories_dir = self.files_root / "laboratories"
            laboratories_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            raise OperationFailedError(f"无法创建实验室基础目录: {e}")
    
    def _safe_unlink(self, file_path: Path, max_retries: int = 5, delay: float = 0.2) -> bool:
        """
        安全删除文件，带重试机制（解决Windows文件占用问题）
        
        Args:
            file_path: 要删除的文件路径
            max_retries: 最大重试次数
            delay: 初始重试延迟（秒）
            
        Returns:
            bool: 是否成功删除
        """
        import time
        if not file_path.exists():
            return True  # 文件不存在，视为成功
        
        for attempt in range(max_retries):
            try:
                file_path.unlink()
                # 验证文件已删除
                if not file_path.exists():
                    return True
                # 如果文件仍存在，继续重试
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # 递增延迟
                    continue
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))  # 递增延迟
                    continue
                else:
                    logger.warning(f"无法删除文件（已重试{max_retries}次）: {file_path}")
                    return False
            except FileNotFoundError:
                # 文件不存在，视为成功
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(delay * (attempt + 1))
                    continue
                else:
                    logger.warning(f"删除文件时发生错误: {file_path}, {e}")
                    return False
        
        # 最终检查
        if not file_path.exists():
            return True
        logger.warning(f"删除文件失败（已重试{max_retries}次）: {file_path}")
        return False
    
    def _cleanup_empty_parent_dirs(self, file_path: Path, root_dirs: Optional[List[str]] = None) -> None:
        """
        清理文件移动后留下的空目录

        Args:
            file_path: 已删除（或移动）的文件路径
            root_dirs: 根目录列表，清理到此为止（如 ['temp_upload', 'review']）
        """
        if root_dirs is None:
            root_dirs = ['temp_upload', 'review']

        parent = file_path.parent
        while parent != self.files_root:
            # 到达指定的根目录（如 temp_upload、review）时停止，不删除根目录本身
            if parent.name in root_dirs or parent == self.files_root:
                break
            if not parent.exists():
                parent = parent.parent
                continue
            try:
                contents = list(parent.iterdir())
                if not contents:
                    parent.rmdir()
                    logger.debug(f"[清理空目录] {parent}")
                else:
                    break
            except Exception as e:
                logger.warning(f"清理目录失败: {parent}, {e}")
                break
            parent = parent.parent

    def cleanup_empty_parent_dirs_for_path(
        self, file_path: Path, root_dirs: Optional[List[str]] = None
    ) -> None:
        """
        删除文件后清理其父级空目录（供外部调用，如 safe_delete_with_file）。

        Args:
            file_path: 已删除文件的绝对路径
            root_dirs: 根目录列表，清理到此为止（如 ['review']），默认 ['temp_upload', 'review']
        """
        if root_dirs is None:
            root_dirs = ['temp_upload', 'review']
        self._cleanup_empty_parent_dirs(file_path, root_dirs)
    
    def _calculate_hash(self, file_path: Path) -> str:
        """计算文件hash"""
        md5_hash = hashlib.md5()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)
        return md5_hash.hexdigest()
    
    # ==================== 1. 查询文件接口 ====================
    
    def find_file(
        self, 
        file_type: FileType,
        file_hash: str,
        session_id: Optional[str] = None,
        status: Optional[SessionStatus] = None,
        lab_id: Optional[int] = None,
        lab_file_type: Optional[LabFileType] = None
    ) -> Path:
        """查找文件 - 未找到抛出FileNotFoundError"""
        if file_type == FileType.SESSION:
            return self._find_session_file(session_id, status, file_hash)
        elif file_type in [FileType.AWARD, FileType.PATENT, FileType.SOFTWARE]:
            return self._find_business_file(file_type, file_hash)
        elif file_type == FileType.OTHER:
            return self._find_lab_file(lab_id, lab_file_type, file_hash)
        else:
            raise InvalidFileTypeError(f"不支持的文件类型: {file_type}")
    
    def _find_business_file(self, file_type: FileType, file_hash: str) -> Path:
        """查找业务文件"""
        search_dir = self.files_root / file_type.directory
        if not search_dir.exists():
            raise FileNotFoundError(f"业务目录不存在: {file_type.value}")
        
        for file_path in search_dir.iterdir():
            if file_path.is_file():
                if file_type == FileType.AWARD and file_path.stem == file_hash:
                    return file_path
                elif file_type != FileType.AWARD and file_hash in file_path.stem:
                    return file_path
        
        raise FileNotFoundError(f"业务文件未找到: {file_type.value}/{file_hash}")
    
    def _find_lab_file(self, lab_id: int, lab_file_type: LabFileType, file_hash: str) -> Path:
        """查找实验室文件"""
        if not lab_id or not lab_file_type:
            raise ValueError("实验室文件需要提供lab_id和lab_file_type")
        
        # 使用新的目录结构：laboratories/{lab_id}/{file_type}/
        search_dir = self.files_root / f"laboratories/{lab_id}/{lab_file_type.value}"
        if not search_dir.exists():
            raise FileNotFoundError(f"实验室目录不存在: laboratories/{lab_id}/{lab_file_type.value}")
        
        # 在新的hash命名方案下，直接查找hash命名的文件
        for file_path in search_dir.iterdir():
            if file_path.is_file():
                # 支持hash命名或旧的时间戳命名方案
                if file_path.stem == file_hash or file_hash in file_path.stem:
                    return file_path
        
        raise FileNotFoundError(f"实验室文件未找到: laboratories/{lab_id}/{lab_file_type.value}/{file_hash}")
    
    # ==================== 2. 业务文件操作 ====================
    
    def save_business_file(self, file_type: FileType, file_data, filename: str) -> Tuple[str, str]:
        """
        直接保存到业务目录，支持专利/软著/奖状/其他文件创建时的文件保存
        
        Args:
            file_type: 文件类型 (AWARD, PATENT, SOFTWARE, OTHER)
            file_data: 文件数据对象 (Flask request.files 对象)
            filename: 原始文件名
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
        """
        if file_type not in [FileType.AWARD, FileType.PATENT, FileType.SOFTWARE, FileType.OTHER]:
            raise InvalidFileTypeError(f"不支持的业务文件类型: {file_type}")
        
        # 生成唯一文件名（基于内容hash）
        import tempfile
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                tmp_path = tmp.name
                file_data.save(tmp.name)
            
            # 在 with 块外计算 hash 和复制，确保临时文件已关闭
            file_hash = self._calculate_hash(Path(tmp_path))
            file_ext = Path(filename).suffix.lower()
            
            # 生成目标路径
            if file_type == FileType.AWARD:
                relative_path = f"{file_type.directory}/{file_hash}{file_ext}"
            elif file_type == FileType.OTHER:
                timestamp = int(datetime.now().timestamp())
                relative_path = f"{file_type.directory}/other_{file_hash}_{timestamp}{file_ext}"
            else:
                timestamp = int(datetime.now().timestamp())
                type_prefix = "patent" if file_type == FileType.PATENT else "software"
                relative_path = f"{file_type.directory}/{type_prefix}_{file_hash}_{timestamp}{file_ext}"
            
            target_path = self.files_root / relative_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            if target_path.exists():
                self._safe_unlink(Path(tmp_path))
                return str(target_path), relative_path
            
            try:
                shutil.copy2(tmp_path, target_path)
                if file_ext in ['.png', '.jpg', '.jpeg'] and hasattr(file_data, 'filename') and file_data.filename:
                    source_filename = Path(file_data.filename).stem
                    if source_filename == Path(filename).stem:
                        self.handle_pdf_conversion_cleanup(Path(tmp_path).parent, source_filename)
            except Exception as e:
                self._safe_unlink(Path(tmp_path))
                raise OperationFailedError(f"保存业务文件失败: {e}")
            finally:
                self._safe_unlink(Path(tmp_path))
        except Exception as e:
            if tmp_path:
                self._safe_unlink(Path(tmp_path))
            raise
        
        return str(target_path), relative_path
    
    def save_business_file_from_path(
        self, 
        file_type: FileType, 
        source_path: Path, 
        filename: str,
        delete_source: bool = False
    ) -> Tuple[str, str]:
        """
        从文件路径保存业务文件，支持专利/软著/奖状/其他文件创建时的文件保存
        
        Args:
            file_type: 文件类型 (AWARD, PATENT, SOFTWARE, OTHER)
            source_path: 源文件路径（绝对路径或相对路径）
            filename: 原始文件名
            delete_source: 是否在复制后删除源文件（默认False，仅复制）
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
            
        Raises:
            FileNotFoundError: 源文件不存在
            InvalidFileTypeError: 不支持的文件类型
            OperationFailedError: 保存操作失败
        """
        if file_type not in [FileType.AWARD, FileType.PATENT, FileType.SOFTWARE, FileType.OTHER]:
            raise InvalidFileTypeError(f"不支持的业务文件类型: {file_type}")
        
        # 转换为绝对路径
        if not source_path.is_absolute():
            source_path = self.files_root / source_path
        
        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")
        
        # 直接计算hash（无需临时文件）
        file_hash = self._calculate_hash(source_path)
        file_ext = Path(filename).suffix.lower()
        
        # 生成目标路径
        if file_type == FileType.AWARD:
            relative_path = f"{file_type.directory}/{file_hash}{file_ext}"
        elif file_type == FileType.OTHER:
            timestamp = int(datetime.now().timestamp())
            relative_path = f"{file_type.directory}/other_{file_hash}_{timestamp}{file_ext}"
        else:
            timestamp = int(datetime.now().timestamp())
            type_prefix = "patent" if file_type == FileType.PATENT else "software"
            relative_path = f"{file_type.directory}/{type_prefix}_{file_hash}_{timestamp}{file_ext}"
        
        target_path = self.files_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已存在（去重）
        if target_path.exists():
            if delete_source and source_path != target_path:
                self._safe_unlink(source_path)
            return str(target_path), relative_path
        
        # 复制文件到目标位置
        try:
            shutil.copy2(source_path, target_path)
            if delete_source and source_path != target_path:
                if self._safe_unlink(source_path):
                    # 如果源文件来自临时目录，清理空目录
                    source_rel = str(source_path.relative_to(self.files_root))
                    if source_rel.startswith('temp_upload') or source_rel.startswith('review'):
                        self._cleanup_empty_parent_dirs(source_path)
        except Exception as e:
            raise OperationFailedError(f"保存业务文件失败: {e}")
        
        return str(target_path), relative_path
    
    def delete_business_file(self, file_type: FileType, relative_path: str) -> bool:
        """
        删除业务文件
        
        Args:
            file_type: 文件类型
            relative_path: 相对路径
            
        Returns:
            bool: 删除成功返回True
        """
        if file_type not in [FileType.AWARD, FileType.PATENT, FileType.SOFTWARE]:
            raise InvalidFileTypeError(f"不支持的业务文件类型: {file_type}")
        
        file_path = self.files_root / relative_path
        
        if not file_path.exists():
            return False
            
        try:
            file_path.unlink()
            return True
        except Exception as e:
            raise OperationFailedError(f"删除业务文件失败: {e}")

    # ==================== 2.3. 会话文件操作（审核流程） ====================

    def resolve_path(self, path: str) -> Path:
        """
        将 file_path 解析为可访问的完整路径，便于跨服务器部署。
        - 若为相对路径（如 temp_upload/session_id/file.ext）：基于 files_root 解析。
        - 若为绝对路径（历史数据）：直接返回，便于兼容。
        """
        if not path or not path.strip():
            raise ValueError("path 不能为空")
        p = Path(path.strip().replace("\\", "/"))
        if p.is_absolute():
            return p.resolve()
        return (self.files_root / p).resolve()

    def move_to_review(self, session_id: str, file_path: str) -> str:
        """
        将文件从 temp_upload 移动到 review 目录

        Args:
            session_id: 会话ID
            file_path: 当前文件的相对路径（temp_upload/{session_id}/{filename}）或历史绝对路径

        Returns:
            str: 新的相对路径（review/{session_id}/{filename}）

        Raises:
            FileNotFoundError: 源文件不存在
            OperationFailedError: 移动操作失败
        """
        source_path = self.resolve_path(file_path)
        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {file_path}")

        # 获取文件名
        filename = source_path.name

        # 构建目标路径：review/{session_id}/{filename}
        target_relative_path = f"review/{session_id}/{filename}"
        target_path = self.files_root / target_relative_path

        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 移动文件（使用copy+unlink替代move，避免Windows文件占用问题）
        try:
            # 先复制文件
            shutil.copy2(str(source_path), str(target_path))
            # 然后删除源文件（带重试机制）
            if self._safe_unlink(source_path):
                # 文件删除成功后，清理可能留下的空目录
                self._cleanup_empty_parent_dirs(source_path, ['temp_upload'])
            else:
                # 如果删除失败，记录警告但继续（文件已在目标位置）
                logger.warning(f"移动文件后删除源文件失败，但文件已复制到目标位置: {source_path}")
            logger.info(f"文件已移动到审核目录: {file_path} -> {target_relative_path}")
            return target_relative_path
        except Exception as e:
            raise OperationFailedError(f"移动文件到review目录失败: {e}")

    def move_from_review_to_business(self, review_path: str, file_type: FileType,
                                       image_hash: Optional[str] = None) -> str:
        """
        将文件从 review 目录移动到业务目录（审核通过）

        Args:
            review_path: review目录中的相对路径（review/{session_id}/{filename}）
            file_type: 目标业务文件类型
            image_hash: 可选的文件hash（用于奖状等去重场景）

        Returns:
            str: 新的相对路径

        Raises:
            FileNotFoundError: 源文件不存在
            OperationFailedError: 移动操作失败
        """
        # 解析源文件路径
        source_path = self.files_root / review_path
        if not source_path.exists():
            raise FileNotFoundError(f"review文件不存在: {review_path}")

        # 获取文件扩展名
        file_ext = source_path.suffix.lower()

        # 构建目标路径
        if image_hash:
            # 使用hash命名（用于奖状等去重场景）
            target_relative_path = f"{file_type.directory}/{image_hash}{file_ext}"
        else:
            # 使用原始文件名
            filename = source_path.name
            timestamp = int(datetime.now().timestamp())
            if file_type == FileType.PATENT:
                filename = f"patent_{timestamp}{file_ext}"
            elif file_type == FileType.SOFTWARE:
                filename = f"software_{timestamp}{file_ext}"
            else:
                filename = f"{file_type.value}_{timestamp}{file_ext}"
            target_relative_path = f"{file_type.directory}/{filename}"

        target_path = self.files_root / target_relative_path

        # 确保目标目录存在
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # 移动文件（使用copy+unlink替代move，避免Windows文件占用问题）
        try:
            # 先复制文件
            shutil.copy2(str(source_path), str(target_path))
            # 然后删除源文件（带重试机制）
            if self._safe_unlink(source_path):
                # 文件删除成功后，清理可能留下的空目录
                self._cleanup_empty_parent_dirs(source_path, ['review'])
            else:
                # 如果删除失败，记录警告但继续（文件已在目标位置）
                logger.warning(f"移动文件后删除源文件失败，但文件已复制到目标位置: {source_path}")
            
            return target_relative_path
        except Exception as e:
            raise OperationFailedError(f"移动文件到业务目录失败: {e}")

    # ==================== 4.6. 实验室文件操作（hash去重） ====================
    
    def save_lab_file(self, lab_id: int, lab_file_type: LabFileType, file_data, filename: str) -> Tuple[str, str]:
        """
        保存实验室文件，使用hash去重机制
        
        Args:
            lab_id: 实验室ID
            lab_file_type: 实验室文件类型
            file_data: 文件数据对象
            filename: 原始文件名
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
        """
        # 生成文件hash
        import tempfile
        import time
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
                tmp_path = tmp.name
                file_data.save(tmp.name)
            
            # 在with块外计算hash，确保文件已关闭
            file_hash = self._calculate_hash(Path(tmp_path))
            file_ext = Path(filename).suffix.lower()
            
            # 构建目标路径（使用hash去重命名）
            if lab_file_type == LabFileType.COVER:
                # 封面图片不去重，直接替换
                relative_path = f"laboratories/{lab_id}/cover/lab_{lab_id}_cover{file_ext}"
            else:
                # 其他文件使用hash命名去重
                relative_path = f"laboratories/{lab_id}/{lab_file_type.value}/{file_hash}{file_ext}"
            
            target_path = self.files_root / relative_path
            
            # 确保目录存在
            target_path.parent.mkdir(parents=True, exist_ok=True)
            
            # 检查是否已存在（去重）
            if target_path.exists():
                # 文件已存在，直接返回路径
                self._safe_unlink(Path(tmp_path))
                return str(target_path), relative_path
            
            # 移动文件到目标位置
            try:
                shutil.copy2(tmp_path, target_path)
                # 延迟删除临时文件，确保Windows文件系统释放文件句柄
                self._safe_unlink(Path(tmp_path))
            except Exception as e:
                self._safe_unlink(Path(tmp_path))
                raise OperationFailedError(f"保存实验室文件失败: {e}")
        except Exception as e:
            if tmp_path:
                self._safe_unlink(Path(tmp_path))
            raise
        
        return str(target_path), relative_path
    
    def save_lab_file_from_path(
        self, 
        lab_id: int, 
        lab_file_type: LabFileType, 
        source_path: Path, 
        filename: str,
        delete_source: bool = False
    ) -> Tuple[str, str]:
        """
        从文件路径保存实验室文件，使用hash去重机制
        
        Args:
            lab_id: 实验室ID
            lab_file_type: 实验室文件类型
            source_path: 源文件路径（绝对路径或相对路径）
            filename: 原始文件名
            delete_source: 是否在复制后删除源文件（默认False，仅复制）
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
            
        Raises:
            FileNotFoundError: 源文件不存在
            OperationFailedError: 保存操作失败
        """
        # 转换为绝对路径
        if not source_path.is_absolute():
            source_path = self.files_root / source_path
        
        if not source_path.exists():
            raise FileNotFoundError(f"源文件不存在: {source_path}")
        
        # 直接计算hash（无需临时文件）
        file_hash = self._calculate_hash(source_path)
        file_ext = Path(filename).suffix.lower()
        
        # 构建目标路径（使用hash去重命名）
        if lab_file_type == LabFileType.COVER:
            # 封面图片不去重，直接替换
            relative_path = f"laboratories/{lab_id}/cover/lab_{lab_id}_cover{file_ext}"
        else:
            # 其他文件使用hash命名去重
            relative_path = f"laboratories/{lab_id}/{lab_file_type.value}/{file_hash}{file_ext}"
        
        target_path = self.files_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 检查是否已存在（去重）
        if target_path.exists():
            if delete_source and source_path != target_path:
                self._safe_unlink(source_path)
            return str(target_path), relative_path
        
        # 复制文件到目标位置
        try:
            shutil.copy2(source_path, target_path)
            if delete_source and source_path != target_path:
                if self._safe_unlink(source_path):
                    # 如果源文件来自临时目录，清理空目录
                    source_rel = str(source_path.relative_to(self.files_root))
                    if source_rel.startswith('temp_upload') or source_rel.startswith('review'):
                        self._cleanup_empty_parent_dirs(source_path)
        except Exception as e:
            raise OperationFailedError(f"保存实验室文件失败: {e}")
        
        return str(target_path), relative_path
    
    def delete_lab_file(self, relative_path: str) -> bool:
        """
        删除实验室文件
        
        Args:
            relative_path: 相对路径
            
        Returns:
            bool: 删除成功返回True
        """
        file_path = self.files_root / relative_path
        
        if not file_path.exists():
            return False
            
        # 使用安全删除方法，避免Windows文件占用问题
        return self._safe_unlink(file_path)

    # ==================== 4.7. 路径查找接口 ====================
    
    def find_file_by_path(self, relative_path: str) -> Path:
        """
        根据相对路径查找文件，用于路由文件访问
        
        对于PDF转图片的情况，优先返回图片文件而不是PDF
        
        Args:
            relative_path: 相对于files_root的路径
            
        Returns:
            Path: 文件绝对路径
            
        Raises:
            FileNotFoundError: 文件不存在
        """
        file_path = self.files_root / relative_path
        
        # 如果直接找到文件
        if file_path.exists():
            # 如果是PDF文件，检查是否存在对应的PNG图片
            if file_path.suffix.lower() == '.pdf':
                png_path = file_path.with_suffix('.png')
                if png_path.exists():
                    # 存在对应的PNG，返回PNG而非PDF
                    file_path = png_path
        else:
            # 文件不存在，检查是否是PDF被转换为图片的情况
            if file_path.suffix.lower() == '.pdf':
                png_path = file_path.with_suffix('.png')
                if png_path.exists():
                    file_path = png_path
                else:
                    raise FileNotFoundError(f"文件不存在: {relative_path}")
            else:
                raise FileNotFoundError(f"文件不存在: {relative_path}")
        
        # 安全检查：确保文件在files_root内
        try:
            file_path.resolve().relative_to(self.files_root.resolve())
        except ValueError:
            raise FileNotFoundError(f"文件路径不安全: {relative_path}")
        
        return file_path
    
    def get_absolute_path(self, relative_path: str) -> Path:
        """
        将相对路径转换为绝对路径（不检查文件是否存在）
        
        Args:
            relative_path: 相对路径
            
        Returns:
            Path: 绝对路径
        """
        return self.files_root / relative_path

    # ==================== 4.8. 临时测试图片管理 ====================
    
    def save_temp_test_image(self, file_data, filename: str) -> Tuple[str, str]:
        """
        保存临时测试图片
        
        Args:
            file_data: 文件数据对象 (Flask request.files 对象)
            filename: 原始文件名
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
        """
        import uuid
        from pathlib import Path
        
        # 确保temp_images目录存在
        temp_images_dir = self.files_root / SessionStatus.TEMP_IMAGES.directory
        temp_images_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名
        file_ext = Path(filename).suffix.lower()
        unique_filename = f"test_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{file_ext}"
        
        # 构建文件路径
        file_path = temp_images_dir / unique_filename
        relative_path = f"{SessionStatus.TEMP_IMAGES.directory}/{unique_filename}"
        
        # 保存文件
        try:
            file_data.save(str(file_path))
        except Exception as e:
            raise OperationFailedError(f"保存临时测试图片失败: {e}")
        
        return str(file_path), relative_path
    
    def save_export_file(self, filename: str, content: bytes) -> Tuple[str, str]:
        """
        保存导出文件到export目录
        
        Args:
            filename: 文件名
            content: 文件内容
            
        Returns:
            Tuple[str, str]: (绝对路径, 相对路径)
        """
        # 确保export目录存在
        export_dir = self.files_root / SessionStatus.EXPORT.directory
        export_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成唯一文件名，包含时间戳
        file_ext = Path(filename).suffix
        file_stem = Path(filename).stem
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        unique_filename = f"{file_stem}_{timestamp}{file_ext}"
        
        # 构建文件路径
        file_path = export_dir / unique_filename
        relative_path = f"{SessionStatus.EXPORT.directory}/{unique_filename}"
        
        # 保存文件
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
        except Exception as e:
            raise OperationFailedError(f"保存导出文件失败: {e}")
        
        return str(file_path), relative_path
    
    def handle_pdf_conversion_cleanup(self, source_dir: Path, pdf_filename: str) -> None:
        """
        处理PDF转图片后的清理工作
        
        当OCR引擎将PDF转为图片后，清理PDF文件，只保留图片
        
        Args:
            source_dir: PDF文件所在目录
            pdf_filename: PDF文件名（不含扩展名）
        """
        try:
            # 查找并删除PDF文件
            pdf_path = source_dir / f"{pdf_filename}.pdf"
            if pdf_path.exists():
                pdf_path.unlink()
                
            # 查找是否有其他PDF相关临时文件
            for pdf_file in source_dir.glob(f"{pdf_filename}*.pdf"):
                pdf_file.unlink()
                
        except Exception as e:
            # 删除失败不影响主流程，仅记录日志
            pass
    
    def cleanup_pdf_conversion_artifacts(self, directory: Path) -> int:
        """
        清理目录中PDF转图片产生的临时文件
        
        搜索目录中的PDF文件，如果同名的PNG图片存在，则删除PDF
        
        Args:
            directory: 要清理的目录
            
        Returns:
            int: 清理的PDF文件数量
        """
        cleanup_count = 0
        
        try:
            for pdf_file in directory.glob("*.pdf"):
                # 检查是否存在同名的PNG图片
                png_file = pdf_file.with_suffix('.png')
                if png_file.exists():
                    # 存在对应图片，删除PDF
                    pdf_file.unlink()
                    cleanup_count += 1
        except Exception:
            pass
        
        return cleanup_count

    # ==================== 5. 清理接口 ====================
    
    def cleanup_expired_sessions(self, temp_upload_hours: int = 1, review_hours: int = 24, temp_images_hours: int = 1, export_hours: int = 2) -> Dict[str, int]:
        """清理过期会话文件"""
        temp_cutoff = datetime.now() - timedelta(hours=temp_upload_hours)
        review_cutoff = datetime.now() - timedelta(hours=review_hours)
        temp_images_cutoff = datetime.now() - timedelta(hours=temp_images_hours)
        export_cutoff = datetime.now() - timedelta(hours=export_hours)
        
        results = {
            'temp_upload_cleaned': 0,
            'review_cleaned': 0,
            'temp_images_cleaned': 0,
            'export_cleaned': 0,
            'total_files_deleted': 0,
            'errors': []
        }
        
        # 清理temp_upload (现在是直接存储文件，不再有子目录)
        temp_dir = self.files_root / SessionStatus.TEMP_UPLOAD.directory
        if temp_dir.exists():
            results['temp_upload_cleaned'] = self._cleanup_files_by_mtime(temp_dir, temp_cutoff, results)
        
        # 清理review  
        review_dir = self.files_root / SessionStatus.REVIEW.directory
        if review_dir.exists():
            results['review_cleaned'] = self._cleanup_files_by_mtime(review_dir, review_cutoff, results)
        
        # 清理temp_images (模板测试图片，1小时过期)
        temp_images_dir = self.files_root / SessionStatus.TEMP_IMAGES.directory
        if temp_images_dir.exists():
            results['temp_images_cleaned'] = self._cleanup_files_by_mtime(temp_images_dir, temp_images_cutoff, results)
        
        # 清理export (报告导出文件，2小时过期)
        export_dir = self.files_root / SessionStatus.EXPORT.directory
        if export_dir.exists():
            results['export_cleaned'] = self._cleanup_files_by_mtime(export_dir, export_cutoff, results)
        
        results['total_files_deleted'] = results['temp_upload_cleaned'] + results['review_cleaned'] + results['temp_images_cleaned'] + results['export_cleaned']
        return results
    
    def _cleanup_session_dir(self, base_dir: Path, cutoff_time: datetime, results: Dict) -> int:
        """清理会话目录"""
        cleaned_count = 0
        
        for session_dir in base_dir.iterdir():
            if not session_dir.is_dir():
                continue
            
            try:
                if self._is_session_expired(session_dir, cutoff_time):
                    shutil.rmtree(session_dir)
                    cleaned_count += 1
            except Exception as e:
                results['errors'].append(f"清理会话失败 {session_dir.name}: {e}")
        
        return cleaned_count
    
    def _cleanup_files_by_mtime(self, target_dir: Path, cutoff_time: datetime, results: Dict) -> int:
        """按文件修改时间清理文件（同时处理可能存在的旧会话目录）"""
        cleaned_count = 0
        
        for file_path in target_dir.iterdir():
            if file_path.is_file():
                try:
                    # 根据文件修改时间判断是否过期
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if file_mtime < cutoff_time:
                        file_path.unlink()
                        cleaned_count += 1
                except Exception as e:
                    results['errors'].append(f"清理文件失败 {file_path.name}: {e}")
            elif file_path.is_dir():
                # 处理可能存在的旧会话目录（遗留清理）
                try:
                    dir_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    if dir_mtime < cutoff_time:
                        shutil.rmtree(file_path)
                        cleaned_count += 1
                except Exception as e:
                    results['errors'].append(f"清理目录失败 {file_path.name}: {e}")
        
        return cleaned_count
    
    


# 全局实例
_unified_file_manager: Optional[UnifiedFileManager] = None


def get_unified_file_manager() -> UnifiedFileManager:
    """获取统一文件管理器实例"""
    global _unified_file_manager
    
    if _unified_file_manager is None:
        _unified_file_manager = UnifiedFileManager()
    
    return _unified_file_manager