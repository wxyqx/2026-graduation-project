"""【候选人端业务请求模板】"""
from pydantic import BaseModel, Field


class PortalApplyIn(BaseModel):
    """候选人投递：只选岗位，简历用「当前版本」，表单在投递后补填。"""

    pos_id: int = Field(description="应聘岗位编号")

    model_config = {"json_schema_extra": {"examples": [{"pos_id": 1}]}}
