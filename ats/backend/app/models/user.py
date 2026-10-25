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
    # HR / 技术管理员的手机号（个人信息必填）；候选人的手机号在 Candidate 表，这里保持 NULL
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, unique=True)
    # HR / 技术管理员的实名（必填）；候选人的姓名在 Candidate 表
    real_name: Mapped[str | None] = mapped_column("real_name", String(50), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="hr")  # admin / hr / candidate
    # 候选人账号专属：指向 Candidate.ID；HR 与管理员为 NULL
    candidate_id: Mapped[int | None] = mapped_column(
        "candidate_id", Integer, ForeignKey("Candidate.ID", ondelete="SET NULL"), nullable=True, unique=True
    )
    is_active: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=1)  # 0=停用，禁止登录
    # 1=还在用默认密码：候选人每次登录都会弹「请修改密码」强提示，改完密码清零
    must_change_password: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    # 淘汰销号后的恢复时间：技术管理员在保存期（3 个月）内恢复账号时写入；
    # 晚于某次淘汰时间的恢复记录会让那次淘汰不再拦截登录
    restore_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_time: Mapped[datetime | None] = mapped_column(DateTime)
    last_login_ip: Mapped[str | None] = mapped_column(String(45))  # IPv6 最长 45 字符
    # 头像：直接存库；NULL=未设置（前端显示用户名首字占位）
    avatar: Mapped[bytes | None] = mapped_column(LargeBinary, deferred=True)
    avatar_mime: Mapped[str | None] = mapped_column(String(50))
    create_time: Mapped[datetime | None] = mapped_column(DateTime)

    # 候选人账号顺手把候选人资料带出来；管理员/HR 的 candidate 是 None
    # （两表之间有两个外键：candidate_id 与 Candidate.owner_id，必须显式指定本关系用哪个）
    candidate = relationship("Candidate", foreign_keys=[candidate_id], lazy="joined")
