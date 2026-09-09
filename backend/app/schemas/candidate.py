"""【候选人相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    """新建候选人：姓名必填，备注可选。"""

    name: str = Field(min_length=1, max_length=255)
    remark: str | None = Field(default=None, max_length=500)


class CandidateUpdate(BaseModel):
    """编辑候选人：目前只允许改备注（姓名是识别同一个人的依据，不让随便改）。"""

    remark: str | None = Field(default=None, max_length=500)


class CandidateOut(BaseModel):
    """回给前端的候选人信息。"""

    id: int
    name: str | None
    remark: str | None
    create_time: datetime | None
