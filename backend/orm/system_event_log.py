"""SystemEventLog ORM 模型（阶段六 L1，与迁移 0006 同步）。"""
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.orm.base import Base


class SystemEventLog(Base):
    __tablename__ = "system_event_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_category: Mapped[str] = mapped_column(String(20))   # ocr|llm|breaker|auth|upload|db|security|system
    event_level: Mapped[str] = mapped_column(String(10))      # debug|info|warning|error|critical
    event_message: Mapped[str] = mapped_column(Text)
    trace_id: Mapped[Optional[str]] = mapped_column(String(64))
    operator_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"))
    operator_code: Mapped[Optional[str]] = mapped_column(String(50))
    detail: Mapped[Optional[str]] = mapped_column(Text)       # JSON
    source_module: Mapped[Optional[str]] = mapped_column(String(100))
    source_file: Mapped[Optional[str]] = mapped_column(String(200))
    source_line: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[Optional[str]] = mapped_column(Text, default=func.now())
