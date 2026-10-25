"""
【Operation_Log 表：操作日志】——技术管理端排查问题用

只记「谁、什么时候、对什么、做了什么」，不存密码、不存文件内容。
写日志失败不能影响主业务，所以调用方一律用 try/except 包住（见 services/log_service.py）。
"""
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class OperationLog(Base):
    __tablename__ = "Operation_Log"

    id: Mapped[int] = mapped_column("ID", BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column("User_ID", Integer)
    username: Mapped[str | None] = mapped_column("Username", String(50))  # 快照：账号删了也能看
    role: Mapped[str | None] = mapped_column("Role", String(20))
    action: Mapped[str] = mapped_column("Action", String(50), nullable=False)
    target_type: Mapped[str | None] = mapped_column("Target_Type", String(30))
    target_id: Mapped[int | None] = mapped_column("Target_ID", Integer)
    detail_json: Mapped[str | None] = mapped_column("Detail_JSON", Text)
    ip: Mapped[str | None] = mapped_column("IP", String(45))
    create_time: Mapped[datetime] = mapped_column("Create_Time", DateTime, nullable=False)
