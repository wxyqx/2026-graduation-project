"""
【AI_API_Config 表：AI 接口配置】
系统自己不会「思考」，筛选简历要请外面的 AI（大模型）帮忙。
请 AI 帮忙需要知道三件事：去哪找它（base_url）、凭什么让它干活（api_key，像门票）、
请哪一位（model，比如 glm-4-flash）。这张表就存这些。

可以存多个配置、同时启用多个。批量筛简历时轮着用，避免某一家限流（一分钟只让调几次）。

User_ID：这条配置是谁添加的。每个用户只能看到、修改自己的配置。
api_key 明文存储——因为是自用系统、数据库只在自己电脑上。
"""
from sqlalchemy import ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AiApiConfig(Base):
    __tablename__ = "AI_API_Config"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)  # 给配置起个名字，比如「GLM 免费版」
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)  # AI 接口的网址
    api_key: Mapped[str] = mapped_column(String(255), nullable=False)  # 密钥（门票）
    model: Mapped[str] = mapped_column(String(100), nullable=False)  # 模型名
    is_enabled: Mapped[int] = mapped_column(SmallInteger, default=0)  # 1 = 启用，0 = 停用（数据库里用数字存开关）
    user_id: Mapped[int] = mapped_column("User_ID", Integer, ForeignKey("User.ID"), nullable=False)  # 属于哪个用户
