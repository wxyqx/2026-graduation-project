from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Application(Base):
    __tablename__ = "Application"
    __table_args__ = (UniqueConstraint("Can_ID", "Pos_ID", name="UK_Can_Pos"),)

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    can_id: Mapped[int] = mapped_column("Can_ID", Integer, ForeignKey("Candidate.ID"), nullable=False)
    pos_id: Mapped[int] = mapped_column("Pos_ID", Integer, ForeignKey("Position.ID"), nullable=False)

    ai_result: Mapped[str | None] = mapped_column(String(20))
    ai_comment: Mapped[str | None] = mapped_column(String(500))
    resume_submit_time: Mapped[datetime | None] = mapped_column(DateTime)
    resume_result: Mapped[str | None] = mapped_column(String(20))
    phone_time: Mapped[datetime | None] = mapped_column(DateTime)
    phone_result: Mapped[str | None] = mapped_column(String(20))
    test_time: Mapped[datetime | None] = mapped_column(DateTime)
    test_result: Mapped[str | None] = mapped_column(String(20))
    pro_time: Mapped[datetime | None] = mapped_column(DateTime)
    pro_result: Mapped[str | None] = mapped_column(String(20))
    hr_time: Mapped[datetime | None] = mapped_column(DateTime)
    hr_result: Mapped[str | None] = mapped_column(String(20))
    final_time: Mapped[datetime | None] = mapped_column(DateTime)
    final_result: Mapped[str | None] = mapped_column(String(20))

    current_stage: Mapped[str | None] = mapped_column(String(20))
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    create_time: Mapped[datetime | None] = mapped_column(DateTime)
    update_time: Mapped[datetime | None] = mapped_column(DateTime)

    candidate = relationship("Candidate", lazy="joined")
    position = relationship("Position", lazy="joined")
