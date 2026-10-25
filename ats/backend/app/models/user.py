"""
【User 表：登录账号】——三个端共用一张账号表，靠 role 区分身份

role 三种取值（照数据字典，不自造）：
    admin     ：技术管理员，进 /tech，管账号/配置/日志/备份
    hr        ：HR，进现有后台，管招聘全流程
    candidate ：候选人，进 /portal，只能看自己的东西

候选人账号没有用户名（username 为 NULL），登录用手机号；
手机号存在 Candidate 表里（Candidate.phone），这里只存 candidate_id 把两边连起来。

password_hash 存的不是密码本身，而是 bcrypt 搅碎后的哈希，见 services/security.py。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class User(Base):
    __tablename__ = "User"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    # HR / 技术管理员用用户名登录；候选人没有用户名（NULL）。MySQL 唯一索引允许多个 NULL。
    username: Mapped[str | None] = mapped_column(String(50), nullable=True, unique=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="hr")  # admin / hr / candidate
    # 候选人账号专属：指向 Candidate.ID；HR 与管理员为 NULL
    candidate_id: Mapped[int | None] = mapped_column(
        "candidate_id", Integer, ForeignKey("Candidate.ID", ondelete="SET NULL"), nullable=True, unique=True
    )
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)  # 0=停用，禁止登录
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 最长 45 字符
    # 头像：直接存库；NULL=未设置（前端显示用户名首字占位）
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_mime: Mapped[str | None] = mapped_column(String(50))
    create_time: Mapped[datetime | None] = mapped_column(DateTime)

    # 候选人账号顺手把候选人资料带出来；管理员/HR 的 candidate 是 None
    candidate = relationship("Candidate", lazy="joined")
