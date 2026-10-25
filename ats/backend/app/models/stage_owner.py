"""【Stage_Owner 表：投递的阶段负责人】

候选人每个关卡都有一个 HR 负责人：
  · 第一次对某关做出编辑（打分推进 / 补写原因评价）的 HR 自动成为该关负责人
  · 候选人负责人（Candidate.owner_id）可以编辑全部关卡
  · 阶段负责人只能编辑自己这一关，其他关卡只能看
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class StageOwner(Base):
    __tablename__ = "stage_owner"  # Windows MySQL 表名统一小写存储，模型直接用小写保持与 alembic/库一致
    __table_args__ = (UniqueConstraint("application_id", "stage", name="UK_App_Stage"),)

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(
        "application_id", Integer, ForeignKey("application.ID", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column("stage", String(20), nullable=False)  # ai / resume / … / final
    user_id: Mapped[int | None] = mapped_column(
        "user_id", Integer, ForeignKey("user.ID", ondelete="SET NULL"), nullable=True
    )
    update_time: Mapped[datetime | None] = mapped_column(DateTime)
