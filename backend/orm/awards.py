"""awards ORM 模型（M1 后半③①——类型规范 G8 完整落地）。"""
from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.orm.base import Base


class Award(Base):
    __tablename__ = "awards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    image_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    certificate_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    match_status: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ocr_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    extract_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    competition_name_in_file: Mapped[str | None] = mapped_column(String(200), nullable=True)
    track: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issuer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    group_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    winner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supervisor_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    award_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    competition_level: Mapped[str | None] = mapped_column(String(20), nullable=True)
    date: Mapped[str | None] = mapped_column(String(10), nullable=True)   # ISO 日期
    project_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    granted_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    related_student_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    edition: Mapped[int | None] = mapped_column(Integer)
    year: Mapped[int | None] = mapped_column(Integer)
    competition_id: Mapped[int | None] = mapped_column(Integer)
    is_abnormal: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    submitter_type: Mapped[str | None] = mapped_column(String(20))
    submitter_id: Mapped[int | None] = mapped_column(Integer)             # users.id（M1 已统一）
    submit_time: Mapped[str | None] = mapped_column(String(30), nullable=True)
    laboratory_id: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    updated_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    llm_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
