"""【认证相关的表格模板】注册表、登录表、返回给前端的用户信息和 token。

Field(description=...) 里的中文会显示在 /docs 网页每个格子旁边；
json_schema_extra 里的 examples 会作为网页上「填写示例」自动出现，点 Try it out 就能直接用。
"""
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    """注册时要填的表。In 结尾 = 「进来的数据」（浏览器发给我们）。"""

    username: str = Field(min_length=2, max_length=50, description="用户名，2～50 个字，登录时用它。例：xiaoming")
    password: str = Field(min_length=6, max_length=72, description="密码，至少 6 位。只会存「搅碎后的哈希」，谁也看不到原文")

    model_config = {"json_schema_extra": {"examples": [{"username": "xiaoming", "password": "secret123"}]}}


class LoginIn(BaseModel):
    """登录时要填的表。登录不限制长度——填错了统一回「用户名或密码错误」就行。"""

    username: str = Field(description="注册时填的用户名")
    password: str = Field(description="注册时填的密码")

    model_config = {"json_schema_extra": {"examples": [{"username": "xiaoming", "password": "secret123"}]}}


class ProfileUpdateIn(BaseModel):
    """修改个人信息要填的表。用户名必填；只有「要改密码」时才需要把密码三项一起填。"""

    username: str = Field(min_length=2, max_length=50, description="用户名，2～50 个字，登录时用它")
    current_password: str | None = Field(
        default=None, description="当前密码：只在要改密码时必填，用于验证身份（防止别人拿到 token 就改密码）"
    )
    new_password: str | None = Field(
        default=None, min_length=6, max_length=72, description="新密码，至少 6 位；不填 = 不修改密码"
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {"username": "xiaoming"},
                {"username": "xiaoming", "current_password": "secret123", "new_password": "newsecret456"},
            ]
        }
    }


class UserOut(BaseModel):
    """回给前端的用户信息。Out 结尾 = 「出去的数据」。注意：绝对不含密码哈希。"""

    id: int = Field(description="用户编号，数据库自动分配")
    username: str = Field(description="用户名")
    create_time: datetime | None = Field(description="注册时间")


class TokenOut(BaseModel):
    """登录 / 注册成功后回给前端的东西：一张通行证 + 用户信息。"""

    token: str = Field(description="通行证（JWT）。复制这一串去点右上角 Authorize，之后所有接口就都能用了。7 天有效")
    token_type: str = Field(default="bearer", description="通行证类型，固定 bearer（意思是「谁拿着谁就是」）")
    user: UserOut = Field(description="你是谁")
