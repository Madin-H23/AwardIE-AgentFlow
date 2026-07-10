"""
OCR缓存数据库管理模块

提供OCR识别结果的数据库缓存功能
"""
import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from ..utils.logger import setup_logger
from ..types import CacheStats

logger = logging.getLogger(__name__)


def init_cache_tables(db_path: str):
    """
    初始化缓存表

    Args:
        db_path: 数据库文件路径
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # OCR 缓存表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ocr_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                image_hash TEXT NOT NULL UNIQUE,
                ocr_text TEXT NOT NULL,
                provider TEXT NOT NULL,
                is_precise BOOLEAN NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引以提高查询性能
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ocr_cache_hash ON ocr_cache(image_hash)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ocr_cache_created_at ON ocr_cache(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ocr_cache_provider ON ocr_cache(provider)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ocr_cache_is_precise ON ocr_cache(is_precise)
        """)

        conn.commit()
        logger.info("OCR缓存表初始化完成")
    except sqlite3.Error as e:
        logger.error(f"初始化缓存表失败: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


class CacheDB:
    """OCR缓存数据库操作类"""

    def __init__(self, db_path: str):
        """
        初始化缓存数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            # 如果数据库文件不存在，创建目录
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 确保缓存表存在
        init_cache_tables(str(self.db_path))
        self.logger = setup_logger("CacheDB")

    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ========== OCR 缓存操作 ==========

    def get_ocr_cache(self, image_hash: str) -> Optional[tuple[str, str, bool]]:
        """
        获取 OCR 缓存

        Args:
            image_hash: 图片哈希值

        Returns:
            (OCR文本, Provider名称, is_precise) 元组，如果不存在返回 None
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT ocr_text, provider, is_precise, created_at FROM ocr_cache WHERE image_hash = ?",
                    (image_hash,)
                )
                row = cursor.fetchone()
                if row:
                    return (row['ocr_text'], row['provider'], bool(row['is_precise']))
        except Exception as e:
            self.logger.error(f"读取 OCR 缓存失败: {e}")
        return None

    def save_ocr_cache(self, image_hash: str, ocr_text: str, provider: str, is_precise: bool) -> bool:
        """
        保存 OCR 缓存
        
        逻辑：优先保持高精度结果
        - 如果数据库中已有高精度记录，而新传入的是低精度，则不覆盖
        - 其他情况都可以覆盖（包括：无记录、低精度->高精度、低精度->低精度、高精度->高精度）

        Args:
            image_hash: 图片哈希值
            ocr_text: OCR识别的纯文本
            provider: OCR提供者名称（如 "zhipu", "baidu", "paddle", "rapid"）
            is_precise: 是否为高精度识别

        Returns:
            是否保存成功
        """
        try:
            # 拒绝保存空文本，避免 API 失败/429 等返回空时覆盖已有有效缓存
            if not (ocr_text or "").strip():
                self.logger.debug(f"跳过保存空 OCR 结果 (image_hash: {image_hash})")
                return True  # 不写入，保留原有缓存

            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # 先查询是否存在该记录
                cursor.execute(
                    "SELECT is_precise FROM ocr_cache WHERE image_hash = ?",
                    (image_hash,)
                )
                existing_row = cursor.fetchone()
                
                if existing_row:
                    # 记录已存在，检查精度
                    existing_is_precise = bool(existing_row['is_precise'])
                    
                    # 如果现有记录是高精度，新记录是低精度，则不覆盖
                    if existing_is_precise and not is_precise:
                        self.logger.debug(f"跳过覆盖：保持高精度记录 (image_hash: {image_hash})")
                        return True  # 返回成功，但实际未更新
                
                # 其他情况：覆盖或插入新记录
                cursor.execute("""
                    INSERT OR REPLACE INTO ocr_cache (image_hash, ocr_text, provider, is_precise, updated_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (image_hash, ocr_text, provider, 1 if is_precise else 0))
                
                conn.commit()
                return True
        except Exception as e:
            self.logger.error(f"保存 OCR 缓存失败: {e}")
            return False

    def delete_ocr_cache(self, image_hash: Optional[str] = None) -> int:
        """
        删除 OCR 缓存

        Args:
            image_hash: 如果提供，删除指定哈希的缓存；否则删除所有

        Returns:
            删除的记录数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                if image_hash:
                    cursor.execute("DELETE FROM ocr_cache WHERE image_hash = ?", (image_hash,))
                else:
                    cursor.execute("DELETE FROM ocr_cache")
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"删除 OCR 缓存失败: {e}")
            return 0

    def clean_ocr_cache_by_age(self, days: int) -> int:
        """
        根据时间清理 OCR 缓存

        Args:
            days: 保留最近 N 天的缓存

        Returns:
            删除的记录数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    DELETE FROM ocr_cache
                    WHERE created_at < datetime('now', '-' || ? || ' days')
                """, (days,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"清理 OCR 缓存失败: {e}")
            return 0

    def get_cache_stats(self) -> CacheStats:
        """
        获取缓存统计信息

        Returns:
            统计信息对象
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute(
                    "SELECT COUNT(*) as count, MIN(created_at) as oldest, MAX(created_at) as newest FROM ocr_cache"
                )
                row = cursor.fetchone()

                return CacheStats(
                    count=row['count'] if row else 0,
                    oldest=row['oldest'] if row and row['oldest'] else None,
                    newest=row['newest'] if row and row['newest'] else None
                )
        except Exception as e:
            self.logger.error(f"获取缓存统计失败: {e}")
            return CacheStats(count=0, oldest=None, newest=None)
    
    def get_provider_stats(self) -> Dict[str, int]:
        """
        获取按提供者分组的缓存统计信息

        Returns:
            字典，键为provider名称，值为该provider的缓存数量
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT provider, COUNT(*) as count FROM ocr_cache GROUP BY provider"
                )
                return {row['provider']: row['count'] for row in cursor.fetchall()}
        except Exception as e:
            self.logger.error(f"获取提供者统计失败: {e}")
            return {}
    
    def delete_ocr_cache_by_provider(self, provider: str) -> int:
        """
        删除指定提供者的所有OCR缓存

        Args:
            provider: OCR提供者名称

        Returns:
            删除的记录数
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM ocr_cache WHERE provider = ?", (provider,))
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            self.logger.error(f"删除提供者缓存失败: {e}")
            return 0
