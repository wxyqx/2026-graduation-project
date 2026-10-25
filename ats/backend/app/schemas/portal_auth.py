"""【候选人端认证的表格模板】手机号登录、我是谁、改密。"""
from datetime import datetime

from pydantic import BaseModel, Field


class PortalLoginIn(BaseModel):
    """候选人登录：手机号 + 密码（默认 admin）。"""

    phone: str = Field(description="手机号，例如 13800138000。必须先在系统里有这个手机号的候选人档案")
    password: str = Field(description="密码。初始密码统一为 admin，可在「我的资料」里修改")

    model_config = {
        "json_schema_extra": {"examples": [{"phone": "13800138000", "password": "admin"}]}
    }


class PortalPasswordIn(BaseModel):
    """候选人改密。"""

    current_password: str = Field(description="当前密码")
    new_password: str = Field(min_length=6, max_length=72, description="新密码，至少 6 位")


class PortalCandidateOut(BaseModel):
    """候选人自己的资料（不包含备注等内部字段）。"""

    id: int = Field(description="候选人编号")
    name: str | None = Field(description="姓名")
    phone: str | None = Field(description="手机号（登录账号）")
    email: str | None = Field(description="邮箱")
    create_time: datetime | None = Field(description="建档时间")


class PortalUserOut(BaseModel):
    """候选人账号信息。"""

    id: int = Field(description="账号编号")
    role: str = Field(description="角色，固定 candidate")
    candidate_id: int | None = Field(description="关联的候选人编号")
    is_active: bool = Field(description="账号是否启用")
    must_change_password: bool = Field(default=False, description="true=还在用默认密码，应提示修改")


class PortalTokenOut(BaseModel):
    """候选人登录成功后的返回。"""

    token: str = Field(description="通行证（JWT），有效期 30 天")
    token_type: str = Field(default="bearer", description="固定 bearer")
    user: PortalUserOut = Field(description="账号信息")
    candidate: PortalCandidateOut = Field(description="候选人资料")


class PortalMeOut(BaseModel):
    """候选人刷新页面时用：我是谁。"""

    user: PortalUserOut
    candidate: PortalCandidateOut
