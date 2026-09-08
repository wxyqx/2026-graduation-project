from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Position(Base):
    __tablename__ = "Position"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    position_name: Mapped[str | None] = mapped_column(String(100))
    owner: Mapped[str | None] = mapped_column(String(100))
    position_requirements: Mapped[str | None] = mapped_column(String(2000))
