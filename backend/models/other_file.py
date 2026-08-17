"""
Other File Management Module

Handles "other" type files that are not awards/patents/software/innovation.
"""
import sqlite3
import logging
import hashlib
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class OtherFile:
    """Other File data model"""
    # File info
    file_name: str
    file_path: str  # Relative path from files/ directory
    file_type: Optional[str] = None  # MIME type or extension
    file_size: Optional[int] = None  # Size in bytes
    file_hash: Optional[str] = None  # SHA256 hash

    # Image flag (images get special treatment)
    is_image: bool = False

    # Metadata
    description: Optional[str] = None

    # Submitter info
    submitter_type: Optional[str] = None  # student, teacher, admin
    submitter_id: Optional[int] = None
    submit_time: Optional[str] = None

    # Laboratory association (required)
    laboratory_id: Optional[int] = None

    # System fields
    id: Optional[int] = None
    created_at: Optional[str] = None

    def __str__(self):
        parts = [self.file_name]
        if self.file_type:
            parts.append(f"类型:{self.file_type}")
        if self.is_image:
            parts.append("[图片]")
        if self.description:
            parts.append(f"说明:{self.description}")
        return " | ".join(parts)

    def get_full_path(self, base_dir: Path) -> Path:
        """Get full file path"""
        return base_dir / self.file_path


@dataclass
class OtherFileFilter:
    """Other File query filter"""
    id: Optional[int] = None
    file_name: Optional[str] = None
    file_type: Optional[str] = None
    is_image: Optional[bool] = None
    submitter_type: Optional[str] = None
    submitter_id: Optional[int] = None
    laboratory_id: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.file_name is None,
            self.file_type is None,
            self.is_image is None,
            self.submitter_type is None,
            self.submitter_id is None,
            self.laboratory_id is None,
        ])


