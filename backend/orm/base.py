"""SQLAlchemy ORM 基础（M1 后半①——复用 G1 连接契约，逐步取代手写 Manager）。

- engine 由 get_connection 契约驱动（WAL/foreign_keys/busy_timeout，见 backend.utils.db_connection）
- 本模块是 ORM 化起点：先定义 users 等核心模型，Manager 逐表退化为 Repository
- SQLAlchemy 2.0 风格（Mapped/mapped_column）
"""
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    """声明式基类。"""


def build_engine(db_path=None):
    """创建 engine（复用 G1 契约：WAL/外键/busy_timeout）。

    Args:
        db_path: 主库路径（默认从配置取）
    """
    if db_path is None:
        from config.loader import get_config_loader
        db_path = get_config_loader().get_path('database', 'competitions_db')
    # Windows 路径须正斜杠（反斜杠在 sqlite URL 中解析错误）
    db_abs = str(Path(db_path).resolve()).replace("\\", "/")
    engine = create_engine(f"sqlite:///{db_abs}", future=True)

    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()

    return engine


_engine = None
_SessionLocal = None


def get_engine():
    """进程级 engine 单例。"""
    global _engine
    if _engine is None:
        _engine = build_engine()
    return _engine


def get_session():
    """获取 Session（请求内用完 close）。"""
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), future=True)
    return _SessionLocal()


def reset_engine():
    """测试/配置热更新时重置单例。"""
    global _engine, _SessionLocal
    _engine = None
    _SessionLocal = None
