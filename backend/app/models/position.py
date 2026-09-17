"""
【Position 表：岗位】
公司在招什么职位？比如「Java 高级工程师」「前端工程师」。

position_requirements（岗位要求）很重要：AI 筛选简历时，就是拿简历和这段文字比对，
看候选人符不符合要求。所以写得越具体，AI 判断得越准。
"""
from sqlalchemy import Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models import Base


class Position(Base):
    __tablename__ = "Position"

    id: Mapped[int] = mapped_column("ID", Integer, primary_key=True, autoincrement=True)  # 岗位编号
    position_name: Mapped[str | None] = mapped_column(String(100))  # 岗位名称
    owner: Mapped[str | None] = mapped_column(String(100))  # 负责人（哪个 HR 负责招这个岗位）
    position_requirements: Mapped[str | None] = mapped_column(String(2000))  # 岗位要求 / 职位描述（JD）
    is_hidden: Mapped[int] = mapped_column(SmallInteger, default=0)  # 1 = 暂不招（隐藏）：该岗位及其投递不在统计与列表中体现
