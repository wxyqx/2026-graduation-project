"""【候选人相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    """新建候选人：姓名必填，备注可选。"""

    name: str = Field(min_length=1, max_length=255, description="姓名（必填）。系统按姓名认人：同名 = 同一个人")
    remark: str | None = Field(default=None, max_length=500, description="备注，可不填。例：内推 / 猎头推荐 / 校招")

    model_config = {"json_schema_extra": {"examples": [{"name": "张三", "remark": "内推"}]}}


class CandidateUpdate(BaseModel):
    """编辑候选人：目前只允许改备注（姓名是识别同一个人的依据，不让随便改）。"""

    remark: str | None = Field(default=None, max_length=500, description="新的备注。传空字符串可以清空备注")

    model_config = {"json_schema_extra": {"examples": [{"remark": "已电话确认到岗时间"}]}}


class CandidateOut(BaseModel):
    """回给前端的候选人信息。"""

    id: int = Field(description="候选人编号。建投递时 can_id 填这个")
    name: str | None = Field(description="姓名")
    remark: str | None = Field(description="备注")
    create_time: datetime | None = Field(description="录入时间")
