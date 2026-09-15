"""
【App_Setting 表：系统设置（键值对）】
存「系统设置页」里那些需要保存、但又不属于某个具体业务的配置。
目前只用来存 AI 筛选提示词（setting_key = 'ai_prompt'）。

设计成 键值对（key-value）而不是给每个设置单独一列，好处是以后再加设置项不用改表结构。

User_ID：这条设置是谁的。每个用户各自一份提示词，互不影响。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class AppSetting(Base):
    __tablename__ = "App_Setting"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column("User_ID", Integer, ForeignKey("User.ID"), nullable=False)
    setting_key: Mapped[str] = mapped_column(String(50), nullable=False)  # 设置项名字，例：ai_prompt
    setting_value: Mapped[str | None] = mapped_column(Text)  # 设置内容
    update_time: Mapped[datetime | None] = mapped_column(DateTime)
