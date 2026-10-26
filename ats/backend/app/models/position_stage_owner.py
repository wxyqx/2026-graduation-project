"""【Position_Stage_Owner 表：岗位级的阶段负责人】

按「岗位 × 关卡」指派 HR 负责人，对该岗位全部候选人的对应关生效——
比如某岗位所有候选人的专业面都由同一位 HR 负责，不用一个投递一个投递地指。

优先级：投递级记录（stage_owner 表，HR 首次编辑自动认领 / 技术端曾按投递指派的）优先于岗位级；
两边都没有的关 = 未认领，任何 HR 都能编辑（编辑即认领）。
"""
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class PositionStageOwner(Base):
    __tablename__ = "position_stage_owner"  # 表名小写，与 alembic/库保持一致
    __table_args__ = (UniqueConstraint("pos_id", "stage", name="UK_Pos_Stage"),)

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)
    pos_id: Mapped[int] = mapped_column(
        "pos_id", Integer, ForeignKey("position.ID", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column("stage", String(20), nullable=False)  # ai / resume / … / final
    user_id: Mapped[int | None] = mapped_column(
        "user_id", Integer, ForeignKey("user.ID", ondelete="SET NULL"), nullable=True
    )
    update_time: Mapped[datetime | None] = mapped_column(DateTime)
