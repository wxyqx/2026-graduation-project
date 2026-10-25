"""
【Candidate 表：候选人】

只存最基础的身份信息：姓名、手机号、邮箱、备注。
手机号是候选人端的登录账号（唯一），但允许为空——AI 录入或 HR 手工建档时可能还没拿到手机号，
等 HR 补上后系统才自动开通账号。没有手机号 = 不能登录。

注意：系统里「同名」仍然可能被当成同一个人（AI 录入的旧逻辑），
但登录一律按手机号，不按姓名，避免同名串账号。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Candidate(Base):
    __tablename__ = "Candidate"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)  # 候选人编号
    create_time: Mapped[datetime | None] = mapped_column(DateTime)  # 录入时间
    name: Mapped[str | None] = mapped_column(String(255))  # 姓名
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)  # 手机号：候选人端登录账号
    email: Mapped[str | None] = mapped_column(String(100))  # 邮箱（可空，仅展示，不做验证）
    remark: Mapped[str | None] = mapped_column(String(500))  # 备注，比如「内推」「AI录入」
    # 负责人 HR：默认 = 建档 / 上传简历录入的 HR；技术管理员可单个或批量改。
    # 负责人能编辑该候选人的全部关卡；非负责人的 HR 只能编辑自己负责的关卡，其余只读
    owner_id: Mapped[int | None] = mapped_column(
        "owner_id", Integer, ForeignKey("User.ID", ondelete="SET NULL"), nullable=True
    )
    # ---- HR 从简历摘录的个人信息（与候选人填写的表单答卷是两套数据，各自独立）----
    onboard_date: Mapped[str | None] = mapped_column(String(50))  # 到岗时间，可写「随时」等
    school: Mapped[str | None] = mapped_column(String(100))  # 毕业院校
    degree: Mapped[str | None] = mapped_column(String(20))  # 学历
    major: Mapped[str | None] = mapped_column(String(100))  # 专业
    expected_salary: Mapped[str | None] = mapped_column(String(50))  # 期望薪资
    work_location: Mapped[str | None] = mapped_column(String(100))  # 期望工作地点
    hire_type: Mapped[str | None] = mapped_column(String(20))  # 招聘类型（校招/社招）
    work_experience: Mapped[str | None] = mapped_column(Text)  # 工作经历
    update_time: Mapped[datetime | None] = mapped_column(DateTime)  # 最近更新时间

    # 负责人 HR（懒加载，只在用到时查）
    owner = relationship("User", foreign_keys=[owner_id])
