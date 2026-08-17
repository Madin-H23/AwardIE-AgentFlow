"""
User Photo Management Module

Handles user photo galleries for lab activities and personal collections.
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
class UserPhoto:
    """User Photo data model"""
    # File info
    file_name: str
    file_path: str  # Relative path from files/ directory
    file_hash: Optional[str] = None  # SHA256 hash (unique)
    thumbnail_path: Optional[str] = None  # Relative path to thumbnail

    # Photo type
    photo_type: str = "personal_gallery"  # lab_activity, personal_gallery

    # Metadata
    description: Optional[str] = None

    # Owner info (required)
    submitter_type: str = "student"  # student, teacher
    submitter_id: int = 0

    # Submit time
    submit_time: Optional[str] = None

    # Laboratory association (for lab_activity photos)
    laboratory_id: Optional[int] = None

    # Visibility
    is_public: bool = True

    # Display order
    display_order: int = 0

    # System fields
    id: Optional[int] = None
    created_at: Optional[str] = None

    def __str__(self):
        parts = [self.file_name]
        if self.photo_type == "lab_activity":
            parts.append("[实验室活动]")
        else:
            parts.append("[个人相册]")
        if self.description:
            parts.append(f"说明:{self.description}")
        return " | ".join(parts)

    def get_full_path(self, base_dir: Path) -> Path:
        """Get full file path"""
        return base_dir / self.file_path

    def get_thumbnail_path(self, base_dir: Path) -> Optional[Path]:
        """Get full thumbnail path"""
        if self.thumbnail_path:
            return base_dir / self.thumbnail_path
        return None


@dataclass
class UserPhotoFilter:
    """User Photo query filter"""
    id: Optional[int] = None
    photo_type: Optional[str] = None  # lab_activity, personal_gallery
    submitter_type: Optional[str] = None
    submitter_id: Optional[int] = None
    laboratory_id: Optional[int] = None
    is_public: Optional[bool] = None
    limit: Optional[int] = None
    offset: Optional[int] = None

    def is_empty(self) -> bool:
        return all([
            self.id is None,
            self.photo_type is None,
            self.submitter_type is None,
            self.submitter_id is None,
            self.laboratory_id is None,
            self.is_public is None,
        ])


class UserPhotoManager:
    """Manages user photo data operations"""

    def __init__(self, db_path: str, files_dir: Optional[Path] = None):
        """
        Initialize UserPhotoManager

        Args:
            db_path: Database file path
            files_dir: Base files directory
        """
        self.db_path = db_path

        if files_dir is None:
            from backend.services.unified_file_manager import get_unified_file_manager, FileType
            file_manager = get_unified_file_manager()
            files_dir = file_manager.files_root / FileType.OTHER.directory

        self.files_dir = Path(files_dir)
        self.users_dir = self.files_dir

        self.photos: List[UserPhoto] = []
        self._load_all_from_db()

    def _get_db_connection(self):
        """Get database connection"""
        from backend.utils.db_connection import get_connection

        return get_connection(self.db_path)
        return conn

    def _load_all_from_db(self):
        """Load all user photos from database"""
        try:
            conn = self._get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM user_photos ORDER BY display_order, submit_time DESC")
            rows = cursor.fetchall()
            conn.close()

            self.photos = [self._row_to_photo(row) for row in rows]
            logger.info(f"Loaded {len(self.photos)} user photos from database")
        except Exception as e:
            logger.error(f"Failed to load user photos: {e}")
            self.photos = []

    def _row_to_photo(self, row: sqlite3.Row) -> UserPhoto:
        """Convert database row to UserPhoto object"""
        data = dict(row)
        data.pop('created_at', None)
        # Convert is_public from int to bool
        if 'is_public' in data and data['is_public'] is not None:
            data['is_public'] = bool(data['is_public'])
        return UserPhoto(**data)

    def get_photo_by_id(self, photo_id: int) -> Optional[UserPhoto]:
        """Get user photo by ID"""
        for photo in self.photos:
            if photo.id == photo_id:
                return photo
        return None

    def add_photo(self, source_path: str, photo_data: Dict[str, Any],
                  create_thumbnail: bool = True) -> UserPhoto:
        """
        Add a new user photo

        Args:
            source_path: Path to source image file
            photo_data: Photo metadata (description, type, etc.)
            create_thumbnail: Whether to create thumbnail

        Returns:
            Created UserPhoto object
        """
        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            source = Path(source_path)
            if not source.exists():
                raise FileNotFoundError(f"Source file not found: {source_path}")

            # Verify it's an image
            if not self._is_image_file(source):
                raise ValueError(f"Not an image file: {source_path}")

            # Calculate file hash
            file_hash = self._calculate_file_hash(source)

            # Check for duplicate by hash
            existing = self._find_by_hash(file_hash)
            if existing:
                logger.warning(f"Photo with same hash already exists: {existing.file_name}")
                return existing

            # 使用统一文件管理器保存用户照片到other目录
            from backend.services.unified_file_manager import get_unified_file_manager, FileType
            
            file_manager = get_unified_file_manager()
            target_filename = f"user_{photo_data.get('submitter_type', 'student')}_{photo_data.get('submitter_id', 0)}_{source.name}"
            
            # 从路径直接保存业务文件（复制，不删除源文件）
            target_path, relative_path = file_manager.save_business_file_from_path(
                FileType.OTHER, source, target_filename, delete_source=False
            )

            # Create thumbnail if requested
            thumbnail_path = None
            if create_thumbnail:
                try:
                    thumbnail_path = self._create_thumbnail(target_path, target_dir)
                except Exception as e:
                    logger.warning(f"Failed to create thumbnail: {e}")

            # Prepare fields
            relative_path = f"users/{submitter_type}/{submitter_id}/photos/{target_filename}"
            relative_thumbnail = f"users/{submitter_type}/{submitter_id}/photos/{thumbnail_path}" if thumbnail_path else None

            fields = [
                "file_name", "file_path", "file_hash", "thumbnail_path",
                "photo_type", "description", "submitter_type", "submitter_id",
                "laboratory_id", "is_public", "display_order"
            ]

            values = [
                source.name,
                relative_path,
                file_hash,
                relative_thumbnail,
                photo_data.get('photo_type', 'personal_gallery'),
                photo_data.get('description'),
                submitter_type,
                submitter_id,
                photo_data.get('laboratory_id'),
                1 if photo_data.get('is_public', True) else 0,
                photo_data.get('display_order', 0)
            ]

            placeholders = ", ".join(["?" for _ in fields])
            cols = ", ".join(fields)

            cursor.execute(f"INSERT INTO user_photos ({cols}) VALUES ({placeholders})", values)
            photo_id = cursor.lastrowid
            conn.commit()
            conn.close()

            # Reload and return
            self._load_all_from_db()
            return self.get_photo_by_id(photo_id)

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to add user photo: {e}")
            raise

    def update_photo(self, photo_id: int, photo_data: Dict[str, Any]) -> bool:
        """
        Update user photo metadata

        Args:
            photo_id: Photo ID
            photo_data: Updated metadata

        Returns:
            True if successful
        """
        photo = self.get_photo_by_id(photo_id)
        if not photo:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Update metadata fields only
            fields = [
                "description", "photo_type", "laboratory_id",
                "is_public", "display_order"
            ]

            set_clause = ", ".join([f"{f} = ?" for f in fields])
            values = [photo_data.get(f, getattr(photo, f)) for f in fields]

            # Handle boolean conversion
            if 'is_public' in photo_data:
                values[fields.index('is_public')] = 1 if photo_data['is_public'] else 0

            cursor.execute(
                f"UPDATE user_photos SET {set_clause} WHERE id = ?",
                values + [photo_id]
            )
            conn.commit()
            conn.close()

            self._load_all_from_db()
            return True

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to update user photo {photo_id}: {e}")
            return False

    def delete_photo(self, photo_id: int, delete_physical: bool = False) -> bool:
        """
        Delete user photo

        Args:
            photo_id: Photo ID
            delete_physical: Whether to delete physical files

        Returns:
            True if successful
        """
        photo = self.get_photo_by_id(photo_id)
        if not photo:
            return False

        conn = self._get_db_connection()
        cursor = conn.cursor()

        try:
            # Delete database record
            cursor.execute("DELETE FROM user_photos WHERE id = ?", (photo_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            conn.close()

            if deleted:
                # Delete physical files if requested
                if delete_physical:
                    try:
                        # Delete main image
                        main_path = self.files_dir / photo.file_path
                        if main_path.exists():
                            main_path.unlink()

                        # Delete thumbnail
                        if photo.thumbnail_path:
                            thumb_path = self.files_dir / photo.thumbnail_path
                            if thumb_path.exists():
                                thumb_path.unlink()

                        logger.info(f"Deleted physical files for photo {photo_id}")
                    except Exception as e:
                        logger.warning(f"Failed to delete physical files: {e}")

                self.photos = [p for p in self.photos if p.id != photo_id]

            return deleted

        except Exception as e:
            conn.rollback()
            conn.close()
            logger.error(f"Failed to delete user photo {photo_id}: {e}")
            return False

    def query_photos(self, filter_obj: Optional[UserPhotoFilter] = None) -> List[UserPhoto]:
        """
        Query user photos with optional filter

        Args:
            filter_obj: UserPhotoFilter object

        Returns:
            List of matching user photos
        """
        results = list(self.photos)

        if not filter_obj or filter_obj.is_empty():
            return results

        # Apply filters
        if filter_obj.id is not None:
            results = [p for p in results if p.id == filter_obj.id]

        if filter_obj.photo_type:
            results = [p for p in results if p.photo_type == filter_obj.photo_type]

        if filter_obj.submitter_type:
            results = [p for p in results if p.submitter_type == filter_obj.submitter_type]

        if filter_obj.submitter_id is not None:
            results = [p for p in results if p.submitter_id == filter_obj.submitter_id]

        if filter_obj.laboratory_id is not None:
            results = [p for p in results if p.laboratory_id == filter_obj.laboratory_id]

        if filter_obj.is_public is not None:
            results = [p for p in results if p.is_public == filter_obj.is_public]

        # Pagination
        if filter_obj.offset is not None:
            results = results[filter_obj.offset:]
        if filter_obj.limit is not None:
            results = results[:filter_obj.limit]

        return results

    def get_photos_by_owner(self, submitter_type: str,
                            submitter_id: int,
                            photo_type: Optional[str] = None) -> List[UserPhoto]:
        """Get photos by owner"""
        filter_obj = UserPhotoFilter(
            submitter_type=submitter_type,
            submitter_id=submitter_id,
            photo_type=photo_type
        )
        return self.query_photos(filter_obj)

    def get_public_photos(self, photo_type: Optional[str] = None) -> List[UserPhoto]:
        """Get all public photos"""
        filter_obj = UserPhotoFilter(
            is_public=True,
            photo_type=photo_type
        )
        return self.query_photos(filter_obj)

    def get_lab_activity_photos(self, laboratory_id: int) -> List[UserPhoto]:
        """Get lab activity photos by laboratory"""
        filter_obj = UserPhotoFilter(
            photo_type="lab_activity",
            laboratory_id=laboratory_id,
            is_public=True
        )
        return self.query_photos(filter_obj)

    def _find_by_hash(self, file_hash: str) -> Optional[UserPhoto]:
        """Find photo by hash"""
        for photo in self.photos:
            if photo.file_hash == file_hash:
                return photo
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

    def _create_thumbnail(self, image_path: Path, output_dir: Path,
                          size: tuple = (200, 200)) -> Optional[str]:
        """
        Create thumbnail for image

        Args:
            image_path: Path to original image
            output_dir: Directory to save thumbnail
            size: Thumbnail size (width, height)

        Returns:
            Thumbnail filename or None if failed
        """
        try:
            from PIL import Image

            # Open image
            img = Image.open(image_path)

            # Convert to RGB if necessary (for PNG with transparency)
            if img.mode in ('RGBA', 'LA', 'P'):
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
                img = background
            elif img.mode != 'RGB':
                img = img.convert('RGB')

            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Save thumbnail
            thumb_filename = f"thumb_{image_path.stem}.jpg"
            thumb_path = output_dir / thumb_filename
            img.save(thumb_path, 'JPEG', quality=85)

            return thumb_filename

        except ImportError:
            logger.warning("PIL not available, skipping thumbnail creation")
            return None
        except Exception as e:
            logger.error(f"Failed to create thumbnail: {e}")
            return None
