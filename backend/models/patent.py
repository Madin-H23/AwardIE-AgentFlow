"""
Patent Management Module

Handles patent (专利) data operations.
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
class Patent:
    """Patent data model"""
    # Core fields
    patent_name: str
    patent_type: Optional[str] = None  # 发明专利, 实用新型, 外观设计
    application_number: Optional[str] = None
    publication_number: Optional[str] = None
    inventor: Optional[str] = None
    application_date: Optional[str] = None
    patentee: Optional[str] = None

    # File path - 实际文件路径为: files/patents/{certificate_file}
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
        parts = [self.patent_name]
        if self.patent_type:
            parts.append(f"类型:{self.patent_type}")
        if self.application_number:
            parts.append(f"申请号:{self.application_number}")
        if self.inventor:
            parts.append(f"发明人:{self.inventor}")
        return " | ".join(parts)


@dataclass
class PatentFilter:
    """Patent query filter"""
    id: Optional[int] = None
    patent_name: Optional[str] = None
    patent_type: Optional[str] = None
    application_number: Optional[str] = None
    inventor: Optional[str] = None
    submitter_type: Optional[str] = None
    submitter_id: Optional[int] = None
    laboratory_id: Optional[int] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.patent_name is None,
            self.patent_type is None,
            self.application_number is None,
            self.inventor is None,
            self.submitter_type is None,
            self.submitter_id is None,
            self.laboratory_id is None,
        ])


class PatentManager:
    """Manages patent data operations"""

    def __init__(self, db_path: str, files_dir: Optional[Path] = None):
        """
        Initialize PatentManager

        Args:
            db_path: Database file path
            files_dir: Directory for patent certificate files
        """
        self.db_path = db_path

        if files_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root / "patents"

        self.files_dir = Path(files_dir)
        self.files_dir.mkdir(parents=True, exist_ok=True)

        self.patents: List[Patent] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)
        return conn

    def _load_all_from_db(self):
        """Load all patents from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM patents ORDER BY id DESC")
            rows = cursor.fetchall()
            conn.close()

            self.patents = [self._row_to_patent(row) for row in rows]
            logger.info(f"Loaded {len(self.patents)} patents from database")
        except Exception as e:
            logger.error(f"Failed to load patents: {e}")
            self.patents = []

    def _row_to_patent(self, row: sqlite3.Row) -> Patent:
        """Convert database row to Patent object"""
        data = dict(row)
        data.pop('created_at', None)
        data.pop('updated_at', None)
        return Patent(**data)

    def get_patent_by_id(self, patent_id: int) -> Optional[Patent]:
        """Get patent by ID"""
        for patent in self.patents:
            if patent.id == patent_id:
                return patent
        return None

    def add_patent(self, patent_data: Dict[str, Any],
                   file_source: Optional[Any] = None,
                   file_path: Optional[str] = None) -> Patent:
        """
        Add a new patent (or update if exists).

        Args:
            patent_data: Patent data dictionary
            file_source: Certificate file (Flask file object) for direct upload
            file_path: Business path (e.g. patents/patent_xxx.pdf) when file already moved from review
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            if patent_data.get('application_number'):
                existing = self._find_by_application_number(patent_data['application_number'])
                if existing:
                    logger.info(f"专利申请号 {patent_data['application_number']} 已存在，将覆盖更新")
                    conn.close()
                    self.update_patent(existing.id, patent_data, file_source=file_source, file_path=file_path)
                    return self.get_patent_by_id(existing.id)

            if file_path and isinstance(file_path, str) and file_path.startswith('patents/'):
                patent_data['certificate_file'] = file_path
            elif file_source:
                patent_data['certificate_file'] = self._save_certificate_file(file_source)
            else:
                patent_data['certificate_file'] = patent_data.get('certificate_file')

            # Prepare fields
            fields = [
                "patent_name", "patent_type", "application_number",
                "publication_number", "inventor", "application_date",
                "patentee", "certificate_file", "submitter_type",
                "submitter_id", "laboratory_id"
            ]

            values = [patent_data.get(f) for f in fields]

            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)

            cursor.execute(f"INSERT INTO patents ({cols}) VALUES ({placeholders})", values)
            patent_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_patent_by_id(patent_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to add patent: {e}")
            raise

    def update_patent(self, patent_id: int, patent_data: Dict[str, Any],
                      file_source: Optional[Any] = None,
                      file_path: Optional[str] = None) -> bool:
        """
        Update existing patent.

        Args:
            patent_id: Patent ID
            patent_data: Updated data
            file_source: New certificate file (Flask object, optional)
            file_path: Business path (e.g. patents/patent_xxx.pdf) when file already moved
        """
        patent = self.get_patent_by_id(patent_id)
        if not patent:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            new_path = None
            if file_path and isinstance(file_path, str) and file_path.startswith('patents/'):
                new_path = file_path
                patent_data['certificate_file'] = file_path
            elif file_source:
                new_path = self._save_certificate_file(file_source)
                patent_data['certificate_file'] = new_path

            if new_path and patent.certificate_file and patent.certificate_file != new_path:
                from backend.services.unified_file_manager import get_unified_file_manager
                fm = get_unified_file_manager()
                old = fm.files_root / patent.certificate_file
                if old.exists():
                    old.unlink()

            # Update fields
            fields = [
                "patent_name", "patent_type", "application_number",
                "publication_number", "inventor", "application_date",
                "patentee", "certificate_file", "submitter_type",
                "submitter_id", "laboratory_id"
            ]

            set_clause = ", ".join([f"{f} = ?" for f in fields])
            values = [patent_data.get(f, getattr(patent, f)) for f in fields]

            cursor.execute(
                f"UPDATE patents SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                values + [patent_id]
            )
            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update patent {patent_id}: {e}")
            return False

    def delete_patent(self, patent_id: int) -> bool:
        """Delete patent"""
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM patents WHERE id = ?", (patent_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                self.patents = [p for p in self.patents if p.id != patent_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete patent {patent_id}: {e}")
            return False

    def query_patents(self, filter_obj: Optional[PatentFilter] = None) -> List[Patent]:
        """
        Query patents with optional filter

        Args:
            filter_obj: PatentFilter object

        Returns:
            List of matching patents
        """
        results = list(self.patents)

        if not filter_obj:
            return results

        # Apply filters (only if filter conditions exist)
        if not filter_obj.is_empty():
            if filter_obj.id is not None:
                results = [p for p in results if p.id == filter_obj.id]

            if filter_obj.patent_type:
                results = [p for p in results if p.patent_type == filter_obj.patent_type]

            if filter_obj.application_number:
                results = [p for p in results if p.application_number == filter_obj.application_number]

            if filter_obj.inventor:
                results = [p for p in results
                          if p.inventor and filter_obj.inventor in p.inventor]

            if filter_obj.submitter_type:
                results = [p for p in results if p.submitter_type == filter_obj.submitter_type]

            if filter_obj.submitter_id is not None:
                results = [p for p in results if p.submitter_id == filter_obj.submitter_id]

            if filter_obj.laboratory_id is not None:
                results = [p for p in results if p.laboratory_id == filter_obj.laboratory_id]

        # Pagination (always apply if specified, regardless of filter conditions)
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def _find_by_application_number(self, application_number: str) -> Optional[Patent]:
        """Find patent by application number"""
        for patent in self.patents:
            if patent.application_number == application_number:
                return patent
        return None

    def _save_certificate_file(self, file_source: Any) -> str:
        """使用统一文件管理器保存证书文件 - 仅支持Flask文件对象"""
        from backend.services.unified_file_manager import get_unified_file_manager, FileType
        
        # 严格验证输入类型
        if not hasattr(file_source, 'save') or not hasattr(file_source, 'filename'):
            raise ValueError(f"file_source必须是Flask文件对象，不支持其他类型: {type(file_source)}")
        
        file_manager = get_unified_file_manager()
        _, relative_path = file_manager.save_business_file(
            FileType.PATENT, file_source, file_source.filename
        )
        
        logger.info(f"专利证书文件已保存: {file_source.filename} -> {relative_path}")
        return relative_path

    def check_duplicate(self, patent_data: Dict[str, Any]) -> Optional[Patent]:
        """
        Check for duplicate patent

        Args:
            patent_data: Patent data to check

        Returns:
            Existing patent if duplicate found, None otherwise
        """
        # Strategy 1: Application number match
        if patent_data.get('application_number'):
            existing = self._find_by_application_number(patent_data['application_number'])
            if existing:
                return existing

        # Strategy 2: Patent name match (normalized)
        if patent_data.get('patent_name'):
            name_normalized = patent_data['patent_name'].strip().lower()
            for patent in self.patents:
                if patent.patent_name and patent.patent_name.strip().lower() == name_normalized:
                    return patent

        return None
