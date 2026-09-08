from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class User(Base):
    __tablename__ = "User"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    create_time: Mapped[datetime | None] = mapped_column(DateTime)
