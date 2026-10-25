"""
【Candidate_Notice 表：候选人通知】

笔试/专业面/HR面/终面通过时，若 HR 开启了该关的「通过通知」，按模板渲染后写一条记录；
候选人登录后前端拉取未读（Read_Time 为空）弹窗展示，点「知道了」写 Read_Time。
撤回再重新通过不会重复发：同一候选人 + 同一投递 + 同一关卡只发一条。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class CandidateNotice(Base):
    __tablename__ = "Candidate_Notice"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    candidate_id: Mapped[int] = mapped_column(
        "Candidate_ID", Integer, ForeignKey("Candidate.ID", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[int | None] = mapped_column(
        "Application_ID", Integer, ForeignKey("Application.ID", ondelete="SET NULL"), nullable=True
    )
    stage: Mapped[str] = mapped_column("Stage", String(20), nullable=False)
    title: Mapped[str] = mapped_column("Title", String(100), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    send_time: Mapped[datetime | None] = mapped_column("Send_Time", DateTime)  # NULL=草稿（候选人不可见）
    read_time: Mapped[datetime | None] = mapped_column("Read_Time", DateTime)
