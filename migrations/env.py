from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# M1 后半③③：接入 ORM 模型元数据（autogenerate 依据）
from backend.orm.base import Base
import backend.orm.users      # noqa: F401
import backend.orm.pending    # noqa: F401
import backend.orm.awards     # noqa: F401
import backend.orm.audit_log  # noqa: F401
target_metadata = Base.metadata


def _resolve_db_path():
    """主库路径。

    覆盖优先级：ALEMBIC_DB 环境变量 > -x db=<path> > config 默认路径
    （-x 在部分 alembic 子命令下解析不稳定，测试优先用环境变量）。
    """
    from config.loader import get_config
    from pathlib import Path
    import os
    x_arg = os.environ.get("ALEMBIC_DB") or context.get_x_argument(as_dictionary=True).get("db")
    if x_arg:
        return Path(x_arg)
    return get_config().get_path('database', 'competitions_db')


def _db_url():
    """主库 URL（Windows 路径正斜杠）。"""
    return f"sqlite:///{str(_resolve_db_path().resolve()).replace(chr(92), '/')}"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = _db_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode（复用 G1 契约：外键/WAL/busy_timeout）。

    库路径必须经 _resolve_db_path（ALEMBIC_DB/-x 可指向测试库）——不得直接
    build_engine() 走默认库，否则测试迁移会误跑生产库（曾致真实库被反复迁移）。
    """
    from backend.orm.base import build_engine
    connectable = build_engine(str(_resolve_db_path()))   # 复用 ORM engine（含 PRAGMA 事件监听）

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
