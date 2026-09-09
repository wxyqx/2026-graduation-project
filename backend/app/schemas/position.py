"""【岗位相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class PositionIn(BaseModel):
    """新建岗位要填的表。只有岗位名称是必填的。"""

    position_name: str = Field(min_length=1, max_length=100, description="岗位名称（必填）。例：Java高级工程师")
    owner: str | None = Field(default=None, max_length=100, description="招聘负责人，可不填。例：王HR")
    position_requirements: str | None = Field(
        default=None,
        max_length=2000,
        description="岗位要求 / 职位描述（JD）。AI 筛简历就是拿简历跟这段话比，写得越具体 AI 判断越准，最多 2000 字",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "position_name": "Java高级工程师",
                    "owner": "王HR",
                    "position_requirements": "3年以上Java开发经验，熟悉Spring Boot、MySQL、Redis；有电商系统经验优先",
                }
            ]
        }
    }


class PositionOut(BaseModel):
    """回给前端的岗位信息，多带一个「这个岗位有多少人投了」方便列表页展示。"""

    id: int = Field(description="岗位编号。别的接口要用到岗位时（比如建投递）就填这个数字")
    position_name: str | None = Field(description="岗位名称")
    owner: str | None = Field(description="负责人")
    position_requirements: str | None = Field(description="岗位要求")
    application_count: int = Field(default=0, description="这个岗位已经收到多少条投递。大于 0 的岗位不能删")


class PositionUpdate(BaseModel):
    """编辑岗位时填的表。所有字段都可不填——没填的就保持原样不动。"""

    position_name: str | None = Field(default=None, min_length=1, max_length=100, description="新的岗位名称，不改就别传")
    owner: str | None = Field(default=None, max_length=100, description="新的负责人，不改就别传")
    position_requirements: str | None = Field(default=None, max_length=2000, description="新的岗位要求，不改就别传")

    model_config = {"json_schema_extra": {"examples": [{"owner": "李HR"}]}}
