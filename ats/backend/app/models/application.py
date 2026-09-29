"""
【Application 表：投递记录】——整个系统最核心的一张表
「某个候选人」投了「某个岗位」，就产生一条投递记录。

一条投递要闯 7 关（7 个阶段）：
    ai（AI筛选）→ resume（简历筛选）→ phone（电话沟通）
    → test（笔试）→ pro（专业面）→ hr（HR面）→ final（终面）

每一关有两个格子记录情况：xxx_result（结果：pass 通过 / fail 淘汰）和 xxx_time（什么时候过的这关）。
    例外：ai 这关只有结果没有时间，但多了一个 ai_comment 记 AI 给的理由

current_stage  ：现在走到第几关了
overall_status ：整体状态——pending 还在闯 / pass 全部通关（录用）/ fail 中途被淘汰
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


class Application(Base):
    __tablename__ = "Application"
    # 「同一个人 + 同一个岗位」只能有一条记录，数据库层面就不允许重复
    __table_args__ = (UniqueConstraint("Can_ID", "Pos_ID", name="UK_Can_Pos"),)

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)

    # 外键：这两列的值必须是 Candidate 表 / Position 表里真实存在的编号，
    # 就像快递单上的收件人必须是真实存在的人
    can_id: Mapped[int] = mapped_column("Can_ID", Integer, ForeignKey("Candidate.ID"), nullable=False)
    pos_id: Mapped[int] = mapped_column("Pos_ID", Integer, ForeignKey("Position.ID"), nullable=False)

    # ---- 7 关的记录格子 ----
    ai_result: Mapped[str | None] = mapped_column(String(20))  # 第 1 关 AI 筛选：pass / fail
    ai_comment: Mapped[str | None] = mapped_column(String(500))  # AI 给出的理由
    resume_submit_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 2 关 简历筛选的时间
    resume_result: Mapped[str | None] = mapped_column(String(20))  # 第 2 关 结果
    phone_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 3 关 电话沟通
    phone_result: Mapped[str | None] = mapped_column(String(20))
    test_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 4 关 笔试
    test_result: Mapped[str | None] = mapped_column(String(20))
    pro_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 5 关 专业面
    pro_result: Mapped[str | None] = mapped_column(String(20))
    hr_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 6 关 HR 面
    hr_result: Mapped[str | None] = mapped_column(String(20))
    final_time: Mapped[datetime | None] = mapped_column(DateTime)  # 第 7 关 终面
    final_result: Mapped[str | None] = mapped_column(String(20))

    # ---- 各关「人工记录」（v3.14 新增，全部可空）----
    # 原因：这关为什么通过 / 为什么淘汰（简历筛选 / 笔试 / 三个面试关都有）
    # 评价：面试评价正文，只有三个面试关（电话沟通 / 专业面 / HR面 / 终面）有
    # ai 这关不在此列，它的理由沿用上面的 ai_comment（由 AI 生成）
    resume_reason: Mapped[str | None] = mapped_column(Text)
    phone_reason: Mapped[str | None] = mapped_column(Text)
    phone_evaluation: Mapped[str | None] = mapped_column(Text)
    test_reason: Mapped[str | None] = mapped_column(Text)
    pro_reason: Mapped[str | None] = mapped_column(Text)
    pro_evaluation: Mapped[str | None] = mapped_column(Text)
    hr_reason: Mapped[str | None] = mapped_column(Text)
    hr_evaluation: Mapped[str | None] = mapped_column(Text)
    final_reason: Mapped[str | None] = mapped_column(Text)
    final_evaluation: Mapped[str | None] = mapped_column(Text)

    # ---- 整体进度 ----
    current_stage: Mapped[str | None] = mapped_column(String(20))  # 当前在第几关
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # 整体状态
    create_time: Mapped[datetime | None] = mapped_column(DateTime)  # 投递创建时间
    update_time: Mapped[datetime | None] = mapped_column(DateTime)  # 最后一次改动时间

    # relationship：顺着外键把「那个人」「那个岗位」的完整信息一起取出来，
    # 这样写 app.candidate.name 就能直接拿到候选人姓名，不用再查一次。
    # lazy="joined" 表示查投递时顺手把这两个一起查出来（一次查询搞定，省时间）
    candidate = relationship("Candidate", lazy="joined")
    position = relationship("Position", lazy="joined")
