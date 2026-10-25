"""【Email_Outbox 表：邮件发件箱】v3.16

站内通知的邮件是「附赠渠道」，失败不能影响通知；但失败也不该静默丢掉。
每封邮件的每次投递都记一行：pending → sent / failed（attempts 满 3 次为 failed）。
清扫时机：每次发送新邮件前、后端启动时。技术管理端可查。
"""
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"  # Windows MySQL 表名统一小写存储，模型直接用小写保持与 alembic/库一致

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    notice_id: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 关联的站内通知
    to_email: Mapped[str] = mapped_column(String(100), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200))  # 冗余记标题，排查时不用回查通知
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending/sent/failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    create_time: Mapped[datetime | None] = mapped_column(DateTime)
    update_time: Mapped[datetime | None] = mapped_column(DateTime)
