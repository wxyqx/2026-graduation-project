from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.user import User  # noqa: E402
from app.models.position import Position  # noqa: E402
from app.models.candidate import Candidate  # noqa: E402
from app.models.application import Application  # noqa: E402
from app.models.ai_api_config import AiApiConfig  # noqa: E402

__all__ = ["Base", "User", "Position", "Candidate", "Application", "AiApiConfig"]
