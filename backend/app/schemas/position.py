from datetime import datetime

from pydantic import BaseModel, Field


class PositionIn(BaseModel):
    position_name: str = Field(min_length=1, max_length=100)
    owner: str | None = Field(default=None, max_length=100)
    position_requirements: str | None = Field(default=None, max_length=2000)


class PositionOut(BaseModel):
    id: int
    position_name: str | None
    owner: str | None
    position_requirements: str | None
    application_count: int = 0


class PositionUpdate(BaseModel):
    position_name: str | None = Field(default=None, min_length=1, max_length=100)
    owner: str | None = Field(default=None, max_length=100)
    position_requirements: str | None = Field(default=None, max_length=2000)
