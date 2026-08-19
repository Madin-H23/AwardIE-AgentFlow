"""users ORM 模型（M1 后半②——按类型规范 G8，映射表 2026-08-19_字段类型规范映射表.md）。

String(N) 对应目标 VARCHAR(N)：SQLite 下仍为 TEXT affinity（无行为差异），
迁移 MySQL/PG 时语义正确（长度校验/默认值能力）。
"""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.orm.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    login_code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(50))
    role: Mapped[str] = mapped_column(String(20))  # student|teacher|admin
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    user_activated: Mapped[int] = mapped_column(Integer, default=1)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qq: Mapped[str | None] = mapped_column(String(50), nullable=True)
    skills: Mapped[str | None] = mapped_column(nullable=True)   # 长文本保留 TEXT
    profile_is_public: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # 学生角色字段
    major: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # 教师角色字段
    title: Mapped[str | None] = mapped_column(String(50), nullable=True)
    department: Mapped[str | None] = mapped_column(String(50), nullable=True)
    id_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    needs_password_change: Mapped[int] = mapped_column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<User {self.id} {self.login_code} ({self.role})>"
