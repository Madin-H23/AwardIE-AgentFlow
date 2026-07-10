"""
LLM缓存数据库

用于缓存LLM的调用结果，避免重复调用
"""
import sqlite3
import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ExtractCacheDB:
    """
    LLM缓存数据库

    使用SQLite存储LLM调用结果，通过提示词哈希检索

    使用示例:
        >>> cache = ExtractCacheDB("database/extract_cache.db")
        >>> 
        >>> # 保存缓存
        >>> cache.save("prompt_hash_123", "提示词内容", "LLM响应")
        >>> 
        >>> # 获取缓存
        >>> result = cache.get("prompt_hash_123")
        >>> 
        >>> # 删除缓存
        >>> cache.delete("prompt_hash_123")
    """

    def __init__(self, db_path: str):
        """
        初始化缓存数据库

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._init_db()
        logger.info(f"LLM缓存数据库初始化完成: {db_path}")

    def _init_db(self) -> None:
        """初始化数据库表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS extract_cache (
                prompt_hash TEXT PRIMARY KEY,
                llm_prompt TEXT NOT NULL,
                llm_response TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 创建索引
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_extract_cache_created_at
            ON extract_cache(created_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_extract_cache_accessed_at
            ON extract_cache(accessed_at)
        """)

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def save(self, prompt_hash: str, llm_prompt: str, llm_response: str) -> bool:
        """
        保存缓存

        Args:
            prompt_hash: 提示词哈希（主键）
            llm_prompt: LLM提示词
            llm_response: LLM响应

        Returns:
            是否保存成功
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR REPLACE INTO extract_cache
                (prompt_hash, llm_prompt, llm_response, accessed_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (prompt_hash, llm_prompt, llm_response))

            conn.commit()
            conn.close()

            logger.debug(f"保存缓存: {prompt_hash[:16]}...")
            return True

        except Exception as e:
            logger.error(f"保存缓存失败: {e}")
            return False

    def get(self, prompt_hash: str) -> Optional[str]:
        """
        获取缓存

        Args:
            prompt_hash: 提示词哈希

        Returns:
            LLM响应文本，不存在返回None
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT llm_response FROM extract_cache
                WHERE prompt_hash = ?
            """, (prompt_hash,))

            row = cursor.fetchone()
            conn.close()

            if row:
                self._update_access_time(prompt_hash)
                return row["llm_response"]

            return None

        except Exception as e:
            logger.error(f"获取缓存失败: {e}")
            return None

    def delete(self, prompt_hash: Optional[str] = None) -> int:
        """
        删除缓存

        Args:
            prompt_hash: 提示词哈希，如果为None则删除所有缓存

        Returns:
            删除的记录数
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            if prompt_hash:
                cursor.execute(
                    "DELETE FROM extract_cache WHERE prompt_hash = ?",
                    (prompt_hash,)
                )
            else:
                cursor.execute("DELETE FROM extract_cache")

            count = cursor.rowcount
            conn.commit()
            conn.close()

            if prompt_hash:
                logger.debug(f"删除缓存: {prompt_hash[:16]}...")
            else:
                logger.info(f"清空所有缓存，共 {count} 条")

            return count

        except Exception as e:
            logger.error(f"删除缓存失败: {e}")
            return 0

    def _update_access_time(self, prompt_hash: str) -> None:
        """更新访问时间"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE extract_cache
                SET accessed_at = CURRENT_TIMESTAMP
                WHERE prompt_hash = ?
            """, (prompt_hash,))

            conn.commit()
            conn.close()

        except Exception:
            pass

    def get_all_hashes(self) -> List[str]:
        """
        获取所有提示词哈希

        Returns:
            提示词哈希列表
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT prompt_hash FROM extract_cache ORDER BY accessed_at DESC")
            rows = cursor.fetchall()
            conn.close()

            return [row["prompt_hash"] for row in rows]

        except Exception as e:
            logger.error(f"获取提示词哈希列表失败: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            统计信息字典
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM extract_cache")
            total = cursor.fetchone()["count"]

            cursor.execute("""
                SELECT
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest
                FROM extract_cache
            """)
            time_info = cursor.fetchone()

            conn.close()

            return {
                "total": total,
                "oldest": time_info["oldest"],
                "newest": time_info["newest"]
            }

        except Exception as e:
            logger.error(f"获取缓存统计失败: {e}")
            return {
                "total": 0,
                "oldest": None,
                "newest": None
            }

    def clear_old(self, days: int = 30) -> int:
        """
        清理指定天数之前的旧缓存

        Args:
            days: 天数

        Returns:
            删除的记录数
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM extract_cache
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days,))

            count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"清理了 {count} 条旧缓存（{days}天前）")
            return count

        except Exception as e:
            logger.error(f"清理旧缓存失败: {e}")
            return 0

    def clear_unused(self, days: int = 7) -> int:
        """
        清理指定天数未访问的缓存

        Args:
            days: 天数

        Returns:
            删除的记录数
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                DELETE FROM extract_cache
                WHERE accessed_at < datetime('now', '-' || ? || ' days')
            """, (days,))

            count = cursor.rowcount
            conn.commit()
            conn.close()

            logger.info(f"清理了 {count} 条未访问缓存（{days}天未访问）")
            return count

        except Exception as e:
            logger.error(f"清理未访问缓存失败: {e}")
            return 0

    def __str__(self) -> str:
        stats = self.get_stats()
        return f"ExtractCacheDB(total={stats['total']})"

    def __repr__(self) -> str:
        return self.__str__()
