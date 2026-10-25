"""【技术管理端的表格模板】账号、改密、状态。"""
from datetime import datetime

from pydantic import BaseModel, Field


class TechPasswordIn(BaseModel):
    current_password: str = Field(description="当前密码")
    new_password: str = Field(min_length=6, max_length=72, description="新密码，至少 6 位")


class TechAccountIn(BaseModel):
    """技术管理员创建 HR / 技术管理员账号。候选人账号不能在这里建（由手机号自动开通）。"""

    username: str = Field(min_length=2, max_length=50, description="登录用户名")
    password: str = Field(default="admin", min_length=6, max_length=72, description="初始密码，默认 admin")
    role: str = Field(default="hr", description="hr=HR / admin=技术管理员")


class TechStatusIn(BaseModel):
    is_active: bool = Field(description="true=启用；false=停用")


class TechAccountOut(BaseModel):
    id: int
    username: str | None = Field(default=None, description="候选人账号为 null")
    name: str | None = Field(default=None, description="显示名：候选人姓名或用户名")
    role: str
    phone: str | None = Field(default=None, description="候选人手机号")
    candidate_id: int | None = None
    is_active: bool
    last_login_time: datetime | None = None
    create_time: datetime | None = None
