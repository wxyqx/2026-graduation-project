from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Candidate(Base):
    __tablename__ = "Candidate"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    create_time: Mapped[datetime | None] = mapped_column(DateTime)
    name: Mapped[str | None] = mapped_column(String(255))
    remark: Mapped[str | None] = mapped_column(String(500))
