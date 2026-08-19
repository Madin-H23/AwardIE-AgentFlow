"""pending_achievements ORM 模型（M1 后半②——按类型规范 G8 + 保留 is_valid 生成列语义）。

生成列说明：SQLAlchemy 用 `computed` 表达 VIRTUAL 生成列；
is_valid 由 validation_result JSON 推导（与 M3 落地的一致）。
"""
from sqlalchemy import Computed, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.orm.base import Base


class PendingAchievement(Base):
    __tablename__ = "pending_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    achievement_type: Mapped[str | None] = mapped_column(String(20))
    achievement_data: Mapped[str] = mapped_column(Text)               # JSON 长文本
    validation_result: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitter_type: Mapped[str | None] = mapped_column(String(20))
    submitter_id: Mapped[int | None] = mapped_column(Integer)         # users.id（M1 已统一）
    submit_time: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20))            # pending|submit|rejected|archived
    reviewer_id: Mapped[int | None] = mapped_column(Integer)
    review_time: Mapped[str | None] = mapped_column(String(30), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str | None] = mapped_column(String(30), nullable=True)
    file_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    assigned_reviewer_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    reviewer_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_hash: Mapped[str] = mapped_column(String(64), default="")
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    llm_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    ext_info: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON 长文本
    session_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    laboratory_id: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)           # 乐观锁
    # M3 生成列：is_valid 由 validation_result JSON 推导（VIRTUAL）
    is_valid: Mapped[int | None] = mapped_column(
        Integer,
        Computed("CASE WHEN json_extract(validation_result, '$.is_valid') IS NULL THEN NULL "
                 "ELSE CAST(json_extract(validation_result, '$.is_valid') AS INTEGER) END",
                 persisted=False),
        nullable=True)
