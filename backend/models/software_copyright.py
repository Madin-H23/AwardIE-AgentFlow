"""
Software Copyright Management Module

Handles software copyright (软著) data operations.
"""
import sqlite3
import logging
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class SoftwareCopyright:
    """Software Copyright data model"""
    # Core fields
    software_name: str
    software_version: Optional[str] = None
    registration_number: Optional[str] = None
    certificate_no: Optional[str] = None
    registration_date: Optional[str] = None
    copyright_owner: Optional[str] = None

    # File path
    certificate_file: Optional[str] = None

    # Submitter info
    submitter_type: Optional[str] = None  # student, teacher, admin
    submitter_id: Optional[int] = None
    submit_time: Optional[str] = None
    laboratory_id: Optional[int] = None

    # System fields
    id: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def __str__(self):
        parts = [self.software_name]
        if self.software_version:
            parts.append(f"版本:{self.software_version}")
        if self.registration_number:
            parts.append(f"登记号:{self.registration_number}")
        if self.copyright_owner:
            parts.append(f"著作权人:{self.copyright_owner}")
        return " | ".join(parts)


@dataclass
class SoftwareCopyrightFilter:
    """Software Copyright query filter"""
    id: Optional[int] = None
    software_name: Optional[str] = None
    registration_number: Optional[str] = None
    copyright_owner: Optional[str] = None
    submitter_type: Optional[str] = None
    submitter_id: Optional[int] = None
    laboratory_id: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.software_name is None,
            self.registration_number is None,
            self.copyright_owner is None,
            self.submitter_type is None,
            self.submitter_id is None,
            self.laboratory_id is None,
        ])


