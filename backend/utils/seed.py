"""系统初始化种子（FR-INIT，SRS 3.10）。

三项职责（均幂等，可重复执行）：
- FR-INIT-01 竞赛白名单种子：空库部署预置 84 条白名单竞赛（database/seed_competitions.json）
- FR-INIT-03 默认管理员：admins 为空时创建强随机密码管理员（一次性明文文件下发，不入 git）
- FR-INIT-02 RAG 知识库：需 docx 源文件，仅在入口打印指引（不自动索引）

用法：python scripts/init_system.py
"""
import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_JSON = PROJECT_ROOT / "database" / "seed_competitions.json"
DEFAULT_ADMIN = "admin"


def _connect(db_path):
    from backend.utils.db_connection import get_connection
    return get_connection(db_path)


def seed_competitions(db_path, seed_json: Path = None) -> int:
    """灌入白名单种子。仅在表为空时执行；按竞赛名查重，幂等。

    Returns:
        新插入条数。
    """
    seed_json = seed_json or SEED_JSON
    if not seed_json.exists():
        logger.warning("种子文件不存在: %s", seed_json)
        return 0
    rows = json.loads(seed_json.read_text(encoding="utf-8"))
    if not rows:
        return 0
    conn = _connect(db_path)
    try:
        existing = conn.execute("SELECT COUNT(*) FROM competitions").fetchone()[0]
        if existing:
            logger.info("competitions 已有 %d 条，跳过种子（幂等）", existing)
            return 0
        cols = list(rows[0].keys())
        placeholders = ",".join("?" * len(cols))
        inserted = 0
        conn.execute("BEGIN IMMEDIATE")
        for r in rows:
            try:
                conn.execute(
                    f"INSERT INTO competitions ({','.join(cols)}) VALUES ({placeholders})",
                    [r.get(c) for c in cols],
                )
                inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.execute("COMMIT")
        logger.info("种子已灌入 %d 条白名单竞赛", inserted)
        return inserted
    finally:
        conn.close()


def ensure_default_admin(db_path, out_txt: Path = None) -> str | None:
    """admins 为空时创建默认管理员（强随机密码，满足 12 位管理员策略）。

    明文初始密码写入一次性文件（database/init_admin_password.txt，gitignore 已覆盖 *.txt）。
    Returns:
        生成的明文初始密码；已存在管理员则返回 None。
    """
    conn = _connect(db_path)
    try:
        if conn.execute("SELECT COUNT(*) FROM admins").fetchone()[0]:
            return None
        from werkzeug.security import generate_password_hash
        from app.password_policy import generate_strong_password
        pwd = generate_strong_password(is_admin=True)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "INSERT INTO admins (username, name, password_hash, user_activated) VALUES (?,?,?,1)",
            (DEFAULT_ADMIN, "系统管理员", generate_password_hash(pwd)),
        )
        conn.execute("COMMIT")
        out_txt = out_txt or (Path(db_path).parent / "init_admin_password.txt")
        out_txt.write_text(
            f"默认管理员初始密码（一次性，请立即修改并妥善销毁本文件）\n用户名: {DEFAULT_ADMIN}\n密码: {pwd}\n",
            encoding="utf-8",
        )
        logger.info("默认管理员已创建，初始密码见 %s", out_txt)
        return pwd
    finally:
        conn.close()


def init_system(db_path=None) -> dict:
    """初始化总入口。"""
    if db_path is None:
        from config.loader import ConfigLoader
        db_path = ConfigLoader().get_path('database', 'competitions_db')
    result = {
        "seed_inserted": seed_competitions(db_path),
        "admin_created": ensure_default_admin(db_path) is not None,
        "rag_hint": "RAG 知识库索引需竞赛规则 docx 源文件，请运行 backend/rag/indexer.py 完成索引（FR-INIT-02）",
    }
    return result
