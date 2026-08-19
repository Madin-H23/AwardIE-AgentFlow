"""achievement_audit_log ORM 模型（M1 后半②——类型规范 G8）。"""
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.orm.base import Base


class AuditLog(Base):
    __tablename__ = "achievement_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    achievement_id: Mapped[int] = mapped_column(Integer)
    achievement_kind: Mapped[str | None] = mapped_column(String(20))
    trace_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action_type: Mapped[int] = mapped_column(Integer)                  # 1-11
    action_result: Mapped[int] = mapped_column(Integer, default=0)
    operator_id: Mapped[int | None] = mapped_column(Integer)           # users.id（AI 时 NULL）
    operator_code: Mapped[str] = mapped_column(String(50))
    operator_name: Mapped[str] = mapped_column(String(50))
    operator_role: Mapped[int | None] = mapped_column(Integer)         # 1学生/2教师/3AI/4管理员
    operator_ip: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_batch_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    change_detail: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