class SoftwareCopyrightManager:
    """Manages software copyright data operations"""

    def __init__(self, db_path: str, files_dir: Optional[Path] = None):
        """
        Initialize SoftwareCopyrightManager

        Args:
            db_path: Database file path
            files_dir: Directory for certificate files
        """
        self.db_path = db_path

        if files_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root / "software"

        self.files_dir = Path(files_dir)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        self.copyrights: List[SoftwareCopyright] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)
        return conn

    def _load_all_from_db(self):
        """Load all software copyrights from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM software_copyrights ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()

            self.copyrights = [self._row_to_copyright(row) for row in rows]
            logger.info(f"Loaded {len(self.copyrights)} software copyrights from database")
        except Exception as e:
            logger.error(f"Failed to load software copyrights: {e}")
            self.copyrights = []

    def _row_to_copyright(self, row: sqlite3.Row) -> SoftwareCopyright:
        """Convert database row to SoftwareCopyright object"""
        data = dict(row)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        return SoftwareCopyright(**data)

    def get_copyright_by_id(self, copyright_id: int) -> Optional[SoftwareCopyright]:
        """Get software copyright by ID"""
        for copyright in self.copyrights:
            if copyright.id == copyright_id:
                return copyright
        return None

    def add_copyright(self, copyright_data: Dict[str, Any],
                      file_source: Optional[Any] = None,
                      file_path: Optional[str] = None) -> SoftwareCopyright:
        """
        Add a new software copyright (or update if exists).

        Args:
            copyright_data: Copyright data dictionary
            file_source: Certificate file (Flask object) for direct upload
            file_path: Business path (e.g. software/software_xxx.pdf) when file already moved
        """
        if file_path and isinstance(file_path, str) and file_path.startswith('software/'):
            copyright_data['certificate_file'] = file_path
        elif file_source:
            copyright_data['certificate_file'] = self._save_certificate_file(file_source)
        else:
            copyright_data['certificate_file'] = copyright_data.get('certificate_file')

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            if copyright_data.get('registration_number'):
                existing = self._find_by_registration_number(copyright_data['registration_number'])
                if existing:
                    logger.info(f"软著登记号 {copyright_data['registration_number']} 已存在，将覆盖更新")
                    conn.close()
                    self.update_copyright(existing.id, copyright_data, file_source=file_source, file_path=file_path)
                    return self.get_copyright_by_id(existing.id)

            # Prepare fields
            fields = [
                "software_name", "software_version", "registration_number",
                "certificate_no", "registration_date", "copyright_owner",
                "certificate_file", "submitter_type", "submitter_id",
                "laboratory_id"
            ]

            values = [copyright_data.get(f) for f in fields]

            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)

            cursor.execute(f"INSERT INTO software_copyrights ({cols}) VALUES ({placeholders})", values)
            copyright_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_copyright_by_id(copyright_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to add software copyright: {e}", exc_info=True)
            raise

    def update_copyright(self, copyright_id: int, copyright_data: Dict[str, Any],
                         file_source: Optional[Any] = None,
                         file_path: Optional[str] = None) -> bool:
        """
        Update existing software copyright.

        Args:
            copyright_id: Copyright ID
            copyright_data: Updated data
            file_source: New certificate file (Flask object, optional)
            file_path: Business path (e.g. software/software_xxx.pdf) when file already moved
        """
        copyright = self.get_copyright_by_id(copyright_id)
        if not copyright:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            new_path = None
            if file_path and isinstance(file_path, str) and file_path.startswith('software/'):
                new_path = file_path
                copyright_data['certificate_file'] = file_path
            elif file_source:
                new_path = self._save_certificate_file(file_source)
                copyright_data['certificate_file'] = new_path

            if new_path and copyright.certificate_file and copyright.certificate_file != new_path:
                from backend.services.unified_file_manager import get_unified_file_manager
                fm = get_unified_file_manager()
                old = fm.files_root / copyright.certificate_file
                if old.exists():
                    old.unlink()
                   

            # Update fields
            fields = [
                "software_name", "software_version", "registration_number",
                "certificate_no", "registration_date", "copyright_owner",
                "certificate_file", "submitter_type", "submitter_id",
                "laboratory_id"
            ]

            set_clause = ", ".join([f"{f} = ?" for f in fields])
            values = [copyright_data.get(f, getattr(copyright, f)) for f in fields]

            cursor.execute(
                f"UPDATE software_copyrights SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [copyright_id]
            )
            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update software copyright {copyright_id}: {e}")
            return False

    def delete_copyright(self, copyright_id: int) -> bool:
        """Delete software copyright"""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM software_copyrights WHERE id = ?", (copyright_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                self.copyrights = [c for c in self.copyrights if c.id != copyright_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete software copyright {copyright_id}: {e}")
            return False

    def query_copyrights(self, filter_obj: Optional[SoftwareCopyrightFilter] = None) -> List[SoftwareCopyright]:
        """
        Query software copyrights with optional filter

        Args:
            filter_obj: SoftwareCopyrightFilter object

        Returns:
            List of matching software copyrights
        """
        results = list(self.copyrights)

        if not filter_obj or filter_obj.is_empty():
            return results

        # Apply filters
        if filter_obj.id is not None:
            results = [c for c in results if c.id == filter_obj.id]

        if filter_obj.registration_number:
            results = [c for c in results if c.registration_number == filter_obj.registration_number]

        if filter_obj.copyright_owner:
            results = [c for c in results
                      if c.copyright_owner and filter_obj.copyright_owner in c.copyright_owner]

        if filter_obj.submitter_type:
            results = [c for c in results if c.submitter_type == filter_obj.submitter_type]

        if filter_obj.submitter_id is not None:
            results = [c for c in results if c.submitter_id == filter_obj.submitter_id]

        if filter_obj.laboratory_id is not None:
            results = [c for c in results if c.laboratory_id == filter_obj.laboratory_id]

        # Pagination
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def _find_by_registration_number(self, registration_number: str) -> Optional[SoftwareCopyright]:
        """Find software copyright by registration number"""
        for copyright in self.copyrights:
            if copyright.registration_number == registration_number:
                return copyright
        return None

    def _save_certificate_file(self, file_source: Any) -> str:
        """使用统一文件管理器保存证书文件 - 仅支持Flask文件对象"""
        from backend.services.unified_file_manager import get_unified_file_manager, FileType
        
        # 严格验证输入类型
        if not hasattr(file_source, 'save') or not hasattr(file_source, 'filename'):
            raise ValueError(f"file_source必须是Flask文件对象，不支持其他类型: {type(file_source)}")
        
        file_manager = get_unified_file_manager()
        _, relative_path = file_manager.save_business_file(
            FileType.SOFTWARE, file_source, file_source.filename
        )
        
        logger.info(f"软著证书文件已保存: {file_source.filename} -> {relative_path}")
        return relative_path

    def check_duplicate(self, copyright_data: Dict[str, Any]) -> Optional[SoftwareCopyright]:
        """
        Check for duplicate software copyright

        Args:
            copyright_data: Copyright data to check

        Returns:
            Existing copyright if duplicate found, None otherwise
        """
        # Strategy 1: Registration number match
        if copyright_data.get('registration_number'):
            existing = self._find_by_registration_number(copyright_data['registration_number'])
            if existing:
                return existing

        # Strategy 2: Software name match (normalized)
        if copyright_data.get('software_name'):
            name_normalized = copyright_data['software_name'].strip().lower()
            for copyright in self.copyrights:
                if copyright.software_name and copyright.software_name.strip().lower() == name_normalized:
                    return copyright

        return None
