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
    phone: str = Field(description="手机号，11 位（必填）。例：13800138000")
    real_name: str = Field(min_length=2, max_length=50, description="实名（必填）。例：张三")
    role: str = Field(default="hr", description="hr=HR / admin=技术管理员")


class TechStatusIn(BaseModel):
    is_active: bool = Field(description="true=启用；false=停用")


class TechAccountOut(BaseModel):
    id: int
    username: str | None = Field(default=None, description="候选人账号为 null")
    name: str | None = Field(default=None, description="显示名：候选人姓名或用户名")
    role: str
    phone: str | None = Field(default=None, description="候选人手机号（在 Candidate 表）或 HR/管理员手机号（在 User 表）")
    real_name: str | None = Field(default=None, description="HR/管理员实名；候选人为 null（姓名在 Candidate.name）")
    candidate_id: int | None = None
    is_active: bool
    close_reason: str | None = Field(default=None, description="停用原因：eliminated=淘汰销号（保存期内可恢复）；null=普通停用或已恢复")
    restore_deadline: datetime | None = Field(default=None, description="恢复截止时间（销号后 3 个月）；仅淘汰销号的账号有值")
    last_login_time: datetime | None = None
    create_time: datetime | None = None
