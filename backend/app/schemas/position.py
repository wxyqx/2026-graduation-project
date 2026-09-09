"""【岗位相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class PositionIn(BaseModel):
    """新建岗位要填的表。只有岗位名称是必填的。"""

    position_name: str = Field(min_length=1, max_length=100)
    owner: str | None = Field(default=None, max_length=100)  # 「str | None」= 可以是文字，也可以不填
    position_requirements: str | None = Field(default=None, max_length=2000)


class PositionOut(BaseModel):
    """回给前端的岗位信息，多带一个「这个岗位有多少人投了」方便列表页展示。"""

    id: int
    position_name: str | None
    owner: str | None
    position_requirements: str | None
    application_count: int = 0


class PositionUpdate(BaseModel):
    """编辑岗位时填的表。所有字段都可不填——没填的就保持原样不动。"""

    position_name: str | None = Field(default=None, min_length=1, max_length=100)
    owner: str | None = Field(default=None, max_length=100)
    position_requirements: str | None = Field(default=None, max_length=2000)
