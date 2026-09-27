"""
【Candidate 表：候选人】
来应聘的人。只存最基本的信息：姓名、备注、什么时候录进来的。

约定：同一个姓名 = 同一个人（自用系统，不搞复杂的查重）。
AI 录入简历时，如果姓名已经存在就直接复用，不会再建一个。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Candidate(Base):
    __tablename__ = "Candidate"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)  # 候选人编号
    create_time: Mapped[datetime | None] = mapped_column(DateTime)  # 录入时间
    name: Mapped[str | None] = mapped_column(String(255))  # 姓名
    remark: Mapped[str | None] = mapped_column(String(500))  # 备注，比如「内推」「AI录入」
