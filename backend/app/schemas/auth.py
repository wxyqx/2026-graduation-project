"""【认证相关的表格模板】注册表、登录表、返回给前端的用户信息和 token。"""
from datetime import datetime

from pydantic import BaseModel, Field


class RegisterIn(BaseModel):
    """注册时要填的表。In 结尾 = 「进来的数据」（浏览器发给我们）。"""

    username: str = Field(min_length=2, max_length=50)  # 用户名 2～50 个字
    password: str = Field(min_length=6, max_length=72)  # 密码至少 6 位；72 是 bcrypt 算法能处理的上限


class LoginIn(BaseModel):
    """登录时要填的表。登录不限制长度——填错了统一回「用户名或密码错误」就行。"""

    username: str
    password: str


class UserOut(BaseModel):
    """回给前端的用户信息。Out 结尾 = 「出去的数据」。注意：绝对不含密码哈希。"""

    id: int
    username: str
    create_time: datetime | None


class TokenOut(BaseModel):
    """登录 / 注册成功后回给前端的东西：一张通行证 + 用户信息。"""

    token: str  # 通行证本体，前端要保存好，以后每次请求都带上
    token_type: str = "bearer"  # 通行证类型，固定是 bearer（「持有者」的意思：谁拿着谁就是）
    user: UserOut
