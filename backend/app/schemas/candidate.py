from datetime import datetime

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    remark: str | None = Field(default=None, max_length=500)


class CandidateUpdate(BaseModel):
    remark: str | None = Field(default=None, max_length=500)


class CandidateOut(BaseModel):
    id: int
    name: str | None
    remark: str | None
    create_time: datetime | None
