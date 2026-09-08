from sqlalchemy import ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AiApiConfig(Base):
    __tablename__ = "AI_API_Config"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    is_enabled: Mapped[int] = mapped_column(SmallInteger, default=0)
    user_id: Mapped[int] = mapped_column("User_ID", Integer, ForeignKey("User.ID"), nullable=False)