class OtherFileManager:
    """Manages other file data operations"""

    def __init__(self, db_path: str, files_dir: Optional[Path] = None):
        """
        Initialize OtherFileManager

        Args:
            db_path: Database file path
            files_dir: Base files directory
        """
        self.db_path = db_path

        if files_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root

        self.files_dir = Path(files_dir)
        self.other_dir = self.files_dir / "other"
        self.other_dir.mkdir(parents=True, exist_ok=True)

        self.files: List[OtherFile] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)
        return conn

    def _load_all_from_db(self):
        """Load all other files from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM other_files ORDER BY submit_time DESC")
            rows = cursor.fetchall()
            conn.close()

            self.files = [self._row_to_file(row) for row in rows]
            logger.info(f"Loaded {len(self.files)} other files from database")
        except Exception as e:
            logger.error(f"Failed to load other files: {e}")
            self.files = []

    def _row_to_file(self, row: sqlite3.Row) -> OtherFile:
        """Convert database row to OtherFile object"""
        data = dict(row)
        data.pop('created_at', None)
        # Convert is_image from int to bool
        if 'is_image' in data and data['is_image'] is not None:
            data['is_image'] = bool(data['is_image'])
        return OtherFile(**data)

    def get_file_by_id(self, file_id: int) -> Optional[OtherFile]:
        """Get other file by ID"""
        for file in self.files:
            if file.id == file_id:
                return file
        return None

    def add_file(self, file_source: Any, file_data: Dict[str, Any]) -> OtherFile:
        """
        Add a new other file

        Args:
            file_source: File source (Flask file object)
            file_data: File metadata (description, submitter info, etc.)

        Returns:
            Created OtherFile object
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # 验证输入类型
            if not hasattr(file_source, 'save') or not hasattr(file_source, 'filename'):
                raise ValueError(f"file_source必须是Flask文件对象，不支持其他类型: {type(file_source)}")

            # 使用统一文件管理器保存其他文件
            from backend.services.unified_file_manager import get_unified_file_manager, FileType
            file_manager = get_unified_file_manager()
            
            abs_path, relative_path = file_manager.save_business_file(
                FileType.OTHER, file_source, file_source.filename
            )

            # 计算文件信息
            file_path_obj = Path(abs_path)
            file_size = file_path_obj.stat().st_size
            
            # 计算文件hash
            file_hash = self._calculate_file_hash(file_path_obj)
            
            # 检查重复
            existing = self._find_by_hash(file_hash)
            if existing:
                logger.warning(f"File with same hash already exists: {existing.file_name}")
                # 删除刚保存的重复文件
                try:
                    file_path_obj.unlink()
                except Exception:
                    pass
                return existing

            # 确定是否为图片
            is_image = self._is_image_file(file_path_obj)

            # Prepare fields
            fields = [
                "file_name", "file_path", "file_type", "file_size",
                "file_hash", "is_image", "description",
                "submitter_type", "submitter_id", "laboratory_id"
            ]

            values = [
                file_source.filename,
                relative_path,
                file_data.get('file_type'),  # Could be detected from extension
                file_size,
                file_hash,
                1 if is_image else 0,
                file_data.get('description'),
                file_data.get('submitter_type'),
                file_data.get('submitter_id'),
                file_data.get('laboratory_id')
            ]

            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)

            cursor.execute(f"INSERT INTO other_files ({cols}) VALUES ({placeholders})", values)
            file_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_file_by_id(file_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to add other file: {e}")
            raise

    def add_file_from_path(self, relative_path: str, file_data: Dict[str, Any]) -> OtherFile:
        """
        从已移动到 other/ 的业务路径添加记录（审核通过后调用）。

        Args:
            relative_path: 相对路径，如 other/other_1737758400.pdf
            file_data: 元数据 (file_name, description, submitter_type, submitter_id, laboratory_id 等)

        Returns:
            Created or existing OtherFile
        """
        if not relative_path or not relative_path.startswith('other/'):
            raise ValueError("relative_path 须为 other/ 下的业务路径")

        abs_path = self.files_dir / relative_path
        if not abs_path.exists():
            raise FileNotFoundError(f"文件不存在: {relative_path}")

        path_obj = Path(abs_path)
        file_size = path_obj.stat().st_size
        file_hash = self._calculate_file_hash(path_obj)
        existing = self._find_by_hash(file_hash)
        if existing:
            return existing

        is_image = self._is_image_file(path_obj)
        file_type = file_data.get('file_type') or path_obj.suffix.lstrip('.')

        conn = self._get_db_connection()
        cursor = conn.cursor()
        try:
            fields = [
                "file_name", "file_path", "file_type", "file_size",
                "file_hash", "is_image", "description",
                "submitter_type", "submitter_id", "laboratory_id"
            ]
            values = [
                file_data.get('file_name') or path_obj.name,
                relative_path,
                file_type,
                file_size,
                file_hash,
                1 if is_image else 0,
                file_data.get('description'),
                file_data.get('submitter_type'),
                file_data.get('submitter_id'),
                file_data.get('laboratory_id'),
            ]
            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)
            cursor.execute(f"INSERT INTO other_files ({cols}) VALUES ({placeholders})", values)
            file_id = cursor.lastrowid
            conn.commit()
            conn.close()
            self._load_all_from_db()
            return self.get_file_by_id(file_id)
        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error("add_file_from_path 失败: %s", e)
            raise

    def update_file(self, file_id: int, file_data: Dict[str, Any]) -> bool:
        """
        Update other file metadata

        Args:
            file_id: File ID
            file_data: Updated metadata

        Returns:
            True if successful
        """
        file = self.get_file_by_id(file_id)
        if not file:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Update only metadata fields (not file path or hash)
            fields = [
                "file_name", "file_type", "description",
                "submitter_type", "submitter_id", "laboratory_id"
            ]

            set_clause = ", ".join([f"{f} = ?" for f in fields])
            values = [file_data.get(f, getattr(file, f)) for f in fields]

            cursor.execute(
                f"UPDATE other_files SET {set_clause} WHERE id = ?",
                values + [file_id]
            )
            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update other file {file_id}: {e}")
            return False

    def delete_file(self, file_id: int, delete_physical: bool = False) -> bool:
        """
        Delete other file

        Args:
            file_id: File ID
            delete_physical: Whether to delete physical file

        Returns:
            True if successful
        """
        file = self.get_file_by_id(file_id)
        if not file:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Delete database record
            cursor.execute("DELETE FROM other_files WHERE id = ?", (file_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                # Delete physical file if requested
                if delete_physical:
                    try:
                        physical_path = self.files_dir / file.file_path
                        if physical_path.exists():
                            physical_path.unlink()
                            logger.info(f"Deleted physical file: {physical_path}")
                    except Exception as e:
                        logger.warning(f"Failed to delete physical file: {e}")

                self.files = [f for f in self.files if f.id != file_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete other file {file_id}: {e}")
            return False

    def query_files(self, filter_obj: Optional[OtherFileFilter] = None) -> List[OtherFile]:
        """
        Query other files with optional filter

        Args:
            filter_obj: OtherFileFilter object

        Returns:
            List of matching other files
        """
        results = list(self.files)

        if not filter_obj or filter_obj.is_empty():
            return results

        # Apply filters
        if filter_obj.id is not None:
            results = [f for f in results if f.id == filter_obj.id]

        if filter_obj.file_name:
            results = [f for f in results
                      if f.file_name and filter_obj.file_name.lower() in f.file_name.lower()]

        if filter_obj.file_type:
            results = [f for f in results if f.file_type == filter_obj.file_type]

        if filter_obj.is_image is not None:
            results = [f for f in results if f.is_image == filter_obj.is_image]

        if filter_obj.submitter_type:
            results = [f for f in results if f.submitter_type == filter_obj.submitter_type]

        if filter_obj.submitter_id is not None:
            results = [f for f in results if f.submitter_id == filter_obj.submitter_id]

        if filter_obj.laboratory_id is not None:
            results = [f for f in results if f.laboratory_id == filter_obj.laboratory_id]

        # Pagination
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def _find_by_hash(self, file_hash: str) -> Optional[OtherFile]:
        """Find file by hash"""
        for file in self.files:
            if file.file_hash == file_hash:
                return file
        return None

    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _is_image_file(self, file_path: Path) -> bool:
        """Check if file is an image"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        return file_path.suffix.lower() in image_extensions

    def get_files_by_laboratory(self, laboratory_id: int,
                                 images_only: bool = False) -> List[OtherFile]:
        """Get files by laboratory"""
        filter_obj = OtherFileFilter(
            laboratory_id=laboratory_id,
            is_image=images_only if images_only else None
        )
        return self.query_files(filter_obj)

    def get_images_by_submitter(self, submitter_type: str,
                                 submitter_id: int) -> List[OtherFile]:
        """Get image files by submitter"""
        filter_obj = OtherFileFilter(
            submitter_type=submitter_type,
            submitter_id=submitter_id,
            is_image=True
        )
        return self.query_files(filter_obj)
