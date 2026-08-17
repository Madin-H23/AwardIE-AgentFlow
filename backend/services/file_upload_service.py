"""
文件上传服务

基于统一文件管理器的文件上传服务，文件按hash命名存储在会话目录中
"""
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
import hashlib
import logging
from uuid import uuid4

from .unified_file_manager import get_unified_file_manager, SessionStatus
from .file_exceptions import OperationFailedError

logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """上传结果"""
    success: bool
    filename: str  # hash命名的文件名
    relative_path: str  # 相对于files目录的路径 (temp_upload/{session_id}/{hash}.ext)
    session_id: str  # 会话ID
    file_hash: str  # 文件内容hash（不含扩展名）
    error: Optional[str] = None


class FileUploadService:
    """基于统一文件管理器的文件上传服务"""

    def __init__(self):
        """初始化上传服务"""
        self.file_manager = get_unified_file_manager()

    # P0-10 上传安全：扩展名白名单 + 魔术字节映射 + 单文件大小上限
    ALLOWED_EXTS = {'.jpg', '.jpeg', '.png', '.pdf', '.xlsx', '.zip', '.docx'}
    MAGIC_BYTES = {
        '.jpg': b'\xff\xd8\xff',
        '.jpeg': b'\xff\xd8\xff',
        '.png': b'\x89PNG',
        '.pdf': b'%PDF',
        '.xlsx': b'PK\x03\x04',
        '.zip': b'PK\x03\x04',
        '.docx': b'PK\x03\x04',
    }
    MAX_UPLOAD_BYTES = 100 * 1024 * 1024  # 与 settings max_content_length_mb=100 对齐（双层限制）

    def _validate_upload(self, uploaded_file, file_ext: str) -> None:
        """上传三重校验：白名单 / 真实大小 / 魔术字节（防伪造扩展名）。"""
        if file_ext not in self.ALLOWED_EXTS:
            raise ValueError(f"不支持的文件类型: {file_ext}（允许: {', '.join(sorted(self.ALLOWED_EXTS))}）")
        stream = uploaded_file.stream
        stream.seek(0, 2)
        size = stream.tell()
        stream.seek(0)
        if size > self.MAX_UPLOAD_BYTES:
            raise ValueError(f"文件超过大小上限 {self.MAX_UPLOAD_BYTES // (1024 * 1024)}MB")
        expected = self.MAGIC_BYTES[file_ext]
        head = stream.read(len(expected))
        stream.seek(0)
        if not head.startswith(expected):
            raise ValueError(f"文件内容与扩展名 {file_ext} 不符（魔术字节校验失败）")

    def upload_file(self, uploaded_file) -> UploadResult:
        """
        上传文件到临时会话目录

        文件存储位置: temp_upload/{session_id}/{hash}.ext
        """
        session_id = str(uuid4())

        try:
            if not hasattr(uploaded_file, 'filename') or not uploaded_file.filename:
                raise ValueError("无效的文件对象或文件名")

            # 获取文件扩展名（P0-10：无扩展名不再默认 .jpg，一律拒绝）
            original_name = uploaded_file.filename
            file_ext = Path(original_name).suffix.lower()
            if not file_ext:
                raise ValueError("文件缺少扩展名，无法校验类型")

            self._validate_upload(uploaded_file, file_ext)

            # 计算文件hash（这会重置文件指针）
            file_hash = self._calculate_file_hash(uploaded_file)
            hash_filename = f"{file_hash}{file_ext}"

            # 保存到 temp_upload/{session_id}/ 目录
            session_dir = self.file_manager.files_root / SessionStatus.TEMP_UPLOAD.directory / session_id
            session_dir.mkdir(parents=True, exist_ok=True)

            file_path = session_dir / hash_filename

            # 确保文件指针在开头（calculate_file_hash已经重置了，但再次确保）
            uploaded_file.stream.seek(0)

            # 使用二进制模式写入文件
            with open(file_path, 'wb') as f:
                while True:
                    chunk = uploaded_file.stream.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            # 验证文件是否保存成功
            if not file_path.exists():
                raise IOError(f"文件保存失败: {file_path}")

            file_size = file_path.stat().st_size

            # 构建相对路径
            relative_path = f"{SessionStatus.TEMP_UPLOAD.directory}/{session_id}/{hash_filename}"

            return UploadResult(
                success=True,
                filename=hash_filename,
                relative_path=relative_path,
                session_id=session_id,
                file_hash=file_hash
            )

        except Exception as e:
            logger.error(f"文件上传失败: {e}", exc_info=True)
            return UploadResult(
                success=False,
                filename="",
                relative_path="",
                session_id=session_id,
                file_hash="",
                error=str(e)
            )

    def _calculate_file_hash(self, uploaded_file) -> str:
        """计算文件内容的MD5 hash"""
        # 重置文件指针到开头
        uploaded_file.stream.seek(0)
        md5_hash = hashlib.md5()
        for chunk in iter(lambda: uploaded_file.stream.read(8192), b''):
            md5_hash.update(chunk)
        # 重置文件指针以便后续保存
        uploaded_file.stream.seek(0)
        return md5_hash.hexdigest()


# 全局实例
_file_upload_service: Optional[FileUploadService] = None


def get_file_upload_service() -> FileUploadService:
    """获取文件上传服务实例"""
    global _file_upload_service

    if _file_upload_service is None:
        _file_upload_service = FileUploadService()

    return _file_upload_service