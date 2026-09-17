"""【候选人相关的表格模板】"""
from datetime import datetime

from pydantic import BaseModel, Field


class CandidateIn(BaseModel):
    """新建候选人：姓名必填，备注可选。"""

    name: str = Field(min_length=1, max_length=255, description="姓名（必填）。系统按姓名认人：同名 = 同一个人")
    remark: str | None = Field(default=None, max_length=500, description="备注，可不填。例：内推 / 猎头推荐 / 校招")

    model_config = {"json_schema_extra": {"examples": [{"name": "张三", "remark": "内推"}]}}


class CandidateUpdate(BaseModel):
    """编辑候选人：可以改备注，也可以改姓名。

    **关于改姓名**：AI 识别简历有时会把名字认错（比如把 PDF 文件名当成了姓名），
    这里提供人工纠正。改名不影响任何投递记录——投递是按候选人编号关联的，
    所以历史进度、各阶段时间线都原样保留。姓名不能改成空。
    """

    name: str | None = Field(default=None, min_length=1, max_length=255, description="新的姓名，不传=不改")
    remark: str | None = Field(default=None, max_length=500, description="新的备注。传空字符串可以清空备注")
    confirm_duplicate: bool = Field(
        default=False,
        description="重名确认：改成与已有候选人相同的姓名时，第一次会返回 409；确认无误后带 true 再提交一次即可",
    )

    model_config = {
        "json_schema_extra": {"examples": [{"remark": "已电话确认到岗时间"}, {"name": "樊浩"}]}
    }


class CandidateOut(BaseModel):
    """回给前端的候选人信息。"""

    id: int = Field(description="候选人编号。建投递时 can_id 填这个")
    name: str | None = Field(description="姓名")
    remark: str | None = Field(description="备注")
    create_time: datetime | None = Field(description="录入时间")
    application_count: int = Field(default=0, description="这名候选人名下有几条投递（删除前会连带删除这些）")
